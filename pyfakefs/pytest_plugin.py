"""A pytest plugin for using pyfakefs as a fixture

When pyfakefs is installed, the "fs" fixture becomes available.

:Usage:

def my_fakefs_test(fs):
    fs.create_file('/var/data/xx1.txt')
    assert os.path.exists('/var/data/xx1.txt')
"""

import linecache
import tokenize

import py
import pytest

from pyfakefs.fake_filesystem_unittest import Patcher

Patcher.SKIPMODULES.add(pytest)
Patcher.SKIPMODULES.add(py)  # Ignore pytest components when faking filesystem

# The "linecache" module is used to read the test file in case of test failure
# to get traceback information before test tear down.
# In order to make sure that reading the test file is not faked,
# we both skip faking the module, and add the build-in open() function
# as a local function in the module (used in Python 2).
# In Python 3, we also have to set back the cached open function in tokenize.
Patcher.SKIPMODULES.add(linecache)
Patcher.SKIPMODULES.add(tokenize)


@pytest.fixture
def fs():
    """ Fake filesystem. """
    patcher = Patcher()
    patcher.setUp()
    linecache.open = patcher.original_open
    tokenize._builtin_open = patcher.original_open
    yield patcher.fs
    patcher.tearDown()
