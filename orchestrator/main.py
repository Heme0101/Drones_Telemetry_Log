from pymavlink import mavutil
from orchestrator.database import Database
from orchestrator.vehicles import Drone
from orchestrator.flight_loop import droneLifeCycle
import asyncio
import config


async def main():
    timeInterval = 2
    missedReadsAllowed = 3

    db = await Database.create()

    try:
        drones = [Drone(f'udp:127.0.0.1:{14540+i}', f"Drone-{i}") for i in range(0, config.totalDrones)]
        boundary = await db.retrieveBoundary()
        corners = [boundary[k] for k in sorted(boundary)]
        routes = [corners[i % len(corners):] + corners[:i % len(corners)] for i in range(len(drones))]

        results = await asyncio.gather(
            *(droneLifeCycle(drone, db, timeInterval, route, missedReadsAllowed)
              for drone, route in zip(drones, routes)),
            return_exceptions=True
        )

        for drone, result in zip(drones, results):
            if isinstance(result, Exception):
                print(f"{drone.droneId}: task ended with an unexpected error: {result}")

    finally:
        await db.pool.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped by user.")