import py
import pytest
from fake_filesystem_unittest import _Patcher

_Patcher.SKIPMODULES.add(py)  # Ignore pytest components when faking filesystem


@pytest.yield_fixture
def fs():
    """ Fake filesystem. """
    patcher = _Patcher()
    patcher.setUp()
    yield
    patcher.tearDown()
