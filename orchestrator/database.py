import asyncio
import config
import asyncpg
from shapely import wkt
from shapely.geometry import Point

class Database:
    def __init__(self, pool):
        self.pool = pool
        self.polygon = None

    async def addToDatabase(self, droneId, att, gps, timestamp):
        await self.pool.execute(
            "INSERT INTO telemetry (drone_id, timestamp, roll, yaw, pitch, altitude) VALUES ($1, $2, $3, $4, $5, $6)",
            droneId, timestamp, att.roll, att.yaw, att.pitch, gps.relative_alt / 304.8
        )

    async def checkSpatialCoordinates(self, gps):
        if self.polygon is None:
            raise RuntimeError("Geofence not loaded: call loadGeofence() first")
        lat = gps.lat/1e7
        long = gps.lon/1e7

        return bool(self.polygon.contains(Point(long, lat)))

    @classmethod
    async def create(cls):
        pool = await asyncpg.create_pool(
            database=config.DB_NAME, 
            user=config.DB_USER, 
            password=config.DB_PASSWORD, 
            host=config.DB_HOST
        )
        db = cls(pool)
        try:
            await db.loadGeofence()
        except Exception:
            await pool.close()
            raise
        return db

    async def loadGeofence(self, name="Test Zone"):
        boundaryAsText = await self.pool.fetchval("SELECT ST_AsText(boundary::geometry) FROM geofences WHERE name = $1", name)
        if boundaryAsText is None:
            raise RuntimeError(f"Geofence '{name}' not found in database")
        self.polygon = wkt.loads(boundaryAsText)

    async def retrieveBoundary(self, name="Test Zone", insetMeters=config.boundaryInsetMeters):
        vertexes = await self.pool.fetch(
            """
            SELECT ST_X(dp.geom) AS lon, ST_Y(dp.geom) AS lat
            FROM geofences, LATERAL ST_DumpPoints(ST_Buffer(boundary, -($2::float8))::geometry) AS dp
            WHERE name = $1
            ORDER BY dp.path;
            """,
            name, insetMeters
        )
        corners = {}
        for i, row in enumerate(vertexes[:-1]):
            corners[i] = (row['lon'], row['lat'])
        return corners

    async def retrieveCenter(self, name="Test Zone", insetMeters=config.boundaryInsetMeters):
        row = await self.pool.fetchrow(
            """
            SELECT ST_X(center) AS lon, ST_Y(center) AS lat
            FROM (
                SELECT ST_Centroid(ST_Buffer(boundary, -($2::float8))::geometry) AS center
                FROM geofences
                WHERE name = $1
            ) AS zone;
            """,
            name, insetMeters
        )
        return (row['lon'], row['lat'])