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

import functools
import os
import shutil
import sys
from threading import RLock
from collections.abc import Callable


class FakeShutilModule:
    """Uses a FakeFilesystem to provide a fake replacement
    for shutil module.

    Automatically created if using `fake_filesystem_unittest.TestCase`,
    the `fs` fixture, the `patchfs` decorator, or directly the `Patcher`.
    """

    module_lock = RLock()

    use_copy_file_range = (
        hasattr(shutil, "_USE_CP_COPY_FILE_RANGE") and shutil._USE_CP_COPY_FILE_RANGE  # type: ignore[attr-defined]
    )
    has_fcopy_file = hasattr(shutil, "_HAS_FCOPYFILE") and shutil._HAS_FCOPYFILE  # type: ignore[attr-defined]
    use_sendfile = hasattr(shutil, "_USE_CP_SENDFILE") and shutil._USE_CP_SENDFILE  # type: ignore[attr-defined]
    use_fd_functions = shutil._use_fd_functions  # type: ignore[attr-defined]
    functions_to_patch = ["copy", "copyfile", "rmtree"]
    if sys.version_info < (3, 12) or sys.platform != "win32":
        functions_to_patch.extend(["copy2", "copytree", "move"])

    @staticmethod
    def dir():
        """Return the list of patched function names. Used for patching
        functions imported from the module.
        """
        return ("disk_usage",)

    def __init__(self, filesystem):
        """Construct fake shutil module using the fake filesystem.

        Args:
          filesystem:  FakeFilesystem used to provide file system information
        """
        self.filesystem = filesystem
        self.shutil_module = shutil
        self._patch_level = 0

    def _start_patching_global_vars(self):
        self._patch_level += 1
        if self._patch_level > 1:
            return  # nested call - already patched
        if self.has_fcopy_file:
            self.shutil_module._HAS_FCOPYFILE = False
        if self.use_copy_file_range:
            self.shutil_module._USE_CP_COPY_FILE_RANGE = False
        if self.use_sendfile:
            self.shutil_module._USE_CP_SENDFILE = False
        if self.use_fd_functions:
            if sys.version_info >= (3, 14):
                self.shutil_module._rmtree_impl = (
                    self.shutil_module._rmtree_unsafe  # type: ignore[attr-defined]
                )
            else:
                self.shutil_module._use_fd_functions = False

    def _stop_patching_global_vars(self):
        self._patch_level -= 1
        if self._patch_level > 0:
            return  # nested call - remains patched
        if self.has_fcopy_file:
            self.shutil_module._HAS_FCOPYFILE = True
        if self.use_copy_file_range:
            self.shutil_module._USE_CP_COPY_FILE_RANGE = True
        if self.use_sendfile:
            self.shutil_module._USE_CP_SENDFILE = True
        if self.use_fd_functions:
            if sys.version_info >= (3, 14):
                self.shutil_module._rmtree_impl = (
                    self.shutil_module._rmtree_safe_fd  # type: ignore[attr-defined]
                )
            else:
                self.shutil_module._use_fd_functions = True

    def with_patched_globals(self, f: Callable) -> Callable:
        """Function wrapper that patches global variables during function execution.
        Can be used in multi-threading code.
        """

        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            with self.module_lock:
                self._start_patching_global_vars()
                try:
                    return f(*args, **kwargs)
                finally:
                    self._stop_patching_global_vars()

        return wrapped

    def disk_usage(self, path):
        """Return the total, used and free disk space in bytes as named tuple
        or placeholder holder values simulating unlimited space if not set.

        Args:
          path: defines the filesystem device which is queried
        """
        return self.filesystem.get_disk_usage(path)

    if sys.version_info >= (3, 12) and sys.platform == "win32":

        def copy2(self, src, dst, *, follow_symlinks=True):
            """Since Python 3.12, there is an optimization fow Windows,
            using the Windows API. We just remove this and fall back to the previous
            implementation.
            """
            if self.filesystem.isdir(dst):
                dst = self.filesystem.joinpaths(dst, os.path.basename(src))

            self.copyfile(src, dst, follow_symlinks=follow_symlinks)
            self.copystat(src, dst, follow_symlinks=follow_symlinks)
            return dst

        def copytree(
            self,
            src,
            dst,
            symlinks=False,
            ignore=None,
            copy_function=shutil.copy2,
            ignore_dangling_symlinks=False,
            dirs_exist_ok=False,
        ):
            """Make sure the default argument is patched."""
            if copy_function == shutil.copy2:
                copy_function = self.copy2
            return self.shutil_module.copytree(
                src,
                dst,
                symlinks,
                ignore,
                copy_function,
                ignore_dangling_symlinks,
                dirs_exist_ok,
            )

        def move(self, src, dst, copy_function=shutil.copy2):
            """Make sure the default argument is patched."""
            if copy_function == shutil.copy2:
                copy_function = self.copy2
            return self.shutil_module.move(src, dst, copy_function)

    def __getattr__(self, name):
        """Forwards any non-faked calls to the standard shutil module."""
        if name in self.functions_to_patch:
            return self.with_patched_globals(getattr(self.shutil_module, name))
        return getattr(self.shutil_module, name)
