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
from pathlib import Path

import pytest


@pytest.fixture
def report_path():
    yield Path(__file__).parent / "report.txt"


def test_1(fs):
    pass


def test_2_report_in_real_fs(report_path):
    print("test_2_report_in_real_fs")
    assert report_path.exists()
    report_path.unlink()


def test_3(fs):
    pass


def test_4_report_in_real_fs(report_path):
    assert report_path.exists()
    report_path.unlink()
