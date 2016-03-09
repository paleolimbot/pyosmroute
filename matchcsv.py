
import os
import sys
import pyosmroute as pyosm


def matchcsv(csvfiles, matchargs, dbargs=None, outpoints=False, outsegs=False):
    if dbargs is None:
        dbargs = {}
    db = pyosm.get_planet_db(**dbargs)
    db.connect()
    allstats = []
    with db.conn:
        for csvfile in csvfiles:
            pyosm.log("Processing CSV: %s" % csvfile)
            try:
                with open(csvfile) as f:
                    firstline = f.readline()
                    if firstline.strip() == "RawGPS":  # is regular trip
                        headers = True
                    else: # is a chris processed trip
                        headers = False
                df = pyosm.read_csv(csvfile, driver="csv", headers=headers, skiprows=1)
                stats, points, segs = pyosm.osmmatch(db, df, lon_column=2, lat_column=1, unparsed_datetime_col=0)
                stats["_csv_file"] = csvfile
                allstats.append(stats)
                if outpoints and points:
                    points.to_csv(csvfile[:-4] + "_osmpoints.csv")
                if outsegs and segs:
                    segs.to_csv(csvfile[:-4] + "_osmsegs.csv")
            except Exception as e:
                pyosm.log("Could not process trip %s: %s" % (csvfile, e), stacktrace=True)
                allstats.append({'_csv_file': csvfile, 'result': type(e).__name__})
    db.disconnect() # already taken care of by context manager, but might as well
    return allstats


if __name__ == "__main__":
    # designed to be run from the command line. folder is main argument, walked recursively if -r is passed
    # output file as -o [FILE]

    import argparse
    parser = argparse.ArgumentParser("Display stats and perform batch operations on Zeusur.io/Polarax trip collection")
    parser.add_argument("infile", help="Directory containing or a single CSV file with GPS Time (UTC), Latitude,"
                                       " and Longitude columns.")
    parser.add_argument("-r", "--recursive", help="Walk directory recursively", action="store_true", default=False)
    parser.add_argument("-o", "--output", help="Specify summary output file, use '.csv' or '.tsv' extension.")
    parser.add_argument("--writepoints", help="Write point matches to %FILE%_osmpoints.csv",
                        action="store_true", default=False)
    parser.add_argument("--writesegs", help="Write all segment matches to %FILE%_osmsegs.csv",
                        action="store_true", default=False)
    parser.add_argument("--processes", help="Specify number of worker processes.", type=int, default=1)
    parser.add_argument("--chunksize", help="Specify the multiprocesing chunksize parameter.", type=int, default=10)
    parser.add_argument("-v", "--verbose", help="Verbose debug output.",
                        action="store_true", default=False)

    args = parser.parse_args()
    if args.verbose:
        pyosm.config_logger()

    csvfiles = []
    if os.path.isfile(args.infile):
        csvfiles.append(args.infile)
    elif os.path.isdir(args.infile):
        if args.recursive:
            for root, dirs, files in os.walk(args.infile):
                for file in files:
                    if file.endswith(".csv"):
                        csvfiles.append(os.path.join(root, file))
        else:
            for file in os.listdir(args.infile):
                if file.endswith(".csv"):
                    csvfiles.append(os.path.join(args.infile, file))

    else:
        pyosm.log("%s is not a file or directory" % args.infile)
        sys.exit(1)

    if not csvfiles:
        pyosm.log("No trips found, nothing to do (exiting)")
        sys.exit(0)

    matchargs = {} # add these to commandline someday?
    dbargs = {} # add these to commandline someday?

    if args.processes > 1 and args.chunksize <= len(csvfiles):
        from multiprocessing import Pool
        csvchunks  = [csvfiles[i:i+args.chunksize] for i in range(0, len(csvfiles), args.chunksize)]
        processargs = [(chunk, matchargs, dbargs, args.writepoints, args.writesegs) for chunk in csvchunks]
        with Pool(args.processes) as p:
            res = list(p.starmap(matchcsv, processargs))
            res = [item for sublist in res for item in sublist]
            summary = pyosm.DataFrame.from_dict_list(res, no_value="")
    else:
        summary = pyosm.DataFrame.from_dict_list(matchcsv(csvfiles, matchargs, dbargs,
                                                           args.writepoints, args.writesegs), no_value="")

    if args.output:
        summary.to_csv(args.output)
    else:
        print(summary.iloc[:, ("_csv_file", "result")])