DB_NAME = "your_database_name"
DB_USER = "your_username"
DB_PASSWORD = "your_password"
DB_HOST = "localhost"

totalDrones = 3
lowBatteryThreshold = 33

LAUNCH_CWD = "/path/to/your/PX4-Autopilot"
LAUNCH_ENV = {"PX4_HOME_LAT": "0.0", "PX4_HOME_LON": "0.0", "PX4_HOME_ALT": "0"}

# Simulated VTOL battery: SIM_BAT_DRAIN is the seconds for a full 100% -> 0% drain while armed.
# 60 seconds gives ~33% remaining after 40 s armed (100 - 60/90*100). MIN_PCT 0 removes PX4's default 50% floor.
VTOL_ENV = {"PX4_PARAM_SIM_BAT_DRAIN": "60", "PX4_PARAM_SIM_BAT_MIN_PCT": "0"}