import time
from pymavlink import mavutil

VEHICLES = {
    "VTOL-1":  "udp:127.0.0.1:14541",
    "Rover-1": "udp:127.0.0.1:14544"
}

for name, address in VEHICLES.items():
    conn = mavutil.mavlink_connection(address)
    print(name)

    end = time.time() + 10
    lastPrint = 0

    while time.time() < end:
        msg = conn.recv_match(type="SYS_STATUS",blocking=True,timeout=2)
        if msg is None:
            continue
        if time.time() - lastPrint >= 2:
            print(f"   remaing battery: {msg.battery_remaining}%   "
                  f"voltage: {msg.voltage_battery / 1000} V   "
                  f"current: {msg.current_battery / 100} A")
            
            lastPrint = time.time()