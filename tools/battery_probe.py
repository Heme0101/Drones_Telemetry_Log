import time
from pymavlink import mavutil

VEHICLES = {
    "VTOL-1":  "udp:127.0.0.1:14540",
    "VTOL-2":  "udp:127.0.0.1:14541",
    "VTOL-3":  "udp:127.0.0.1:14542",
    "Rover-1": "udp:127.0.0.1:14543"
}

for name, address in VEHICLES.items():
    conn = mavutil.mavlink_connection(address)
    print(name)

    end = time.time() + 10
    lastPrint = 0

    while time.time() < end:
        msg = conn.recv_match(type="SYS_STATUS",blocking=True,timeout=2)
        if msg is None:
            print("  no SYS_STATUS in 2 seconds")
            continue
        if time.time() - lastPrint >= 2:
            if msg.battery_remaining == -1:
                print('   battery: unknown')
            else:
                current = "unknown" if msg.current_battery == -1 else f"{msg.current_battery/100} A"
                print(f"   remaining battery: {msg.battery_remaining}%   "
                  f"voltage: {msg.voltage_battery / 1000} V   "
                  f"current: {current}")
            
            lastPrint = time.time()