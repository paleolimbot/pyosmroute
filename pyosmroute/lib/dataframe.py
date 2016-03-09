
import numpy as np
import csv
import decimal
from lib.logger import log


def _len(obj):
    if type(obj) in (list, tuple, np.ndarray, set):
        return len(obj)
    else:
        return 1


def _aslist(obj):
    if type(obj) in (list, tuple, np.ndarray, set):
        return obj
    else:
        return [obj, ]

def _asnumeric(obj):
    if type(obj) in (int, float, np.int, np.int64, np.int8, np.int16, np.int32, decimal.Decimal):
        return obj
    try:
        return int(obj)
    except ValueError:
        pass

    try:
        return float(obj)
    except ValueError:
        pass

    return obj


class _DFRow(dict):

    def __init__(self, columns, vals):
        super().__init__(zip(columns, vals))
        self._keys = tuple(columns)

    def __getitem__(self, item):
        if item in self:
            return super().__getitem__(item)
        else:
            try:
                return super().__getitem__(self._keys[item])
            except IndexError:
                raise KeyError("So such key in row")

    def __iter__(self):
        for key in self._keys:
            yield self[key]

    def keys(self):
        return self._keys

    def items(self):
        for key in self._keys:
            yield key, self[key]


class _Iloc(object):

    def __init__(self, df):
        self.df = df

    def __getitem__(self, item):
        if type(item) != tuple:
            return self.df._row(item)
        elif len(item) == 2 and type(item[0]) == int and type(item[1]) == int:
            return self.df[item[1]][item[0]]  # single value
        else:
            return self.df._subset(*item)

    def __setitem__(self, key, value):
        raise NotImplementedError("Setting is not available for this class (use pandas DataFrame instead)")


class DataFrame(object):
    """
    An object mostly designed to store database output in a way that is easy to process.
    Not designed to be easily modified, corner cases are definitely not tackled. The idea
    is basically to be able to select columns by name. Columns are Numpy to allow for
    vector processing.
    """
    def __init__(self, *args, **kwargs):
        self.__rows = None
        if "columns" in kwargs:
            _columns = list(kwargs["columns"])
            del kwargs["columns"]
            if len(args) == 0:
                # empty data frame
                args = [[] for i in range(len(_columns))]
            if len(_columns) != len(args):
                raise ValueError("Length of columns must be equal to list of names: %s, %s" % (_columns,
                                                                                                 len(args)))
        else:
            _columns = [self.__default_arg_name(i) for i in range(len(args))]

        self.__keynames = []
        for i in range(len(args)):
            self.__setitem__(_columns[i], args[i])
        for key, value in kwargs.items():
            self.__setitem__(key, value)

        self.iloc = _Iloc(self)

    def __default_arg_name(self, index):
        return "V%02d" % index

    def copy(self):
        return DataFrame(*[self[col] for col in self], columns=self.__keynames)

    def nrow(self):
        log("WARNING nrow() is deprecated, use len() instead.")
        return len(self)

    def ncol(self):
        return len(self.__keynames)

    def columns(self):
        log("WARNING: DataFrame.columns() as a method is deprecated, use 'in' and iter() instead")
        return np.array(self.__keynames)

    def rowasdict(self, i):
        log("WARNING: DataFrame.rowasdict(i) is deprecated, use iloc[i] instead")
        return self._row(i)

    def _subset(self, rows, cols):
        if type(cols) == slice:
            icols = [self. __internal_key(col) for col in list(range(len(self.__keynames)))[cols]]
        elif type(cols) == int:
            icols = [self.__internal_key(cols), ]
        else:
            icols = [self.__internal_key(col) for col in cols]
        if None in icols:
            raise KeyError("One of the following is not a valid column: %s" % (cols, ))
        if type(rows) == tuple:
            rows = list(rows)
        return DataFrame(*[_aslist(self[col][rows]) for col in icols], columns=icols)

    def _row(self, i):
        return _DFRow(self.__keynames, [self[col][i] for col in self])

    def itertuples(self, header=False, rownames=True):
        if header:
            if rownames:
                yield [-1, ] + self.__keynames
            else:
                yield list(self.__keynames)
        if rownames:
            for i in range(len(self)):
                yield _DFRow(["_index", ] + self.__keynames, [i, ] + [self[col][i] for col in self])
        else:
            for i in range(len(self)):
                yield _DFRow(self.__keynames, [self[col][i] for col in self])

    def __iter__(self):
        return iter(self.__keynames)

    def __reversed__(self):
        return reversed(self.__keynames)

    def __contains__(self, item):
        return item in self.__keynames

    def __len__(self):
        return 0 if self.__rows is None else self.__rows

    def __internal_key(self, keyin):
        if keyin in self.__keynames:
            return keyin
        else:
            try:
                if keyin < len(self.__keynames):
                    return self.__keynames[keyin]
            except (TypeError, IndexError):
                return None

    def __delitem__(self, orig):
        key = self.__internal_key(orig)
        if key is None:
            raise KeyError("No such column: %s" % orig)
        del self.__dict__[key]
        if orig in self.__keynames:
            self.__keynames.remove(orig)

    def __setitem__(self, orig, value, check=True):
        key = self.__internal_key(orig)
        if key is None:
            key = orig
        if self.__rows is None:
            self.__rows = len(value)
        else:
            if self.__rows != len(value) and check:
                raise ValueError("Number of observations is not consistent (%s, %s) for arg %s" % (self.__rows,
                                                                                                  len(value),
                                                                                                    key))

        self.__dict__[key] = np.array(value)
        if key not in self.__keynames:
            self.__keynames.append(key)

    def __getattr__(self, item):
        if item in self.__keynames:
            key = self.__internal_key(item)
            if key is None:
                raise KeyError("No such column: %s" % item)
            return self.__dict__[key]
        else:
            return super().__getattribute__(item)

    def __getitem__(self, item):
        key = self.__internal_key(item)
        if key is None:
            raise KeyError("No such column: %s" % item)
        return self.__dict__[key]

    def append(self, *args, **kwargs):
        if (len(args) + len(kwargs)) != self.ncol():
            raise ValueError("Dimension mismatch: %s cols found and %s expected" % (len(args)+len(kwargs), self.ncol()))
        newrows = None

        # check input (just warning for now because lists are added sometimes in dbinterface)
        lengths = [_len(arg) for arg in args] + [_len(value) for value in kwargs.values()]
        newrows = min(lengths)
        if any([length != newrows for length in lengths]):
            log("WARNING: possible dimension mismatch in DataFrame.append()")
        axis = None if newrows > 1 else 0

        # going to use
        for i in range(len(args)):
            key = self.__internal_key(i)
            if key is None:
                raise KeyError("No such column: ", i)
            self.__dict__[key] = np.append(self[key], args[i])
        for key, value in kwargs.items():
            if key not in self:
                raise KeyError("No such column: ", key)
            self.__dict__[key] = np.append(self[key], value)
        self.__rows += newrows

    def __bool__(self):
        return self.__rows is not None and self.__rows > 0

    def cols(self):
        for i in range(len(self.__columns)):
            yield self.__columns[i], self.__getitem__(i)
        for key in self.__keynames:
            yield self.__getitem__(key)

    def __repr__(self, sep="\t"):
        return "\n".join(sep.join(str(cell) for cell in row) for row in self.itertuples(header=True, rownames=False))

    def write(self, writer, driver=None, mode="w"):
        fname = None
        if "write" in dir(writer):
            # is an open file object
            if driver is None:
                raise ValueError("Must specify driver of 'csv', 'tsv', or 'json'")
        else:
            # is a filename
            if not isinstance(writer, str):
                raise ValueError("Writer paramter is not an open file or a filename")
            fname = writer
            if driver is None:
                # autodetect from ext
                ext = writer[fname.rfind("."):]
                if len(ext) > 1:
                    driver = ext[1:]
                else:
                    raise ValueError("Invalid extension provided, cannot autodetect out driver")
            writer = open(fname, mode)

        headers = mode == "w"
        if driver == "csv":
            for row in self.itertuples(header=headers, rownames=False):
                cells = [str(cell) for cell in row]
                for i, cell in enumerate(cells):
                    if "," in cell:
                        cells[i] = '"%s"' % cell
                writer.write(",".join(cells))
                writer.write("\n")
        elif driver == "tsv":
            for row in self.itertuples(header=headers, rownames=False):
                writer.write("\t".join([str(cell) for cell in row]))
                writer.write("\n")
        elif driver == "json":
            if fname:
                writer.close()
            raise NotImplementedError("JSON driver not yet implemented")
        else:
            if fname:
                writer.close()
            raise ValueError("Unrecgonized driver: %s" % driver)

        if fname:
            writer.close()

    @staticmethod
    def from_records(data, columns=None):
        return DataFrame(*zip(*data)) if columns is None else DataFrame(*zip(*data), columns=columns)

    @staticmethod
    def read(reader, driver=None, headers=True, skiprows=0, numeric=True):
        fname = None
        if "readline" in dir(reader):
            # is an open file object
            if driver is None:
                raise ValueError("Must specify driver of 'csv', 'tsv', or 'json'")
        else:
            # is a filename
            if not isinstance(reader, str):
                raise ValueError("Reader paramter is not an open file or a filename")
            fname = reader
            if driver is None:
                # autodetect from ext
                ext = reader[fname.rfind("."):]
                if len(ext) > 1:
                    driver = ext[1:]
                else:
                    raise ValueError("Invalid extension provided, cannot autodetect out driver")
            reader = open(fname, "r")

        if driver != "csv":
            if fname:
                reader.close()
            raise NotImplementedError("Driver other than csv is not yet supported.")

        csvreader = csv.reader(reader)
        df = None
        records = []
        columns = None
        for line in csvreader:
            if skiprows > 0:
                skiprows -= 1
                continue
            if not records and not columns:
                # look for data
                if any([bool(c) for c in line]):
                    if headers:
                        columns = line
                    else:
                        if numeric:
                            records.append([[_asnumeric(c),] for c in line])
                        else:
                            records.append([[c,] for c in line])
                else:
                    # no data
                    continue
            else:
                # already a df
                if numeric:
                    records.append([_asnumeric(c) for c in line])
                else:
                    records.append([c for c in line])
        if fname:
            reader.close()
        return DataFrame.from_records(records, columns=columns)

    @staticmethod
    def flatten(list_of_dicts, no_value=float('nan'), keys=None):
        if keys is None:
            keys = set()
            for dict in list_of_dicts:
                keys = keys.union(set(dict.keys()))
        df = DataFrame()
        for key in keys:
            df[key] = [d[key] if key in d else no_value for d in list_of_dicts]
        return df

if __name__ == "__main__":
    # test
    import os

    a = DataFrame([1, 2, 3], ["one", "two", "three"], ["data1", "data2", "data3"])
    b = DataFrame([], [], [], columns=["Column1", "Column2", "Column3"])
    print(a[0])
    print(a[1])
    print(a.columns())
    print(b[0])
    print(b[1])
    print(b.Column1)
    print(b.Column2)
    print(len(b))
    print(b.ncol())
    # a.newcol = [1.23, 4.44, 9.19] #this does not add 'newcol' to columns, and does not work. use [] for assigning
    a["newcol"] = [1.23, 4.44, 9.19]
    b["newcol"] = [] #like this
    b.append(1,2,3, newcol="bananas")
    a.append([4, 5], ["four", "five"], ["data4", "data5"], newcol=[13, 10])
    print(a)
    print(b)
    with open("fish", "w") as f:
        a.write(f, driver="csv")
    a.write("fish", driver="tsv")
    b.write("fish.csv")
    b.write("fish.csv", mode="a")
    c = DataFrame.read("fish.csv")
    print(c)
    d = DataFrame.read("fish.csv", headers=False)
    print(d)

    with open("fish.csv") as f:
        e = DataFrame.read(f, driver="csv")
        print(e)

    a = DataFrame([1,2], columns=["fish",])
    a["fish"] = ["one", "two"]
    print(a)
    print("-----")
    # print(b.rowasdict(0))
    print(a.iloc[0])  # should be the same
    print(a.iloc[0, :])  # should be the same except as data frame

    print(b.copy())

    os.unlink("fish")
    os.unlink("fish.csv")