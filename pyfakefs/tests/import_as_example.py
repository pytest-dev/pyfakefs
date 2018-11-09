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
from os import path
from os.path import exists
import os as my_os
from os import stat

import sys

try:
    from pathlib import Path
except ImportError:
    try:
        from pathlib2 import Path
    except ImportError:
        Path = None


def check_if_exists1(filepath):
    # test patching module imported under other name
    return my_os.path.exists(filepath)


def check_if_exists2(filepath):
    # tests patching path imported from os
    return path.exists(filepath)


if Path:
    def check_if_exists3(filepath):
        # tests patching Path imported from pathlib
        return Path(filepath).exists()


def check_if_exists4(filepath, exists=my_os.path.exists):
    # this is a similar case as in the tempfile implementation under Posix
    return exists(filepath)


def check_if_exists5(filepath):
    # tests patching `exists` imported from os.path
    return exists(filepath)


def file_stat(filepath):
    # tests patching `stat` imported from os
    return stat(filepath)


def system_stat(filepath):
    if sys.platform == 'win32':
        from nt import stat as system_stat
    else:
        from posix import stat as system_stat
    return system_stat(filepath)
