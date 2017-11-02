# pyfakefs
pyfakefs implements a fake file system that mocks the Python file system modules.
Using pyfakefs, your tests operate on a fake file system in memory without
touching the real disk.  The software under test requires no modification to
work with pyfakefs.

pyfakefs works with Linux, Windows and MacOS.

## Documentation

This file provides general usage instructions for pyfakefs.  There is more:

* The [Release pyfakefs API Reference](http://jmcgeheeiv.github.io/pyfakefs/release)
  contains documentation for each pyfakefs class, method and function for the last version released on PyPi
* The [Development pyfakefs API Reference](http://jmcgeheeiv.github.io/pyfakefs/master)
  contains the same documentation for the current master branch
* The [pyfakefs Wiki](https://github.com/jmcgeheeiv/pyfakefs/wiki/Home) provides more detailed information on
  specific topics
* The [Release Notes](https://github.com/jmcgeheeiv/pyfakefs/blob/master/CHANGES.md) shows a list of changes in the latest versions

### Link to pyfakefs.org

In your own documentation, please link to pyfakefs using <http://pyfakefs.org>.
This URL always points to the most relevant top page for pyfakefs.

## Usage
There are several approaches to implementing tests using pyfakefs.

### Automatically find and patch
The first approach is to allow pyfakefs to automatically find all real file functions and modules, and stub these out with the fake file system functions and modules.  This is explained in the pyfakefs wiki page
[Automatically find and patch file functions and modules](https://github.com/jmcgeheeiv/pyfakefs/wiki/Automatically-find-and-patch-file-functions-and-modules)
and demonstrated in files `example.py` and `example_test.py`.

### Patch using the PyTest plugin

If you use [PyTest](https://doc.pytest.org), you will be interested in the PyTest plugin in pyfakefs.
This automatically patches all file system functions and modules in a manner similar to the
[automatic find and patch approach](https://github.com/jmcgeheeiv/pyfakefs/wiki/Automatically-find-and-patch-file-functions-and-modules)
described above.

The PyTest plugin provides the `fs` fixture for use in your test. For example:

```python
def my_fakefs_test(fs):
    # "fs" is the reference to the fake file system
    fs.CreateFile('/var/data/xx1.txt')
    assert os.path.exists('/var/data/xx1.txt')
```

### Patch using fake_filesystem_unittest.Patcher
If you are using other means of testing like [nose](http://nose2.readthedocs.io), you can do the
patching using `fake_filesystem_unittest.Patcher` - the class doing the the actual work
of replacing the filesystem modules with the fake modules in the first two approaches.

The easiest way is to just use `Patcher` as a context manager:

```python
from fake_filesystem_unittest import Patcher

with Patcher() as patcher:
   # access the fake_filesystem object via patcher.fs
   patcher.fs.CreateFile('/foo/bar', contents='test')

   # the following code works on the fake filesystem
   with open('/foo/bar') as f:
       contents = f.read()
```

You can also initialize `Patcher` manually:

```python
from fake_filesystem_unittest import Patcher

patcher = Patcher()
patcher.setUp()     # called in the initialization code
...
patcher.tearDown()  # somewhere in the cleanup code
```

### Patch using unittest.mock (deprecated)

You can also use ``mock.patch()`` to patch the modules manually. This approach will
only work for the directly imported modules, therefore it is not suited for testing
larger code bases. As the other approaches are more convenient, this one is considered
deprecated.
You have to create a fake filesystem object, and afterwards fake modules based on this file system
for the modules you want to patch.

The following modules and functions can be patched:

* `os` and `os.path` by `fake_filessystem.FakeOsModule`
* `io` by `fake_filessystem.FakeIoModule`
* `pathlib` by `fake_pathlib.FakePathlibModule`
* build-in `open()` by `fake_filessystem.FakeFileOpen`

```python

   import pyfakefs.fake_filesystem as fake_fs

   # Create a faked file system
   fs = fake_fs.FakeFilesystem()

   # Do some setup on the faked file system
   fs.CreateFile('/foo/bar', contents='test')

   # Replace some built-in file system related modules you use with faked ones

   # Assuming you are using the mock library to ... mock things
   try:
       from unittest.mock import patch  # In Python 3, mock is built-in
   except ImportError:
       from mock import patch  # Python 2

   # Note that this fake module is based on the fake fs you just created
   os = fake_fs.FakeOsModule(fs)
   with patch('mymodule.os', os):
       fd = os.open('/foo/bar', os.O_RDONLY)
       contents = os.read(fd, 4)
```

## Installation

### Compatibility
pyfakefs works with CPython 2.6, 2.7, 3.3 and above, on Linux, Windows and OSX (MacOS), and with PyPy2 and PyPy3.

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

pyfakefs is currently automatically tested with Python 2.6, 2.7, 3.3 and above under Linux, with Python 2.7 and 3.6 under MacOSX,
 and with Python 2.7, 3.3 and 3.6 under Windows.
It is currently [![Build Status](https://travis-ci.org/jmcgeheeiv/pyfakefs.svg)](https://travis-ci.org/jmcgeheeiv/pyfakefs).

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
[here on GitHub](https://github.com/jmcgeheeiv/pyfakefs) where an enthusiastic community actively supports, maintains
and extends pyfakefs.
