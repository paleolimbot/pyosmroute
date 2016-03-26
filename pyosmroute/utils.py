import numpy as np
from .osm import mapmatch
from .osm.planetdb import PlanetDB


def get_planet_db(db_host=None, db_user=None, db_password=None, db_name=None):
    """
    Get the PlanetDB object according to parameters. If no db_host is passed,
    the function will try "from .dbconfig import DB_NAME, DB_PASSWORD, DB_USER, DB_HOST".

    :param db_host: The database host
    :param db_user: The database user
    :param db_password: The database password
    :param db_name: The database name
    :return: A PlanetDB object referring to the above.
    """
    if db_host is None:
        try:
            from .dbconfig import DB_NAME, DB_PASSWORD, DB_USER, DB_HOST
            return PlanetDB(DB_HOST, DB_USER, DB_PASSWORD, DB_NAME)
        except ImportError:
            raise ImportError("dbconfig.py not found and database login information not specified.")
    else:
        return PlanetDB(db_host, db_user, db_password, db_name)


def on_road(db, gpsdf, radius=15, latitude_column="Latitude", longitude_column="Longitude"):
    """
    Calculate a percentage of points within the given radius of an OSM road segment.

    :param db: A PlanetDB object
    :param gpsdf: A DataFrame with lat/lon information.
    :param radius: The radius within which to consider the point "on a road".
    :param latitude_column: The column identifier referring to the latitude column.
    :param longitude_column: The column identifier referring to the longitude column.
    :return: A float between 0 and 1.
    """
    res = np.array([mapmatch.nearest_road(db, radius,
                                          (gpsdf[longitude_column][i], gpsdf[latitude_column][i])) is not None
                    for i in range(len(gpsdf))])
    return res
