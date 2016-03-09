"""
Library for cleaning raw GPS data
"""

import datetime
from lib.dataframe import DataFrame
from lib.geomeasure import geodist, bearing_to, bearing_difference
from lib.logger import log
import numpy as np


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
    return [_parsetime(df.iloc[i, unparsed_col]) for i in range(len(df))]


def velocities(df, nwindow=2, datetime_col="_datetime", lon_col="Longitude", lat_col="Latitude"):
    # nwindow: number of points to consider
    iminus = nwindow // 2
    iplus = nwindow - iminus - 1
    return [_velbyrow(df.iloc[max(0, i - iminus)], df.iloc[min(i + iplus, len(df) - 1)],
                      datetime_col=datetime_col, lon_col=lon_col, lat_col=lat_col)
            for i in range(len(df))]


def distances(df, lon_col="Longitude", lat_col="Latitude"):
    return [float("nan"), ] + [_distbyrow(df.iloc[i - 1], df.iloc[i], lon_col=lon_col, lat_col=lat_col)
                               for i in range(1, len(df))]


def bearings(df, nwindow=2, datetime_col="_datetime", lon_col="Longitude", lat_col="Latitude"):
    iminus = nwindow // 2
    iplus = nwindow - iminus - 1
    return [_bearingbyrow(df.iloc[max(0, i - iminus)], df.iloc[min(i + iplus, len(df) - 1)],
                          lon_col=lon_col, lat_col=lat_col)
            for i in range(len(df))]


def rotations(df, force=True, nwindow=2):
    iminus = (nwindow) // 2
    iplus = nwindow - iminus - 1
    return [_rotationbyrow(df.iloc[max(0, i - iminus)], df.iloc[min(i + iplus, len(df) - 1)])
            for i in range(len(df))]


def cleanpoints(indf, max_velocity=100, min_velocity=0, min_distance=None, recursion_limit=100):
    # if less than 3 rows, return
    if len(indf) < 3:
        return indf

    # calculate velocities
    if "_datetime" not in indf:
        indf["_datetime"] = datetimes(indf)
    indf["_velocity"] = velocities(indf, nwindow=2)
    # test threshold and 0.0 velocity (same point repeated)
    highpoints = list(np.where(indf._velocity[1:] > max_velocity)[0] + 1) if max_velocity is not None else []
    lowpoints = list(np.where(indf._velocity[1:] <= min_velocity)[0] + 1) if min_velocity is not None else []
    badpoints = list(set(highpoints + lowpoints))

    # check first point
    if 1 in badpoints:
        # check velocity from 1 to 2
        vel = _velbyrow(indf.iloc[1], indf.iloc[2])
        if vel < max_velocity:
            # 1 was added because 0 was the bad point
            badpoints.remove(1)
            badpoints.append(0)

    # find points that violate the min_distance
    lowdistpoints = []
    if min_distance:
        pt = (indf.Longitude[0], indf.Latitude[0])
        for i in range(1, len(indf)):
            if i in badpoints:
                continue
            newpt = (indf.Longitude[i], indf.Latitude[i])
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
                               recursion_limit=recursion_limit - 1)
        else:
            return newdf
    else:
        return indf


def writecleaned(df, file, include_extra=True):
    if not include_extra:
        df = df.copy()
        if "_velocity" in df:
            del df["_velocity"]
        if "_datetime" in df:
            del df["_datetime"]
    with open(file, "w") as f:
        f.write("RawGPS_cleaned\n")
        df.write(f, driver="csv")


def readcleaned(file):
    df = DataFrame.read(file, skiprows=1)
    addvelocities(df, force=True)
    return df


if __name__ == "__main__":
    # test
    df = DataFrame.read("../../../example-data/badtrips/trip_sensor_086f1b28-a8f8-4663-aaec-050a4c40ec24/RawGPS.csv",
                        skiprows=1)
    print("Testing data frame with %s rows" % len(df))
    df = cleanpoints(df)
    print("got data frame with %s rows" % len(df))
    # write "fixed" RawGPS.csv
    writecleaned(df, "RawGPS.csv")
