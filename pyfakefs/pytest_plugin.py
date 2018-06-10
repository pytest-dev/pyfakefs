"""A pytest plugin for using pyfakefs as a fixture

When pyfakefs is installed, the "fs" fixture becomes available.

:Usage:

def my_fakefs_test(fs):
    fs.create_file('/var/data/xx1.txt')
    assert os.path.exists('/var/data/xx1.txt')
"""

import linecache

import py
import pytest

from pyfakefs.fake_filesystem_unittest import Patcher

try:
    import builtins
except ImportError:
    import __builtin__ as builtins

Patcher.SKIPMODULES.add(py)  # Ignore pytest components when faking filesystem

# The "linecache" module is used to read the test file in case of test failure
# to get traceback information before test tear down.
# In order to make sure that reading the test file is not faked,
# we both skip faking the module, and add the build-in open() function
# as a local function in the module
Patcher.SKIPMODULES.add(linecache)
linecache.open = builtins.open


@pytest.fixture
def fs(request):
    """ Fake filesystem. """
    patcher = Patcher()
    patcher.setUp()
    request.addfinalizer(patcher.tearDown)
    return patcher.fs
