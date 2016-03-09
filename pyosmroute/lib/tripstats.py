
import numpy as np
import lib.gpsclean as gpsclean
from lib.logger import log

allstats = {}


def tripstat(*paramnames):
    global allstats

    def real_decorator(function):
        allstats[tuple(paramnames)] = function

        def wrapper(*args, **kwargs):
            function(*args, **kwargs)
        return wrapper
    return real_decorator


def calcstats(trip, out=None):
    global allstats
    if out is None:
        out = {}
    for paramnames, fun in allstats.items():
        try:
            params = fun(trip)
        except Exception as e:
            log("Error getting parameters %s: %s" % (paramnames, e))
            continue
        if params is None:
            continue
        if len(paramnames) == 1:
            out[paramnames[0]] = params
            continue
        for name, param in zip(paramnames, params):
            out[name] = param
    return out


def statnames():
    return [item for sublist in allstats.keys() for item in sublist]


def load_default():

    @tripstat("gps_vel_mean", "gps_vel_median", "gps_vel_var", "low_point_rate",
              "avg_stop_dist", "sd_stop_dist", "num_stop_dist", "on_road_proportion")
    def _gpsparams(trip):
        if trip.gps is None:
            return None
        gps = gpsclean.cleanpoints(trip.gps, min_distance=10)
        gps["_distance"] = gpsclean.distances(gps)
        # total distance divided by total time
        difftime = (gps._datetime[-1] - gps._datetime[0]).seconds
        dist = np.nansum(gps["_distance"])
        vel_mean = dist / difftime
        vel_median = np.median(gps["_velocity"])
        vel_var = np.nanvar(gps["_velocity"])

        return vel_mean, vel_median, vel_var

    @tripstat("acc_mean", "acc_median", "acc_var")
    def _accparams(trip):
        accdata = trip.acceleration
        if accdata is None:
            return None
        acc = np.sqrt(accdata["X"]**2+accdata["Y"]**2+accdata["Z"]**2)
        acc_mean = np.mean(acc) - 1
        acc_median = np.median(acc) - 1
        acc_var = np.var(acc)
        return acc_mean, acc_median, acc_var


def load_planetdb(planetdb, on_road_radius=15):
    import lib.osm.mapmatch as mapmatch

    @tripstat("on_road_percentage")
    def on_road_percentage(trip, radius=on_road_radius):
        if trip.gps is None:
            return None
        gps = trip.gps
        res = np.array([mapmatch.nearest_road(planetdb, gps.Longitude[i], gps.Latitude[i], radius=radius) is not None
                       for i in range(len(gps))])
        return res.sum() / len(gps)