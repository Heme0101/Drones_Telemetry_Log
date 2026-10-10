import asyncio
import time
import datetime
import config

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
                await asyncio.sleep(0.05)
                if missedReads >= missedReadsAllowed:
                    print(f"{drone.droneId}: failed to broadcast telemetry, landing.")
                    await drone.returnToLaunch()
                    return
                continue
            missedReads=0

            boundaryCompliance = await db.checkSpatialCoordinates(fastCoordinates)

            if boundaryCompliance == False:
                ack = await drone.returnToLaunch()
                print(f"{drone.droneId} left the boundary: {ack.result if ack is not None else 'no reply'}")
                return

            if time.time() - lastLoggedTime >= timeInterval:
                battery = await drone.getBattery()
                if battery is None:
                    batteryText = f"{drone.droneId}  unknown"
                elif battery <= config.lowBatteryThreshold:
                    batteryText = f"{drone.droneId}  Battery Left: {battery}%. WARNING BATTERY LOW"
                    await drone.returnToLaunch()
                else:
                    batteryText = f"{drone.droneId}  Battery Left: {battery}%"
                print(batteryText)

                await db.addToDatabase(drone.droneId, fastPos, fastCoordinates, datetime.datetime.now())

                if fastCoordinates.relative_alt / 304.8 >= 111:
                    await drone.goto(*target)

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