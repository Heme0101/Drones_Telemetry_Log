import asyncio
import config
import asyncpg

class Database:
    def __init__(self, pool):
        self.pool = pool

    async def addToDatabase(self, droneId, att, gps, timestamp):
        await self.pool.execute(
            "INSERT INTO telemetry (drone_id, timestamp, roll, yaw, pitch, altitude) VALUES ($1, $2, $3, $4, $5, $6)",
            droneId, timestamp, att.roll, att.yaw, att.pitch, gps.relative_alt / 304.8
        )

    async def checkSpatialCoordinates(self, gps):
        lat = gps.lat/1e7
        long = gps.lon/1e7
        
        boundaryCompliance = await self.pool.fetchval("""
        SELECT ST_Contains(boundary::geometry, ST_GeogFromText($1)::geometry)
        FROM geofences WHERE name=$2;
        """,
        f"POINT({long} {lat})", "Test Zone"
        )

        return boundaryCompliance

    @classmethod
    async def create(cls):
        pool = await asyncpg.create_pool(
            database=config.DB_NAME, 
            user=config.DB_USER, 
            password=config.DB_PASSWORD, 
            host=config.DB_HOST
        )
        return cls(pool)