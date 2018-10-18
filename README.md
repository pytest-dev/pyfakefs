# pyfakefs
pyfakefs implements a fake file system that mocks the Python file system modules.
Using pyfakefs, your tests operate on a fake file system in memory without
touching the real disk.  The software under test requires no modification to
work with pyfakefs.

pyfakefs works with Linux, Windows and MacOS.

## Documentation

This file provides general usage instructions for pyfakefs.  There is more:

* The documentation at [GitHub Pages:](http://jmcgeheeiv.github.io/pyfakefs)
  * The [Release documentation](http://jmcgeheeiv.github.io/pyfakefs/release)
    contains usage documentation for pyfakefs and a description of the 
    most relevent classes, methods and functions for the last version 
    released on PyPi
  * The [Development documentation](http://jmcgeheeiv.github.io/pyfakefs/master)
    contains the same documentation for the current master branch
  * The [Release 3.3 documentation](http://jmcgeheeiv.github.io/pyfakefs/release33)
    contains usage documentation for the last version of pyfakefs 
    supporting Python 2.6, and for the old-style API (which is still 
    supported but not documented in the current release)
* The [Release Notes](https://github.com/jmcgeheeiv/pyfakefs/blob/master/CHANGES.md) 
  show a list of changes in the latest versions

### Linking to pyfakefs

In your own documentation, please link to pyfakefs using the canonical URL <http://pyfakefs.org>.
This URL always points to the most relevant top page for pyfakefs.

## Usage

pyfakefs has support for `unittest` and `pytest`, but can also be used 
directly using `fake_filesystem_unittest.Patcher`. Refer to the
[usage documentation](http://jmcgeheeiv.github.io/pyfakefs/master/usage.html) 
for more information on test scenarios, test customization and 
using convenience functions.

## Installation

### Compatibility
pyfakefs works with CPython 2.7, 3.4 and above, on Linux, Windows and OSX 
(MacOS), and with PyPy2 and PyPy3.

pyfakefs works with [PyTest](http://doc.pytest.org) version 2.8.6 or above.

pyfakefs will not work with Python libraries that use C libraries to access the
file system.  This is because pyfakefs cannot patch the underlying C libraries'
file access functions--the C libraries will always access the real file system.
For example, pyfakefs will not work with [`lxml`](http://lxml.de/).  In this case
`lxml` must be replaced with a pure Python alternative such as
[`xml.etree.ElementTree`](https://docs.python.org/3/library/xml.etree.elementtree.html).

### PyPi
[pyfakefs is available on PyPi](https://pypi.python.org/pypi/pyfakefs/).

## Development

### Continuous integration

pyfakefs is currently automatically tested:
* On Linux, with Python 2.7, and 3.4 to 3.7, using [Travis](https://travis-ci.org/jmcgeheeiv/pyfakefs)
  [![Build Status](https://travis-ci.org/jmcgeheeiv/pyfakefs.svg)](https://travis-ci.org/jmcgeheeiv/pyfakefs)
* On MacOS, with Python 2.7, 3.6 and 3.7, also using [Travis](https://travis-ci.org/jmcgeheeiv/pyfakefs)
  [![Build Status](https://travis-ci.org/jmcgeheeiv/pyfakefs.svg)](https://travis-ci.org/jmcgeheeiv/pyfakefs)
* On Windows, with Python 2.7, and 3.4 to 3.7 using [Appveyor](https://ci.appveyor.com/project/jmcgeheeiv/pyfakefs)
  [![Build status](https://ci.appveyor.com/api/projects/status/4o8j21ufuo056873/branch/master?svg=true)](https://ci.appveyor.com/project/jmcgeheeiv/pyfakefs/branch/master).

### Running pyfakefs unit tests

pyfakefs unit tests are available via two test scripts:

```bash
$ python -m pyfakefs.tests.all_tests
$ python -m pytest pyfakefs/tests/pytest_plugin_test.py
```

These scripts are called by `tox` and Travis-CI. `tox` can be used to run tests
locally against supported python versions:

```bash
$ tox
```

### Contributing to pyfakefs

We always welcome contributions to the library. Check out the [Contributing 
Guide](https://github.com/jmcgeheeiv/pyfakefs/blob/master/CONTRIBUTING.md)
for more information.

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
[here on GitHub](https://github.com/jmcgeheeiv/pyfakefs) where an enthusiastic community actively supports, maintains
and extends pyfakefs.
