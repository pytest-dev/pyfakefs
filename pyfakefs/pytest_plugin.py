"""A pytest plugin for using pyfakefs as a fixture

When pyfakefs is installed, the "fs" fixture becomes available.

:Usage:

def my_fakefs_test(fs):
    fs.create_file('/var/data/xx1.txt')
    assert os.path.exists('/var/data/xx1.txt')
"""

import pytest

from pyfakefs.fake_filesystem_unittest import Patcher


@pytest.fixture
def fs(request):
    """ Fake filesystem. """
    if hasattr(request, 'param'):
        # pass optional parameters via @pytest.mark.parametrize
        patcher = Patcher(*request.param)
    else:
        patcher = Patcher()
    patcher.setUp()
    yield patcher.fs
    patcher.tearDown()
