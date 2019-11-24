# Copyright 2009 Google Inc. All Rights Reserved.
#
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

"""A fake shutil module implementation that uses fake_filesystem for
unit tests.
Note that only `shutildisk_usage()` is faked, the rest of the functions shall
work fine with the fake file system if `os`/`os.path` are patched.

:Includes:
  FakeShutil: Uses a FakeFilesystem to provide a fake replacement for the
    shutil module.

:Usage:
  The fake implementation is automatically involved if using
  `fake_filesystem_unittest.TestCase`, pytest fs fixture,
  or directly `Patcher`.
"""

import shutil


class FakeShutilModule:
    """Uses a FakeFilesystem to provide a fake replacement for shutil module.
    """

    @staticmethod
    def dir():
        """Return the list of patched function names. Used for patching
        functions imported from the module.
        """
        return 'disk_usage',

    def __init__(self, filesystem):
        """Construct fake shutil module using the fake filesystem.

        Args:
          filesystem:  FakeFilesystem used to provide file system information
        """
        self.filesystem = filesystem
        self._shutil_module = shutil

    def disk_usage(self, path):
        """Return the total, used and free disk space in bytes as named tuple
        or placeholder holder values simulating unlimited space if not set.

        Args:
          path: defines the filesystem device which is queried
        """
        return self.filesystem.get_disk_usage(path)

    def __getattr__(self, name):
        """Forwards any non-faked calls to the standard shutil module."""
        return getattr(self._shutil_module, name)
