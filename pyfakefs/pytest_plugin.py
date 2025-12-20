"""A pytest plugin for using pyfakefs as a fixture

When pyfakefs is installed, the "fs" fixture becomes available.

:Usage:

def my_fakefs_test(fs):
    fs.create_file('/var/data/xx1.txt')
    assert os.path.exists('/var/data/xx1.txt')
"""

import contextlib

import pytest
from _pytest import capture

from pyfakefs.fake_filesystem_unittest import Patcher, Pause

try:
    from _pytest import pathlib

    Patcher.SKIPMODULES.add(pathlib)
except ImportError:
    pass

try:
    from coverage import python  # type:ignore[import]

    Patcher.SKIPMODULES.add(python)
except ImportError:
    pass

try:
    import py

    Patcher.SKIPMODULES.add(py)
except ImportError:
    pass

Patcher.SKIPMODULES.add(pytest)
Patcher.SKIPMODULES.add(capture)


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


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    """Make sure that the cache is cleared before the final test shutdown."""
    Patcher.clear_fs_cache()


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_logreport(report):
    """Make sure that patching is not active during reporting."""
    pause = Patcher.PATCHER is not None and Patcher.PATCHER.is_patching
    context_mgr = Pause(Patcher.PATCHER) if pause else contextlib.nullcontext()
    with context_mgr:
        yield
    if pause and report.when == "teardown":
        # if we get here, we are not in a function scope fixture
        # in this case, we still want to pause patching between the tests
        Patcher.PATCHER.pause()


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    # resume patcher if not in a function scope
    if Patcher.PATCHER is not None:
        Patcher.PATCHER.resume()
