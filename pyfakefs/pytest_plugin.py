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
# we skip faking the module.
# We also have to set back the cached open function in tokenize.
Patcher.SKIPMODULES.add(linecache)
Patcher.SKIPMODULES.add(tokenize)


@pytest.fixture
def fs(request):
    """ Fake filesystem. """
    if hasattr(request, 'param'):
        # pass optional parameters via @pytest.mark.parametrize
        patcher = Patcher(*request.param)
    else:
        patcher = Patcher()
    patcher.setUp()
    tokenize._builtin_open = patcher.original_open
    yield patcher.fs
    patcher.tearDown()
