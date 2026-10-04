import subprocess
import config
import time

totalDrones = 3
processes=[]

home_env = " ".join(f"{k}={v}" for k,v in config.LAUNCH_ENV.items())

for i in range(1, totalDrones + 1):
    y_offset = i-1

    shell_cmd = (
        f"{home_env} "
        f"PX4_SYS_AUTOSTART=4001 "
        f"PX4_SIM_MODEL=gz_x500 "
        f'PX4_GZ_MODEL_POSE="0,{y_offset}" '
        f"./build/px4_sitl_default/bin/px4 -i {i}; exec bash"
    )
    
    proc = subprocess.Popen([
        "gnome-terminal",
        f"--working-directory={config.LAUNCH_CWD}",
        "--", "bash", "-c", shell_cmd,
    ])
    processes.append(proc)

    if i==1:
        time.sleep(8)

qgc = subprocess.Popen([
    "gnome-terminal", 
    f"--working-directory={config.LAUNCH_CWD}", 
    "--", "./QGroundControl-x86_64.AppImage",
])

processes.append(qgc)