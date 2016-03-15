
try:
    import psycopg2
except ImportError:
    import psycopg2cffi as psycopg2

import numpy as np
from .logger import log
from .dataframe import DataFrame


class DBException(Exception):
    pass


def _where(arg):
    # this exists because 1-arg np.where is not supported in pypy
    return np.array([i for i, item in enumerate(arg) if item])

# functions for dealing with data out of the db


def pairwise(iterable):
    try:
        itnext = iter(iterable).__next__
    except AttributeError:
        itnext = iter(iterable).next
    while True:
        yield itnext(), itnext()


def hstore_to_dict(seq):
    if seq is not None:
        return dict(pairwise(seq))
    else:
        return {}


def bycol(cursor):
    return zip(*cursor.fetchall())


def byrow(cursor):
    return cursor.fetchall()


def asdataframe(cursor):
    columns = [str(c[0]) for c in cursor.description]
    hstoreind = _where("tags" == np.array(columns))
    data = bycol(cursor)
    df = DataFrame(*data, columns=columns)
    for i in hstoreind:
        df[i] = [hstore_to_dict(item) for item in df[i]]
    return df


class GenericDB(object):
    """
    A generic Postgres DB wrapper, returning cursor results as a DataFrame.
    """

    def __init__(self, host, username, password, dbname):
        self.host = host
        self.username = username
        self.password = password
        self.dbname = dbname
        self.conn = None

    def __repr__(self):
        return "%s(%s, %s, %s, %s)" % (type(self).__name__, self.host, self.username, self.password, self.dbname)

    def __str__(self):
        return repr(self)

    def is_connected(self):
        """
        :return: True if this database has a self.conn attribute, False otherwise.
        """
        return self.conn is not None

    def connect(self):
        """
        Connect to this database if it is not currently connected.
        :return: True if the database is connected, False otherwise.
        """
        if self.conn:
            return True
        log("Connecting to %s" % repr(self))
        try:
            self.conn = psycopg2.connect(host=self.host, user=self.username, password=self.password,
                                         database=self.dbname)
            return True
        except:
            log("error connecting to Postgre database", stacktrace=True)
            return False

    def cursor(self):
        """
        Get a new cursor from self.conn

        :return: A psycopg2 Cursor object.
        """
        if self.conn:
            return self.conn.cursor()
        else:
            raise DBException("Attempted to create cursor from disconnected database")

    def disconnect(self):
        """
        Disconnect from this database.

        :return: True if database is disconnected, false otherwise.
        """
        if self.conn:
            self.conn.close()
            self.conn = None
            log("Disconnected from database: %s" % repr(self))
            return True
        else:
            log("Failed to disconnect from database: self.conn is None")
            return True
