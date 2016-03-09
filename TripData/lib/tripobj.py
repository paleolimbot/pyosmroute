
from lib.dataframe import DataFrame
import os
from lib.logger import log
import lib.tripstats as tripstats
import lib.osm.mapmatch as mapmatch
import json


class TripInterface(object):

    def __init__(self):
        self.info = {}
        self.stats = {}

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, state):
        self.__dict__.update(state)

    def __getattr__(self, item):
        try:
            return super().__getattribute__(item)
        except AttributeError:
            if not self._load_item(item):
                log("Failed to load attribute %s" % item)
                return None
            else:
                return self.__dict__[item]

    def _load_item(self, item):
        raise NotImplementedError()

    def _colnames(self):
        return tuple(self.info.keys()) + tuple(self.stats.keys())

    def _getcol(self, colname, default=None):
        if colname in self.info:
            return self.info[colname]
        elif colname in self.stats:
            return self.stats[colname]
        else:
            return default

    @staticmethod
    def summary(*trips, colnames=None, no_value=float('nan')):
        if colnames is None:
            cols = set()
            for trip in trips:
                for tcol in trip._colnames():
                    cols.add(tcol)
            colnames = list(cols)
        data = [[trip._getcol(col, default=no_value) for trip in trips] for col in colnames]
        return DataFrame(*data, columns=colnames)


class TripFolder(TripInterface):

    def __init__(self, folder, writecache=False, usecache=False, planetdb=None):
        super().__init__()
        if not os.path.isdir(folder):
            raise ValueError("Trip folder is not a folder")
        self.usecache = usecache
        self.writecache = writecache
        self.planetdb = planetdb

        self.__gpsfile = os.path.join(folder, "RawGPS.csv")
        self.__accfile = os.path.join(folder, "RawAccelerometer.csv")
        self.__magfile = os.path.join(folder, "RawMagnetometer.csv")
        self.__gyrofile = os.path.join(folder, "RawGyroscope.csv")
        self.__actstatesfile = os.path.join(folder, "RawActivityStates.csv")
        self.__statuesfile = os.path.join(folder, "RawStatues.csv")

        self.__matchstatsfile = os.path.join(folder, "OSMResults.json")
        self.__roadmatchfile = os.path.join(folder, "OSMPoints.csv")
        self.__roadmatchsegs = os.path.join(folder, "OSMSegments.csv")

        self.__statsfile = os.path.join(folder, "_tripmeta.json")

        self.info = {'folder': folder,
                     'name': os.path.basename(folder)}
        self. stats = {}
        self.osmmatch_args = {}

        # always try to load stats
        if usecache:
            try:
                with open(self.__statsfile) as f:
                    self.stats = json.load(f)
            except IOError:
                pass

    def calcstats(self):
        # leave which stats to calculate up to the lib.tripstats module
        tripstats.calcstats(self, self.stats)
        if self.writecache:
            with open(self.__statsfile, "w") as f:
                json.dump(self.stats, f)

    def _load_item(self, item):
        log("Reading item %s for folder %s" % (item, self.info["folder"]))

        try:
            if item == "acceleration":
                self.acceleration = DataFrame.read(self.__accfile, skiprows=1)
            elif item == "activities":
                self.activities = DataFrame.read(self.__actstatesfile, skiprows=1)
            elif item == "gyroscope":
                self.gyroscope = DataFrame.read(self.__gyrofile, skiprows=1)
            elif item == "statues":
                self.statues = DataFrame.read(self.__statuesfile, skiprows=1)
            elif item == "magnetometer":
                self.magnetometer = DataFrame.read(self.__magfile, skiprows=1)
            elif item == "gps":
                self.gps = DataFrame.read(self.__gpsfile, skiprows=1)
            elif item == "osmmatch":
                matched = False
                if self.usecache:
                    try:
                        with open(self.__matchstatsfile) as matchresultf:
                            self.osmmatch = json.load(matchresultf), DataFrame.read(self.__roadmatchfile), \
                                DataFrame.read(self.__roadmatchsegs)
                    except (IOError, ValueError):
                        if self.planetdb is None:
                            raise ValueError("PlanetDB is needed to perform OSM matching")
                        self.osmmatch = mapmatch.osmmatch(self.planetdb, self.gps, **self.osmmatch_args)
                        matched = True
                else:
                    if self.planetdb is None:
                        raise ValueError("PlanetDB is needed to perform OSM matching")
                    self.osmmatch = mapmatch.osmmatch(self.planetdb, self.gps, **self.osmmatch_args)
                    matched = True

                if matched and self.writecache:
                    with open(self.__matchstatsfile, "w") as f:
                        json.dump(self.osmmatch[0], f)
                    if self.osmmatch[1]:
                        self.osmmatch[1].write(self.__roadmatchfile)
                    if self.osmmatch[2]:
                        self.osmmatch[2].write(self.__roadmatchsegs)

            else:
                # unrecognized attribute
                return False

            return True
        except IOError as e:
            return False

    @staticmethod
    def walk(root_folder, **kwargs):
        trips = []
        for root, dirs, files in os.walk(root_folder):
            if "RawGPS.csv" in files:
                trips.append(TripFolder(root, **kwargs))
        return trips

    def __repr__(self):
        return "TripFolder(%s)" % self.info["folder"]


if __name__ == "__main__":
    # test
    from lib.osm.planetdb import PlanetDB
    from dbconfig import DB_NAME, DB_PASSWORD, DB_USER, DB_HOST
    import pandas as pd

    osmdb = PlanetDB(DB_HOST, DB_USER, DB_PASSWORD, DB_NAME)
    osmdb.connect()

    trip = TripFolder("../../../training-data/car/2016-03-02 18_16_13_Car - Normal Drive_Android", planetdb=osmdb,
                      usecache=False)
    trip.calcstats()  # shouldn't be any stats yet
    print(trip.osmmatch[0])

    # test if pandas data frame works in this code
    tripstats.load_default()
    tripstats.load_planetdb(osmdb)
    trip = TripFolder("../../../training-data/car/2016-03-02 18_16_13_Car - Normal Drive_Android", planetdb=osmdb,
                      usecache=False)
    trip.gps = pd.read_csv("../../../training-data/car/2016-03-02 18_16_13_Car - Normal Drive_Android/RawGPS.csv",
                           skiprows=1)
    trip.calcstats()
    print(trip.osmmatch[0])

    t2 = TripFolder("../../../training-data/car/2016-03-02 19_21_41_Car - Normal Drive_Android", planetdb=osmdb,
                    usecache=False)
    print(t2.osmmatch[0])
    t2.calcstats()

    d = TripFolder.summary(trip, t2)
    print(d)

    print(TripFolder.walk("../../../training-data"))