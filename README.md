## What is Drones_Telemetry_Log

Three simulated VTOL drones fly a patrol loop inside a PostGIS geofence, logging telemetry to PostgreSQL every 2 seconds. When a battery runs low, a drone takes the single charging pad on a rover, lands, recharges (simulated), and returns to patrol. The simulation runs on PX4, Gazebo and QGroundCont

An async Python orchestrator (asyncio, pymavlink) that runs one control loop per drone against PX4 SITL. Once started, it runs unattended. It does not need operator input, though the patrol route is fixed and a single process controls all three drones. The recharge is simulated: the simulator resets a drone's battery when it lands.

Each drone moves through five states: TAKEOFF, PATROL, LOW_BATTERY, RENDEZVOUS, RECHARGING. At 90% (adjustable)  battery a drone tries to take the pad. One drone at a time holds it (an asyncio.Lock), so the others keep patrolling until it is free.

## Design Notes
- **One pad, three drones.** After awaiting the rover's position, a drone re-checks the pad lock before taking it. An `await` hands control to the event loop, which can run another drone first, so a check made before the `await` may no longer hold after it. A `finally` block releases the pad if a drone's task ends while holding it.
- **Geofence.** The polygon is loaded from PostGIS once at startup and checked in memory with shapely. I compared it with PostGIS `ST_Contains` on 2,000 random points around the fence and found 0 differences. If the geofence row is missing, the program stops at startup.
- **Waypoints.** The patrol route is the corners of an inset of the geofence, so drones never fly along the edge. Each drone flies the same direction around the loop, starting at a different corner.
- **Validation.** Position messages from PX4 are validated with a Pydantic model and a reading that fails validation counts as a missed read.
- **Failure handling.** Each of these ends differently and none stops the other drones: a refused command (`COMMAND_ACK` is checked), a rover that does not answer, a drone that never reaches the rover (timeout derived from distance and speed), a landing that is refused (3 attempts), a recharge that stalls (75 s), and a failed telemetry write.
- **Telemetry** is stored with `timestamptz` timestamps.

## Prerequisites

| Needs | Version | Notes |
|---|---|---|
| Ubuntu | 24.04.4 LTS | |
| Python | 3.12.3 | ships with Ubuntu |
| PostgreSQL | 16.15 | install with 'apt' |
| PostGIS | 3.4.2 | PostgreSQL extension: 'sudo apt install postgresql-16-postgis-3' |
| QGroundControl | 5.1.5 (64-bit AppImage) | **required** in my setup: with it closed, PX4 reports "connection to ground control station lost" and the drones do not arm |

Python packages required are in 'requirements.txt'.

## How to run

1. pip install -r requirements.txt
2. Create a PostgreSQL database with PostGIS enabled, then load **schema.sql**:
```bash
psql -U <your_username> -d <your_database> -h <your_host> -f schema.sql
```
3. Insert the geofence polygon named `Test Zone` (the program refuses to start without it). Then load **seed.sql**: 
```bash
psql -U <your_username> -d <your_database> -h <your_host> -f seed.sql
```
The polygon in seed.sql must surround the home point in **LAUNCH_ENV**. If you change its coordinates, change `PX4_HOME_LAT` and `PX4_HOME_LON` in your `config.py` to match, because PX4 takes its home point from `config.py`, not from the database.
4. Copy `config_example.py` to `config.py` and fill in your database details.
5. Make sure no old simulator processes are left: `pgrep -af "px4 -i"` should print nothing.
6. **python3 Launch_Apps.py** starts the four vehicles and QGroundControl.
7. **python3 -m orchestrator.main** begins the drones async processes.

## Known limitations

- The recharge is simulated: the drone's battery resets when it lands.
- QGroundControl has to be running (see table).
- After a recharge, return-to-launch may bring a drone back to the pad. PX4 resets the launch point/home when a drone re-arms on the pad.
- The route is fixed and one process controls all three drones, so this is automated orchestration, not independent autonomy.
- No automated tests yet, and nothing here has been tried on real hardware.
