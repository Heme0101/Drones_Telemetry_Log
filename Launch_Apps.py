import subprocess
import config
import time

processes=[]
env_prefix = " ".join(f"{key}={value}" for key, value in config.LAUNCH_ENV.items())

vehicles = [
    {"instance": "0", "model":"gz_standard_vtol", "pose": "0,0", "standalone": False},
    {"instance": "1", "model":"gz_standard_vtol", "pose": "0,4", "standalone": True},
    {"instance": "2", "model":"gz_standard_vtol", "pose": "0,8", "standalone": True},
    {"instance": "3", "model":"gz_rover_differential", "pose": "0,12", "standalone": True}
]

for v in vehicles:
    standalone = "PX4_GZ_STANDALONE=1" if v["standalone"] else ""
    battery_env = " ".join(f"{key}={value}" for key, value in config.VTOL_ENV.items()) if v["model"] == "gz_standard_vtol" else ""

    shell_cmd = (
        f"{env_prefix} {standalone} {battery_env} PX4_GZ_WORLD=default "
        f"PX4_SIM_MODEL={v['model']} PX4_GZ_MODEL_POSE=\"{v['pose']}\" "
        f"./build/px4_sitl_default/bin/px4 -i {v['instance']}; exec bash"
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
    "--", "./QGroundControl-x86_64.AppImage",
])