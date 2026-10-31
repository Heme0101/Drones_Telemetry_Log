import asyncio
import math
import time
import datetime
import config
from orchestrator.flight_state import FlightState
from orchestrator.geo import distanceMeters, METERS_PER_DEGREE, expectedTravelTime
from orchestrator.vehicles import commandAccepted, describeAck, raiseAckError

async def droneLifeCycle(drone, db, timeInterval, waypoints, missedReadsAllowed, rover):
    droneMissedReads = 0
    roverMissedReads = 0
    waypointIndex = 0
    padLocked = False
    landAttempts = 0
    rechargeTimeoutAttempts = 0
    stalled = False
    lastLoggedTime = time.time()

    try:
        ack = await drone.arm()
        if not commandAccepted(ack):
            raiseAckError(ack, "arm")

        ack = await drone.takeoff()
        if not commandAccepted(ack):
            raiseAckError(ack, "takeoff")
        
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
                print(f"{drone.droneId} breached the boundary!")
                ack = await drone.returnToLaunch()
                if not commandAccepted(ack):
                    print(f"{drone.droneId}: failed to return to launch. Mission Abort! (result: {describeAck(ack)})")
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

                    if stalled:
                        print(f"{drone.droneId}: charged for too long, but battery is not full.")
                        ack = await drone.returnToLaunch()
                        if not commandAccepted(ack):
                            print(f"{drone.droneId}: failed to return to launch (result: {describeAck(ack)})")
                            return

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

                try:
                    await db.addToDatabase(drone.droneId, fastPos, fastCoordinates, datetime.datetime.now(datetime.timezone.utc))
                except Exception as dbError:
                    print(f"{drone.droneId}: database failed to log telemetry: {dbError}")

                if state == FlightState.PATROL:
                    await drone.goto(*waypoints[waypointIndex], cruiseAmsl)

                if state == FlightState.LOW_BATTERY:
                    if roverMissedReads >= missedReadsAllowed:
                        print(f"{drone.droneId}: rover not responding, returning to launch")
                        ack = await drone.returnToLaunch()
                        if not commandAccepted(ack):
                            print(f"{drone.droneId}: failed to return to launch. Mission Abort! (result: {describeAck(ack)})")
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
                            landLong = roverLong + config.rendezvousOffsetMeters / (METERS_PER_DEGREE * math.cos(math.radians(roverLat)))
                            initialRoverProximity = distanceMeters(lat, lon, roverLat, landLong)
                            rendezvousLimit = expectedTravelTime(initialRoverProximity, config.cruiseSpeedMps) *2
                            print(f"{drone.droneId}: secured the pad")
                            padLocked = True
                            await drone.goto(landLong, roverLat, cruiseAmsl)
                            state = FlightState.RENDEZVOUS
                            rendezvousClock = time.time()
                    else:
                        state = FlightState.PATROL
                elif state == FlightState.RENDEZVOUS:
                    currentRoverProximity = distanceMeters(lat, lon, roverLat, landLong)
                    print(f"{drone.droneId} is {round(currentRoverProximity)} meters from the rover")
                    if currentRoverProximity <= config.rendezvousRadiusMeters:
                        ack = await drone.land()
                        if commandAccepted(ack):
                            state = FlightState.RECHARGING
                            rechargeTimeoutCounter = time.time()
                            landAttempts = 0
                        else:
                            landAttempts += 1
                            print(f"{drone.droneId}: land not accepted (result: {describeAck(ack)}), attempt {landAttempts}")
                            if landAttempts >= 3:
                                raiseAckError(ack, "land")
                    elif time.time() - rendezvousClock >= rendezvousLimit:
                        print(f"{drone.droneId} rendezvous timed out, releasing pad lock.")
                        rover.padLock.release()
                        padLocked = False
                        state = FlightState.PATROL
                if state == FlightState.RECHARGING and (battery == 100 or time.time() - rechargeTimeoutCounter >= config.rechargeTimeoutSeconds):
                    ack = await drone.arm()
                    if not commandAccepted(ack):
                        raiseAckError(ack, "arm")
                    
                    ack = await drone.takeoff()
                    if not commandAccepted(ack):
                        raiseAckError(ack, "takeoff")

                    if time.time() - rechargeTimeoutCounter >= config.rechargeTimeoutSeconds:
                        rechargeTimeoutAttempts += 1
                        if rechargeTimeoutAttempts >= config.rechargeTimeoutLimit:
                            stalled = True
                    else:
                        rechargeTimeoutAttempts = 0

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
        ack = await drone.returnToLaunch()
        if not commandAccepted(ack):
            print(f"{drone.droneId}: failed to return to launch. Mission Abort! (result: {describeAck(ack)})")
    finally:
        if padLocked:
            rover.padLock.release()