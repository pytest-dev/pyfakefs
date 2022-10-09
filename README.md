# pyfakefs [![PyPI version](https://badge.fury.io/py/pyfakefs.svg)](https://badge.fury.io/py/pyfakefs) [![Python version](https://img.shields.io/pypi/pyversions/pyfakefs.svg)](https://img.shields.io/pypi/pyversions/pyfakefs.svg) ![Testsuite](https://github.com/pytest-dev/pyfakefs/workflows/Testsuite/badge.svg) [![Documentation Status](https://readthedocs.org/projects/pytest-pyfakefs/badge/?version=latest)](https://pytest-pyfakefs.readthedocs.io/en/latest/?badge=latest)


pyfakefs implements a fake file system that mocks the Python file system modules.
Using pyfakefs, your tests operate on a fake file system in memory without
touching the real disk. The software under test requires no modification to
work with pyfakefs.

pyfakefs acts as a `pytest` plugin by providing the `fs` fixture, which will 
automatically invoke the fake filesystem. It also provides 
the `fake_filesystem_unittest.TestCase` class for use with `unittest` and 
the means to use the fake filesystem with other test frameworks. 

pyfakefs works with current versions of Linux, Windows and macOS.

## Documentation

This document provides a general overview for pyfakefs.  There is more:

* The documentation at **Read the Docs**:
  * The [Release documentation](https://pytest-pyfakefs.readthedocs.io/en/stable)
    contains usage documentation for pyfakefs and a description of the 
    most relevant classes, methods and functions for the last version 
    released on PyPI
  * The [Development documentation](https://pytest-pyfakefs.readthedocs.io/en/latest)
    contains the same documentation for the current main branch
  * The [Release 3.7 documentation](https://pytest-pyfakefs.readthedocs.io/en/v3.7.2/)
    contains usage documentation for the last version of pyfakefs 
    supporting Python 2.7
* The [Release Notes](https://github.com/pytest-dev/pyfakefs/blob/main/CHANGES.md) 
  show a list of changes in the latest versions

## Usage
The simplest method to use pyfakefs is using the `fs` fixture with `pytest`. 
Refer to the
[usage documentation](http://pytest-dev.github.io/pyfakefs/main/usage.html) 
for information on other test scenarios, test customization and 
using convenience functions.

## Features
Apart from automatically mocking most file-system functions, pyfakefs 
provides some additional features:
- mapping files and directories from the real file system into the fake filesystem
- configuration and tracking of the file system size
- pause and resume of patching to be able to use the real file system inside a 
  test step
- (limited) emulation of other OSes (Linux, macOS or Windows)
- configuration to behave as if running as a non-root user while running 
  under root

## Compatibility
pyfakefs works with CPython 3.7 and above, on Linux, Windows and macOS, and 
with PyPy3.

pyfakefs works with [pytest](http://doc.pytest.org) version 3.0.0 or above, 
though a current version is recommended.

pyfakefs will not work with Python libraries that use C libraries to access the
file system. This is because pyfakefs cannot patch the underlying C libraries'
file access functions--the C libraries will always access the real file 
system. Refer to the 
[documentation](https://pytest-dev.github.io/pyfakefs/release/intro.html#limitations)
for more information about the limitations of pyfakefs.

## Development

### Continuous integration

pyfakefs is currently automatically tested on Linux, macOS and Windows, with
Python 3.7 to 3.11, and with PyPy3 on Linux, using
[GitHub Actions](https://github.com/pytest-dev/pyfakefs/actions).

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
[Contributing Guide](https://github.com/pytest-dev/pyfakefs/blob/main/CONTRIBUTING.md)
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
[here on GitHub](https://github.com/pytest-dev/pyfakefs) where an enthusiastic community actively supports, maintains
and extends pyfakefs. In 2022, the repository has been transferred to 
[pytest-dev](https://github.com/pytest-dev) to ensure continuous maintenance.
