from pymavlink import mavutil
import time
import asyncpg
import asyncio
import datetime
import config


class Drone:
    def __init__(self, connection_string='udp:127.0.0.1:14540'):
        self.connection = mavutil.mavlink_connection(connection_string)    
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
            att = await asyncio.to_thread(self.connection.recv_match, type="ATTITUDE", blocking=True)
            return att

    async def getLocation(self):
        async with self.lock:
            gps = await asyncio.to_thread(self.connection.recv_match, type="GLOBAL_POSITION_INT", blocking=True)
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

    async def add2Database(self, att, gps, timestamp):
        await self.pool.execute(
            "INSERT INTO telemetry (timestamp, roll, yaw, pitch, altitude) VALUES ($1, $2, $3, $4, $5)",
            timestamp, att.roll, att.yaw, att.pitch, gps.relative_alt / 304.8
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


async def main():
    drone = Drone()
    drone2 = Drone('udp:127.0.0.1:14541')
    db = await Database.create()

    timeInterval = 2
    lastLoggedTime = time.time()

    flyTo = (-121.9640,37.3985)
    await drone.arm()
    await drone.takeoff()


    try: 
        while True:
            fastPos = await drone.getPosition()
            fastCoordinates = await drone.getLocation()
            boundaryCompliance = await db.checkSpatialCoordinates(fastCoordinates)

            if time.time() - lastLoggedTime >= timeInterval:
                write = await db.add2Database(fastPos, fastCoordinates, datetime.datetime.now())
                sequence = [fastCoordinates.relative_alt/1000]

                for action in sequence:
                    print(action)

                lastLoggedTime = time.time()

                if fastCoordinates.relative_alt / 304.8 >= 111:
                    await drone.goto(*flyTo)
                
                elif boundaryCompliance == False:
                    land = await drone.land()
                    break

    except Exception as E:
        print(f"An unexpected error has occured: {E}")
        await drone.land()

    finally:
        await db.pool.close()


if __name__ == "__main__":
    asyncio.run(main())