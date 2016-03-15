import time

import numpy as np

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
             lazy_probabilities=True, points_summary=True, segments_summary=True):
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
    :return: A 3-tuple. The first item is a dictionary containing summary statistics about the match, the second
                item is the points_summary, the third item is the segments_summary. If both points_summary
                and segments_summary are False, the function returns an output that allows the complete
                match to be reconstructed.
    """

    tstart = time.time()
    log("Starting map matching")

    # add indicies so we can keep track of original observation indicies
    gpsdf["_original_index"] = [i for i in range(len(gpsdf))]

    log("Cleaning data...")
    if "_datetime" not in gpsdf:
        gpsdf["_datetime"] = gpsclean.datetimes(gpsdf, unparsed_col=unparsed_datetime_col)
    cleaned = gpsclean.cleanpoints(gpsdf, min_distance=minpointdistance, min_velocity=None, lat_column=lat_column,
                                   lon_column=lon_column)

    log("Calculating velocities and directions...")
    cleaned["_velocity"] = gpsclean.velocities(cleaned, nwindow=paramter_window, lat_col=lat_column, lon_col=lon_column)
    cleaned["_bearing"] = gpsclean.bearings(cleaned, nwindow=paramter_window, lat_col=lat_column, lon_col=lon_column)
    cleaned["_rotation"] = gpsclean.rotations(cleaned, nwindow=paramter_window)
    cleaned["_distance"] = gpsclean.distances(cleaned, lat_col=lat_column, lon_col=lon_column)

    if len(cleaned) < minpoints:
        log("Too few points to perform matching (%s)" % len(gpsdf))
        return {"result": "not enough points"}, DataFrame(), DataFrame()

    # at least have output columns have a standard name
    if "Latitude" not in cleaned or "Longitude" not in cleaned:
        cleaned["Latitude"] = cleaned[lat_column]
        cleaned["Longitude"] = cleaned[lon_column]
        del cleaned[lat_column]
        del cleaned[lon_column]

    # from now on, don't refer to gps data frame, just the gps points (list of dicts)
    gpspoints = [cleaned.iloc[i] for i in range(len(cleaned))]

    log("Fetching all possible ways within radius %s..." % searchradius)
    ways = [DataFrame(wayid=db.nearest_ways(p["Longitude"], p["Latitude"], radius=searchradius)) for p in gpspoints]

    log("Building in-memory cache...")
    cache = OSMCache(db)
    idlist = set([item for sublist in [wayids["wayid"] for wayids in ways] for item in sublist])
    cache.addways(*idlist)  # best done like this so there is only one query to the database
    log("Loaded %s nodes and %s ways with %s links" % (len(cache.nodes), len(cache.ways), len(cache.routing)))

    log("Calculating emission probabilities...")
    # 'score' how well each set of observations matches up with each row of the data frame of possible ways
    eprobs = []
    states = []
    for t, waydf in enumerate(ways):
        ptdict = gpspoints[t]
        segs = [cache.get_segment(wayid, (ptdict["Longitude"], ptdict["Latitude"]))
                for wayid in waydf["wayid"]]
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
    nodes = [[], ]
    breaks = []
    for t in range(1, len(path)):
        if path[t][1] and path[t - 1][1]:  # need both t and t-1 to have a segment result
            nodes.append(tpdict.getdata(t - 1, path[t - 1][0], path[t][0]))
        elif path[t][1]:
            nodes.append([])  # and don't append at all if not path[t]
        else:
            breaks.append(t)

    # keep everything the same length or else throws errors
    for t in reversed(breaks):
        path.pop(t)
        gpspoints.pop(t)

    assert len(pathsegs) == len(path) == len(nodes) == len(gpspoints)

    telapsed = time.time() - tstart

    # general summary stats
    stats = {
        "result": "ok",
        "started": time.strftime("%Y-%m-%d %H:%M:%S +0000", time.gmtime(tstart)),
        "match_time": telapsed,
        "in_points": len(gpsdf),
        "cleaned_points": len(cleaned),
        "matched_points": len(gpspoints),
        "matched_proportion": len(gpspoints) / len(cleaned)
    }

    log("Generating summary...")

    if points_summary:
        summary = _points_summary(cache, gpspoints, pathsegs)
        _summary_statistics(summary, output=stats, gps_distance=(np.nansum, "gps__distance"), mean_xte=(np.mean, "xte"))
    else:
        summary = DataFrame()

    if segments_summary:
        tripsummary = _segment_summary(cache, pathsegs, nodes)
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

    summarytime = time.time() - tstart - telapsed
    stats["summary_time"] = summarytime

    log("Done: %s points in %0.1f sec (%d points/sec) matching, %0.1f sec summary" %
        (len(cleaned), telapsed, len(cleaned) / telapsed, summarytime))
    return stats, summary, tripsummary


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


def _segment_summary(cache, pathsegs, nodes):
    # generate trip summary (just the route, nothing to do with points)
    allsegs = []
    for t, d in enumerate(pathsegs):
        mnodes = nodes[t]
        if len(mnodes) >= 2:
            missingsegs = [cache.routing[mnodes[i - 1]][mnodes[i]] for i in range(1, len(mnodes))]
            for seg in missingsegs:
                allsegs.append(seg)
        if len(mnodes) >= 1 or t == 0:
            allsegs.append(d)
        else:
            # matched point was same segment (no missing nodes)
            pass

    keys = ("wayid", "segment", "node1", "node2", "typetag", "name", "distance", "bearing",
            "p1", "p2")
    tripsummary = DataFrame.from_dict_list(allsegs, keys=keys)
    tripsummary["p1_lon"], tripsummary["p1_lat"] = zip(*tripsummary["p1"])
    tripsummary["p2_lon"], tripsummary["p2_lat"] = zip(*tripsummary["p2"])
    del tripsummary["p1"]
    del tripsummary["p2"]

    # go through tripsummary and calculate direction and assign nodetags
    direction = []
    nodetags = []
    for i in range(len(tripsummary)):
        nextrow = tripsummary.iloc[i+1] if i+1 < len(tripsummary) else None
        row = tripsummary.iloc[i]
        prevrow = tripsummary.iloc[i-1] if i-1 < 0 else None
        if nextrow and nextrow["wayid"] == row["wayid"]:
            s1 = row["segment"]
            s2 = nextrow["segment"]
            direction.append(0 if s2 == s1 else 1 if s2 > s1 else -1)
        elif prevrow and prevrow["wayid"] == row["wayid"]:
            s1 = prevrow["segment"]
            s2 = row["segment"]
            direction.append(0 if s2 == s1 else 1 if s2 > s1 else -1)
        elif nextrow and row["node2"] in (nextrow["node1"], nextrow["node2"]):
            direction.append(1)
        elif nextrow and row["node1"] in (nextrow["node1"], nextrow["node2"]):
            direction.append(-1)
        elif prevrow and row["node2"] in (prevrow["node1"], prevrow["node2"]):
            direction.append(-1)
        elif prevrow and row["node1"] in (prevrow["node1"], prevrow["node2"]):
            direction.append(1)
        else:
            # somehow?
            direction.append(0)

        if direction[-1] > 0:
            nodetags.append(cache.nodes[row["node2"]]["tags"])
        else:
            nodetags.append(cache.nodes[row["node1"]]["tags"])

    tripsummary["direction"] = direction

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

    return tripsummary


def _summary_statistics(df, output=None, **stats):
    if output is None:
        output = {}
    for name, stat in stats.items():
       output[name] = stat[0](df[stat[1]])
    return output

