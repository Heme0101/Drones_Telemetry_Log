import subprocess
import os
import config

px4 = subprocess.Popen(
    ["gnome-terminal", "--", "make", "px4_sitl", "gz_x500"], 
    cwd=config.LAUNCH_CWD, 
    env=config.LAUNCH_ENV
)

qgc = subprocess.Popen(
    ["gnome-terminal", "--", "./QGroundControl-x86_64.AppImage"],
    cwd=config.LAUNCH_CWD
)