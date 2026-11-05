DB_NAME = "your_database_name"
DB_USER = "your_username"
DB_PASSWORD = "your_password"
DB_HOST = "localhost"

totalDrones = 3
lowBatteryThreshold = 90
rendezvousRadiusMeters = 0.5
rendezvousOffsetMeters = 0.3
arrivalRadiusMeters = 5   # a corner counts as reached within this distance
cruiseAltMeters = 35      # patrol height above home; takeoff() asks for 60 m AMSL = 35 m over a 25 m home
cruiseSpeedMps = 5
boundaryInsetMeters = 8   # patrol corners sit this many meters inside the geofence edge
rechargeTimeoutSeconds = 75
rechargeTimeoutLimit = 2

LAUNCH_CWD = "/path/to/your/PX4-Autopilot"
QGC_PATH = "/path/to/QGroundControl.AppImage"
LAUNCH_ENV = {"PX4_HOME_LAT": "0.0", "PX4_HOME_LON": "0.0", "PX4_HOME_ALT": "0"}

#MIN_PCT 0 removes PX4's default 50% floor.
VTOL_ENV = {"PX4_PARAM_SIM_BAT_MIN_PCT": "0"}