
import math


class Ellipsoid(object):

    def __init__(self, equatorRadius, poleRadius=None, name=None, shortName=None):

        self.__equatorRadius = equatorRadius
        if poleRadius is None:
            poleRadius = equatorRadius
        self.__poleRadius = poleRadius
        self.__eccentricitySquared = 1.0 - (poleRadius * poleRadius) / (equatorRadius * equatorRadius);
        self.__eccentricity = math.sqrt(self.__eccentricitySquared)
        self.__name = name
        self.__shortName = name

    def poleRadius(self):
        return self.__poleRadius
    def equatorRadius(self):
        return self.__equatorRadius
    def eccentricity(self):
        return self.__eccentricity
    def eccentricitySquared(self):
        return self.__eccentricitySquared
    def rMajor(self):
        return self.equatorRadius()
    def rMinor(self):
        return self.poleRadius()
    def reciprocalFlattening(self):
        return self.rMajor() / (self.rMajor() - self.rMinor())
    def flattening(self):
        return 1 / self.reciprocalFlattening()

    def radiusAt(self, latitude):
        a = self.rMajor()
        b = self.rMinor()
        f = latitude
        rSquared = ( ((a**2)*math.cos(f))**2 + ((b**2)*math.sin(f))**2 ) / ( (a*math.cos(f))**2 + (b*math.sin(f))**2 )
        return math.sqrt(rSquared)

    def __repr__(self):
        return "Ellipsoid(%f, %f)" % (self.equatorRadius(), self.poleRadius())

    def __str__(self):
        return repr(self)

    @staticmethod
    def byReciprocalFlattening(equatorRadius, reciprocalFlattening, name=None, shortName=None):
        f = 1.0 / reciprocalFlattening
        eccentricity2 = 2 * f - f * f;
        return Ellipsoid.byEccentricitySquared(equatorRadius, eccentricity2, name, shortName)

    @staticmethod
    def byEccentricitySquared(equatorRadius, eccentricitySquared, name=None, shortName=None):
        poleRadius = equatorRadius * math.sqrt(1.0 - eccentricitySquared)
        return Ellipsoid(equatorRadius, poleRadius, name, shortName)


class Ellipsoids(object):

    def __init__(self):
        pass

    SPHERE = Ellipsoid(6371008.7714)
    WGS84 = Ellipsoid.byReciprocalFlattening(6378137.0, 298.257223563)
    GRS1980 = Ellipsoid.byReciprocalFlattening(6378137.0, 298.257222101)


def _radius(p1, p2, ellipsoid):
    if ellipsoid is not None:
        averageLat = (p1[1]+p2[1]) / 2
        return ellipsoid.radiusAt(averageLat)
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

    dlat = math.radians(dlatdeg)
    dlon = math.radians(dlondeg)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) \
        * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
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

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    dlon = math.radians(dlondeg)

    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dlon)
    result = math.degrees(math.atan2(y, x))
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
    diffbearing = math.radians(bearing_difference(bearing, bearing_true))
    distance = geodist(p1, p3, ellipsoid=ellipsoid)
    radius = _radius(p1, p2, ellipsoid)

    return math.asin(math.sin(distance / radius) * math.sin(diffbearing)) * radius


def along_track_distance(p1, p2, p3, ellipsoid=None):

    d13 = geodist(p1, p3)
    dxt = crosstrack_error(p1, p2, p3, ellipsoid=ellipsoid) # TODO this should return negative sometimes
    radius = _radius(p1, p2, ellipsoid)
    result = math.acos(math.cos(d13 / radius) / math.cos(dxt / radius)) * radius
    angle = abs(bearing_difference(bearing_to(p1, p2), bearing_to(p1, p3)))
    return result if angle <= 90 else -result

if __name__ == "__main__":
    # test
    p1 = (-64.36449, 45.09123) # wolfville
    p2 = (-63.57497, 44.64842) # halifax
    p3 = (-64.131036 ,44.990286) # windsor
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