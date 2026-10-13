import asyncio
from orchestrator.vehicles import Rover

async def main():
    rover = Rover()
    print(f"Rover: {await rover.waitForHeartbeat()}")

    for _ in range(5):
        print(f"Location (Lon, Lat): {await rover.getLocation()}")
        await asyncio.sleep(1)

asyncio.run(main())