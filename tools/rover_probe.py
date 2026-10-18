import asyncio
from orchestrator.vehicles import Rover

async def main():
    rover = Rover()
    ok = await rover.waitForHeartbeat()
    print("Heartbeat ok:", ok)
    hb = rover.connection.messages.get("HEARTBEAT")
    print("Raw type: ", hb.type if hb is not None else "no heartbeat stored")

    for _ in range(5):
        coordinates = await rover.getLocation()
        print(f"Location (Lon, Lat): {coordinates}")
        await asyncio.sleep(1)

asyncio.run(main())