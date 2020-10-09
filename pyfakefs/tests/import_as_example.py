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
Example module that is used for testing modules that import file system modules
to be patched under another name.
"""
import os as my_os
import pathlib
import sys
from builtins import open as bltn_open
from io import open as io_open
from os import path
from os import stat
from os import stat as my_stat
from os.path import exists
from os.path import exists as my_exists
from pathlib import Path


def check_if_exists1(filepath):
    # test patching module imported under other name
    return my_os.path.exists(filepath)


def check_if_exists2(filepath):
    # tests patching path imported from os
    return path.exists(filepath)


def check_if_exists3(filepath):
    # tests patching Path imported from pathlib
    return Path(filepath).exists()


def check_if_exists4(filepath, file_exists=my_os.path.exists):
    return file_exists(filepath)


def check_if_exists5(filepath):
    # tests patching `exists` imported from os.path
    return exists(filepath)


def check_if_exists6(filepath):
    # tests patching `exists` imported from os.path as other name
    return my_exists(filepath)


def check_if_exists7(filepath):
    # tests patching pathlib
    return pathlib.Path(filepath).exists()


def file_stat1(filepath):
    # tests patching `stat` imported from os
    return stat(filepath)


def file_stat2(filepath):
    # tests patching `stat` imported from os as other name
    return my_stat(filepath)


def system_stat(filepath):
    if sys.platform == 'win32':
        from nt import stat as system_stat
    else:
        from posix import stat as system_stat
    return system_stat(filepath)


def file_contents1(filepath):
    with bltn_open(filepath) as f:
        return f.read()


def file_contents2(filepath):
    with io_open(filepath) as f:
        return f.read()


def exists_this_file():
    """Returns True in real fs only"""
    return exists(__file__)


def open_this_file():
    """Works only in real fs"""
    with open(__file__):
        pass


def return_this_file_path():
    """Works only in real fs"""
    return Path(__file__)


class TestDefaultArg:
    def check_if_exists(self, filepath, file_exists=my_os.path.exists):
        # this is a similar case as in the tempfile implementation under Posix
        return file_exists(filepath)
