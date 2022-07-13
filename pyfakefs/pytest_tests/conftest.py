# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Example for a custom pytest fixture with an argument to Patcher.
# Use this as a template if you want to write your own pytest plugin
# with specific Patcher arguments.
# See `pytest_plugin.py` for more information.

import pytest

from pyfakefs.fake_filesystem_unittest import Patcher

# import the fs fixture to be visible if pyfakefs is not installed
from pyfakefs.pytest_plugin import fs, fs_module  # noqa: F401

from pyfakefs.pytest_tests import example  # noqa: E402


@pytest.fixture
def fs_reload_example():
    """ Fake filesystem. """
    patcher = Patcher(modules_to_reload=[example])
    patcher.setUp()
    yield patcher.fs
    patcher.tearDown()


@pytest.fixture
def fake_filesystem(fs):  # noqa: F811
    """Shows how to use an alias for the fs fixture."""
    yield fs
