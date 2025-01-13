import pytest

from pyfakefs.fake_filesystem_unittest import Patcher
from pyfakefs.fake_pathlib import FakePathlibModule
from pyfakefs.helpers import reload_cleanup_handler
from pyfakefs.pytest_tests import local_import


@pytest.fixture
def test_fs():
    with Patcher() as patcher:
        patcher.cleanup_handlers["pyfakefs.pytest_tests.lib_using_pathlib"] = (
            reload_cleanup_handler
        )
        yield patcher.fs


class TestReloadCleanupHandler:
    def test1(self, test_fs):
        path = local_import.load("some_path")
        assert isinstance(path, FakePathlibModule.Path)

    def test2(self):
        path = local_import.load("some_path")
        # will fail without reload handler
        assert not isinstance(path, FakePathlibModule.Path)
