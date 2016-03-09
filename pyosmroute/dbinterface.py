

import psycopg2
import numpy as np
from .logger import log
from .dataframe import DataFrame


class DBException(Exception):
    pass

# functions for dealing with data out of the db


def pairwise(iterable):
    itnext = iter(iterable).__next__
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
    columns = [c[0] for c in cursor.description]
    hstoreind = np.where("tags"==np.array(columns))[0]
    data = bycol(cursor)
    df = DataFrame(*data, columns=columns)
    for i in hstoreind:
        df[i] = [hstore_to_dict(item) for item in df[i]]
    return df


class GenericDB(object):
    """
    A generic Postgre DB wrapper designed to abstract the particulars of dealing with
    databases to the rest of the application. This allows smooth transition to MySQL,
    SQLite, etc. should it be required. Good for retrieving small amounts of data,
    bad (slow) for storing lots of it.
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
        return self.conn is not None

    def connect(self):
        log("Connecting to %s" % repr(self))
        try:
            self.conn = psycopg2.connect(host=self.host, user=self.username, password=self.password,
                                         database=self.dbname)
            return True
        except:
            log("error connecting to Postgre database", stacktrace=True)
            return False

    def cursor(self):
        if self.conn:
            return self.conn.cursor()
        else:
            raise DBException("Attempted to create cursor from disconnected database")

    def disconnect(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            log("Disconnected from database: %s" % repr(self))
            return True
        else:
            log("Failed to disconnect from database: self.conn is None")
            raise DBException("Cannot disconnect from database that is not connected")

