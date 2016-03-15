
import numpy as np
from ..geomeasure import geodist


class Router(object):
    """
    An object utilizing an OSMCache object to route from one node to another.
    """

    def __init__(self, cache, startnode, endnode, maxdist=None, maxcount=1000000, seed=None, weights=True,
                 exclude=None):
        """
        :param cache: an OSMCache object.
        :param startnode: The node id at which to start.
        :param endnode: A list of end node ids that will terminate the search.
        :param maxdist: The maximum distance to search before abandoning a route.
        :param maxcount: The maximum number of iterations to search.
        :param seed: If provided, routing will consider this node first.
        :param weights: True if weighted distance should be considered, False otherwise.
        :param exclude: Nodes that constitute abandoning a path.
        """

        self.data = cache
        self.queue = []
        self.maxdist = maxdist
        self.weights= weights
        self.maxcount = maxcount
        self.searchStart = startnode
        if not hasattr(endnode, "__len__"):
            endnode = (endnode, )
        self.searchEnd = endnode
        endnodes = [cache.nodes[nid] for nid in endnode]
        self.searchendpos = np.mean([n["lon"] for n in endnodes]), np.mean([n["lat"] for n in endnodes])
        self.seed = seed
        self.exclude = [] if exclude is None else list(exclude)

    def doRoute(self):
        """
        Do the routing as setup above.

        :return: A 3-tuple: result, nodelist, distance (in metres)
        """
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
