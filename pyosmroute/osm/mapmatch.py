import time

import numpy as np
from gevent.pool import Pool

from pyosmroute import gpsclean
from ._hiddenmarkovmodel import HiddenMarkovModel
from ._osmcache import OSMCache
from ._probabilities import emission_probability, get_lazy, get_all
from ..dataframe import DataFrame
from ..logger import log


def nearest_road(db, radius, *points):
    """
    Finds the nearest road to points, giving up after raidus radius.

    :param db: A PlanetDB database object.
    :param points: One or more tuples of (lon, lat).
    :param radius: The radius at which to terminate the search
    :return: A DataFrame with the information about the way closest to the point or None.
    """
    allres = []
    for point in points:
        lon, lat = point
        res = db.nearest_ways(lon, lat, radius=radius)
        allres.append(db.ways(res[0]).iloc[0] if res else None)
    return allres[0] if len(allres) == 1 else allres


def osmmatch(db, gpsdf, lat_column="Latitude", lon_column="Longitude", unparsed_datetime_col=0,
             searchradius=50, minpoints=10, maxvel=250, sigmaZ=10, beta=10.0, maxiter=1,
             minpointdistance=30, paramter_window=3, bearing_penalty_weight=1, viterbi_lookahead=1,
             lazy_probabilities=True, points_summary=True, segments_summary=True, db_threads=20):
    """
    Match timestamped GPS points to roads in the OSM database. The matching is based a Hidden Markov Model
    with emission probabilities based on the distance to the road segment, and transition probabilities
    based on the difference between the GPS distance between two points and what the driving distance would
    be. This model is explained in Microsoft Research paper by Paul Newson and John Krumm entitled
    'Hidden Markov Map Matching Through Noise and Sparseness'. This implementation of what is explained
    in the paper has two differences. First, emission probability has a component that is based on the
    difference between the direction of the segment and the direction based on the two surrounding GPS points.
    Second, solving the Hidden Markov Model implements a 'lookahead' parameter, such that a next step can be chosen
    based on looking several steps into the future (see the viterbi_lookahead parameter).

    Driving distances are based on the pyroutelib2 library (https://github.com/gaulinmp/pyroutelib2), although
    considerable modifications had to be made to accommodate the needs of this function (mostly driving distances
    between adjacent segments and connecting to the database instead of reading a downloaded XML).

    :param db: a PlanetDB object, as generated by get_planet_db() or by instantiating the object yourself.
    :param gpsdf: A DataFrame (either pyosmroute.DataFrame or pandas.DataFrame, although the former is about twice
                  as fast) of GPS points with at least date/time, longitude, and latitude columns.
    :param lat_column: A column reference to gpsdf specifying which column contains the latitude information.
    :param lon_column: A column reference to gpsdf specifying which column contains the longitude information.
    :param unparsed_datetime_col: A column reference to gpsdf specifying which column contains the datetime
                                  information. The format must be '2016-03-01 20:59:46' (extra letters are stripped).
    :param searchradius: The radius around each GPS point to search for roads. The original paper uses a radius of
                         200 metres, around 50 seems to work well though.
    :param minpoints: After cleaning the GPS data such that there are data points ever 'minpointdistance' metres,
                      if fewer than this number of points remain, no matching is performed. For debugging it's good
                      to keep this low, but realistically any trip with less than about 20 points isn't worth matching.
    :param maxvel: The maximum assumed velocity (m/s). This value is used to terminate routing between two points once
                   the route would require the driver to travel over this speed. GPS points are noisy enough that this
                   must be about twice the maximum speed. Anything under 250 caused unnecessary gaps during testing.
    :param sigmaZ: The standard deviation of GPS error (metres). A higher value places less emphasis on how close a
                   point is to any given segment.
    :param beta: The standard deviation of the difference between the GPS distance and the driving distance between
                 two points on a segment. Increasing this allows for less efficient routes to be considered.
    :param maxiter: Problematic points can be removed, but this requires that transition probabilities are calculated
                    twice, which can be slow.
    :param minpointdistance: Prior to performing analysis, GPS data are cleaned such that no two points are closer than
                             this distance. The original paper suggests setting this value to sigmaZ * 2, so far
                             sigmaZ * 3 has produced better results.
    :param paramter_window: Velocities, rotations, and bearings are calculated according to this window. 3 is the
                            default value.
    :param bearing_penalty_weight: Use this to increase or decrease the effect of a bearing difference on the emission
                                   probability of a point. A number between 0 and 1 is preferred, although higher than
                                   1 will not cause errors.
    :param viterbi_lookahead: The length of the path to consider when making decisions about the best path through
                              the Hidden Markov Model. 0 is fastest, 1 produces better results, and 2 appears to be
                              slow. Passing > 0 to this parameter will not work when using pypy.
    :param lazy_probabilities: True if only transition probabilities that are used should be calculated. If lookahead
                               is 0, this is significantly faster. If lookahead is 1 or greater, most transition
                               probabilties are used, so this does not lead to a performance increase.
    :param points_summary: True if the list of point/segment matches should be returned, False otherwise.
    :param segments_summary: True if the complete list of segments should be returned, False otherwise.
    :param db_threads: Number of threads to execute synchronous queries.
    :return: A 3-tuple. The first item is a dictionary containing summary statistics about the match, the second
                item is the points_summary, the third item is the segments_summary. If both points_summary
                and segments_summary are False, the function returns an output that allows the complete
                match to be reconstructed.
    """

    log("Starting map matching")
    t_start = time.time()

    log("Cleaning data...")
    # add indicies so we can keep track of original observation indicies
    gpsdf["_original_index"] = [i for i in range(len(gpsdf))]
    if "_datetime" not in gpsdf:
        gpsdf["_datetime"] = gpsclean.datetimes(gpsdf, unparsed_col=unparsed_datetime_col)
    cleaned = gpsclean.cleanpoints(gpsdf, min_distance=minpointdistance, min_velocity=None, lat_column=lat_column,
                                   lon_column=lon_column)
    t_cleaned = time.time()

    log("Calculating velocities and directions...")
    cleaned["_velocity"] = gpsclean.velocities(cleaned, nwindow=paramter_window, lat_col=lat_column, lon_col=lon_column)
    cleaned["_bearing"] = gpsclean.bearings(cleaned, nwindow=paramter_window, lat_col=lat_column, lon_col=lon_column)
    cleaned["_rotation"] = gpsclean.rotations(cleaned, nwindow=paramter_window)
    cleaned["_distance"] = gpsclean.distances(cleaned, lat_col=lat_column, lon_col=lon_column)

    if len(cleaned) < minpoints:
        log("Too few points to perform matching (%s)" % len(gpsdf))
        return {"result": "not_enough_points"}, DataFrame(), DataFrame()

    # at least have output columns have a standard name
    if "Latitude" not in cleaned or "Longitude" not in cleaned:
        cleaned["Latitude"] = cleaned[lat_column]
        cleaned["Longitude"] = cleaned[lon_column]
        del cleaned[lat_column]
        del cleaned[lon_column]

    # from now on, don't refer to gps data frame, just the gps points (list of dicts)
    gpspoints = [cleaned.iloc[i] for i in range(len(cleaned))]
    t_velocity_direction = time.time()

    log("Fetching all possible ways within radius %s..." % searchradius)
    tp = Pool(db_threads if db_threads else len(gpspoints))
    ways = list(tp.imap(db.nearest_ways, cleaned["Longitude"], cleaned["Latitude"],
                        np.repeat(searchradius, len(gpspoints))))

    # ways = [db.nearest_ways(p["Longitude"], p["Latitude"], radius=searchradius) for p in gpspoints]
    t_fetchways = time.time()

    log("Building in-memory cache...")
    cache = OSMCache(db)
    idlist = set([item for sublist in ways for item in sublist])
    cache.addways(*idlist)  # best done like this so there is only one query to the database
    log("Loaded %s nodes and %s ways with %s links" % (len(cache.nodes), len(cache.ways), len(cache.routing)))
    t_cache = time.time()

    log("Calculating emission probabilities...")
    # 'score' how well each set of observations matches up with each row of the data frame of possible ways
    eprobs = []
    states = []
    for t, wayids in enumerate(ways):
        ptdict = gpspoints[t]
        segs = [cache.get_segment(wayid, (ptdict["Longitude"], ptdict["Latitude"]))
                for wayid in wayids]
        states.append(segs)
        eprobs.append([emission_probability(seg, ptdict, sigmaZ=sigmaZ, bearing_penalty_weight=bearing_penalty_weight)
                       for seg in segs])

    log("Cleaning points with no way matches...")
    for i in reversed(range(len(states))):
        if not states[i]:
            gpspoints.pop(i)
            states.pop(i)
            eprobs.pop(i)

    if not states:
        log("No matches found for points. There is likely no roads data available for this location.")
        return {"result": "no matches"}, DataFrame(), DataFrame()
    t_eprobs = time.time()

    log("Calculating transition probabilities...")
    tpdict = None
    path = None
    count = 0
    badpoints = []

    while count < maxiter:
        count += 1
        # clean bad points identified by previous iteration
        if badpoints:
            log("Removing %s bad points identified by previous iteration" % len(badpoints))
        for t in reversed(badpoints):
            # removing t-1 here is a judgement call...the bad point could easily be at t (or t+1)
            # until routing though the HMM is perfected, this is a mute point
            gpspoints.pop(t - 1)
            states.pop(t - 1)
            eprobs.pop(t - 1)

        # using LazyTransitionProbabilities allows for only necessary transition probabilities to be calculated
        # if a large proportion of probabilities are going to be used (e.g. if going forward two points)
        # it may be slightly faster to calculate them all in advance? it's possible to do this using a nested loop
        # here like this:

        tpdict = get_lazy(cache, obs=gpspoints, states=states, beta=beta,
                          grace_distance=minpointdistance, maxvel=maxvel) if lazy_probabilities else \
            get_all(cache, obs=gpspoints, states=states, beta=beta,
                          grace_distance=minpointdistance, maxvel=maxvel)

        log("Extracting probable path...")
        hmm = HiddenMarkovModel(eprobs, tpdict)
        # path = hmm.viterbi_lookahead() not pypy friendly!
        path = hmm.viterbi() if viterbi_lookahead == 0 else hmm.viterbi_lookahead(lookahead=viterbi_lookahead)
        badpoints = [t for t, result in enumerate(path) if result[0] is None]
        if not badpoints:
            break

    if path is None or tpdict is None:
        raise ValueError("path or tpdict somehow not assigned in transition probability loop")

    pathsegs = [states[t][result[0]] for t, result in enumerate(path) if result[1]]
    nodes = [None, ]
    breaks = []
    for t in range(1, len(path)):
        if path[t][1] and path[t - 1][1]:  # need both t and t-1 to have a segment result
            nodes.append(tpdict.getdata(t - 1, path[t - 1][0], path[t][0]))
        elif path[t][1]:
            nodes.append(None)  # and don't append at all if not path[t]
        else:
            breaks.append(t)

    # keep everything the same length or else throws errors
    for t in reversed(breaks):
        path.pop(t)
        gpspoints.pop(t)

    assert len(pathsegs) == len(path) == len(nodes) == len(gpspoints)

    t_tprobshmm = time.time()
    telapsed = t_tprobshmm - t_start

    # general summary stats
    stats = {
        "result": "ok",
        "started": time.strftime("%Y-%m-%d %H:%M:%S +0000", time.gmtime(t_start)),
        "t_total": telapsed,
        "t_cleaned": t_cleaned - t_start,
        "t_velocity_direction": t_velocity_direction - t_cleaned,
        "t_fetchways": t_fetchways - t_velocity_direction,
        "t_cache": t_cache - t_fetchways,
        "t_eprobs": t_eprobs - t_cache,
        "t_hmm": t_tprobshmm - t_eprobs,
        "in_points": len(gpsdf),
        "cleaned_points": len(cleaned),
        "matched_points": len(gpspoints),
        "matched_proportion": len(gpspoints) / len(cleaned)
    }

    log("Generating summary...")

    if points_summary:
        summary = _points_summary(cache, gpspoints, pathsegs)
        _summary_statistics(summary, output=stats, gps_distance=(np.nansum, "gps__distance"), mean_xte=(np.mean, "xte"))
        dur_sec = (summary["gps__datetime"][len(summary)-1] - summary["gps__datetime"][0]).seconds
        stats["trip_duration_min"] = dur_sec / 60.0
    else:
        summary = DataFrame()

    if segments_summary:
        tripsummary = _segment_summary(cache, gpspoints, pathsegs, nodes)
        _summary_statistics(tripsummary, output=stats, segment_distance=(np.sum, "distance"))
    else:
        tripsummary = DataFrame()

    if not points_summary and not segments_summary:
        # make simple, reconstructable summary
        for t, seg in enumerate(pathsegs):
            seg["missingnodes"] = nodes[t]
            seg["gps__original_index"] = int(cleaned["_original_index"][t])
        summary = DataFrame.from_dict_list(pathsegs, keys=("gps__original_index", "wayid", "segment",
                                                    "node1", "node2", "missingnodes"))
        tripsummary = DataFrame()  # makes output types at least consistent

    summarytime = time.time() - t_start - telapsed
    stats["t_summary"] = summarytime

    log("Done: %s points in %0.1f sec (%d points/sec) matching, %0.1f sec summary" %
        (len(cleaned), telapsed, len(cleaned) / telapsed, summarytime))
    return stats, summary, tripsummary


def make_linestring(segsoutput):
    """
    Make a dict of the linestring represented by the segments output (useful for passing to json to
    create a mappable version of this in some JS mapping api).

    :param segsoutput: Output as created by osmmatch()
    :return: A list of dicts with elements "lon" and "lat"
    """
    out = []
    lon = []
    lat = []

    # loop through segs output testing for breaks. beginning of breaks use the
    # pt_onseg as the beginning point and p2 as the end point. end of breaks use
    # pt_onseg as
    for i in range(len(segsoutput)):
        row = segsoutput.iloc[i]
        nextrow = segsoutput.iloc[i+1] if i+1 < len(segsoutput) else None
        if (len(lat) == len(lon) == 0) and not (np.isnan(row["pt_onseg_lon"]) or np.isnan(row["pt_onseg_lon"])):
            lon.append(row["pt_onseg_lon"])
            lat.append(row["pt_onseg_lat"])

        # test for break situation: next lat/lon pair doesn't match up
        if (nextrow and nextrow["p1_lon"] != row["p2_lon"] and nextrow["p1_lat"] != row["p2_lat"] or
              nextrow is None):
            lon.append(row["pt_onseg_lon"])
            lat.append(row["pt_onseg_lat"])
            out.append({"lon": list(lon), "lat": list(lat)})
            lat = []
            lon = []
        elif (nextrow["node1"] == row["node2"]) and (nextrow["node2"] == row["node1"]):
            # out and back situation
            lon.append(row["pt_onseg_lon"])
            lat.append(row["pt_onseg_lat"])
        else:
            lon.append(row["p2_lon"])
            lat.append(row["p2_lat"])

    if not (len(lat) == len(lon) == 0):
        out.append({"lon": list(lon), "lat": list(lat)})

    return out


def _points_summary(cache, gpspoints, pathsegs):

    keys = list(sorted(pathsegs[0].keys()))
    gpskeys = list(sorted(gpspoints[0].keys()))

    keys.remove("pt")

    summary = DataFrame.from_dict_list(pathsegs, keys=keys)
    summary["p1_lon"], summary["p1_lat"] = zip(*summary["p1"])
    summary["p2_lon"], summary["p2_lat"] = zip(*summary["p2"])
    summary["pt_onseg_lon"], summary["pt_onseg_lat"] = zip(*summary["pt_onseg"])
    del summary["p1"]
    del summary["p2"]
    del summary["pt_onseg"]

    gpssummary = DataFrame.from_dict_list(gpspoints, keys=gpskeys)
    for col in gpssummary:
        summary["gps_" + col] = gpssummary[col]
    summary["gps__original_index"] = summary["gps__original_index"].astype(int)

    waytags = DataFrame.from_dict_list([cache.ways[wayid]["tags"] for wayid in summary["wayid"]], no_value="")
    for tagname in waytags:
        summary["waytag_" + tagname] = waytags[tagname]

    return summary


def _segment_summary(cache, gpspoints, pathsegs, nodes):
    # generate trip summary (just the route, nothing to do with points)
    allsegs = []
    for t, d in enumerate(pathsegs):
        mnodes = nodes[t]
        if mnodes is not None and len(mnodes) >= 2:
            missingsegs = [cache.routing[mnodes[i - 1]][mnodes[i]] for i in range(1, len(mnodes))]
            for seg in missingsegs:
                seg["points_indicies"] = []
                allsegs.append(seg)

        if (len(allsegs) > 0) and d["node1"] == allsegs[-1]["node1"] and d["node2"] == allsegs[-1]["node2"]:
            # matched point was same segment (no missing nodes)
            if "points_indicies" not in allsegs[-1]:
                allsegs[-1]["points_indicies"] = []
            allsegs[-1]["points_indicies"].append(t)
            if 0 not in allsegs[-1]["points_indicies"]:
                allsegs[-1]["pt_onseg"] = d["pt_onseg"]
        elif mnodes is None:
            d["points_indicies"] = [t,]
            allsegs.append(d)
        elif len(mnodes) >= 1:
            d["points_indicies"] = [t,]
            allsegs.append(d)
        else:
            # start up after break, other reasons probably as well
            pass

    keys = ("wayid", "segment", "node1", "node2", "typetag", "name", "distance", "bearing",
            "p1", "p2", "pt_onseg", "points_indicies")
    tripsummary = DataFrame.from_dict_list(allsegs, keys=keys)

    # go through tripsummary and calculate direction and assign nodetags
    direction = []
    nodetags = []

    i = 0
    while i < len(tripsummary):
        nextrow = tripsummary.iloc[i+1] if i+1 < len(tripsummary) else None
        row = tripsummary.iloc[i]
        prevrow = tripsummary.iloc[i-1] if (i-1) > 0 else None
        segdirections = []

        if prevrow and prevrow["wayid"] == row["wayid"]:
            s1 = prevrow["segment"]
            s2 = row["segment"]
            # -direction[-1] catches out and back situation with newly inserted row
            segdirections.append(-direction[-1] if s2 == s1 else 1 if s2 > s1 else -1)
        elif prevrow and row["node2"] in (prevrow["node1"], prevrow["node2"]):
            segdirections.append(-1)
        elif prevrow and row["node1"] in (prevrow["node1"], prevrow["node2"]):
            segdirections.append(1)

        if nextrow and nextrow["wayid"] == row["wayid"]:
            s1 = row["segment"]
            s2 = nextrow["segment"]
            assert s2 != s1
            val = 0 if s2 == s1 else 1 if s2 > s1 else -1
            if val not in segdirections:
                segdirections.append(val)
        elif nextrow and row["node2"] in (nextrow["node1"], nextrow["node2"]):
            if 1 not in segdirections:
                segdirections.append(1)
        elif nextrow and row["node1"] in (nextrow["node1"], nextrow["node2"]):
            if -1 not in segdirections:
                segdirections.append(-1)

        if len(segdirections) > 0:
            direction.append(segdirections[0])
        else:
            direction.append(0)

        # this is intended to catch an 'out and back' scenario
        # insert a row in segments that is the same as this row
        # the prevrow test with equal wayids should catch this and reverse direction
        if len(segdirections) > 1:
            # pick a pt_onseg that is relevant (largest distance from node1)
            alongtrack = np.array([pathsegs[j]["alongtrack"] for j in row["points_indicies"]])
            ind = np.argmin(alongtrack) if direction[-1] < 0 else np.argmax(alongtrack)
            tripsummary["pt_onseg"][i] = pathsegs[row["points_indicies"][ind]]["pt_onseg"]
            tripsummary.insert(i+1, *row)

        if direction[-1] > 0:
            nodetags.append(cache.nodes[row["node2"]]["tags"])
        elif direction[-1] < 0:
            # switch node 1 and node 2 so that node 1 always comes first
            tripsummary["node1"][i] = row["node2"]
            tripsummary["node2"][i] = row["node1"]
            p1 = tuple(row["p1"])
            tripsummary["p1"][i] = row["p2"]
            tripsummary["p2"][i] = p1
            nodetags.append(cache.nodes[row["node1"]]["tags"])
        else:
            nodetags.append({})

        i += 1

    tripsummary["direction"] = direction
    tripsummary["p1_lon"], tripsummary["p1_lat"] = zip(*tripsummary["p1"])
    tripsummary["p2_lon"], tripsummary["p2_lat"] = zip(*tripsummary["p2"])
    tripsummary["pt_onseg_lon"], tripsummary["pt_onseg_lat"] = \
        zip(*[p if type(p) == tuple else (float("nan"), float("nan")) for p in tripsummary["pt_onseg"]])
    del tripsummary["p1"]
    del tripsummary["p2"]
    del tripsummary["pt_onseg"]

    # flatten nodetags and waytags, much easier to do here than in R
    nodetags = DataFrame.from_dict_list(nodetags, "")
    for tagname in nodetags:
        tripsummary["nodetag_" + tagname] = nodetags[tagname]

    waytags = DataFrame.from_dict_list([cache.ways[wayid]["tags"] for wayid in tripsummary["wayid"]], no_value="")
    for tagname in waytags:
        tripsummary["waytag_" + tagname] = waytags[tagname]

    # fix column types (node1, node2, segment, wayid, oneway, gps__original_index)
    tripsummary["node1"] = tripsummary["node1"].astype(int)
    tripsummary["node2"] = tripsummary["node2"].astype(int)
    tripsummary["wayid"] = tripsummary["wayid"].astype(int)
    tripsummary["segment"] = tripsummary["segment"].astype(int)

    # subset to not include segments with multiple direction matches
    return tripsummary.iloc[tripsummary["direction"] != 0, :]


def _summary_statistics(df, output=None, **stats):
    if output is None:
        output = {}
    for name, stat in stats.items():
        output[name] = stat[0](df[stat[1]])
    return output
