# pyfakefs
pyfakefs implements a fake file system that mocks the Python file system modules.
Using pyfakefs, your tests operate on a fake file system in memory without
touching the real disk.  The software under test requires no modification to
work with pyfakefs.

## Usage
See the [usage tutorial](http://github.com/jmcgeheeiv/pyfakefs/wiki/Tutorial)
for a concrete example of how to apply pyfakefs.

Usually you would use it this way:

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

## Continuous Integration

pyfakefs is automatically tested with Python 2.6 and above, and it is currently
[![Build Status](https://travis-ci.org/jmcgeheeiv/pyfakefs.svg)](https://travis-ci.org/jmcgeheeiv/pyfakefs).

See [Travis-CI](http://travis-ci.org) for
[test results for each Python version](https://travis-ci.org/jmcgeheeiv/pyfakefs).

## Installation

### Compatibility
pyfakefs works with Python 2.6 and above.  pyfakefs requires [mox3](https://pypi.python.org/pypi/mox3).

### PyPi
[pyfakefs is available on PyPi](https://pypi.python.org/pypi/pyfakefs/).

## History
pyfakefs.py was initially developed at Google by Mike Bland as a modest fake
implementation of core Python modules.  It was introduced to all of Google
in September 2006. Since then, it has been enhanced to extend its
functionality and usefulness.  At Google alone, pyfakefs is used in over 2,000
Python tests.

pyfakefs was released to the public in 2011 as Google Code project
[pyfakefs](http://code.google.com/p/pyfakefs/).

Fork
[jmcgeheeiv-pyfakefs](http://code.google.com/p/jmcgeheeiv-pyfakefs/)
added a [usage tutorial](http://github.com/jmcgeheeiv/pyfakefs/wiki/Tutorial),
direct support for [unittest](http://docs.python.org/2/library/unittest.html)
and [doctest](http://docs.python.org/2/library/doctest.html).

Fork
[shiffdane-jmcgeheeiv-pyfakefs](http://code.google.com/p/shiffdane-jmcgeheeiv-pyfakefs/)
added further corrections.

After the [shutdown of Google Code was announced,](http://google-opensource.blogspot.com/2015/03/farewell-to-google-code.html)
all three Google Code projects are merged together here on GitHub as pyfakefs.

