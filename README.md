# pyfakefs
pyfakefs implements a fake file system that mocks the Python file system modules.
Using pyfakefs, your tests operate on a fake file system in memory without
touching the real disk.  The software under test requires no modification to
work with pyfakefs.

## Installation

### Prerequisites
pyfakefs works with Python 2.6 and above.  The mox package is required.  This code
is tested with Python 2.7.1 and 2.7.5.

### PyPi
pyfakefs project is hosted on PyPi and can be installed:

```bash
pip install pyfakefs
```

## History
pyfakefs.py was initially developed at Google by Mike Bland as a modest fake
implementation of core Python modules.  It was introduced to all of Google
in September 2006. Since then, it has been enhanced to extend its
functionality and usefulness.  At Google alone, pyfakefs is used in over 2,000
Python tests.

pyfakefs was released to the public in 2011 as Google Code project
[pyfakefs](http://code.google.com/p/pyfakefs/).  Fork
[jmcgeheeiv-pyfakefs](http://code.google.com/p/jmcgeheeiv-pyfakefs/)
added direct support for [unittest](http://docs.python.org/2/library/unittest.html)
and [doctest](http://docs.python.org/2/library/doctest.html).

[After the shutdown of Google Code was announced,](http://google-opensource.blogspot.com/2015/03/farewell-to-google-code.html)
all three Google Code projects are merged together here on GitHub as pyfakefs.  

## Tutorial

The source code contains two files that show an example of software under test and unit test for it:

  * `example.py` is the software under test.  In production, it uses the real file system.
  * `example_test.py` tests `example.py`.  During testing, the pyfakefs fake file system is used.

### Software Under Test

`example.py` contains a few functions that manipulate files.  For instance:

```python

def create_file(path):
'''Create the specified file and add some content to it.  Use the open()
built in function.

For example, the following file operations occur in the fake file system.
In the real file system, we would not even have permission to write /test:

>>> os.path.isdir('/test')
False
>>> os.mkdir('/test')
>>> os.path.isdir('/test')
True
>>> os.path.exists('/test/file.txt')
False
>>> create_file('/test/file.txt')
>>> os.path.exists('/test/file.txt')
True
>>> with open('/test/file.txt') as f:
...     f.readlines()
["This is test file '/test/file.txt'.\\n", 'It was created using the open() function.\\n']
'''
with open(path, 'w') as f:
f.write("This is test file '{}'.\n".format(path))
f.write("It was created using the open() function.\n")```

No functional code in `example.py` even hints at a fake file system.  In production, `create_file()` invokes the real file functions `open()` and `write()`.

### Unit Tests and Doctests

`example_test.py` contains doctests and unit tests for `example.py`.

Module `fake_filesystem_unittest` contains code that finds all real file functions and modules, and stubs these out with the fake file system functions and modules:

```python

import os
import unittest
import fake_filesystem_unittest
# The module under test is pyfakefs.example
import example```

`example_test.py` defines `load_tests()`, which runs the doctests in `example.py`:

```python

def load_tests(loader, tests, ignore):
'''Load the pyfakefs/example.py doctest tests into unittest.'''
return fake_filesystem_unittest.load_doctests(loader, tests, ignore, example)```

Everything, including all imported modules and the test, is stubbed out with the fake filesystem.  Thus you can use familiar file functions like `os.mkdir()` as part of your test fixture and they too will operate on the fake file system.

Next comes the `unittest` test class.  This class is derived from `fake_filesystem_unittest.TestCase`, which is in turn derived from `unittest.TestClass`:

```python

class TestExample(fake_filesystem_unittest.TestCase):

def setUp(self):
self.setUpPyfakefs()

def tearDown(self):
self.tearDownPyfakefs()

def test_create_file(self):
'''Test example.create_file()'''
# The os module has been replaced with the fake os module so all of the
# following occurs in the fake filesystem.
self.assertFalse(os.path.isdir('/test'))
os.mkdir('/test')
self.assertTrue(os.path.isdir('/test'))

self.assertFalse(os.path.exists('/test/file.txt'))
example.create_file('/test/file.txt')
self.assertTrue(os.path.exists('/test/file.txt'))

...```

Add `self.setUpPyfakefs()` in `setUp()` and `self.tearDownPyfakefs()` in `tearDown()`.  Write your tests as usual.  The file manipulation methods appearing in your test will operate on the fake file system.

### `fs` Reference to the Fake File System
`setUpPyfakefs()` defines attribute `fs`, a reference to the fake file system.  This gives you access to the pyfakefs file system methods and attrbutes, the most useful of which os `CreateFile()`.  It creates directories as required and adds content to the file, all in one convenient method:

```python

self.fs.CreateFile('/test/lots/of/nonexistent/directories/ad/nauseum/full.txt',
contents='First line\n'
'Second Line\n')```

## History

This example is based on a suggestion from David Baird in issue pyfakefs:22.

The original [pyfakefs](https://code.google.com/p/pyfakefs/) code is unchanged.  A pull request to pyfakefs would make more sense than a clone, but  [pull requests are not implemented on Google Code](https://code.google.com/p/support/issues/detail?id=4753).

