# pyfakefs [![PyPI version](https://badge.fury.io/py/pyfakefs.svg)](https://badge.fury.io/py/pyfakefs) [![Python version](https://img.shields.io/pypi/pyversions/pyfakefs.svg)](https://img.shields.io/pypi/pyversions/pyfakefs.svg) ![Testsuite](https://github.com/jmcgeheeiv/pyfakefs/workflows/Testsuite/badge.svg)

pyfakefs implements a fake file system that mocks the Python file system modules.
Using pyfakefs, your tests operate on a fake file system in memory without
touching the real disk. The software under test requires no modification to
work with pyfakefs.

pyfakefs works with Linux, Windows and MacOS.

pyfakefs provides the `fs` fixture for use with `pytest`, which will 
automatically invoke the fake filesystem. It also provides 
the `fake_filesystem_unittest.TestCase` class for use with `unittest` and 
the means to use the fake filesystem with other test frameworks. 

## Documentation

This file provides general usage instructions for pyfakefs.  There is more:

* The documentation at [GitHub Pages:](http://jmcgeheeiv.github.io/pyfakefs)
  * The [Release documentation](http://jmcgeheeiv.github.io/pyfakefs/release)
    contains usage documentation for pyfakefs and a description of the 
    most relevant classes, methods and functions for the last version 
    released on PyPi
  * The [Development documentation](http://jmcgeheeiv.github.io/pyfakefs/master)
    contains the same documentation for the current master branch
  * The [Release 3.7 documentation](http://jmcgeheeiv.github.io/pyfakefs/release37)
    contains usage documentation for the last version of pyfakefs 
    supporting Python 2.7
* The [Release Notes](https://github.com/jmcgeheeiv/pyfakefs/blob/master/CHANGES.md) 
  show a list of changes in the latest versions

## Usage
The simplest method to use pyfakefs is using the `fs` fixture with `pytest`. 
Refer to the
[usage documentation](http://jmcgeheeiv.github.io/pyfakefs/master/usage.html) 
for information on other test scenarios, test customization and 
using convenience functions.


## Compatibility
pyfakefs works with CPython 3.7 and above, on Linux, Windows and OSX 
(MacOS), and with PyPy3.

pyfakefs works with [pytest](http://doc.pytest.org) version 3.0.0 or above, 
though a current version is recommended.

pyfakefs will not work with Python libraries that use C libraries to access the
file system. This is because pyfakefs cannot patch the underlying C libraries'
file access functions--the C libraries will always access the real file system.
For example, pyfakefs will not work with [`lxml`](http://lxml.de/).  In this case
`lxml` must be replaced with a pure Python alternative such as
[`xml.etree.ElementTree`](https://docs.python.org/3/library/xml.etree.elementtree.html).

## Development

### Continuous integration

pyfakefs is currently automatically tested on Linux, MacOS and Windows, with
Python 3.7 to 3.11, and with PyPy3 on Linux, using
[GitHub Actions](https://github.com/jmcgeheeiv/pyfakefs/actions).

### Running pyfakefs unit tests

#### On the command line
pyfakefs unit tests can be run using `pytest` (all tests) or `unittest` 
(all tests except `pytest`-specific ones):

```bash
$ cd pyfakefs/
$ export PYTHONPATH=$PWD

$ python -m pytest pyfakefs
$ python -m pyfakefs.tests.all_tests
```

Similar scripts are called by `tox` and Github Actions. `tox` can be used to 
run tests locally against supported python versions:

```bash
$ tox
```

#### In a Docker container

The `Dockerfile` at the repository root will run the tests on the latest
Ubuntu version.  Build the container:
```bash
cd pyfakefs/
docker build -t pyfakefs .
```
Run the unit tests in the container:
```bash
docker run -t pyfakefs
```

### Contributing to pyfakefs

We always welcome contributions to the library. Check out the
[Contributing Guide](https://github.com/jmcgeheeiv/pyfakefs/blob/master/CONTRIBUTING.md)
for more information.

## History
pyfakefs.py was initially developed at Google by Mike Bland as a modest fake
implementation of core Python modules.  It was introduced to all of Google
in September 2006. Since then, it has been enhanced to extend its
functionality and usefulness.  At last count, pyfakefs was used in over 2,000
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
