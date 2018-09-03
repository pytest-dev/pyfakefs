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

try:
    import pathlib
except ImportError:
    try:
        import pathlib2 as pathlib
    except ImportError:
        pathlib = None


def check_if_exists(filepath):
    return my_os.path.exists(filepath)


if pathlib:
    def check_if_path_exists(filepath):
        return pathlib.Path(filepath).exists()
