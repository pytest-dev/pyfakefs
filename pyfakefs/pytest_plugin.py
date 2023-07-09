"""A pytest plugin for using pyfakefs as a fixture

When pyfakefs is installed, the "fs" fixture becomes available.

:Usage:

def my_fakefs_test(fs):
    fs.create_file('/var/data/xx1.txt')
    assert os.path.exists('/var/data/xx1.txt')
"""
import py
import pytest
from _pytest import capture

from pyfakefs.fake_filesystem_unittest import Patcher

try:
    from _pytest import pathlib
except ImportError:
    pathlib = None

Patcher.SKIPMODULES.add(py)
Patcher.SKIPMODULES.add(pytest)
Patcher.SKIPMODULES.add(capture)
if pathlib is not None:
    Patcher.SKIPMODULES.add(pathlib)


@pytest.fixture
def fs(request):
    """Fake filesystem."""
    if hasattr(request, "param"):
        # pass optional parameters via @pytest.mark.parametrize
        patcher = Patcher(*request.param)
    else:
        patcher = Patcher()
    patcher.setUp()
    yield patcher.fs
    patcher.tearDown()


@pytest.fixture(scope="class")
def fs_class(request):
    """Class-scoped fake filesystem fixture."""
    if hasattr(request, "param"):
        patcher = Patcher(*request.param)
    else:
        patcher = Patcher()
    patcher.setUp()
    yield patcher.fs
    patcher.tearDown()


@pytest.fixture(scope="module")
def fs_module(request):
    """Module-scoped fake filesystem fixture."""
    if hasattr(request, "param"):
        patcher = Patcher(*request.param)
    else:
        patcher = Patcher()
    patcher.setUp()
    yield patcher.fs
    patcher.tearDown()


@pytest.fixture(scope="session")
def fs_session(request):
    """Session-scoped fake filesystem fixture."""
    if hasattr(request, "param"):
        patcher = Patcher(*request.param)
    else:
        patcher = Patcher()
    patcher.setUp()
    yield patcher.fs
    patcher.tearDown()
