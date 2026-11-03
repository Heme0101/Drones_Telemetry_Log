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
ON_PAD_HEIGHT = 2.0

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

    async def addToDatabase(self, *args):
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

    def _advance(self):
        now = time.time()
        dt = (now - self.last_t) * TIME_SCALE
        self.last_t = now

        if not self.armed:
            return
        self.battery = max(0.0, self.battery - dt * 100 / DRAIN_SECONDS)
        if self.mode == "Landing":
            self.height = max(0.0, self.height - 2.5 * dt)
            if self.height == 0.0:
                self.mode, self.armed, self.battery = "Ground", False, 100.0
                if distanceMeters(self.lat, self.lon, CENTER_LAT, CENTER_LON) <= PAD_RADIUS:
                    self.pad_landings += 1
        elif self.mode == "Flying":
            climb = 3.0 * dt
            if self.height < self.target_height:
                self.height = min(self.target_height, self.height + climb)
            dx = (self.target_lon - self.lon) * METERS_PER_DEGREE * math.cos(math.radians(self.lat))
            dy = (self.target_lat - self.lat) * METERS_PER_DEGREE
            remaining = math.hypot(dx, dy)
            step = config.cruiseSpeedMps * dt
            if remaining <= step:
                self.lon, self.lat = self.target_lon, self.target_lat
            else:
                frac = step/remaining
                self.lon += (self.target_lon - self.lon) * frac
                self.lat += (self.target_lat - self.lat) * frac

    def _onPad(self):
        near = distanceMeters(self.lat, self.lon, CENTER_LAT, CENTER_LON) <= PAD_RADIUS
        return near and self.height < ON_PAD_HEIGHT

    async def arm(self):
        await asyncio.sleep(0)
        self.armed = True
        return ACCEPTED

    async def takeoff(self):
        await asyncio.sleep(0)
        self.mode, self.target_height = "Flying", config.cruiseAltMeters
        self.target_lon, self.target_lat = self.lon, self.lat
        return ACCEPTED

    async def land(self):
        await asyncio.sleep(0)
        self.mode = "Landing"
        return ACCEPTED

    async def returnToLaunch(self):
        await asyncio.sleep(0)
        self.rtl_calls += 1
        return ACCEPTED

    async def goto(self, lon, lat, alt_asml):
        await asyncio.sleep(0)
        if self.mode == "Flying":
            self.target_lon, self.target_lat = lon, lat

    async def getPosition(self):
        await asyncio.sleep(0)
        return SimpleNamespace()

    async def getLocation(self):
        await asyncio.sleep(0)
        self._advance()
        return SimpleNamespace(lat = round(self.lat * 1e7), lon = round(self.lon * 1e7), 
                                alt = round((HOME_AMSL + self.height) * 1000),
                                relative_alt = round(self.height * 1000))

    async def getBattery(self):
        await asyncio.sleep(0)
        self._advance()
        return int(self.battery)

async def monitor(drones, stats):
    while True:
        stats["max_on_pad"] = max(stats["max_on_pad"], sum(d._onPad() for d in drones))
        await asyncio.sleep(0.005)

async def main():
    rover, db = FakeRover(), FakeDB()
    drones = [FakeDrone(f"Drone-{i}", i) for i in range(NUM_DRONES)]
    stats = {"max_on_pad": 0}
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        tasks = [asyncio.create_task(droneLifeCycle(
                    d, db, TIME_INTERVAL, WAYPOINTS[i%4:] + WAYPOINTS[:i % 4], 3, rover))
                for i, d in enumerate(drones)]
        watcher = asyncio.create_task(monitor(drones, stats))
        await asyncio.sleep(RUN_SECONDS)
        sent_home = {d.droneId: d.rtl_calls for d in drones if d.rtl_calls}
        for t in tasks + [watcher]:
            t.cancel()
        await asyncio.gather(*tasks, watcher, return_exceptions=True)

        for d in drones:
            print(d.droneId, "mode:", d.mode, "armed:", d.armed, "battery:", round(d.battery),
              "height:", round(d.height, 1),
              "distance to rover:", round(distanceMeters(d.lat, d.lon, CENTER_LAT, CENTER_LON)))
    print("--- last 15 lines the loop printed ---")
    print("\n".join(output.getvalue().splitlines()[-15:]))


    pad_lines = [l for l in output.getvalue().splitlines() if "the pad" in l]
    print("\n".join(pad_lines[:12]))
    failures = []
    if rover.padLock.blocked_acquires:
        failures.append(f"{rover.padLock.blocked_acquires} acquire call(s) on a pad that was already taken")
    if stats["max_on_pad"] > 1:
        failures.append(f"{stats['max_on_pad']} drones on the pad at once")
    if sent_home:
        failures.append(f"drones sent home during the run: {sent_home}")
    failures += [f"{d.droneId} never landed on the pad" for d in drones if d.pad_landings ==0]

    print("\npad visits per drone:", {d.droneId: d.pad_landings for d in drones})
    print("most drones on the pad at once:", stats["max_on_pad"])
    print("acquire() calls on a taken pad:", rover.padLock.blocked_acquires)
    print("FAIL: " + "; ".join(failures) if failures else "PASS")
    if failures:
        raise SystemExit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program stopped by user.")