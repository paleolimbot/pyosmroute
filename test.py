
import pyosmroute as pyosm


def test_match():
    file = "example-data/test/2016-03-02 17_37_41_Car - Normal Drive_Android.csv"

    pyosm.log("Reading trip %s" % file)
    gps = pyosm.read_csv(file, skiprows=1)

    osmdb = pyosm.get_planet_db()
    osmdb.connect()
    try:
        stats, points, segs = pyosm.osmmatch(osmdb, gps)
        if points:
            # points.write("OSMPoints.csv")
            # segs.write("OSMSegments.csv")
            print(stats)
    except:
        pyosm.log("Error executing test!", stacktrace=True)
    osmdb.disconnect()

if __name__ == "__main__":
    test_match()