
from lib.dataframe import DataFrame
import datetime
import scipy.signal as signal
import numpy as np
from lib.logger import log

# dummy, currently does nothing except add datetime

def _parsetime(text):
    if text:
        return datetime.datetime.strptime(text.split(".")[0].split("+")[0].replace('"',"").replace("Z","").replace("T"," "),
                                   "%Y-%m-%d %H:%M:%S")
    else:
        return None


def adddatetime(df, force=False):
    if not "datetime" in df.colnames() or force:
        df["datetime"] = [_parsetime(row[0]) for row in df.rows()]


def detrend_acceleration(accdf, kernel_size=25):
    cleandf = DataFrame(colnames=tuple(accdf.colnames())+("acc_tot", "g_x", "g_y", "g_z"))
    g_x = signal.medfilt(accdf[1], kernel_size)
    g_y = signal.medfilt(accdf[2], kernel_size)
    g_z = signal.medfilt(accdf[3], kernel_size)
    # should probably make sure that g_x g_y and g_z have a length of 1 at every point?
    scale = np.median(np.sqrt(g_x**2 + g_y**2 + g_z**2)) # length of the gravity vector should be 1 or 9.8
    if scale == 0:
        scale = 1
    scale = 1 / scale
    log("Scaling acceleration data by 1/%0.2f" % (1.0/scale,))
    g_x = g_x * scale
    g_y = g_y * scale
    g_z = g_z * scale
    acc_x = accdf[1] * scale - g_x
    acc_y = accdf[2] * scale - g_y
    acc_z = accdf[3] * scale - g_z
    acc_tot = np.sqrt(acc_x**2 + acc_y**2 + acc_z**2)
    cleandf.append(accdf[0], acc_x, acc_y, acc_z, acc_tot, g_x, g_y, g_z)
    adddatetime(cleandf)
    return cleandf


def cleanacceleration(accelerationdf, **kwargs):
    return detrend_acceleration(accelerationdf)


def writecleaned(df, file, include_extra=True):
    with open(file, "w") as f:
        f.write("RawAcceleration_cleaned\n")
        df.write(f, driver="csv")


def readcleaned(file):
    df = DataFrame.read(file, skiprows=1)
    adddatetime(df, force=True)
    return df