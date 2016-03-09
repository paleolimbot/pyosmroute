
from math import sin, cos, atan2, sqrt, radians, degrees, acos, asin


def _radius(p1, p2, ellipsoid):
    if ellipsoid is not None:
        raise NotImplementedError("Ellipsoid support was dropped.")
    else:
        return 6371008.7714


def geodist(origin, destination, ellipsoid=None, wraplat=True):

    lon1, lat1 = origin
    lon2, lat2 = destination

    dlatdeg = lat2-lat1
    dlondeg = lon2-lon1
    if wraplat:
        if dlondeg > 180:
            dlondeg = 360 - dlondeg
        elif dlondeg < -180:
            dlondeg = -360 - dlondeg

    dlat = radians(dlatdeg)
    dlon = radians(dlondeg)
    a = sin(dlat/2) * sin(dlat/2) + cos(radians(lat1)) \
        * cos(radians(lat2)) * sin(dlon/2) * sin(dlon/2)
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    d = _radius(origin, destination, ellipsoid) * c

    return d


def bearing_to(origin, destination, wraplat=True):
    if origin == destination:
        return float('nan')
    lon1, lat1 = origin
    lon2, lat2 = destination
    dlondeg = lon2-lon1
    if wraplat:
        if dlondeg > 180:
            dlondeg = 360 - dlondeg
        elif dlondeg < -180:
            dlondeg = -360 - dlondeg

    lat1 = radians(lat1)
    lat2 = radians(lat2)
    dlon = radians(dlondeg)

    y = sin(dlon) * cos(lat2)
    x = cos(lat1)*sin(lat2) - sin(lat1)*cos(lat2)*cos(dlon)
    result = degrees(atan2(y, x))
    return result if result >= 0 else result + 360


def bearing_difference(bearing1, bearing2):
    bearing1 = (bearing1 + 360) % 360
    bearing2 = (bearing2 + 360) % 360
    result = bearing2 - bearing1

    return result - 360 if result > 180 else result + 360 if result < -180 else result


def crosstrack_error(p1, p2, p3, ellipsoid=None):
    # from https://github.com/FlightDataServices/FlightDataUtilities/blob/master/flightdatautilities/geometry.py

    bearing = bearing_to(p1, p3)
    bearing_true = bearing_to(p1, p2)
    diffbearing = radians(bearing_difference(bearing, bearing_true))
    distance = geodist(p1, p3, ellipsoid=ellipsoid)
    radius = _radius(p1, p2, ellipsoid)

    return asin(sin(distance / radius) * sin(diffbearing)) * radius


def along_track_distance(p1, p2, p3, ellipsoid=None):
    d13 = geodist(p1, p3)
    dxt = crosstrack_error(p1, p2, p3, ellipsoid=ellipsoid)
    radius = _radius(p1, p2, ellipsoid)
    result = acos(cos(d13 / radius) / cos(dxt / radius)) * radius
    angle = abs(bearing_difference(bearing_to(p1, p2), bearing_to(p1, p3)))
    return result if angle <= 90 else -result

if __name__ == "__main__":
    # test
    p1 = (-64.36449, 45.09123)  # wolfville
    p2 = (-63.57497, 44.64842)  # halifax
    p3 = (-64.131036 ,44.990286)  # windsor
    print(geodist(p1, p2))
    print(geodist(p2, p1))
    print(bearing_to(p1, p2))
    print(bearing_to(p2, p1))
    print(bearing_difference(360, 0))
    print(bearing_difference(0, 5))
    print(bearing_difference(0, -5))
    print(bearing_difference(359, 0))
    print(bearing_difference(140, 23))
    print(bearing_difference(270, 90))
    print(bearing_difference(359, 1))
    print(bearing_difference(359, 1))

    print(crosstrack_error(p1, p2, p3))
    print(crosstrack_error(p2, p1, p3))
    print(along_track_distance(p1, p2, p3))
    print(along_track_distance(p2, p1, p3))
    print(geodist(p1, p2))
    print(along_track_distance(p1, p2, p3) + along_track_distance(p2, p1, p3))
    print(along_track_distance(p3, p2, p1))
    print(along_track_distance(p1, p3, p2))
