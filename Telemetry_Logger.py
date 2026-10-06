from pymavlink import mavutil
import time
import asyncpg
import asyncio
import datetime
import config


class Drone:
    def __init__(self, connection_string, droneId):
        self.droneId = droneId
        self.connection = mavutil.mavlink_connection(connection_string)
        self.connection_string = connection_string    
        self.connection.wait_heartbeat()
        print("Connected to system: ", self.connection.target_system)
        self.lock = asyncio.Lock()

    async def arm(self):
        async with self.lock:
            await asyncio.to_thread(
                self.connection.mav.command_long_send,
                self.connection.target_system,
                self.connection.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,
                1,0,0,0,0,0,0
            )
            armConfirmation = await asyncio.to_thread(self.connection.recv_match, type="COMMAND_ACK", blocking=True, timeout=2)
            return armConfirmation

    async def takeoff(self):
        async with self.lock:
            await asyncio.to_thread(
                self.connection.mav.command_long_send,
                self.connection.target_system,
                self.connection.target_component,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0,
                0,0,0,0,0,0,60
            )
            takeoffConfirmation = await asyncio.to_thread(self.connection.recv_match, type="COMMAND_ACK", blocking=True, timeout=2)
            return takeoffConfirmation

    async def land(self):
        async with self.lock:
            await asyncio.to_thread(
                self.connection.mav.command_long_send,
                self.connection.target_system,
                self.connection.target_component,
                mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                0,0,0,0,0,0,0,0
            )
            landConfirmation = await asyncio.to_thread(self.connection.recv_match, type="COMMAND_ACK", blocking=True, timeout=2)
            return landConfirmation

    async def getPosition(self):
        async with self.lock:
            att = await asyncio.to_thread(self.connection.recv_match, type="ATTITUDE", blocking=True, timeout=2)
            return att

    async def getLocation(self):
        async with self.lock:
            gps = await asyncio.to_thread(self.connection.recv_match, type="GLOBAL_POSITION_INT", blocking=True, timeout=2)
            return gps

    async def goto(self, long, lat):
        async with self.lock:
            await asyncio.to_thread(
                self.connection.mav.command_long_send,
                self.connection.target_system,
                self.connection.target_component,
                mavutil.mavlink.MAV_CMD_DO_REPOSITION,
                0,
                -1,0,0,float('nan'),lat,long,40
            )

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


async def droneLifeCycle(drone, db, timeInterval, target, missedReadsAllowed):
    missedReads = 0
    lastLoggedTime = time.time()

    try:
        await drone.arm()
        await drone.takeoff() 
        while True:
            fastPos = await drone.getPosition()
            fastCoordinates = await drone.getLocation()

            if fastPos is None or fastCoordinates is None:
                missedReads+=1
                if missedReads >= missedReadsAllowed:
                    print(f"{drone.droneId}: failed to broadcast telemetry, landing.")
                    await drone.land()
                    return
                continue
            missedReads=0

            boundaryCompliance = await db.checkSpatialCoordinates(fastCoordinates)

            if boundaryCompliance == False:
                ack = await drone.land()
                print(f"{drone.droneId} left the boundary: {ack.result if ack is not None else 'no reply'}")
                return

            if time.time() - lastLoggedTime >= timeInterval:
                await db.addToDatabase(drone.droneId, fastPos, fastCoordinates, datetime.datetime.now())

                if fastCoordinates.relative_alt / 304.8 >= 111:
                    await drone.goto(*target)

                lastLoggedTime = time.time()
                    
    except asyncio.CancelledError:
        print(f"{drone.droneId}: cancelled, landing")
        try:
            await drone.land()
        except Exception as landError:
            print(f"{drone.droneId}: couldn't land: {landError}")
        raise
    except Exception as E:
        print(f"{drone.droneId}: has failed in the loop: {E}")
        await drone.land()



async def main():
    timeInterval = 2
    missedReadsAllowed = 3

    flyTo = (-121.9640,37.3985)
    db = await Database.create()

    try:
        drones = [Drone(f'udp:127.0.0.1:{14540+i}', f"Drone-{i}") for i in range(1, config.totalDrones+1)]

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