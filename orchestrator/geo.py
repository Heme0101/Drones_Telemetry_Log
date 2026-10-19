import math
METERS_PER_DEGREE = 111320

def offsetMeters(originLat, originLon, lat, lon):
    east = (lon - originLon) * METERS_PER_DEGREE * math.cos(math.radians(originLat))
    north = (lat - originLat) * METERS_PER_DEGREE
    return east, north

def distanceMeters(lat1, lon1, lat2, lon2):
    east, north = offsetMeters(lat1, lon1, lat2, lon2)
    return math.hypot(east, north)

def expectedTravelTime(distanceMeters, speedMps):
    return distanceMeters/speedMps