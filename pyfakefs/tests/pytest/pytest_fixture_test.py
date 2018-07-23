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

# Example for a test using a custom pytest fixture with an argument to Patcher
# Needs Python >= 3.6

import pytest

import pyfakefs.tests.pytest.example as example


@pytest.mark.xfail
def test_example_file_failing(fs):
    """Test fails because EXAMPLE_FILE is cached in the module
    and not patched."""
    fs.create_file(
        example.EXAMPLE_FILE, contents='stuff here')

    with open(example.EXAMPLE_FILE) as file:
        assert file.read() == 'stuff here'

    with example.EXAMPLE_FILE.open() as file:
        assert file.read() == 'stuff here'

    assert example.EXAMPLE_FILE.read_text() == 'stuff here'
    assert example.EXAMPLE_FILE.is_file()


def test_example_file_passing(fs_reload_example):
    """Test passes if using a fixture that reloads the module containing
    EXAMPLE_FILE"""
    fs_reload_example.create_file(
        example.EXAMPLE_FILE, contents='stuff here')

    with open(example.EXAMPLE_FILE) as file:
        assert file.read() == 'stuff here'

    with example.EXAMPLE_FILE.open() as file:
        assert file.read() == 'stuff here'

    assert example.EXAMPLE_FILE.read_text() == 'stuff here'
    assert example.EXAMPLE_FILE.is_file()
