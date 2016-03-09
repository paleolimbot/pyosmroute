from lib.dbinterface import GenericDB, asdataframe
from lib.logger import log

class PlanetDB(GenericDB):
    """
    Database object to represent an OSM Planet file DB. Should contain methods to
    get_tags(node_id), get_attrs(node_id) and for way_id as well. Searching for
    nodes based on ways, ways based on nodes should also occur. Also,
    something like find_closest_nodes(lon, lat, n, maxdistance) should exist.

    Returns are a dataframe.DataFrame (set default by
    """

    def __init__(self, host, username, password, dbname):
        super(PlanetDB, self).__init__(host, username, password, dbname)

    def _transform(self, x, y, fromepsg, toepsg, parse=False):
        # SELECT ST_AsText(ST_Transform(ST_GeomFromText('POINT(8764554.20 3695679.11)', 3857), 4326))
        with self.cursor() as cur:
            cur.execute("""SELECT ST_AsText(ST_Transform(ST_GeomFromText('POINT(%s %s)', %s), %s))""" %
                        (x, y, fromepsg, toepsg))
            ptext = cur.fetchone()[0]
            if parse:
                try:
                    parts = ptext.replace("POINT(", "").replace(")", "").split()
                    return float(parts[0]), float(parts[1])
                except:
                    log("Error converting string to point: %s" % ptext)
                    return float("nan"), float("nan")
            else:
                return ptext

    def unproject(self, x, y, parse=True):
        return self._transform(x, y, 900913, 4326, parse=parse)

    def project(self, lon, lat, parse=True):
        return self._transform(lon, lat, 4326, 900913, parse=parse)

    def nodes(self, *nodeids):
        arg = " OR ".join("id=%s" % id for id in nodeids)
        with self.cursor() as cur:
            cur.execute("""SELECT id, CAST(lat/100.0 AS FLOAT) as lat, CAST(lon/100.0 AS FLOAT) as lon, tags
                    FROM planet_osm_nodes WHERE %s""" % arg)
            out = asdataframe(cur)
            if len(out) > 0:
                # convert points to lat/lon
                newpoints = [self.unproject(out["lon"][i], out["lat"][i]) for i in range(len(out))]
                newpoints = list(zip(*newpoints))
                out["lon"] = newpoints[0]
                out["lat"] = newpoints[1]
            return out

    def node_way(self, *nodeids):
        arg = ", ".join(str(nodeid) for nodeid in nodeids)
        with self.cursor() as cur:
            cur.execute("""SELECT * FROM planet_osm_ways where nodes @> ARRAY[%s]::bigint[]""" % arg)
            return asdataframe(cur)

    def ways(self, *wayids):
        arg = " OR ".join("id=%s" % id for id in wayids) if wayids else "FALSE"
        with self.cursor() as cur:
            cur.execute("""SELECT * from planet_osm_ways WHERE %s""" % arg)
            return asdataframe(cur)

    def nearest_ways(self, lon, lat, radius=15):
        pt = self.project(lon, lat, parse=False)
        with self.cursor() as cur:
            cur.execute(
                """SELECT osm_id, ST_Distance(way, ST_GeomFromText('%s', 900913)) as distance
                FROM planet_osm_line WHERE
                ST_DWithin(way, ST_GeomFromText('%s', 900913), %s) AND
                highway IS NOT NULL
                AND (highway != 'cycleway'
                AND highway != 'footway'
                AND highway != 'bridleway'
                AND highway != 'steps'
                AND highway != 'path')
                ORDER BY ST_Distance(way, ST_GeomFromText('%s', 900913))""" %
                (pt, pt, radius, pt))
            tup = cur.fetchall()
            if tup:  # not using the 'distance' item yet since XTE is calculated later
                return tuple(zip(*tup))[0]
            else:
                return ()


if __name__ == "__main__":
    # test
    from dbconfig import DB_NAME, DB_PASSWORD, DB_USER, DB_HOST
    osmdb = PlanetDB(DB_HOST, DB_USER, DB_PASSWORD, DB_NAME)
    osmdb.connect()
    try:
        print("Getting ways from node ids")
        print(osmdb.node_way(253333910))
        print(osmdb.node_way(253333910, 3304026514))
        print(osmdb.node_way(55))  # returns empty
        print(osmdb.node_way(55, 253333910))  # returns empty

        print("Getting nodes attributes by id")
        print(osmdb.nodes(253333910))
        print(osmdb.nodes(253333910, 3304026514))
        print(osmdb.nodes(55))  # returns empty
        print(osmdb.nodes(55, 253333910))  # returns one empty line

        print("Getting way attributes by id")
        print(osmdb.ways(4181592, 55))  # onerow
        print(osmdb.ways(55))  # empty

        a = osmdb.ways(4181592, 4182662)  # two rows
        print(a)
        print(a.colnames())

    except:
        log("error!", stacktrace=True)
    osmdb.disconnect()