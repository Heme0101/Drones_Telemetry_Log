import asyncio
import contextlib
import io
import math
import time
from types import SimpleNamespace
from pymavlink import mavutil

import config
from orchestrator.flight_loop import droneLifeCycle
from orchestrator.geo import METERS_PER_DEGREE, distanceMeters

NUM_DRONES = 6
RUN_SECONDS = 60
TIME_SCALE = 20
DRAIN_SECONDS = 1200
ROVER_READ_DELAY = 0.03
PAD_RADIUS = 3.0
TIME_INTERVAL = 0.1

CENTER_LON, CENTER_LAT = 10.0, 10.0
HOME_AMSL = 25.0
WAYPOINTS = [(CENTER_LON - 0.001, CENTER_LAT - 0.001), (CENTER_LON + 0.001, CENTER_LAT - 0.001),
             (CENTER_LON + 0.001, CENTER_LAT + 0.001), (CENTER_LON - 0.001, CENTER_LAT + 0.001)]

config.lowBatteryThreshold = 80
config.cruiseAltMeters = 35
config.cruiseSpeedMps = 5
config.arrivalRadiusMeters = 5
config.rendezvousRadiusMeters = 1
config.rendezvousOffsetMeters = 2.0
config.rechargeTimeoutSeconds = 75
config.rechargeTimeoutLimit = 2

ACCEPTED = SimpleNamespace(result=mavutil.mavlink.MAV_RESULT_ACCEPTED)

class CheckedLock:
    def __init__(self):
        self._lock = asyncio.Lock()
        self.blocked_acquires = 0

    def locked(self):
        return self._lock.locked()

    async def acquire(self):
        if self._lock.locked():
            self.blocked_acquires += 1
        await self._lock.acquire()

    def release(self):
        self._lock.release()

class FakeRover:
    def __init__(self):
        self.padLock = CheckedLock()

    async def getLocation(self):
        await asyncio.sleep(ROVER_READ_DELAY)
        return SimpleNamespace(lat = round(CENTER_LAT*1e7), lon = round(CENTER_LON * 1e7))

class FakeDB:
    async def checkSpatialCoordinates(self, gps):
        return True

    async def addToDatabse(self, *args):
        pass

class FakeDrone:
    def __init__(self, name, index):
        self.droneId = name
        self.lat = CENTER_LAT + 4 * (index + 1) / METERS_PER_DEGREE
        self.lon = CENTER_LON
        self.height = 0.0
        self.battery = 100.0
        self.armed = False
        self.mode = "Ground"
        self.target_lon, self.target_lat = self.lon, self.lat
        self.target_height = 0.0
        self.last_t = time.time()
        self.rtl_calls = 0
        self.pad_landings = 0