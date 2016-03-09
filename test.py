
import os
import sys
import pyosmroute as pyosm


def test_match(db):
    file = "example-data/test/2016-03-02 17_37_41_Car - Normal Drive_Android.csv"

    pyosm.log("Reading trip %s" % file)
    gps = pyosm.read_csv(file, skiprows=1)

    stats, points, segs = pyosm.osmmatch(db, gps)
    if points:
        # points.write("OSMPoints.csv")
        # segs.write("OSMSegments.csv")
        pyosm.log(stats)


def test_clean():
    df = pyosm.read_csv("example-data/test/2016-03-02 17_37_41_Car - Normal Drive_Android.csv", skiprows=1)
    pyosm.log("Testing data frame with %s rows" % len(df))
    df = pyosm.cleanpoints(df)
    pyosm.log("got data frame with %s rows" % len(df))


def test_onroad(db):
    df = pyosm.read_csv("example-data/test/2016-03-02 17_37_41_Car - Normal Drive_Android.csv", skiprows=1)
    pyosm.log(pyosm.on_road_percent(db, df))


def test_nearest_road(db):
    df = pyosm.read_csv("example-data/test/2016-03-02 17_37_41_Car - Normal Drive_Android.csv", skiprows=1)
    pyosm.log(pyosm.nearest_road(db, (df.Longitude[100], df.Latitude[100]))["tags"])
    pyosm.log(pyosm.nearest_road(db, (0,0))) # should be None
    pyosm.log(len(pyosm.nearest_road(db, (df.Longitude[5], df.Latitude[5]), (df.Longitude[6], df.Latitude[6]))))


def test_data_frame():
    a = pyosm.DataFrame([1, 2, 3], ["one", "two", "three"], ["data1", "data2", "data3"])
    b = pyosm.DataFrame([], [], [], columns=["Column1", "Column2", "Column3"])
    pyosm.log(a[0])
    pyosm.log(a[1])
    pyosm.log(b[0])
    pyosm.log(b[1])
    pyosm.log(b.Column1)
    pyosm.log(b.Column2)
    pyosm.log(len(b))
    pyosm.log(b.ncol())
    # a.newcol = [1.23, 4.44, 9.19] #this does not add 'newcol' to columns, and does not work. use [] for assigning
    a["newcol"] = [1.23, 4.44, 9.19]
    b["newcol"] = [] #like this
    b.append(1,2,3, newcol="bananas")
    a.append([4, 5], ["four", "five"], ["data4", "data5"], newcol=[13, 10])
    pyosm.log(a)
    pyosm.log(b)
    with open("fish.csv", "w") as f:
        a.to_csv(f, driver="csv")
    a.to_csv("fish.tsv", driver="tsv")
    b.to_csv("fish.csv")
    b.to_csv("fish.csv", mode="a")
    c = pyosm.read_csv("fish.csv")
    pyosm.log(c)
    d = pyosm.read_csv("fish.csv", headers=False)
    pyosm.log(d)

    with open("fish.csv") as f:
        e = pyosm.read_csv(f, driver="csv")
        pyosm.log(e)

    a = pyosm.DataFrame([1,2], columns=["fish",])
    a["fish"] = ["one", "two"]
    pyosm.log(a)
    pyosm.log("-----")
    # pyosm.log(b.rowasdict(0))
    pyosm.log(a.iloc[0])  # should be the same
    pyosm.log(a.iloc[0, :])  # should be the same except as data frame

    pyosm.log(b.copy())

    os.unlink("fish.tsv")
    os.unlink("fish.csv")


def test_osm_cache():
    # TODO implement routing test
    # from dbconfig import DB_NAME, DB_PASSWORD, DB_USER, DB_HOST
    # import sys
    # import os
    # from lib.dbinterface import PlanetDB
    # from lib.dataframe import DataFrame
    #
    # folder = sys.argv[1] if len(sys.argv) >= 2 else \
    #     "../../../../example-data/ChinaTrips_v2/trip_sensor_41b705b6-a44f-4da2-a54b-f81c51fabb80"
    #
    # log("Reading trip %s" % folder)
    # gpsdf = DataFrame.read(os.path.join(folder, "RawGPS.csv"), skiprows=1)
    # radius = 50
    #
    # db = PlanetDB(DB_HOST, DB_USER, DB_PASSWORD, DB_NAME)
    # db.connect()
    # try:
    #     lon = gpsdf.Longitude
    #     lat = gpsdf.Latitude
    #
    #     log("Fetching all possible ways within radius %s..." % radius)
    #     ways = [db.nearest_ways(lon[i], lat[i], radius=radius) for i in range(len(gpsdf))]
    #     idlist = []
    #     for wayids in ways:
    #         for id in wayids:
    #             idlist.append(id)
    #
    #     cache = OSMCache(db, "car")
    #     log("Building Cache...")
    #     cache.addways(*idlist)
    #     log("Loaded %s nodes and %s ways with %s links" % (len(cache.nodes), len(cache.ways), len(cache.routing)))
    #     print(cache.get_segment(idlist[0], (lon[0], lat[0])))
    # except:
    #     log("Error executing test!", stacktrace=True)
    # db.disconnect()
    pass


def test_routing():
    # TODO implement routing test
    # from dbconfig import DB_NAME, DB_PASSWORD, DB_USER, DB_HOST
    # import sys
    # import os
    # from lib.dbinterface import PlanetDB
    # from lib.dataframe import DataFrame
    # from lib.logger import log
    # from lib.osm._osmcache import OSMCache
    #
    # folder = sys.argv[1] if len(sys.argv) >= 2 else \
    #     "../../../../example-data/ChinaTrips_v2/trip_sensor_41b705b6-a44f-4da2-a54b-f81c51fabb80"
    #
    # log("Reading trip %s" % folder)
    # gpsdf = DataFrame.read(os.path.join(folder, "RawGPS.csv"), skiprows=1)
    # radius = 50
    #
    # db = PlanetDB(DB_HOST, DB_USER, DB_PASSWORD, DB_NAME)
    # db.connect()
    # try:
    #     lon = gpsdf.Longitude
    #     lat = gpsdf.Latitude
    #
    #     log("Fetching all possible ways within radius %s..." % radius)
    #     ways = [db.nearest_ways(lon[i], lat[i], radius=radius) for i in range(gpsdf.nrow())]
    #     idlist = []
    #     for wayids in ways:
    #         for id in wayids:
    #             idlist.append(id)
    #
    #     cache = OSMCache(db, "car")
    #     log("Building Cache...")
    #     cache.addways(*idlist)
    #     log("Loaded %s nodes and %s ways with %s links" % (len(cache.nodes), len(cache.ways), len(cache.routing)))
    #     print(cache.get_segment(idlist[0], (lon[0], lat[0])))
    #
    #     log("Starting routing test")
    #     router = Router(cache, 119895157, 1888621542)
    #     r = router.doRoute()
    #     print(r)
    #     if r[0] == "success":
    #         nodes = r[1]
    #         segs = [cache.routing[nodes[i-1]][nodes[i]] for i in range(1, len(nodes))]
    #         keys = list(segs[0].keys())
    #         keys.append("p1_lon")
    #         keys.append("p1_lat")
    #         keys.append("p2_lon")
    #         keys.append("p2_lat")
    #         keys.remove("p1")
    #         keys.remove("p2")
    #         out = DataFrame(colnames=keys)
    #         for d in segs:
    #             d = d.copy()
    #             d["p1_lon"] = d["p1"][0]
    #             d["p1_lat"] = d["p1"][1]
    #             d["p2_lon"] = d["p2"][0]
    #             d["p2_lat"] = d["p2"][1]
    #             out.append(*[d[key] for key in keys])
    #
    #         out.to_csv("../../../../example-data/ChinaTrips_v2/trip_sensor_41b705b6-a44f-4da2-a54b-f81c51fabb80/routetest.csv")
    #
    # except:
    #     log("Error executing test!", stacktrace=True)
    # db.disconnect()
    pass


if __name__ == "__main__":
    osmdb = pyosm.get_planet_db()
    osmdb.connect()
    pyosm.config_logger()

    with osmdb.conn:
        pyosm.log("Testing osmmatch...")
        test_match(osmdb)
        pyosm.log("Testing cleanpoints...")
        test_clean()
        pyosm.log("Testing on_road_percent...")
        test_onroad(osmdb)
        pyosm.log("Testing nearest_road...")
        test_nearest_road(osmdb)
        pyosm.log("Testing DataFrame class...")
        test_data_frame()

    osmdb.disconnect()