from pymavlink import mavutil
import time
import sqlite3
import datetime

db = sqlite3.connect("telemetry.db")
cursor = db.cursor()
count = 0

connection = mavutil.mavlink_connection('udp:127.0.0.1:14540')
connection.wait_heartbeat()
print("Connected to system: ", connection.target_system)


connection.mav.command_long_send(
    connection.target_system,
    connection.target_component,
    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
    0,
    1,0,0,0,0,0,0
)

time.sleep(2)

print(connection.recv_match(type="COMMAND_ACK", blocking=True, timeout=5))


connection.mav.command_long_send(
    connection.target_system,
    connection.target_component,
    mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0,
    0,0,0,0,0,0,50
)

print(connection.recv_match(type="COMMAND_ACK", blocking=True, timeout=5))

last_log_time = time.time()


while count < 20:
    att = connection.recv_match(type="ATTITUDE", blocking=True)
    gps = connection.recv_match(type="GLOBAL_POSITION_INT", blocking=True)

    if time.time() - last_log_time >= 2:
        timestamp = str(datetime.datetime.now())
        cursor.execute("INSERT INTO telemetry (timestamp, roll, yaw, pitch, altitude) VALUES (?,?,?,?,?)", 
                    (timestamp, att.roll, att.yaw, att.pitch, gps.relative_alt / 304.8))
        db.commit()
        print("Logged: ", att.roll, gps.relative_alt/304.8)
        last_log_time = time.time()
        count+=1

connection.mav.command_long_send(
    connection.target_system,
    connection.target_component,
    mavutil.mavlink.MAV_CMD_NAV_LAND, 0,
    0,0,0,0,0,0,0
)

print(connection.recv_match(type="COMMAND_ACK", blocking=True, timeout=5))