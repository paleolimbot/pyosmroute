
import numpy as np
from ..geomeasure import geodist


class Router(object):

    def __init__(self, cache, startnode, *endnode, maxdist=None, maxcount=1000000, seed=None, weights=True,
                 exclude=None):

        self.data = cache
        self.queue = []
        self.maxdist = maxdist
        self.weights= weights
        self.maxcount = maxcount
        self.searchStart = startnode
        self.searchEnd = endnode
        endnodes = [cache.nodes[nid] for nid in endnode]
        self.searchendpos = np.mean([n["lon"] for n in endnodes]), np.mean([n["lat"] for n in endnodes])
        self.seed = seed
        self.exclude = [] if exclude is None else list(exclude)

    def doRoute(self):
        """Do the routing"""
        closed = [self.searchStart, ] + self.exclude
        self.queue = []

        # Start by queueing all outbound links from the start node
        blankQueueItem = {'end': -1, 'distance': 0, 'weighted_distance': 0, 'nodes': [self.searchStart, ]}

        try:
            if self.seed: # make sure first item in the queue is the seeded node
                seg = self.data.routing[self.searchStart][self.seed]
                self.addToQueue(self.searchStart, self.seed, blankQueueItem, seg["weight"], seg["distance"])
            for nodeid, seg in self.data.routing[self.searchStart].items():
                if nodeid == self.seed:
                    continue
                self.addToQueue(self.searchStart, nodeid, blankQueueItem, seg["weight"], seg["distance"])
        except KeyError:
            return 'no_such_node', [], 0.0

        # Limit for how long it will search
        count = 0
        while count < self.maxcount:
            count += 1
            try:
                nextItem = self.queue.pop(0)
            except IndexError:
                # Queue is empty: failed
                return 'no_route', [], 0.0
            x = nextItem['end']
            if x in closed: # keeps track of all of the points that currently exist on routes to prevent double back
                continue
            if x in self.searchEnd:
                # Found the end node - success
                return 'success', nextItem['nodes'], nextItem['distance']
            closed.append(x)

            # test for distance greater than max distance, don't add to queue if this is true
            # had previously tested this before checking if this segment satisfied the route
            if self.maxdist and nextItem["distance"] > self.maxdist:
                # prevent from considering any options that go past maxdist
                continue

            try:
                for i, seg in self.data.routing[x].items():
                    if i not in closed:
                        self.addToQueue(x,i,nextItem, seg['weight'], seg['distance'])
            except KeyError:
                pass
        else:
            return 'gave_up',[], 0.0

    def addToQueue(self, start, end, queueSoFar, weight=1, distance=1):
        """Add another potential route to the queue"""

        end_pos = self.data.nodes[end]

        # If already in queue, ignore
        for test in self.queue:
            if test['end'] == end:
                return

        if weight == 0 and self.weights:
            return

        weighted_distance = distance / weight if self.weights else distance
        # Create a hash for all the route's attributes
        distanceSoFar = queueSoFar['distance']
        weightedSoFar = queueSoFar['weighted_distance']
        queueItem = {
              'distance': distanceSoFar + distance,
              'weighted_distance': weightedSoFar + weighted_distance,
              'maxdistance': weightedSoFar + geodist((end_pos["lon"], end_pos["lat"]), self.searchendpos),
              'nodes': list(queueSoFar['nodes']) + [end,],
              'end': end
            }

        # Try to insert, keeping the queue ordered by decreasing worst-case distance
        count = 0
        for test in self.queue:
            if test['maxdistance'] > queueItem['maxdistance']:
                self.queue.insert(count,queueItem)
                break
            count += 1
        else:
            self.queue.append(queueItem)

if __name__ == "__main__":
    from dbconfig import DB_NAME, DB_PASSWORD, DB_USER, DB_HOST
    import sys
    import os
    from lib.dbinterface import PlanetDB
    from lib.dataframe import DataFrame
    from lib.logger import log
    from lib.osm._osmcache import OSMCache

    folder = sys.argv[1] if len(sys.argv) >= 2 else \
        "../../../../example-data/ChinaTrips_v2/trip_sensor_41b705b6-a44f-4da2-a54b-f81c51fabb80"

    log("Reading trip %s" % folder)
    gpsdf = DataFrame.read(os.path.join(folder, "RawGPS.csv"), skiprows=1)
    radius = 50

    db = PlanetDB(DB_HOST, DB_USER, DB_PASSWORD, DB_NAME)
    db.connect()
    try:
        lon = gpsdf.Longitude
        lat = gpsdf.Latitude

        log("Fetching all possible ways within radius %s..." % radius)
        ways = [db.nearest_ways(lon[i], lat[i], radius=radius) for i in range(gpsdf.nrow())]
        idlist = []
        for wayids in ways:
            for id in wayids:
                idlist.append(id)

        cache = OSMCache(db, "car")
        log("Building Cache...")
        cache.addways(*idlist)
        log("Loaded %s nodes and %s ways with %s links" % (len(cache.nodes), len(cache.ways), len(cache.routing)))
        print(cache.get_segment(idlist[0], (lon[0], lat[0])))

        log("Starting routing test")
        router = Router(cache, 119895157, 1888621542)
        r = router.doRoute()
        print(r)
        if r[0] == "success":
            nodes = r[1]
            segs = [cache.routing[nodes[i-1]][nodes[i]] for i in range(1, len(nodes))]
            keys = list(segs[0].keys())
            keys.append("p1_lon")
            keys.append("p1_lat")
            keys.append("p2_lon")
            keys.append("p2_lat")
            keys.remove("p1")
            keys.remove("p2")
            out = DataFrame(colnames=keys)
            for d in segs:
                d = d.copy()
                d["p1_lon"] = d["p1"][0]
                d["p1_lat"] = d["p1"][1]
                d["p2_lon"] = d["p2"][0]
                d["p2_lat"] = d["p2"][1]
                out.append(*[d[key] for key in keys])

            out.write("../../../../example-data/ChinaTrips_v2/trip_sensor_41b705b6-a44f-4da2-a54b-f81c51fabb80/routetest.csv")

    except:
        log("Error executing test!", stacktrace=True)
    db.disconnect()