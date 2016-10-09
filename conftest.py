import py
import pytest
from pyfakefs.fake_filesystem_unittest import Patcher


Patcher.SKIPMODULES.add(py)  # Ignore pytest components when faking filesystem


@pytest.yield_fixture
def fs():
    """ Fake filesystem. """
    patcher = Patcher()
    patcher.setUp()
    yield
    patcher.tearDown()
