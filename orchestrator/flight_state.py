from enum import Enum, auto

class FlightState(Enum):
    PATROL = auto()
    LOW_BATTERY = auto()
    RENDEZVOUS = auto()
    RECHARGING = auto()
    TAKEOFF = auto()