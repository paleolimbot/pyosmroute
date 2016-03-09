
import time
import numpy as np

from ..logger import log
from ..dataframe import DataFrame
from .. import gpsclean

from ._probabilities import emission_probability, get_lazy, get_all
from ._osmcache import OSMCache
from ._hiddenmarkovmodel import HiddenMarkovModel


def nearest_road(db, *points, radius=15):
    allres = []
    for point in points:
        lon, lat = point
        res = db.nearest_ways(lon, lat, radius=radius)
        allres.append(db.ways(res[0]).iloc[0] if res else None)
    return allres[0] if len(allres) == 1 else allres


def osmmatch(db, gpsdf, searchradius=50, minpoints=10, maxvel=250, sigmaZ=10, beta=10.0, maxiter=1,
             minpointdistance=30, paramter_window=3, bearing_penalty_weight=1, viterbi_lookahead=1,
             lazy_probabilities=True, points_summary=True, segments_summary=True):
    # maxvel used to discard improbable routes when calculating driving distance between two points
    # less than 100 causes gaps (probably because time resolution is only plus or minus one second
    # plus distance uncertainties). if maxvel is too high, performance slows down significantly.
    # lazy probabilities seems slightly faster, increasing the number of processes tends to
    # actually decrease efficiency, probably because a huge amount of overhead is involved in
    # exchanging the data between processes. setting viterbi_lookahead to > 10 will probably hang
    # your machine, setting to greater than 5 is probably unnecessary. lookahead=1 appears to be
    # the best option, setting lookahead to more than this does not increase accuracy.
    tstart = time.time()
    log("Starting map matching")

    # add indicies so we can keep track of original observation indicies
    gpsdf["_original_index"] = [i for i in range(len(gpsdf))]

    log("Cleaning data...")
    cleaned = gpsclean.cleanpoints(gpsdf, min_distance=minpointdistance, min_velocity=None)

    log("Calculating velocities and directions...")
    cleaned["_velocity"] = gpsclean.velocities(cleaned, nwindow=paramter_window)
    cleaned["_bearing"] = gpsclean.bearings(cleaned, nwindow=paramter_window)
    cleaned["_rotation"] = gpsclean.rotations(cleaned, nwindow=paramter_window)
    cleaned["_distance"] = gpsclean.distances(cleaned)

    if len(cleaned) < minpoints:
        log("Too few points to perform matching (%s)" % len(gpsdf))
        return {"result": "not enough points"}, DataFrame(), DataFrame()

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
        path = hmm.viterbi_lookahead(lookahead=viterbi_lookahead)
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

