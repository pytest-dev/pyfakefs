# pyfakefs
pyfakefs implements a fake file system that mocks the Python file system modules.
Using pyfakefs, your tests operate on a fake file system in memory without
touching the real disk.  The software under test requires no modification to
work with pyfakefs.

pyfakefs works with Linux, Windows and MacOS.

## Documentation

This file provides general usage instructions for pyfakefs.  There is more:

* The [pyfakfs API Reference](http://jmcgeheeiv.github.io/pyfakefs/)
  contains documentation for each pyfakefs class, method and function
* The [pyfakefs Wiki](../../wiki/Home) provides more detailed information on
  specific topics
* The [Release Notes](CHANGES.md) shows a list of changes in the latest versions

### Link to pyfakefs.org

In your own documentation, please link to pyfakefs using <http://pyfakefs.org>.
This URL always points to the most relevant top page for pyfakefs.

## Usage
There are several approaches to implementing tests using pyfakefs.

### Automatically find and patch
The first approach is to allow pyfakefs to automatically find all real file functions and modules, and stub these out with the fake file system functions and modules.  This is explained in the pyfakefs wiki page
[Automatically find and patch file functions and modules](../../wiki/Automatically-find-and-patch-file-functions-and-modules)
and demonstrated in files `example.py` and `example_test.py`.

### Patch using the PyTest plugin

If you use [PyTest](https://doc.pytest.org), you will be interested in the PyTest plugin in pyfakefs.
This automatically patches all file system functions and modules in a manner similar to the
[automatic find and patch approach](../../wiki/Automatically-find-and-patch-file-functions-and-modules)
described above.

The PyTest plugin provides the `fs` fixture for use in your test. For example:

```python
def my_fakefs_test(fs):
    # "fs" is the reference to the fake file system
    fs.CreateFile('/var/data/xx1.txt')
    assert os.path.exists('/var/data/xx1.txt')
```

### Patch using unittest.mock

The other approach is to do the patching yourself using `mock.patch()`:

```python
import pyfakefs.fake_filesystem as fake_fs

# Create a faked file system
fs = fake_fs.FakeFilesystem()

# Do some setup on the faked file system
fs.CreateFile('/var/data/xx1.txt')
fs.CreateFile('/var/data/xx2.txt')

# Replace some built-in file system related modules you use with faked ones

# Assuming you are using the mock library to ... mock things
try:
    from unittest.mock import patch  # In Python 3, mock is built-in
except ImportError:
    from mock import patch  # Python 2

import pyfakefs.fake_filesystem_glob as fake_glob

# Note that this fake module is based on the fake fs you just created
glob = fake_glob.FakeGlobModule(fs)
with patch('mymodule.glob', glob):
    print(glob.glob('/var/data/xx*'))
```

## Installation

### Compatibility
pyfakefs works with Python 2.6 and above, on Linux, Windows and OSX (MacOS).

pyfakefs requires [mox3](https://pypi.python.org/pypi/mox3).

pyfakefs works with [PyTest](doc.pytest.org) version 2.8.0 or above.

### PyPi
[pyfakefs is available on PyPi](https://pypi.python.org/pypi/pyfakefs/).

## Development

### Continuous integration

pyfakefs is automatically tested with Python 2.6 and above, and it is currently
[![Build Status](https://travis-ci.org/jmcgeheeiv/pyfakefs.svg)](https://travis-ci.org/jmcgeheeiv/pyfakefs).

See [Travis-CI](http://travis-ci.org) for
[test results for each Python version](https://travis-ci.org/jmcgeheeiv/pyfakefs).

### Running pyfakefs unit tests

pyfakefs unit tests are available via two test scripts:

```bash
$ python all_tests.py
$ py.test pytest_plugin_test.py
```

These scripts are called by `tox` and Travis-CI. `tox` can be used to run tests
locally against supported python versions:

```bash
$ tox
```

## History
pyfakefs.py was initially developed at Google by Mike Bland as a modest fake
implementation of core Python modules.  It was introduced to all of Google
in September 2006. Since then, it has been enhanced to extend its
functionality and usefulness.  At last count, pyfakefs is used in over 2,000
Python tests at Google.

Google released pyfakefs to the public in 2011 as Google Code project
[pyfakefs](http://code.google.com/p/pyfakefs/):
* Fork
  [jmcgeheeiv-pyfakefs](http://code.google.com/p/jmcgeheeiv-pyfakefs/) added
  [direct support for unittest and doctest](../../wiki/Automatically-find-and-patch-file-functions-and-modules)
* Fork
  [shiffdane-jmcgeheeiv-pyfakefs](http://code.google.com/p/shiffdane-jmcgeheeiv-pyfakefs/)
  added further corrections

After the [shutdown of Google Code](http://google-opensource.blogspot.com/2015/03/farewell-to-google-code.html)
was announced, [John McGehee](https://github.com/jmcgeheeiv) merged all three Google Code projects together
[here on GitHub](https://github.com/jmcgeheeiv/pyfakefs) where an enthusiastic community actively maintains
and extends pyfakefs.
