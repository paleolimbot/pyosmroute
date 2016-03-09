
import os
import sys
from lib.logger import log
from lib.tripobj import TripFolder
import lib.tripstats as tripstats
import atexit


def process_trip(trip, matchstats, on_road_radius=15):
    try:
        trip.calcstats()
        if matchstats:
            if not trip.planetdb.is_connected():
                trip.planetdb.connect()
                atexit.register(trip.planetdb.disconnect)
                tripstats.load_planetdb(trip.planetdb, on_road_radius=on_road_radius)
            matchresults = trip.osmmatch[0]
            for key, val in matchresults.items():
                trip.stats["match_" + key] = val
    except Exception as e:
        log("Could not process trip %s: %s" % (trip, e))
    # clean object so only stats are returned
    trip.gps = None
    trip.acceleration = None
    trip.osmmatch = None
    trip.gyroscope = None
    trip.statues = None
    trip.activities = None
    trip.magnetometer = None
    return trip


if __name__ == "__main__":
    # designed to be run from the command line. folder is main argument, walked recursively if -r is passed
    # output file as -o [FILE]

    import argparse
    parser = argparse.ArgumentParser("Display stats and perform batch operations on Zeusur.io/Polarax trip collection")
    parser.add_argument("tripdir",
                        help="Base directory containing the RawGPS and RawAccelerometer files, or a directory "
                             "containing such folders passed with the -r option.")
    parser.add_argument("-r", "--recursive", help="Walk directory recursively", action="store_true", default=False)
    parser.add_argument("-o", "--output", help="Specify summary output file, use '.csv' or '.tsv' extension.")
    parser.add_argument("--usecache", help="Use cached statistics instead of recalculating.",
                        action="store_true", default=False)
    parser.add_argument("--writecache", help="Write cached statistics/matching (may be useful for loading data into R)",
                        action="store_true", default=False)
    parser.add_argument("--cols", help="Summary columns to output", nargs="*",
                        default=None)
    parser.add_argument("--matchstats", help="Run OSM matching algorithm and add statistics to output.",
                        default=False, action="store_true")
    parser.add_argument("--processes", help="Use multiple processes to perform calculations.", type=int, default=1)
    parser.add_argument("-v", "--verbose", help="Verbose debug output (currently not implemented)",
                        action="store_true", default=False)

    args = parser.parse_args()
    if not os.path.isdir(args.tripdir):
        log("%s is not a directory" % args.tripdir)
        sys.exit(1)

    if args.matchstats:
        from lib.osm.planetdb import PlanetDB
        from dbconfig import DB_NAME, DB_PASSWORD, DB_USER, DB_HOST
        osmdb = PlanetDB(DB_HOST, DB_USER, DB_PASSWORD, DB_NAME)  # don't connect! will cause errors in multiprocessing
    else:
        osmdb = None

    tripargs = {
        "writecache": args.writecache,
        "usecache": args.usecache,
        "planetdb": osmdb
    }

    tripstats.load_default()

    if args.recursive:
        trips = TripFolder.walk(args.tripdir, **tripargs)
    else:
        if not os.path.isfile(os.path.join(args.tripdir, "RawGPS.csv")):
            raise ValueError("No RawGPS.csv found, cannot process trip.")
        trips = [TripFolder(args.tripdir, **tripargs), ]

    if not trips:
        log("No trips found, nothing to do (exiting)")

    processargs = [(trip, args.matchstats) for trip in trips]

    if args.processes > 1:
        from multiprocessing import Pool
        with Pool(args.processes) as p:
            summary = TripFolder.summary(*list(p.starmap(process_trip, processargs)))
    else:
        summary = TripFolder.summary(*list(map(process_trip, *zip(*processargs))))

    if args.output:
        summary.to_csv(args.output)