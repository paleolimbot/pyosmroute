"""
Geometry tools for mapmatch.py
"""

from lib.geomeasure import bearing_difference, geodist
import numpy as np
from multiprocessing import Pool


def _bearing_diff(bearinggps, bearingroad, oneway):
    diff = abs(bearing_difference(bearinggps, bearingroad))
    return diff if oneway else (diff if diff <= 90 else 180-diff)


def _emission_probability_formula(xte, sigmaZ):  # reasonable estimation for error in GPS noise (5 m)
    # return 1.0 / (np.sqrt(2 * np.pi) * sigmaZ) * np.exp(-0.5 * (xte / sigmaZ)**2)
    return np.exp(-0.5 * (xte / sigmaZ)**2)  # returns one for xte = 0, easier


def _transition_probability_formula(gpsdist, routedist, beta=10.0):
    return np.exp(-(abs(gpsdist - routedist) / beta))


def emission_probability(seg, point_dict, sigmaZ=1.0, maxspeed=30, bearing_penalty_weight=1):
    # produce a bearing score based on speed and bearingdiff and distance from road
    v = point_dict["_velocity"]
    bdiff = _bearing_diff(point_dict["_bearing"], seg["bearing"], seg["oneway"])
    speed_scale = (v/maxspeed)**0.25 if v < maxspeed else 1  # sqrt seems to perform well
    score_bearing = (bdiff / 180)
    bearing_penalty = speed_scale * score_bearing * bearing_penalty_weight
    eprob = _emission_probability_formula(seg["dist_from_route"], sigmaZ=sigmaZ)
    return eprob * (1 - bearing_penalty)


def transition_probability(cache, seg1, seg2, gpsdist=None, beta=10.0, maxdist=None, grace_distance=0):
    if gpsdist is None:
        gpsdist = geodist(seg1["pt"], seg2["pt"])
    ddist, nodes = cache.driving_distance(seg1, seg2, maxdist=maxdist, grace_distance=grace_distance)
    tprob = _transition_probability_formula(gpsdist, ddist, beta=beta) if ddist else 0
    return tprob, nodes


def _batch_transitions(cache, states, obs, t, i, maxvel, beta, grace_distance):
    gpsdist = geodist(states[t][0]["pt"], states[t+1][0]["pt"])  # could also use obs to do this here
    dtime = (obs[t+1]["_datetime"] - obs[t]["_datetime"]).seconds
    maxdist = dtime * maxvel

    probs = {}
    data = {}
    for j in range(len(states[t+1])):
        tprob, nodes = transition_probability(cache, states[t][i], states[t+1][j], gpsdist=gpsdist,
                                              beta=beta, maxdist=maxdist, grace_distance=grace_distance)
        probs[t, i, j] = tprob
        data[t, i, j] = nodes
    return tuple(probs.keys()), probs, data


def get_lazy(osmcache, obs, states, beta=10.0, grace_distance=0, maxvel=250):
    return LazyTransitionProbabilities(osmcache, obs, states, beta=beta, grace_distance=grace_distance, maxvel=maxvel)


def get_all(osmcache, obs, states, beta=10.0, grace_distance=0, maxvel=250, processes=1):
    tis = [(t, i) for t, substates in enumerate(states) if t < len(states)-1 for i in range(len(substates))]
    args = [(osmcache, states, obs, t, i, maxvel, beta, grace_distance) for t, i in tis]
    tprobs = DictTransitionProbabilities()
    if processes > 1:
        with Pool(processes) as p:
            for result in p.starmap(_batch_transitions, args, chunksize=len(args)//processes):
                keys, probs, data = result
                for key in keys:
                    tprobs[key] = probs[key], data[key]
    else:
        for result in map(_batch_transitions, *zip(*args)):
            keys, probs, data = result
            for key in keys:
                tprobs[key] = probs[key], data[key]

    return tprobs


class TransitionProbabilities(object):

    def __init__(self):
        pass

    def __setitem__(self, key, value):
        t, i, j = key
        try:
            prob, data = value
        except ValueError:
            prob, data = value, None
        self.put(t, i, j, prob, data)

    def __getitem__(self, item):
        return self.getprob(*item)

    def put(self, t, i, j, prob, data=None):
        raise NotImplementedError()

    def getprob(self, t, i, j):
        raise NotImplementedError()

    def getdata(self, t, i, j):
        raise NotImplementedError()


class DictTransitionProbabilities(TransitionProbabilities):

    def __init__(self):
        super().__init__()
        self.probs = {}
        self.data = {}

    def put(self, t, i, j, prob, data=None):
        self.probs[t, i, j] = prob
        self.data[t, i, j] = data

    def getprob(self, t, i, j):
        return self.probs[t, i, j]

    def getdata(self, t, i, j):
        return self.data[t, i, j]


class LazyTransitionProbabilities(DictTransitionProbabilities):

    def __init__(self, osmcache, obs, states, beta=10.0, grace_distance=0, maxvel=250):
        super().__init__()
        self.cache = osmcache
        self.obs = obs
        self.states = states
        self.maxvel = maxvel
        self.beta = beta
        self.grace_distance = grace_distance

    def calcprobs(self, t, i): # will be called for t[i] for all j, only single call to geodist
        keys, probs, data = _batch_transitions(self.cache, self.states, self.obs, t, i, maxvel=self.maxvel, beta=self.beta,
                                         grace_distance=self.grace_distance)
        for key in keys:
            self[key] = probs[key], data[key]

    def getprob(self, t, i, j):
        key = (t, i, j)
        if key in self.probs:
            return self.probs[key]
        else:
            # could also calculate single prob here, but this slightly less lazy behaviour is probably more efficient
            self.calcprobs(t, i)
            return self.probs[key]