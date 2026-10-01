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

    def arm(self):
        self.connection.mav.command_long_send(
            self.connection.target_system,
            self.connection.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1,0,0,0,0,0,0
        )
        return self.connection.recv_match(type="COMMAND_ACK", blocking=True, timeout=2)

    def takeoff(self):
        self.connection.mav.command_long_send(
            self.connection.target_system,
            self.connection.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,
            0,0,0,0,0,0,60
        )
        return self.connection.recv_match(type="COMMAND_ACK", blocking=True, timeout=2)

    def land(self):
        self.connection.mav.command_long_send(
            self.connection.target_system,
            self.connection.target_component,
            mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
            0,0,0,0,0,0,0,0
        )
        return self.connection.recv_match(type="COMMAND_ACK", blocking=True, timeout=2)

    def getPosition(self):
        att = self.connection.recv_match(type="ATTITUDE", blocking=True)
        return att

    def getLocation(self):
        gps = self.connection.recv_match(type="GLOBAL_POSITION_INT", blocking=True)
        return gps

    def goto(self, long, lat):
        self.connection.mav.command_long_send(
            self.connection.target_system,
            self.connection.target_component,
            mavutil.mavlink.MAV_CMD_DO_REPOSITION,
            0,
            -1,0,0,float('nan'),lat,long,40
        )


class Database:
    def __init__(self, pool):
        self.db = psycopg2.connect(
            dbname=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            host=config.DB_HOST
        )
        self.cursor = self.db.cursor()

    def add2Database(self, att, gps, timestamp):
        self.cursor.execute(
            "INSERT INTO telemetry (timestamp, roll, yaw, pitch, altitude) VALUES (%s, %s, %s, %s, %s)",
            (timestamp, att.roll, att.yaw, att.pitch, gps.relative_alt / 304.8)
        )
        self.db.commit()


    def checkSpatialCoordinates(self, gps):
        lat = gps.lat/1e7
        long = gps.lon/1e7
        
        boundaryCompliance = self.cursor.execute("""
        SELECT ST_Contains(boundary::geometry, ST_GeogFromText(%s)::geometry)
        FROM geofences WHERE name=%s;
        """,
        (f"POINT({long} {lat})", "Test Zone")
        )

        result = self.cursor.fetchone()
        return result[0]

    @classmethod
    async def create(cls):
        pool = await asyncpg.create_pool(
            db=config.DB_NAME, 
            username=config.DB_USER, 
            password=config.DB_PASSWORD, 
            host=config.DB_HOST
        )
        return cls(pool)


drone = Drone()
db = await Database.create()

timeInterval = 2
lastLoggedTime = time.time()

flyTo = (-121.9640,37.3985)
drone.arm()
drone.takeoff()


try: 
    while True:
        fastPos = drone.getPosition()
        fastCoordinates = drone.getLocation()
        boundaryCompliance = db.checkSpatialCoordinates(fastCoordinates)

        if time.time() - lastLoggedTime >= timeInterval:
            write = db.add2Database(fastPos, fastCoordinates, datetime.datetime.now())
            sequence = [fastCoordinates.relative_alt/1000]

            for action in sequence:
                print(action)

            lastLoggedTime = time.time()

            if fastCoordinates.relative_alt / 304.8 >= 111:
                drone.goto(*flyTo)
            
            elif boundaryCompliance == False:
                land = drone.land()
                break

except Exception as E:
    print(f"An unexpected error has occured: {E}")
    drone.land()

finally:
    db.cursor.close()
    db.db.close()