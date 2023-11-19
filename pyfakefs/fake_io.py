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

""" Uses :py:class:`FakeIoModule` to provide a
    fake ``io`` module replacement.
"""
import _io  # pytype: disable=import-error
import io
import os
import sys
import traceback
from enum import Enum
from typing import (
    List,
    Optional,
    Callable,
    Union,
    Any,
    AnyStr,
    IO,
    TYPE_CHECKING,
)

from pyfakefs.fake_file import AnyFileWrapper
from pyfakefs.fake_open import FakeFileOpen
from pyfakefs.helpers import IS_PYPY

if TYPE_CHECKING:
    from pyfakefs.fake_filesystem import FakeFilesystem


class PatchMode(Enum):
    """Defines if patching shall be on, off, or in automatic mode.
    Currently only used for `patch_open_code` option.
    """

    OFF = 1
    AUTO = 2
    ON = 3


class FakeIoModule:
    """Uses FakeFilesystem to provide a fake io module replacement.

    You need a fake_filesystem to use this:
    filesystem = fake_filesystem.FakeFilesystem()
    my_io_module = fake_io.FakeIoModule(filesystem)
    """

    @staticmethod
    def dir() -> List[str]:
        """Return the list of patched function names. Used for patching
        functions imported from the module.
        """
        _dir = ["open"]
        if sys.version_info >= (3, 8):
            _dir.append("open_code")
        return _dir

    def __init__(self, filesystem: "FakeFilesystem"):
        """
        Args:
            filesystem: FakeFilesystem used to provide file system information.
        """
        self.filesystem = filesystem
        self.skip_names: List[str] = []
        self._io_module = io

    def open(
        self,
        file: Union[AnyStr, int],
        mode: str = "r",
        buffering: int = -1,
        encoding: Optional[str] = None,
        errors: Optional[str] = None,
        newline: Optional[str] = None,
        closefd: bool = True,
        opener: Optional[Callable] = None,
    ) -> Union[AnyFileWrapper, IO[Any]]:
        """Redirect the call to FakeFileOpen.
        See FakeFileOpen.call() for description.
        """
        # workaround for built-in open called from skipped modules (see #552)
        # as open is not imported explicitly, we cannot patch it for
        # specific modules; instead we check if the caller is a skipped
        # module (should work in most cases)
        stack = traceback.extract_stack(limit=2)
        # handle the case that we try to call the original `open_code`
        # and get here instead (since Python 3.12)
        from_open_code = (
            sys.version_info >= (3, 12)
            and stack[0].name == "open_code"
            and stack[0].line == "return self._io_module.open_code(path)"
        )
        module_name = os.path.splitext(stack[0].filename)[0]
        module_name = module_name.replace(os.sep, ".")
        if from_open_code or any(
            [
                module_name == sn or module_name.endswith("." + sn)
                for sn in self.skip_names
            ]
        ):
            return io.open(  # pytype: disable=wrong-arg-count
                file,
                mode,
                buffering,
                encoding,
                errors,
                newline,
                closefd,
                opener,
            )
        fake_open = FakeFileOpen(self.filesystem)
        return fake_open(
            file, mode, buffering, encoding, errors, newline, closefd, opener
        )

    if sys.version_info >= (3, 8):

        def open_code(self, path):
            """Redirect the call to open. Note that the behavior of the real
            function may be overridden by an earlier call to the
            PyFile_SetOpenCodeHook(). This behavior is not reproduced here.
            """
            if not isinstance(path, str) and not IS_PYPY:
                raise TypeError("open_code() argument 'path' must be str, not int")
            patch_mode = self.filesystem.patch_open_code
            if (
                patch_mode == PatchMode.AUTO
                and self.filesystem.exists(path)
                or patch_mode == PatchMode.ON
            ):
                return self.open(path, mode="rb")
            # mostly this is used for compiled code -
            # don't patch these, as the files are probably in the real fs
            return self._io_module.open_code(path)

    def __getattr__(self, name):
        """Forwards any unfaked calls to the standard io module."""
        return getattr(self._io_module, name)


class FakeIoModule2(FakeIoModule):
    """Similar to ``FakeIoModule``, but fakes `_io` instead of `io`."""

    def __init__(self, filesystem: "FakeFilesystem"):
        """
        Args:
            filesystem: FakeFilesystem used to provide file system information.
        """
        super().__init__(filesystem)
        self._io_module = _io


if sys.platform != "win32":
    import fcntl

    class FakeFcntlModule:
        """Replaces the fcntl module. Only valid under Linux/MacOS,
        currently just mocks the functionality away.
        """

        @staticmethod
        def dir() -> List[str]:
            """Return the list of patched function names. Used for patching
            functions imported from the module.
            """
            return ["fcntl", "ioctl", "flock", "lockf"]

        def __init__(self, filesystem: "FakeFilesystem"):
            """
            Args:
                filesystem: FakeFilesystem used to provide file system
                    information (currently not used).
            """
            self.filesystem = filesystem
            self._fcntl_module = fcntl

        def fcntl(self, fd: int, cmd: int, arg: int = 0) -> Union[int, bytes]:
            return 0 if isinstance(arg, int) else arg

        def ioctl(
            self, fd: int, request: int, arg: int = 0, mutate_flag: bool = True
        ) -> Union[int, bytes]:
            return 0 if isinstance(arg, int) else arg

        def flock(self, fd: int, operation: int) -> None:
            pass

        def lockf(
            self, fd: int, cmd: int, len: int = 0, start: int = 0, whence=0
        ) -> Any:
            pass

        def __getattr__(self, name):
            """Forwards any unfaked calls to the standard fcntl module."""
            return getattr(self._fcntl_module, name)
