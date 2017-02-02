"""A pytest plugin for using pyfakefs as a fixture

When pyfakefs is installed, the "fs" fixture becomes avaialable.

:Usage:

def my_fakefs_test(fs):
    fs.CreateFile('/var/data/xx1.txt')
    assert os.path.exists('/var/data/xx1.txt')
"""
import py
import pytest
from pyfakefs.fake_filesystem_unittest import Patcher


Patcher.SKIPMODULES.add(py)  # Ignore pytest components when faking filesystem


@pytest.yield_fixture
def fs():
    """ Fake filesystem. """
    patcher = Patcher()
    patcher.setUp()
    yield patcher.fs
    patcher.tearDown()
