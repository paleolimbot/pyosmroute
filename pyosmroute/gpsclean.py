"""
Library for cleaning raw GPS data
"""

import datetime
import numpy as np

from .dataframe import DataFrame
from .geomeasure import geodist, bearing_to, bearing_difference
from .logger import log

def _parsetime(text):
    if text:
        return datetime.datetime.strptime(
                text.split(".")[0].split("+")[0].replace('"', "").replace("Z", "").replace("T", " "),
                "%Y-%m-%d %H:%M:%S")
    else:
        return None


def _distbyrow(row1, row2, lon_col="Longitude", lat_col="Latitude"):
    return geodist((row1[lon_col], row1[lat_col]), (row2[lon_col], row2[lat_col]))


def _velbyrow(row1, row2, datetime_col="_datetime", lon_col="Longitude", lat_col="Latitude"):
    dist = _distbyrow(row1, row2, lon_col=lon_col, lat_col=lat_col)
    difftime = (row2[datetime_col] - row1[datetime_col]).seconds
    return dist / difftime if difftime != 0 else float("nan")


def _bearingbyrow(row1, row2, lat_col="Latitude", lon_col="Longitude"):
    return bearing_to((row1[lon_col], row1[lat_col]), (row2[lon_col], row2[lat_col]))


def _rotationbyrow(row1, row2, bearing_col="_bearing", datetime_col="_datetime"):  # need rows as dicts here
    bearing = bearing_difference(row1[bearing_col], row2[bearing_col])
    difftime = (row2[datetime_col] - row1[datetime_col]).seconds
    # in degrees per second, positive means turning right, negative turning left
    return bearing / difftime if difftime != 0 else float("nan")


def datetimes(df, unparsed_col=0):
    """
    Return a list of parsed date/times given a DataFrame and column.

    :param df: A DataFrame
    :param unparsed_col: The column identifier to parse.
    :return: A list of parsed dates.
    """
    return [_parsetime(df.iloc[i][unparsed_col]) for i in range(len(df))]


def velocities(df, nwindow=2, datetime_col="_datetime", lon_col="Longitude", lat_col="Latitude"):
    """
    Return a list of velocities given the symmetric slope around a point as given by nwindow.

    :param df: A DataFrame
    :param nwindow: The number of points to consider (2 is valid, uses previous point and current point)
    :param datetime_col: The column containing the parsed datetimes.
    :param lon_col: The column containing longitude information.
    :param lat_col: The column containing latitude information.
    :return: A list of velocities in metres per second.
    """
    # nwindow: number of points to consider
    iminus = nwindow // 2
    iplus = nwindow - iminus - 1
    return [_velbyrow(df.iloc[max(0, i - iminus)], df.iloc[min(i + iplus, len(df) - 1)],
                      datetime_col=datetime_col, lon_col=lon_col, lat_col=lat_col)
            for i in range(len(df))]


def distances(df, lon_col="Longitude", lat_col="Latitude"):
    """
    Return a list of distances from the previous point to the current point.

    :param df: A DataFrame
    :param lon_col: The column containing longitude information.
    :param lat_col: The column containing latitude information.
    :return: A list of distances in metres.
    """
    return [float("nan"), ] + [_distbyrow(df.iloc[i - 1], df.iloc[i], lon_col=lon_col, lat_col=lat_col)
                               for i in range(1, len(df))]


def bearings(df, nwindow=2, datetime_col="_datetime", lon_col="Longitude", lat_col="Latitude"):
    """
    Return a list of bearings given the symmetric slope around a point as given by nwindow.

    :param df: A DataFrame
    :param nwindow: The number of points to consider (2 is valid, uses previous point and current point)
    :param lon_col: The column containing longitude information.
    :param lat_col: The column containing latitude information.
    :return: A list of bearings in degrees.
    """
    iminus = nwindow // 2
    iplus = nwindow - iminus - 1
    return [_bearingbyrow(df.iloc[max(0, i - iminus)], df.iloc[min(i + iplus, len(df) - 1)],
                          lon_col=lon_col, lat_col=lat_col)
            for i in range(len(df))]


def rotations(df, nwindow=2):
    """
    Return a list of rotation values based on nwindow.

    :param df: A DataFrame
    :param nwindow: The number of points to consider (2 is valid, uses previous point and current point)
    :return: A list of rotations in degrees/second.
    """
    iminus = (nwindow) // 2
    iplus = nwindow - iminus - 1
    return [_rotationbyrow(df.iloc[max(0, i - iminus)], df.iloc[min(i + iplus, len(df) - 1)])
            for i in range(len(df))]


def cleanpoints(indf, max_velocity=100, min_velocity=0, min_distance=None, recursion_limit=100, lat_column="Latitude",
                lon_column="Longitude"):
    """
    Clean points according to min velocity, max velocity and/or distance.

    :param indf: A Dataframe containing unparsed date/times and lat/lon pairs.
    :param max_velocity: Points that require a velocity greater than this will be discarded (in m/s)
    :param min_velocity: Points that that require a velocity slower than this will be discarded (in m/s)
    :param min_distance: Points that are with in this distance of the preious point will be discarded (in metres)
    :param recursion_limit: Cleaned recursively so that places with multiple points in a bad location are covered.
    :param lat_column: The column identifier for latitude in the indf.
    :param lon_column: The column identifier for longitude in the indf.
    :return: A DataFrame of cleaned points, which may or may not be a copy of the original DataFrame.
    """
    # if less than 3 rows, return
    if len(indf) < 3:
        return indf

    # calculate velocities
    if "_datetime" not in indf:
        indf["_datetime"] = datetimes(indf)
    indf["_velocity"] = velocities(indf, nwindow=2, lat_col=lat_column, lon_col=lon_column)
    # test threshold and 0.0 velocity (same point repeated)
    highpoints = list(np.where(indf._velocity[1:] > max_velocity)[0] + 1) if max_velocity is not None else []
    lowpoints = list(np.where(indf._velocity[1:] <= min_velocity)[0] + 1) if min_velocity is not None else []
    badpoints = list(set(highpoints + lowpoints))

    # check first point
    if 1 in badpoints:
        # check velocity from 1 to 2
        vel = _velbyrow(indf.iloc[1], indf.iloc[2], lat_col=lat_column, lon_col=lon_column)
        if vel < max_velocity:
            # 1 was added because 0 was the bad point
            badpoints.remove(1)
            badpoints.append(0)

    # find points that violate the min_distance
    lowdistpoints = []
    if min_distance:
        pt = (indf[lon_column][0], indf[lat_column][0])
        for i in range(1, len(indf)):
            if i in badpoints:
                continue
            newpt = (indf[lon_column][i], indf[lat_column][i])
            if geodist(pt, newpt) <= min_distance:
                lowdistpoints.append(i)
            else:
                pt = newpt
        badpoints = badpoints + lowdistpoints

    # if no bad points, return indf
    if badpoints:
        log("Removing %s fast, %s slow, %s low dist points (%0.1f percent; recursion level %s)" %
            (len(highpoints), len(lowpoints), len(lowdistpoints), len(badpoints) * 100 / len(indf),
             recursion_limit))
        goodpoints = sorted(set(range(len(indf))).difference(set(badpoints)))
        newdf = indf.iloc[goodpoints, :]

        if recursion_limit > 0:
            # perpetuating cleaning of slow points is probably not a good idea
            return cleanpoints(newdf, min_velocity=min_velocity / 1.5 if min_velocity is not None else None,
                               max_velocity=max_velocity,
                               min_distance=None,
                               recursion_limit=recursion_limit - 1, lat_column=lat_column, lon_column=lon_column)
        else:
            return newdf
    else:
        return indf
