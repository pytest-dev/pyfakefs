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
import os

import pytest


@pytest.fixture(scope='module', autouse=True)
def use_fs(fs_module):
    fs_module.create_file(os.path.join('foo', 'bar'))
    yield fs_module


def test_fs_uses_fs_module(fs):
    # check that `fs` uses the same filesystem as `fs_module`
    assert os.path.exists(os.path.join('foo', 'bar'))
