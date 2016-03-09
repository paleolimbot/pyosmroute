
from lib.geomeasure import geodist, bearing_to, crosstrack_error, bearing_difference, along_track_distance
from lib.osm._routing import Router
from lib.logger import log
import numpy as np

_WEIGHTINGS = {
      'motorway': {'car': 10},
      'trunk': {'car': 10, 'cycle': 0.05},
      'primary': {'cycle': 0.3, 'car': 2, 'foot': 1, 'horse': 0.1},
      'secondary': {'cycle': 1, 'car': 1.5, 'foot': 1, 'horse': 0.2},
      'tertiary': {'cycle': 1, 'car': 1, 'foot': 1, 'horse': 0.3},
      'unclassified': {'cycle': 1, 'car': 1, 'foot': 1, 'horse': 1},
      'minor': {'cycle': 1, 'car': 1, 'foot': 1, 'horse': 1},
      'cycleway': {'cycle': 3, 'foot': 0.2},
      'residential': {'cycle': 3, 'car': 0.7, 'foot': 1, 'horse': 1},
      'track': {'cycle': 1, 'car': 1, 'foot': 1, 'horse': 1, 'mtb': 3},
      'service': {'cycle': 1, 'car': 1, 'foot': 1, 'horse': 1},
      'bridleway': {'cycle': 0.8, 'foot': 1, 'horse': 10, 'mtb': 3},
      'footway': {'cycle': 0.2, 'foot': 1},
      'steps': {'foot': 1, 'cycle': 0.3},
      'rail': {'train': 1},
      'light_rail': {'train': 1},
      'subway': {'train': 1}
      }

_EQUALTAGS = {
      "motorway_link": "motorway",
      "primary_link": "primary",
      "trunk": "primary",
      "trunk_link": "primary",
      "secondary_link": "secondary",
      "tertiary": "secondary",
      "tertiary_link": "secondary",
      "residential": "unclassified",
      "minor": "unclassified",
      "steps": "footway",
      "driveway": "service",
      "pedestrian": "footway",
      "bridleway": "cycleway",
      "track": "cycleway",
      "arcade": "footway",
      "canal": "river",
      "riverbank": "river",
      "lake": "river",
      "light_rail": "railway"
      }


def _weighting(transport, tag):
    try:
        return _WEIGHTINGS[_EQUALTAGS[tag] if tag in _EQUALTAGS else tag][transport]
    except KeyError:
        # Default: if no weighting is defined, then assume it can't be routed
        return 0


def _bearing_diff(bearinggps, bearingroad, oneway):
    diff = bearing_difference(bearinggps, bearingroad)
    return diff if oneway else (diff if diff <= 90 else 180-diff)


def _isoneway(waydict):
    return ("oneway" in waydict["tags"]) and (waydict["tags"]["oneway"] in ('yes','true','1'))


def _distcompare(p1, p2, p3):
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    px = x2-x1
    py = y2-y1

    something = px*px + py*py

    u = ((x3 - x1) * px + (y3 - y1) * py) / float(something)

    if u > 1:
        u = 1
    elif u < 0:
        u = 0

    x = x1 + u * px
    y = y1 + u * py

    dx = x - x3
    dy = y - y3

    return dx*dx + dy*dy


class OSMCache(object):

    def __init__(self, db, trans_type="car"):
        self.trans_type = trans_type
        self.db = db
        self.nodes = {}
        self.ways = {}
        self.routing = {}

    def addways(self, *wayids):
        ways = self.db.ways(*wayids)
        for i in range(len(ways)):
            way = ways.iloc[i]
            self.ways[way["id"]] = way
            nodes = way["nodes"]
            oneway = _isoneway(way)
            typetag = way["tags"]["railway"] if self.trans_type == "train" else way["tags"]["highway"]
            name = way["tags"]["name"] if "name" in way["tags"] else None
            self.addnodes(*nodes)
            # add links
            for k in range(1, len(nodes)):
                n1 = self.nodes[nodes[k-1]]
                n2 = self.nodes[nodes[k]]
                p1 = (n1["lon"], n1["lat"])
                p2 = (n2["lon"], n2["lat"])
                seg = {'wayid': way["id"],
                    'segment': k,
                    'p1': p1, 'p2': p2,
                    'node1': nodes[k-1], 'node2': nodes[k],
                    'distance': geodist(p1, p2),
                    'bearing': bearing_to(p1, p2),
                    'oneway': oneway,
                    'typetag': typetag,
                    'name': name, # useful for debugging
                    'weight': _weighting(self.trans_type, typetag)
                  }
                self._addlink(seg)

    def _addlink(self, seg, reverse=False):
        nodes = (seg["node1"], seg["node2"]) if not reverse else (seg["node2"], seg["node1"])
        try:
            self.routing[nodes[0]][nodes[1]] = seg
        except KeyError:
            self.routing[nodes[0]] = {nodes[1]: seg}
        if not seg["oneway"] and not reverse:
            self._addlink(seg, True) # passing true here keeps from recursing more than once

    def addnodes(self, *nodes):
        nodes = self.db.nodes(*nodes)
        for i in range(len(nodes)):
            node = nodes.iloc[i]
            self.nodes[node["id"]] = node

    def _segments(self, wayid):
        waydict = self.ways[wayid]
        nodes = waydict["nodes"]
        for i in range(1, len(nodes)):
            try:
                yield self.routing[nodes[i-1]][nodes[i]]
            except KeyError:
                raise KeyError("Segment not found: wayid %s; segment %s" % (wayid, i))

    def get_segment(self, wayid, pt, delta=0.5):
        # TODO this needs optimization: for long ways with many points this is incredibly slow
        # information to compare with segments
        # delta parameter in the wiggle room in metres in regards to seeing if a segment is valid
        segments = list(self._segments(wayid))
        # find index where the two sequential nodes are the closest
        dists = [_distcompare(s["p1"], s["p2"], pt) for s in segments]
        seg = segments[np.argmin(dists)].copy()

        p1 = seg["p1"]
        p2 = seg["p2"]
        atrack = along_track_distance(p1, p2, pt)
        seg["alongtrack"] = atrack = atrack if atrack >= 0 and atrack <= seg["distance"] else \
            seg["distance"] if atrack >= seg["distance"] else 0
        seg["pt_onseg"] = (p1[0] + (p2[0]-p1[0])*atrack/seg["distance"], p1[1] + (p2[1]-p1[1])*atrack/seg["distance"])
        seg["xte"] = abs(crosstrack_error(p1, p2, pt))
        seg["dist_from_route"] = geodist(pt, seg["pt_onseg"]) # often close to xte but not if point is off end of route
        seg["pt"] = pt
        return seg

    def driving_distance(self, s1, s2, maxdist=None, grace_distance=0.0):
        # segments as produced by get_segment()
        # grace_distance used for moving the wrong way down the same segment. not having this
        # can cause errors when the gps is stationary (and may appear to be moving backwards)

        # useful for debugging specific driving distances
        # if s1["node1"] == 93218183 and s1["node2"] == 105397191 and s2["node1"] == 105397185 and s2["node2"] == 93218131:
        #     pass

        if s1["wayid"] == s2["wayid"] and s1["segment"] == s2["segment"]:
            # are on same segment (probably most common)
            diff = s2["alongtrack"] - s1["alongtrack"]
            # check for 'going the wrong way'
            if s1["oneway"] and diff < -grace_distance:
                # do routing from the end node to the beginning node
                router = Router(self, s1["node2"], s1["node1"])
                status, nodes, distance = router.doRoute()
                if nodes:
                    return distance + s1["distance"] + diff, nodes
                else:
                    return None, []
            else:
                return abs(diff), []

        if s1["node1"] == s2["node1"]:
            if not s1["oneway"]:
                return s1["alongtrack"] + s2["alongtrack"], [s1["node1"], ]
        elif s1["node1"] == s2["node2"]:
            if (not s1["oneway"]) and (not s2["oneway"]):
                return s1["alongtrack"] + s2["distance"] - s2["alongtrack"], [s1["node1"], ]
        elif s1["node2"] == s2["node1"]:
            return s1["distance"] - s1["alongtrack"] + s2["alongtrack"], [s1["node2"],]
        elif s1["node2"] == s2["node2"]:
            if not s2["oneway"]:
                return s1['distance'] - s1["alongtrack"] + s2['distance'] - s2["alongtrack"], [s1["node2"], ]

        router = Router(self, s1["node1"], s2["node1"], s2["node2"], maxdist=maxdist)
        status, nodes, distance = router.doRoute()

        if nodes:
            if s2["oneway"] and (s2["node1"] not in nodes):
                # we need a different route
                router = Router(self, s1["node1"], s2["node1"], maxdist=maxdist)
                status, nodes, distance = router.doRoute()
                # handle start/end distances
                if s1["node2"] in nodes:
                    nodes.remove(s1["node1"])
                    sdist = -s1["alongtrack"]
                else:
                    sdist = s1["alongtrack"]

                if s2["node2"] in nodes:
                    nodes.remove(s2["node2"])
                    edist = -s2["alongtrack"]
                else:
                    edist = s2["alongtrack"]
                return sdist + edist + distance, nodes
            else:
                # handle start/end distances
                if s1["node2"] in nodes:
                    nodes.remove(s1["node1"])
                    sdist = -s1["alongtrack"]
                else:
                    sdist = s1["alongtrack"]

                if s2["node1"] == nodes[-1]:
                    # end on node1
                    edist = s2["alongtrack"]
                elif s2["node2"] == nodes[-1]:
                    # end on node2
                    edist = s2["distance"] - s2["alongtrack"]

                return sdist + edist + distance, nodes
        else:
            return None, []

if __name__ == "__main__":
    from dbconfig import DB_NAME, DB_PASSWORD, DB_USER, DB_HOST
    import sys
    import os
    from lib.dbinterface import PlanetDB
    from lib.dataframe import DataFrame

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
        ways = [db.nearest_ways(lon[i], lat[i], radius=radius) for i in range(len(gpsdf))]
        idlist = []
        for wayids in ways:
            for id in wayids:
                idlist.append(id)

        cache = OSMCache(db, "car")
        log("Building Cache...")
        cache.addways(*idlist)
        log("Loaded %s nodes and %s ways with %s links" % (len(cache.nodes), len(cache.ways), len(cache.routing)))
        print(cache.get_segment(idlist[0], (lon[0], lat[0])))
    except:
        log("Error executing test!", stacktrace=True)
    db.disconnect()