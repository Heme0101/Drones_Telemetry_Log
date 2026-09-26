from pymavlink import mavutil
import time
import psycopg2
import datetime
import asyncio
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
            0,0,0,0,0,0,30
        )
        return self.connection.recv_match(type="COMMAND_ACK", blocking=True, timeout=2)

    def land(self):
        self.connection.mav.command_long_send(
            self.connection.target_system,
            self.connection.target_component,
            mavutil.mavlink.MAV_CMD_NAV_LAND,
            0,0,0,0,0,0,0,0
        )
        return self.connection.recv_match(type="COMMAND_ACK", blocking=True, timeout=2)


    async def getPosition(self):
        att = self.connection.recv_match(type="ATTITUDE", blocking=True)
        asyncio.sleep(2)
        return att


    async def getLocation(self):
        gps = self.connection.recv_match(type="GLOBAL_POSITION_INT", blocking=True)
        asyncio.sleep(2)
        return gps


class Database:
    def __init__(self):
        self.db = psycopg2.connect(
            dbname=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            host=config.DB_HOST
        )
        self.cursor = self.db.cursor()

    async def add2Database(self, att, gps, timestamp):
        await self.cursor.execute(
            "INSERT INTO telemetry (timestamp, roll, yaw, pitch, altitude) VALUES (%s, %s, %s, %s, %s)",
            (timestamp, att.roll, att.yaw, att.pitch, gps.relative_alt / 304.8)
        )
        await self.db.commit()



active = Drone.arm()
fly = Drone.takeoff()

while True:
    currentTime = time.time()
    if currentTime >= time.time():
        Drone.getPosition()
        Drone.getLocation()
        Database.add2Database()

    if Drone.getLocation.gps.relative_alt >= 30:
        descend = Drone.land()
        break