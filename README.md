
# PyOSMRoute

## Installation

The Python package `pyosmroute` depends on the Python modules: `numpy`, `gevent` and `psycopg2` (when using `pypy` the appropriate package is `psycopg2cffi`). All are available via `pip` except `numpy` for `pypy`, which requires [special instructions](http://pypy.org/download.html#installing-numpy). The interface to the `pyosmroute` package is the package itself, imported like any Python module, but for debugging it is usually easier to use the command line or R interfaces that are also provided.

### Setting up the OSM Database

The second input needed by `pyosmroute` methods is a Postgres database created by [osm2pgsql](http://wiki.openstreetmap.org/wiki/Osm2pgsql). The input for this is a .pbf or .osm file acquired from the various distributors of OSM data on the web. It is accessible by country [here](http://download.gisgraphy.com/openstreetmap/pbf/). If multiple countries are desired, it is necessary to use the [Osmosis](http://wiki.openstreetmap.org/wiki/Osmosis) tool to merge together bordering countries (or overlapping PBF files). This can be done using the following command:

```
osmosis --readpbf my_file.pbf --read-pbf my_other_file.pbf --merge --write-pbf combined.pbf
```

Adding the PBF file to the database uses the following command:

```
osm2pgsql -s -C 1600 -H localhost -d DB_name -U DB_user -W combined.pbf
```

For the purpose of base testing, a pbf of Kings County in Nova Scotia is included and can be loaded with the command:

```
osm2pgsql -s -C 1600 -H localhost -d DB_name -U DB_user -W example-data/osm_ns/kings_cty.pbf
```

The most important argument is the **-s** parameter, which leaves a copy of the raw nodes/ways in the database. This data is used by the routing and matching function extensively. The **-C** parameter just specifies an amount of memory to be used (in MB). The **-W** parameter prompts for a password, so it may be desirable to have no password on this database for the preparation phase. Note that the database is loaded in **EPSG:900913**. It is not more efficient to have this be in **EPSG:4326** since the PostGIS `ST_DWithin()` function runs much faster on geometries than geographies. At some point in the future it may be worth converting the `lat` and `lon` columns in the `planet_osm_nodes` table because these are not used by PostGIS.


## From the Command Line

It's possible to use the `matchcsv.py` file (in this folder) from the command line to match CSVs and write/aggreate output. This is mostly useful for running the script from R, which has more interctive capabilities for mapping. The usage for the command line interface looks like this:

```
dewey >> python matchcsv.py --help
usage: Run route matching on CSVs containing date/time, latitude, and longitude information.
       [-h] [-r] [-o OUTPUT] [--outcols [OUTCOLS [OUTCOLS ...]]]
       [--writepoints] [--writesegs] [--writelines] [--processes PROCESSES]
       [--chunksize CHUNKSIZE] [-v] [--matchargs MATCHARGS] [-n N]
       infile

positional arguments:
  infile                Directory containing or a single CSV file with GPS
                        Time (UTC), Latitude, and Longitude columns.

optional arguments:
  -h, --help            show this help message and exit
  -r, --recursive       Walk directory recursively
  -o OUTPUT, --output OUTPUT
                        Specify summary output file, use '.csv' or '.tsv'
                        extension.
  --outcols [OUTCOLS [OUTCOLS ...]]
                        Specify which summary columns to write.
  --writepoints         Write point matches to FILE_osmpoints.csv
  --writesegs           Write all segment matches to FILE_osmsegs.csv
  --writelines          Write all segment matches to FILE_osmlines.json
  --processes PROCESSES
                        Specify number of worker processes.
  --chunksize CHUNKSIZE
                        Specify the multiprocesing chunksize parameter.
  -v, --verbose         Verbose debug output.
  --matchargs MATCHARGS
                        Arguments to pass to the matching algorithm as a JSON
                        string.
  -n N                  Specifiy the number of times to repeat the matching
                        (useful for speed tests)

```

Note that for this to work, you'll have to have your `dbconfig.py` setup (see below). A useful command for speed testing (assuming you've loaded the included Kings County PBF) is:

```
python matchcsv.py --verbose -n=20 "example-data/test/2016-03-02 17_37_41_Car - Normal Drive_Android.csv" -o results.csv
pypy matchcsv.py --verbose -n=20 "example-data/test/2016-03-02 17_37_41_Car - Normal Drive_Android.csv" -o results.csv
python3 matchcsv.py --verbose -n=20 "example-data/test/2016-03-02 17_37_41_Car - Normal Drive_Android.csv" -o results.csv
```

## From R

The command line interface is best run straight from the `testmatch.R` or `testmatch.Rmd`, which are already setup to handle the output and display it complete with scalebar and basemap. This is the preferred method for debugging the script. There is an RStudio project already setup for the directory.


## From Python

The package is loaded in Python like any normal Python module:


```python
import pyosmroute as pyosm
```

### The DataFrame

At the heart of passing large amounts of data is the `DataFrame` class (here it would be accessed as `pyosm.DataFrame`). Usually this is accessed by the `read_csv()` function, which returns a `DataFrame`.


```python
gpsdata = pyosm.read_csv("example-data/test/2016-03-02 17_37_41_Car - Normal Drive_Android_start.csv", skiprows=1)
gpsdata.head()
```




<table><tr><td><strong>Time (UTC)</strong></td><td><strong>Latitude</strong></td><td><strong>Longitude</strong></td></tr>
<tr><td>2016-03-02 17:37:51</td><td>45.0917807</td><td>-64.36975685</td></tr>
<tr><td>2016-03-02 17:37:53</td><td>45.09165327</td><td>-64.36969589</td></tr>
<tr><td>2016-03-02 17:37:54</td><td>45.09168978</td><td>-64.36977029</td></tr>
<tr><td>2016-03-02 17:37:55</td><td>45.09167523</td><td>-64.36973768</td></tr>
<tr><td>2016-03-02 17:37:56</td><td>45.09165241</td><td>-64.36973143</td></tr>
<tr><td>2016-03-02 17:37:57</td><td>45.09169459</td><td>-64.36969024</td></tr></table>



The `DataFrame` class supports most of the methods that the `pandas.DataFrame` class contains, but is much more lightweight (running a `pyosmroute.DataFrame` is about twice as fast in this context as the `pandas` version). Some quick examples:


```python
"Latitude" in gpsdata
```




    True




```python
gpsdata.iloc[3]
```




    {'Latitude': 45.09167523,
     'Longitude': -64.36973768,
     'Time (UTC)': '2016-03-02 17:37:55'}




```python
gpsdata.iloc[3, :]
```




<table><tr><td><strong>Time (UTC)</strong></td><td><strong>Latitude</strong></td><td><strong>Longitude</strong></td></tr>
<tr><td>2016-03-02 17:37:55</td><td>45.09167523</td><td>-64.36973768</td></tr></table>




```python
len(gpsdata)
```




    176




```python
for colname in gpsdata:
    print(colname)
```

    Time (UTC)
    Latitude
    Longitude



```python
for row in gpsdata.itertuples():
    # do something with each row...
    pass

# set columns
gpsdata["newcol"] = [lat+5 for lat in gpsdata["Latitude"]]
gpsdata.head()
```




<table><tr><td><strong>Time (UTC)</strong></td><td><strong>Latitude</strong></td><td><strong>Longitude</strong></td><td><strong>newcol</strong></td></tr>
<tr><td>2016-03-02 17:37:51</td><td>45.0917807</td><td>-64.36975685</td><td>50.0917807</td></tr>
<tr><td>2016-03-02 17:37:53</td><td>45.09165327</td><td>-64.36969589</td><td>50.09165327</td></tr>
<tr><td>2016-03-02 17:37:54</td><td>45.09168978</td><td>-64.36977029</td><td>50.09168978</td></tr>
<tr><td>2016-03-02 17:37:55</td><td>45.09167523</td><td>-64.36973768</td><td>50.09167523</td></tr>
<tr><td>2016-03-02 17:37:56</td><td>45.09165241</td><td>-64.36973143</td><td>50.09165241</td></tr>
<tr><td>2016-03-02 17:37:57</td><td>45.09169459</td><td>-64.36969024</td><td>50.09169459</td></tr></table>




```python
# delete columns
del gpsdata["newcol"]
```

The `DataFrame` object does quite a bit, but at heart it's just a collection of related information. This implementation is not really designed to be used in an analysis environment but is lightweight and is more or less interface compatible with the `pandas` version such that `pandas` objects can be used as input without breaking the code.

### Loading the OSM Database

This database is accessed via the `PlanetDB` class, usually instantiated by `get_planet_db()`. It is possible to specify login credentials within `get_planet_db()`, however it is more efficient to specify them in the `dbconfig.py` file in the `pyosmroute` folder. Contained in the folder is a `dbconfig.example.py` that specifies the format:

```Python
DB_USER = "osm"
DB_PASSWORD = "osm"
DB_HOST = "localhost"
DB_NAME = "osm"
```

Obviously, you'll want to change this to fit the configuration of the target machine. You can then get a database object like this:


```python
planetdb = pyosm.get_planet_db()
planetdb.connect()
planetdb.is_connected()
```




    True



Don't forget to `planetdb.disconnect()` when you're finished. Connecting to and disconnecting from the database takes enough time that it's worth maintaining a single connection per process.

### Road Matching Methods

There are two primary road-matching methods in the `pyosmroute` package: `on_road()` and `osmmatch()`. The `on_road()` function takes a `PlanetDB` and a `DataFrame` with the GPS information and returns a boolean for each point indicating if it is within `radius` of the nearest road.


```python
pyosm.on_road(planetdb, gpsdata, radius=20)
```




    array([False,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True, False, False, False, False,
           False,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True], dtype=bool)



If your `DataFrame` contains non-standard column names (i.e. not `Latitude` and `Longitude`), you can pass these in as parameters as well:


```python
pyosm.on_road(planetdb, gpsdata, latitude_column=1, longitude_column=2)
```




    array([False,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True, False, False, False, False, False,
           False, False,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True,  True,  True,  True,  True,
            True,  True,  True,  True,  True], dtype=bool)



It's also possible to specify a radius (the default is 15 metres):


```python
matches = [pyosm.on_road(planetdb, gpsdata, radius=radius) for radius in (5, 10, 15, 20)]
[match.sum() / len(match) for match in matches]
```




    [0.67613636363636365, 0.8125, 0.95454545454545459, 0.96590909090909094]



It may be worth cleaning points by distance to get this paramter, which can be done using the `cleanpoints()` function.


```python
cleandf = pyosm.cleanpoints(gpsdata, min_distance=30)
matches = [pyosm.on_road(planetdb, cleandf, radius=radius) for radius in (5, 10, 15, 20)]
[match.sum() / len(match) for match in matches]
```




    [0.58620689655172409,
     0.7931034482758621,
     0.96551724137931039,
     0.96551724137931039]



The `cleanpoints()` function also takes some other parameters involving max and min velocities and lat/lon columns like `on_road_percent()`. This function is used internally in the `osmmatch()` function; is it not necessary to clean data before putting it into the function.

### Notes on Logging

The `pyosmroute` module uses Python's `logging` module to do its logging, but won't do any logging unless you explicitly tell it to do so. Now we can see a little more of what the `cleanpoints()` function is actually doing. This is logged to `sys.stderr` by default, but you can pass in any keyword arguments to be passed to `logging.basicConfig()`.


```python
pyosm.config_logger()
cleandf = pyosm.cleanpoints(gpsdata, min_distance=30)
```

### Map Matching

Map matching is accessed via the `osmmatch()` method. Its basic usage and ouput are straightforward (except `xte`, which stands for cross track error, or distance from the route).


```python
stats, points, segs = pyosm.osmmatch(planetdb, gpsdata)
stats
```

    /Users/dewey/d/zensurio/pyosmroute/pyosmroute/osm/_hiddenmarkovmodel.py:86: VisibleDeprecationWarning: using a non-integer number instead of an integer will result in an error in the future
      path.append((int(minind[0]), probs[minind]))





    {'cleaned_points': 29,
     'gps_distance': 959.58746357071789,
     'in_points': 176,
     'matched_points': 29,
     'matched_proportion': 1.0,
     'mean_xte': 3.8960529214450101,
     'result': 'ok',
     'segment_distance': 1017.1652743409202,
     'started': '2016-04-21 20:00:25 +0000',
     't_cache': 0.03412508964538574,
     't_cleaned': 0.012423038482666016,
     't_eprobs': 0.013159990310668945,
     't_fetchways': 0.02208089828491211,
     't_hmm': 0.02213597297668457,
     't_summary': 0.01111292839050293,
     't_total': 0.1100001335144043,
     't_velocity_direction': 0.006075143814086914,
     'trip_duration_min': 3.0}



The `points` and `segs` output are both `DataFrame`s. The `points` output describes the specific segment matched to each GPS point that was used to perform matching. Columns are described here:

**alongtrack**: How far from **node1** towards **node2** the nearest point on the segment is.

**bearing**: The bearing of the segment (from **node1** to **node2).

**dist_from_route**: How far the point on the route is from the actual GPS point.

**distance**: The distance from **node1** to **node2**.

**name**: The value of the *name* tag. Useful for debugging.

**node1**, **node2**: The OSM ID number for the node at the start and end, respectively (refers to which point was encountered first and second with regard to the trip, not with regard to the underlying OSM data for the `segs` output).

**oneway**: `True` if the route can only be traced from **node1** to **node2**.

**segment**: Which segment in the **wayid**.

**typetag**: The value of the *highway* tag for **wayid** (e.g. `motorway`, `trunk`, etc.)

**xte**: The cross-track error of the GPS point with regard to **node1** and **node2**. Mostly the same as **dist_from_route**.

**p1, p2**: The locations of **node1** and **node2** (refers to which point was encountered first and second with regard to the trip, not with regard to the underlying OSM data for the `segs` output).

**pt_onseg**: The location of the GPS point if it were on the segment.

**gps...**: All the columns passed into the original `DataFrame`. Guaranteed are **gps_Latitude**, **gps_Longitude**, **gps__datetime** (as a Python `datetime` object), **gps__bearing**, **gps__distance**, and **gps__original_index**, which refers to the row index of the GPS point with regard to the original `DataFrame`.

**waytag...**: Values of the **wayid** tags.


```python
points.head()
```




<table><tr><td><strong>alongtrack</strong></td><td><strong>bearing</strong></td><td><strong>dist_from_route</strong></td><td><strong>distance</strong></td><td><strong>name</strong></td><td><strong>node1</strong></td><td><strong>node2</strong></td><td><strong>oneway</strong></td><td><strong>segment</strong></td><td><strong>typetag</strong></td><td><strong>wayid</strong></td><td><strong>weight</strong></td><td><strong>xte</strong></td><td><strong>p1_lon</strong></td><td><strong>p1_lat</strong></td><td><strong>p2_lon</strong></td><td><strong>p2_lat</strong></td><td><strong>pt_onseg_lon</strong></td><td><strong>pt_onseg_lat</strong></td><td><strong>gps_Latitude</strong></td><td><strong>gps_Longitude</strong></td><td><strong>gps_Time (UTC)</strong></td><td><strong>gps__bearing</strong></td><td><strong>gps__datetime</strong></td><td><strong>gps__distance</strong></td><td><strong>gps__original_index</strong></td><td><strong>gps__rotation</strong></td><td><strong>gps__velocity</strong></td><td><strong>waytag_highway</strong></td><td><strong>waytag_lanes</strong></td><td><strong>waytag_name</strong></td><td><strong>waytag_source</strong></td><td><strong>waytag_surface</strong></td></tr>
<tr><td>2.23854439378</td><td>74.6450683853</td><td>15.890550937</td><td>3.19573724588</td><td>None</td><td>3624069719</td><td>3624069724</td><td>False</td><td>20</td><td>unclassified</td><td>357012198</td><td>1</td><td>15.8905507523</td><td>-64.3697307537</td><td>45.091637562</td><td>-64.3696914973</td><td>45.0916451723</td><td>-64.3697032554</td><td>45.0916428929</td><td>45.0917807</td><td>-64.36975685</td><td>2016-03-02 17:37:51</td><td>66.6926429519</td><td>2016-03-02 17:37:51</td><td>nan</td><td>0</td><td>1.92087908237</td><td>1.26275096175</td><td>unclassified</td><td>2</td><td></td><td>NRCan-CanVec-10.0</td><td>paved</td></tr>
<tr><td>0.723006684459</td><td>348.718992602</td><td>6.6738156106</td><td>2.73967742202</td><td>None</td><td>3624069825</td><td>3624069834</td><td>False</td><td>40</td><td>unclassified</td><td>357012198</td><td>1</td><td>6.67381558472</td><td>-64.3693023471</td><td>45.091898403</td><td>-64.3693091743</td><td>45.0919225655</td><td>-64.3693041488</td><td>45.0919047795</td><td>45.09189303</td><td>-64.36938752</td><td>2016-03-02 17:38:16</td><td>114.714620011</td><td>2016-03-02 17:38:16</td><td>31.5687740437</td><td>21</td><td>2.65564234267</td><td>1.25486265933</td><td>unclassified</td><td>2</td><td></td><td>NRCan-CanVec-10.0</td><td>paved</td></tr>
<tr><td>31.0891424822</td><td>341.476092117</td><td>1.59826207522</td><td>38.7551944285</td><td>None</td><td>2542694962</td><td>3624069741</td><td>False</td><td>5</td><td>service</td><td>247371551</td><td>1</td><td>1.59827339614</td><td>-64.3690744445</td><td>45.0913455811</td><td>-64.3692312904</td><td>45.0916760572</td><td>-64.3692002652</td><td>45.0916106867</td><td>45.09160612</td><td>-64.36921957</td><td>2016-03-02 17:38:28</td><td>164.951409631</td><td>2016-03-02 17:38:28</td><td>34.5198996316</td><td>33</td><td>3.20753363665</td><td>3.45601032391</td><td>service</td><td></td><td></td><td></td><td></td></tr>
<tr><td>-0.0</td><td>341.476092117</td><td>7.94447404062</td><td>38.7551944285</td><td>None</td><td>2542694962</td><td>3624069741</td><td>False</td><td>5</td><td>service</td><td>247371551</td><td>1</td><td>7.94445882345</td><td>-64.3690744445</td><td>45.0913455811</td><td>-64.3692312904</td><td>45.0916760572</td><td>-64.3690744445</td><td>45.0913455811</td><td>45.09132275</td><td>-64.36917034</td><td>2016-03-02 17:38:35</td><td>175.657759108</td><td>2016-03-02 17:38:35</td><td>31.7454619601</td><td>40</td><td>0.158127083996</td><td>5.32494236069</td><td>service</td><td></td><td></td><td></td><td></td></tr>
<tr><td>19.6727191847</td><td>356.365949549</td><td>2.0184189008</td><td>23.141645667</td><td>None</td><td>2542694952</td><td>2542694954</td><td>False</td><td>2</td><td>service</td><td>247371551</td><td>1</td><td>2.0184195809</td><td>-64.3691163959</td><td>45.0908576956</td><td>-64.3691350808</td><td>45.0910653947</td><td>-64.3691322799</td><td>45.0910342606</td><td>45.09103311</td><td>-64.36915794</td><td>2016-03-02 17:38:40</td><td>166.848934639</td><td>2016-03-02 17:38:40</td><td>32.2212499875</td><td>45</td><td>-1.28637246974</td><td>1.65780809845</td><td>service</td><td></td><td></td><td></td><td></td></tr>
<tr><td>14.8047532051</td><td>340.698757122</td><td>5.99144896345</td><td>30.5303607328</td><td>None</td><td>2542694950</td><td>2542694952</td><td>False</td><td>1</td><td>service</td><td>247371551</td><td>1</td><td>5.99143750712</td><td>-64.3689878469</td><td>45.0905985622</td><td>-64.3691163959</td><td>45.0908576956</td><td>-64.3690501828</td><td>45.090724221</td><td>45.09074203</td><td>-64.36897815</td><td>2016-03-02 17:39:15</td><td>124.202860318</td><td>2016-03-02 17:39:15</td><td>35.3100868925</td><td>79</td><td>-2.06725787148</td><td>1.38043172741</td><td>service</td><td></td><td></td><td></td><td></td></tr></table>



The `segs` output is similar, but contains a complete list of the segments that make up the route. Only several columns are new here.

**direction**: Either 1, -1, or 0. 1 if the way was traced in the order in which it was defined (by OSM), -1 if the route was traced backwards, or 0 if neither. Note that **node1** and **node2** have already been rearranged according to this information.

**nodetag...**: Similar to waytag, but refers to the tags of **node2**. Signals, if in the OSM database, would be referred to here.

**points_indicies**: Which rows from the `points` output are contained within the segment.

**pt_onseg**: This output is mostly for internal use in the `make_linestring()` function, but contains a lat/lon pair that lies on the segment.


```python
segs.head()
```




<table><tr><td><strong>wayid</strong></td><td><strong>segment</strong></td><td><strong>node1</strong></td><td><strong>node2</strong></td><td><strong>typetag</strong></td><td><strong>name</strong></td><td><strong>distance</strong></td><td><strong>bearing</strong></td><td><strong>points_indicies</strong></td><td><strong>direction</strong></td><td><strong>p1_lon</strong></td><td><strong>p1_lat</strong></td><td><strong>p2_lon</strong></td><td><strong>p2_lat</strong></td><td><strong>pt_onseg_lon</strong></td><td><strong>pt_onseg_lat</strong></td><td><strong>waytag_highway</strong></td><td><strong>waytag_lanes</strong></td><td><strong>waytag_name</strong></td><td><strong>waytag_source</strong></td><td><strong>waytag_surface</strong></td></tr>
<tr><td>357012198</td><td>20</td><td>3624069719</td><td>3624069724</td><td>unclassified</td><td>None</td><td>3.19573724588</td><td>74.6450683853</td><td>[0]</td><td>1</td><td>-64.3697307537</td><td>45.091637562</td><td>-64.3696914973</td><td>45.0916451723</td><td>-64.3697032554</td><td>45.0916428929</td><td>unclassified</td><td>2</td><td></td><td>NRCan-CanVec-10.0</td><td>paved</td></tr>
<tr><td>357012198</td><td>21</td><td>3624069724</td><td>3624069728</td><td>unclassified</td><td>None</td><td>3.17269358001</td><td>76.2417253711</td><td>[]</td><td>1</td><td>-64.3696914973</td><td>45.0916451723</td><td>-64.3696522409</td><td>45.0916519581</td><td>nan</td><td>nan</td><td>unclassified</td><td>2</td><td></td><td>NRCan-CanVec-10.0</td><td>paved</td></tr>
<tr><td>357012198</td><td>22</td><td>3624069728</td><td>3624069731</td><td>unclassified</td><td>None</td><td>3.19949996964</td><td>74.4015177491</td><td>[]</td><td>1</td><td>-64.3696522409</td><td>45.0916519581</td><td>-64.3696129845</td><td>45.0916596952</td><td>nan</td><td>nan</td><td>unclassified</td><td>2</td><td></td><td>NRCan-CanVec-10.0</td><td>paved</td></tr>
<tr><td>357012198</td><td>23</td><td>3624069731</td><td>3624069735</td><td>unclassified</td><td>None</td><td>3.18893641931</td><td>74.6115182813</td><td>[]</td><td>1</td><td>-64.3696129845</td><td>45.0916596952</td><td>-64.369573818</td><td>45.0916673055</td><td>nan</td><td>nan</td><td>unclassified</td><td>2</td><td></td><td>NRCan-CanVec-10.0</td><td>paved</td></tr>
<tr><td>357012198</td><td>24</td><td>3624069735</td><td>3624069740</td><td>unclassified</td><td>None</td><td>3.1908145295</td><td>74.4894314829</td><td>[]</td><td>1</td><td>-64.369573818</td><td>45.0916673055</td><td>-64.3695346515</td><td>45.0916749791</td><td>nan</td><td>nan</td><td>unclassified</td><td>2</td><td></td><td>NRCan-CanVec-10.0</td><td>paved</td></tr>
<tr><td>357012198</td><td>25</td><td>3624069740</td><td>3624069743</td><td>unclassified</td><td>None</td><td>3.32184257533</td><td>73.2191898948</td><td>[]</td><td>1</td><td>-64.3695346515</td><td>45.0916749791</td><td>-64.3694941374</td><td>45.0916836041</td><td>nan</td><td>nan</td><td>unclassified</td><td>2</td><td></td><td>NRCan-CanVec-10.0</td><td>paved</td></tr></table>



It may be that only a line string of the output is required, and this output can be obtained using the `make_linestring()` function, taking the `segs` output as its only argument. Note that the output produced is a *list* of objects. This is because there are breaks in the model that are best represented as breaks on the map (cleaner).


```python
pyosm.make_linestring(segs.iloc[1:6, :])
```




    [{'lat': [45.091651958104322,
       45.091659695196469,
       45.091667305450038,
       45.091674979121336],
      'lon': [-64.369652240926158,
       -64.369612984548226,
       -64.36957381800184,
       -64.369534651455467]}]



This can be used in conjunction with a javascript maps API such as [Google Maps](https://developers.google.com/maps/documentation/javascript/) or [Mapbox](https://www.mapbox.com/mapbox.js/api/v2.3.0/). The output of `make_linestring()` is a `dict`, so it can be used with the `json` module to output a javascript-friendly representation (`json.dump(obj, file)`). The following is [how to create a polyline in the Google Maps API](https://developers.google.com/maps/documentation/javascript/examples/polyline-simple).

```javascript
function initMap() {
  var map = new google.maps.Map(document.getElementById('map'), {
    zoom: 3,
    center: {lat: 0, lng: -180},
    mapTypeId: google.maps.MapTypeId.TERRAIN
  });

  var flightPlanCoordinates = [
    {lat: 37.772, lng: -122.214},
    {lat: 21.291, lng: -157.821},
    {lat: -18.142, lng: 178.431},
    {lat: -27.467, lng: 153.027}
  ];
  var flightPath = new google.maps.Polyline({
    path: flightPlanCoordinates,
    geodesic: true,
    strokeColor: '#FF0000',
    strokeOpacity: 1.0,
    strokeWeight: 2
  });

  flightPath.setMap(map);
}
```

In the mapbox API, [the syntax is slightly different](https://www.mapbox.com/mapbox.js/example/v1.0.0/polyline/):

```javascript
L.mapbox.accessToken = '<your access token here>';
var map = L.mapbox.map('map', 'mapbox.streets')
    .setView([38.89399, -77.03659], 17);

// Create array of lat,lon points.
var line_points = [
    [38.893596444352134, -77.0381498336792],
    [38.89337933372204, -77.03792452812195],
    [38.89316222242831, -77.03761339187622],
    [38.893028615148424, -77.03731298446655],
    [38.892920059048464, -77.03691601753235],
    [38.892903358095296, -77.03637957572937],
    [38.89301191422077, -77.03592896461487],
    [38.89316222242831, -77.03549981117249],
    [38.89340438498248, -77.03514575958252],
    [38.893596444352134, -77.0349633693695]
];

// Define polyline options
// http://leafletjs.com/reference.html#polyline
var polyline_options = {
    color: '#000'
};

// Defining a polygon here instead of a polyline will connect the
// endpoints and fill the path.
// http://leafletjs.com/reference.html#polygon
var polyline = L.polyline(line_points, polyline_options).addTo(map);
```

### Road Matching Parameters

Match timestamped GPS points to roads in the OSM database. The matching is based a Hidden Markov Model with emission probabilities based on the distance to the road segment, and transition probabilities based on the difference between the GPS distance between two points and what the driving distance would be. This model is explained in Microsoft Research paper by Paul Newson and John Krumm entitled 'Hidden Markov Map Matching Through Noise and Sparseness'. This implementation of what is explained in the paper has two differences. First, emission probability has a component that is based on the difference between the direction of the segment and the direction based on the two surrounding GPS points. Second, solving the Hidden Markov Model implements a 'lookahead' parameter, such that a next step can be chosen based on looking several steps into the future (see the viterbi_lookahead parameter). Driving distances are based on the pyroutelib2 library (https://github.com/gaulinmp/pyroutelib2), although
considerable modifications had to be made to accommodate the needs of this function (mostly driving distances
between adjacent segments and connecting to the database instead of reading a downloaded XML). The `osmmatch()` function takes the following arguments:

```python
osmmatch(db, gpsdf, lat_column="Latitude", lon_column="Longitude", unparsed_datetime_col=0,
             searchradius=50, minpoints=10, maxvel=250, sigmaZ=10, beta=10.0, maxiter=1,
             minpointdistance=30, paramter_window=3, bearing_penalty_weight=1, viterbi_lookahead=1,
             lazy_probabilities=True, points_summary=True, segments_summary=True, db_threads=20):
```


**db**: a PlanetDB object, as generated by get_planet_db() or by instantiating the object yourself.

**gpsdf**: A DataFrame (either `pyosmroute.DataFrame` or `pandas.DataFrame`, although the former is about twice as fast) of GPS points with at least date/time, longitude, and latitude columns.

**lat_column**: A column reference to gpsdf specifying which column contains the latitude information.

**lon_column**: A column reference to gpsdf specifying which column contains the longitude information.

**unparsed_datetime_col**: A column reference to gpsdf specifying which column contains the datetime information. The format must be '2016-03-01 20:59:46' (extra letters are stripped).

**searchradius**: The radius around each GPS point to search for roads. The original paper uses a radius of 200 metres, around 50 seems to work well though.

**minpoints**: After cleaning the GPS data such that there are data points ever 'minpointdistance' metres, if fewer than this number of points remain, no matching is performed. For debugging it's good to keep this low, but realistically any trip with less than about 20 points isn't worth matching.

**maxvel**: The maximum assumed velocity (m/s). This value is used to terminate routing between two points once the route would require the driver to travel over this speed. GPS points are noisy enough that this must be about twice the maximum speed. Anything under 250 caused unnecessary gaps during testing.

**sigmaZ**: The standard deviation of GPS error (metres). A higher value places less emphasis on how close a point is to any given segment.

**beta**: The standard deviation of the difference between the GPS distance and the driving distance between two points on a segment. Increasing this allows for less efficient routes to be considered.

**maxiter**: Problematic points can be removed, but this requires that transition probabilities are calculated twice, which can be slow.

**minpointdistance**: Prior to performing analysis, GPS data are cleaned such that no two points are closer than this distance. The original paper suggests setting this value to sigmaZ * 2, so far sigmaZ * 3 has produced better results.

**paramter_window**: Velocities, rotations, and bearings are calculated according to this window. 3 is the default value.

**bearing_penalty_weight**: Use this to increase or decrease the effect of a bearing difference on the emission probability of a point. A number between 0 and 1 is preferred, although higher than 1 will not cause errors.

**viterbi_lookahead**: The length of the path to consider when making decisions about the best path through the Hidden Markov Model. 0 is fastest, 1 produces better results, and 2 appears to be quite slow.

**lazy_probabilities**: True if only transition probabilities that are used should be calculated. If lookahead is 0, this is significantly faster. If lookahead is 1 or greater, most transition probabilties are used, so this does not lead to a performance increase.

**points_summary**: True if the list of point/segment matches should be returned, False otherwise.

**segments_summary**: True if the complete list of segments should be returned, False otherwise.

**db_threads**: Number of threads to use to concurrently process database requests.


```python
planetdb.disconnect()
```




    True


