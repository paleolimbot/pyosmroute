
from osgeo import ogr
from osgeo import osr

from ..dbinterface import GenericDB, asdataframe


_ll = osr.SpatialReference()
_ll.ImportFromEPSG(4326)

_smerc = osr.SpatialReference()
_smerc.ImportFromEPSG(900913)

_project_t = osr.CoordinateTransformation(_ll, _smerc)
_unproject_t = osr.CoordinateTransformation(_smerc, _ll)


def _project(ptin):
    pt = ogr.CreateGeometryFromWkt("POINT (%s %s)" % ptin)
    pt.Transform(_project_t)
    return pt.GetX(), pt.GetY()


def _unproject(ptin):
    pt = ogr.CreateGeometryFromWkt("POINT (%s %s)" % ptin)
    pt.Transform(_unproject_t)
    return pt.GetX(), pt.GetY()


class PlanetDB(GenericDB):
    """
    Database object containing OSM data as created by osm2pgsql. See README for specific
    details on creating this database.
    """

    def __init__(self, host, username, password, dbname):
        super(PlanetDB, self).__init__(host, username, password, dbname)

    def nodes(self, *nodeids):
        """
        Get node information according to node ids. Order is not considered between
        the arguments, and nodes that are not found do not throw a warning (will just not
        be contained in output)
        :param nodeids: A list of node ids.
        :return: A DataFrame with columns id, lon, lat, and tags.
        """
        arg = " OR ".join("id=%s" % id for id in nodeids)
        if not arg:
            arg = "FALSE"
        with self.cursor() as cur:
            cur.execute("""SELECT id, lat/1e2 as lat, lon/1e2 as lon, tags
                    FROM planet_osm_nodes WHERE %s""" % arg)
            out = asdataframe(cur)
            if len(out) > 0:
                # convert points to lat/lon
                newpoints = [_unproject((out["lon"][i], out["lat"][i])) for i in range(len(out))]
                newpoints = list(zip(*newpoints))
                out["lon"] = newpoints[0]
                out["lat"] = newpoints[1]
            return out

    def node_way(self, *nodeids):
        """
        Select a way that contains all of the node ids listed.

        :param nodeids: The node ids
        :return: A DataFrame of the output.
        """
        arg = ", ".join(str(nodeid) for nodeid in nodeids)
        with self.cursor() as cur:
            cur.execute("""SELECT * FROM planet_osm_ways where nodes @> ARRAY[%s]::bigint[]""" % arg)
            return asdataframe(cur)

    def ways(self, *wayids):
        """
        Get way information according to wayids. Order is not considered between
        the arguments, and ways that are not found do not throw a warning (will just not
        be contained in output)
        :param wayids: A list of way ids.
        :return: A DataFrame with columns id (int), nodes (list), and tags (dict).
        """
        arg = " OR ".join("id=%s" % id for id in wayids) if wayids else "FALSE"
        with self.cursor() as cur:
            cur.execute("""SELECT * from planet_osm_ways WHERE %s""" % arg)
            return asdataframe(cur)

    def nearest_ways(self, lon, lat, radius=15):
        """
        Get a list of the wayids closest to this lon/lat, ordered closest first.

        :param lon: The longitude
        :param lat: The latitude
        :param radius: The radius to consider
        :return: A list of wayids
        """

        pt = "%s, %s" % _project((lon, lat))

        with self.cursor() as cur:
            cur.execute(
                """SELECT osm_id, ST_Distance(way, ST_SetSRID(ST_MakePoint(%s), 900913)) as distance
                FROM planet_osm_line WHERE
                ST_DWithin(way, ST_SetSRID(ST_MakePoint(%s),900913), %s) AND
                highway IS NOT NULL
                AND (highway != 'cycleway'
                AND highway != 'footway'
                AND highway != 'bridleway'
                AND highway != 'steps'
                AND highway != 'path')
                ORDER BY ST_Distance(way, ST_SetSRID(ST_MakePoint(%s), 900913))""" %
                (pt, pt, radius, pt))
            tup = cur.fetchall()
            if tup:  # not using the 'distance' item yet since XTE is calculated later
                return tuple(zip(*tup))[0]
            else:
                return ()
