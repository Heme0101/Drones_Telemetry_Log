from pymavlink import mavutil
import asyncio


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

    async def disarm(self):
        async with self.lock:
            await asyncio.to_thread(
                self.connection.mav.command_long_send,
                self.connection.target_system,
                self.connection.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,
                0,0,0,0,0,0,0
            )
            disarmConfirmation = await asyncio.to_thread(self.connection.recv_match, type="COMMAND_ACK", blocking=True, timeout=2)
            return disarmConfirmation

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
                mavutil.mavlink.MAV_CMD_NAV_LAND,
                0,
                0,0,0,0,0,0,0
            )
            landConfirmation = await asyncio.to_thread(self.connection.recv_match, type="COMMAND_ACK", blocking=True, timeout=2)
            return landConfirmation

    async def returnToLaunch(self):
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

    async def goto(self, long, lat, alt_amsl):
        async with self.lock:
            await asyncio.to_thread(
                self.connection.mav.command_long_send,
                self.connection.target_system,
                self.connection.target_component,
                mavutil.mavlink.MAV_CMD_DO_REPOSITION,
                0,
                -1,0,0,float('nan'),lat,long,alt_amsl
            )

    async def getBattery(self):
        msg = self.connection.messages.get("SYS_STATUS")
        if msg is None or msg.battery_remaining== -1:
                return None
        return msg.battery_remaining


class Rover:
    def __init__(self, connection_string="udpin:0.0.0.0:14543"):
        self.connection = mavutil.mavlink_connection(connection_string)
        self.lock = asyncio.Lock()
        self.padLock = asyncio.Lock()

    async def waitForHeartbeat(self):
        msg = await asyncio.to_thread(self.connection.wait_heartbeat, timeout=2)
        return True if msg is not None else 'Null, vehicle dead'

    async def getLocation(self):
        async with self.lock:
            msg = await asyncio.to_thread(
                self.connection.recv_match,
                type="GLOBAL_POSITION_INT",
                blocking=True,
                timeout=2,
            )
            if msg is None:
                return None
            return (msg.lon / 1e7, msg.lat / 1e7, 25)