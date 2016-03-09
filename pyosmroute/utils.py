
from .lib import dataframe
from .lib.osm import mapmatch
from .lib.osm.planetdb import PlanetDB
import numpy as np


def get_planet_db(db_host=None, db_user=None, db_password=None, db_name=None):
    if db_host is None:
        try:
            from .dbconfig import DB_NAME, DB_PASSWORD, DB_USER, DB_HOST
            return PlanetDB(DB_HOST, DB_USER, DB_PASSWORD, DB_NAME)
        except ImportError:
            raise ImportError("dbconfig.py not found and database login information not specified.")
    else:
        return PlanetDB(db_host, db_user, db_password, db_name)


def on_road_percent(db, gpsdf, radius=15, latitude_column="Latitude", longitude_column="Longitude"):
        res = np.array([mapmatch.nearest_road(db, (gpsdf.iloc[i, longitude_column], gpsdf.iloc[i, latitude_column]),
                                              radius=radius) is not None
                       for i in range(len(gpsdf))])
        return res.sum() / len(gpsdf)

def read_csv(reader, driver=None, headers=True, skiprows=0, numeric=True):
    return dataframe.DataFrame.read(reader, driver=driver, headers=headers, skiprows=skiprows, numeric=numeric)