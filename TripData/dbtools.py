
import sys
import os
from lib.logger import log
import lib.dbinterface as dbinterface


def test(db):
    with db.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        result = cur.fetchall()
        if result:
            result = [item[0] for item in result]
            log(" %s Tables found in schema 'public'." % len(result))
            err = False
            if not "planet_osm_ways" in result:
                log("Missing table planet_osm_ways")
                err = True
            if not "planet_osm_nodes" in result:
                log("Missing table planet_osm_nodes")
                err = True
            if not err:
                log("Required tables found: current_ways, current_nodes, current_way_nodes, current_way_tags")
        else:
            log("No tables found in schema 'public'. Use subcommand 'create'.")


def createschema(db, sqlschemafile="../../data-osm/db_structure.sql"):
    with db.cursor() as cur:
        f = open(sqlschemafile, "r")
        cur.execute(f.read())
        cur.commit()
        f.close()

def populatedb(host, username, dbname, password, pbffile="../../data-osm/CN.osm.pbf"):
    command = 'osmosis -v --read-pbf file="%s" --write-apidb database="%s" user="%s" ' \
              'password="%s" validateSchemaVersion=no' % (pbffile, dbname, username, password)
    os.system(command)

if __name__ == "__main__":
    args = sys.argv

    try:
        db = None
        from dbconfig import DB_HOST, DB_NAME, DB_PASSWORD, DB_USER
        subcommand = args[1]
        if subcommand == "test":
            db = dbinterface.GenericDB(DB_HOST, DB_USER, DB_PASSWORD, DB_NAME)
            db.connect()

            db.disconnect()
            log("Test succeeded")
        elif subcommand == "create":
            if len(args) > 2:
                sqlschemafile = args[2]
            else:
                #TODO may want to change this location or download from within this script
                sqlschemafile = "../../data-osm/db_structure.sql"
            if not os.path.exists(sqlschemafile):
                raise IOError("File not found: %s" % sqlschemafile)
            db = dbinterface.GenericDB(DB_HOST, DB_USER, DB_PASSWORD, DB_NAME)
            db.connect()
            createschema(db)
            db.disconnect()
        elif subcommand == "populate":
            if len(args) > 2:
                pbffile = args[2]
            else:
                #TODO may want to change this location or download from within this script
                pbffile = "../../data-osm/CN.osm.pbf"
            if not os.path.exists(pbffile):
                raise IOError("File not found: %s" % pbffile)
            populatedb(DB_USER, DB_USER, DB_NAME, DB_PASSWORD, pbffile)
        elif subcommand == "applydiff":
            #TODO will want to create function to apply diffs, will be much faster than re downloading database
            log("Subcommand applydiff is not yet implemented")
        else:
            log("Subcommand %s not recognized. Try 'test', 'create', 'populate [FILE]', 'applydiff [FILE]'" % subcommand)
    except ImportError as e:
        log("Error importing dbconfig.py, is it properly installed?", stacktrace=True)

    # cleanup
    if db is not None:
        if db.conn is not None:
            db.disconnect()
    log("Finished.")





