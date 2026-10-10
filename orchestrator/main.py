from pymavlink import mavutil
from orchestrator.database import Database
from orchestrator.vehicles import Drone
from orchestrator.flight_loop import droneLifeCycle
import asyncio
import config


async def main():
    timeInterval = 2
    missedReadsAllowed = 3

    flyTo = (-121.9638,37.3975)
    db = await Database.create()

    try:
        drones = [Drone(f'udp:127.0.0.1:{14540+i}', f"Drone-{i}") for i in range(0, config.totalDrones)]

        targets = []
        for i in range(len(drones)):
            target = (flyTo[0] + 0.0001 * i, flyTo[1])
            targets.append(target)

        results = await asyncio.gather(
            *(droneLifeCycle(drone, db, timeInterval, target, missedReadsAllowed)
              for drone, target in zip(drones,targets)),
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