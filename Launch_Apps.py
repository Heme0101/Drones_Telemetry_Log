import asyncio
import subprocess
import config
import time
from orchestrator.database import Database
from orchestrator.geo import offsetMeters

env_prefix = " ".join(f"{key}={value}" for key, value in config.LAUNCH_ENV.items())

async def findCenter():
    db = await Database.create()
    try:
        return await db.retrieveCenter()
    finally:
        await db.pool.close()

centerLon, centerLat = asyncio.run(findCenter())
centerEast, centerNorth = offsetMeters(
    float(config.LAUNCH_ENV["PX4_HOME_LAT"]),
    float(config.LAUNCH_ENV["PX4_HOME_LON"]),
    centerLat,
    centerLon
)

def pose(east, north):
    return f"{round(east, 2) + 0.0:.2f},{round(north, 2) + 0.0:.2f}"

vehicles = [
    {"instance": "0", "model":"gz_standard_vtol", "pose": pose(centerEast, centerNorth + 4), "standalone": False, "drain" : "840"},
    {"instance": "1", "model":"gz_standard_vtol", "pose": pose(centerEast, centerNorth + 8), "standalone": True, "drain" : "840"},
    {"instance": "2", "model":"gz_standard_vtol", "pose": pose(centerEast, centerNorth + 12), "standalone": True, "drain" : "840"},
    {"instance": "3", "model":"gz_rover_differential", "pose": pose(centerEast, centerNorth), "standalone": True}
]

for v in vehicles:
    standalone = "PX4_GZ_STANDALONE=1" if v["standalone"] else ""
    if v["model"] == "gz_standard_vtol":
        batteryParameters = {**config.VTOL_ENV, "PX4_PARAM_SIM_BAT_DRAIN": v["drain"]}
        battery_env = " ".join(f"{key}={value}" for key, value in batteryParameters.items())
    else:
        battery_env = ""

    shell_cmd = (
        f"{env_prefix} {standalone} {battery_env} PX4_GZ_WORLD=default "
        f"PX4_SIM_MODEL={v['model']} PX4_GZ_MODEL_POSE=\"{v['pose']}\" "
        f"~//Documents/Larp/PX4-Autopilot/build/px4_sitl_default/bin/px4 -i {v['instance']}; exec bash"
    )
    
    initiation = subprocess.Popen([
        "gnome-terminal",
        f"--working-directory={config.LAUNCH_CWD}",
        "--", "bash", "-c", shell_cmd,
    ])

    if v['instance']=="0":
        time.sleep(10)
    else:
        time.sleep(2)

qgc = subprocess.Popen([
    "gnome-terminal", 
    f"--working-directory={config.LAUNCH_CWD}", 
    "--", "/home/fs/Applications/QGroundControl.AppImage",
])