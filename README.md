# pyfakefs [![PyPI version](https://badge.fury.io/py/pyfakefs.svg)](https://badge.fury.io/py/pyfakefs) [![Python version](https://img.shields.io/pypi/pyversions/pyfakefs.svg)](https://img.shields.io/pypi/pyversions/pyfakefs.svg) ![Testsuite](https://github.com/pytest-dev/pyfakefs/workflows/Testsuite/badge.svg) [![Documentation Status](https://readthedocs.org/projects/pytest-pyfakefs/badge/?version=latest)](https://pytest-pyfakefs.readthedocs.io/en/latest/?badge=latest) [![pre-commit.ci status](https://results.pre-commit.ci/badge/github/pytest-dev/pyfakefs/main.svg)](https://results.pre-commit.ci/latest/github/pytest-dev/pyfakefs/main) ![PyPI - Downloads](https://img.shields.io/pypi/dw/pyfakefs)


`pyfakefs` implements a fake file system that mocks the Python file system modules.
Using `pyfakefs`, your tests operate on a fake file system in memory without
touching the real disk. The software under test requires no modification to
work with `pyfakefs`.

`pyfakefs` creates a new empty in-memory file system at each test start, which replaces
the real filesystem during the test. Think of pyfakefs as making a per-test temporary
directory, except for an entire file system.

`pyfakefs` is tested with current versions of Linux, Windows and macOS.

## Usage

There are several ways to invoke `pyfakefs`:
* using the `fs` fixture with `pytest`
* deriving from `fake_filesystem_unittest.TestCase` for `unittest`
* using `fake_filesystem_unittest.Patcher` as context manager
* using the `fake_filesystem_unittest.patchfs` decorator on a single test

Refer to the [usage documentation](https://pytest-pyfakefs.readthedocs.io/en/latest/usage.html) for more information.

## Documentation

* [Release documentation](https://pytest-pyfakefs.readthedocs.io/en/stable)
  covers the latest released version
* [Development documentation](https://pytest-pyfakefs.readthedocs.io/en/latest)
  for the current main branch
* [Release 3.7 documentation](https://pytest-pyfakefs.readthedocs.io/en/v3.7.2/)
  for the last version supporting Python 2.7
* [Release Notes](https://github.com/pytest-dev/pyfakefs/blob/main/CHANGES.md)
* [Contributing Guide](https://github.com/pytest-dev/pyfakefs/blob/main/CONTRIBUTING.md) - contributions are welcome!

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

## Limitations
pyfakefs will not work with Python libraries that use C libraries to access the
file system. This is because pyfakefs cannot patch the underlying C libraries'
file access functions--the C libraries will always access the real file
system. Refer to the [documentation](https://pytest-pyfakefs.readthedocs.io/en/latest/intro.html#limitations)
for more information about the limitations of pyfakefs.

## History
pyfakefs.py was initially developed at Google by Mike Bland as a modest fake
implementation of core Python modules.  It was introduced to all of Google
in September 2006. At last count, pyfakefs was used in over 20,000
Python tests at Google.

Google released pyfakefs to the public in 2011 as a Google Code project.
Support for `unittest` and `doctest` was added in a fork by user `jmcgeheeiv`,
further corrections were made in a separate fork with user `shiffdane`, and after
the [shutdown of Google Code](http://google-opensource.blogspot.com/2015/03/farewell-to-google-code.html)
was announced, [John McGehee](https://github.com/jmcgeheeiv) merged all three Google Code projects together
[here on GitHub](https://github.com/pytest-dev/pyfakefs). In 2022, the repository has been transferred to
[pytest-dev](https://github.com/pytest-dev) to ensure continuous maintenance.
