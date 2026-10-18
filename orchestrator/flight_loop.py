import asyncio
import math
import time
import datetime
import config
from orchestrator.flight_state import FlightState
from orchestrator.geo import distanceMeters, METERS_PER_DEGREE

async def droneLifeCycle(drone, db, timeInterval, waypoints, missedReadsAllowed, rover):
    droneMissedReads = 0
    roverMissedReads = 0
    lastLoggedTime = time.time()
    waypointIndex = 0
    padLocked = False

    try:
        await drone.arm()
        await drone.takeoff()
        state = FlightState.TAKEOFF
        while True:
            fastPos = await drone.getPosition()
            fastCoordinates = await drone.getLocation()

            if fastPos is None or fastCoordinates is None:
                droneMissedReads+=1
                await asyncio.sleep(0.05)
                if droneMissedReads >= missedReadsAllowed:
                    print(f"{drone.droneId}: failed to broadcast telemetry, landing.")
                    await drone.returnToLaunch()
                    return
                continue
            droneMissedReads = 0

            boundaryCompliance = await db.checkSpatialCoordinates(fastCoordinates)

            if boundaryCompliance is not True:
                ack = await drone.returnToLaunch()
                print(f"{drone.droneId} left the boundary: {ack.result if ack is not None else 'no reply'}")
                return

            lat = fastCoordinates.lat / 1e7
            lon = fastCoordinates.lon / 1e7
            heightMeters = fastCoordinates.relative_alt / 1000
            homeAmsl = (fastCoordinates.alt - fastCoordinates.relative_alt) / 1000
            cruiseAmsl = homeAmsl + config.cruiseAltMeters

            if state != FlightState.LOW_BATTERY:
                if state == FlightState.TAKEOFF and heightMeters >= config.cruiseAltMeters - 2:
                    state = FlightState.PATROL
                    if padLocked:
                        rover.padLock.release()
                        padLocked = False
                        print(f"{drone.droneId} released the pad")
                    await drone.goto(*waypoints[waypointIndex], cruiseAmsl)

                elif state == FlightState.PATROL:
                    targetLon, targetLat = waypoints[waypointIndex]
                    if distanceMeters(lat, lon, targetLat, targetLon) <= config.arrivalRadiusMeters:
                        waypointIndex = (waypointIndex + 1) % len(waypoints)
                        print(f"{drone.droneId}: reached corner, heading to waypoint {waypointIndex}")
                        await drone.goto(*waypoints[waypointIndex], cruiseAmsl)

            if time.time() - lastLoggedTime >= timeInterval:
                battery = await drone.getBattery()
                if battery is None:
                    batteryText = f"{drone.droneId}  unknown"
                elif battery <= config.lowBatteryThreshold:
                    batteryText = f"{drone.droneId}  Battery Left: {battery}%. WARNING BATTERY LOW"
                    if state in (FlightState.LOW_BATTERY, FlightState.PATROL):
                        state = FlightState.LOW_BATTERY
                else:
                    batteryText = f"{drone.droneId}  Battery Left: {battery}%"
                print(batteryText)

                await db.addToDatabase(drone.droneId, fastPos, fastCoordinates, datetime.datetime.now())

                if state == FlightState.PATROL:
                    await drone.goto(*waypoints[waypointIndex], cruiseAmsl)

                if state == FlightState.LOW_BATTERY:
                    if roverMissedReads >= missedReadsAllowed:
                        print(f"{drone.droneId}: rover not responding, returning to launch")
                        await drone.returnToLaunch()
                        return

                    elif not rover.padLock.locked():
                        roverLocation = await rover.getLocation()
                        if roverLocation is None:
                            roverMissedReads += 1
                        elif not rover.padLock.locked():
                            roverLong = roverLocation.lon / 1e7
                            roverLat = roverLocation.lat / 1e7
                            roverMissedReads = 0
                            await rover.padLock.acquire()
                            print(f"{drone.droneId}: secured the pad")
                            padLocked = True
                            landLong = roverLong- config.rendezvousOffsetMeters / (METERS_PER_DEGREE * math.cos(math.radians(roverLat)))
                            await drone.goto(landLong, roverLat, cruiseAmsl)
                    else:
                        state = FlightState.PATROL
                elif state == FlightState.RENDEZVOUS:
                    roverProximity = distanceMeters(lat, lon, roverLat, roverLong)
                    print(roverProximity)
                    if roverProximity <= 1:
                        await drone.land()
                        state = FlightState.RECHARGING

                if state == FlightState.RECHARGING and battery == 100:
                    await drone.arm()
                    await drone.takeoff()
                    state = FlightState.TAKEOFF

                lastLoggedTime = time.time()
            await asyncio.sleep(0.05)
                    
    except asyncio.CancelledError:
        print(f"{drone.droneId}: cancelled, landing")
        try:
            await drone.returnToLaunch()
        except Exception as landError:
            print(f"{drone.droneId}: couldn't land: {landError}")
        raise
    except Exception as E:
        print(f"{drone.droneId}: has failed in the loop: {E}")
        await drone.returnToLaunch()
    finally:
        if padLocked:
            rover.padLock.release()