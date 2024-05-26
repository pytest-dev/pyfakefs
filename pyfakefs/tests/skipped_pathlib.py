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
"""
Provides functions for testing additional_skip_names functionality.
"""

import os
from pathlib import Path


def read_pathlib(file_name):
    return (Path(__file__).parent / file_name).open("r").read()


def read_text_pathlib(file_name):
    return (Path(__file__).parent / file_name).read_text()


def read_bytes_pathlib(file_name):
    return (Path(__file__).parent / file_name).read_bytes()


def read_open(file_name):
    with open(os.path.join(os.path.dirname(__file__), file_name)) as f:
        return f.read()
