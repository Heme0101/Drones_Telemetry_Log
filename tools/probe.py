import time
from collections import Counter
from pymavlink import mavutil

VEHICLES = {
    "VTOL-1":  "udp:127.0.0.1:14541",
    "Rover-1": "udp:127.0.0.1:14544"
}

for name, address in VEHICLES.items():
    conn = mavutil.mavlink_connection(address)
    hb = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=10)

    if hb is None:
        print(f"No signal on {address}")
        continue

    vehicleType = mavutil.mavlink.enums["MAV_TYPE"][hb.type].name
    print(f"{name}: system id {conn.target_system}, type {vehicleType}")

    seen = Counter()
    end = time.time() + 5

    while time.time() < end:
        msg = conn.recv_match(blocking=True, timeout=1)
        if msg is not None:
            seen[msg.get_type()] +=1 
    print("   messages in 5 s:", dict(seen))