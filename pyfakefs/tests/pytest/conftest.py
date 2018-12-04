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
# See `pytest_plugin.py` for more information.

import linecache
import tokenize

import py
import pytest

from pyfakefs.fake_filesystem_unittest import Patcher

Patcher.SKIPMODULES.add(py)
Patcher.SKIPMODULES.add(linecache)

from pyfakefs.fake_filesystem_unittest import Patcher
from pyfakefs.tests.pytest import example


@pytest.fixture
def fs_reload_example(request):
    """ Fake filesystem. """
    patcher = Patcher(modules_to_reload=[example])
    patcher.setUp()
    linecache.open = patcher.original_open
    tokenize._builtin_open = patcher.original_open
    request.addfinalizer(patcher.tearDown)
    return patcher.fs
