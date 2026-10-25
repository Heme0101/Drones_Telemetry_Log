import asyncio
from types import SimpleNamespace
from shapely import wkt
from shapely.geometry import Point
from orchestrator.database import Database

POINTS = [
    ("center",            -121.9650, 37.3975),
    ("far outside",       -121.9700, 37.3975),
    ("east edge",         -121.9640, 37.3975),
    ("south-west corner", -121.9660, 37.3965),
]

async def main():
    db = await Database.create()
    try:
        boundaryInText = await db.pool.fetchval(
            "SELECT ST_AsText(boundary::geometry) FROM geofences WHERE name = $1", "Test Zone"
        )
        polygon = wkt.loads(boundaryInText)

        for label, long, lat in POINTS:
            fromDatabase = await db.pool.fetchval("""
                    SELECT ST_Contains(boundary::geometry, ST_GeogFromText($1)::geometry)
                    FROM geofences WHERE name=$2;
                    """,
                    f"POINT({long} {lat})", "Test Zone"
                    )
            fromShapely = polygon.contains(Point(long, lat))
            verdict = "OK" if fromDatabase == fromShapely else "Mismatch"
            print(f"{label:18} database = {fromDatabase} shapely = {fromShapely} {verdict}")

    finally:
        await db.pool.close()

asyncio.run(main())