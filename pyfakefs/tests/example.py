# Copyright 2014 Altera Corporation. All Rights Reserved.
# Author: John McGehee
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

"""
Example module that is tested in :py:class`pyfakefs.example_test.TestExample`.
This demonstrates the usage of the
:py:class`pyfakefs.fake_filesystem_unittest.TestCase` base class.

The modules related to file handling are bound to the respective fake modules:

>>> os     #doctest: +ELLIPSIS
<pyfakefs.fake_filesystem.FakeOsModule object...>
>>> os.path     #doctest: +ELLIPSIS
<pyfakefs.fake_filesystem.FakePathModule object...>
>>> shutil     #doctest: +ELLIPSIS
<pyfakefs.fake_filesystem_shutil.FakeShutilModule object...>

`open()` is an alias for `io.open()` and is bound to `FakeIoModule.open`.
"""

import glob
import os
import shutil

try:
    import scandir
    has_scandir = True
except ImportError:
    scandir = None
    has_scandir = False


def create_file(path):
    """Create the specified file and add some content to it.  Use the `open()`
    built in function.

    For example, the following file operations occur in the fake file system.
    In the real file system, we would not even have permission
    to write `/test`:

    >>> os.path.isdir('/test')
    False
    >>> os.mkdir('/test')
    >>> os.path.isdir('/test')
    True
    >>> os.path.exists('/test/file.txt')
    False
    >>> create_file('/test/file.txt')
    >>> os.path.exists('/test/file.txt')
    True
    >>> with open('/test/file.txt') as f:
    ...     f.readlines()
    ["This is test file '/test/file.txt'.\\n", \
'It was created using open().\\n']
    """
    with open(path, 'w') as f:
        f.write("This is test file '{0}'.\n".format(path))
        f.write("It was created using open().\n")


def delete_file(path):
    """Delete the specified file.

    For example:

    >>> os.mkdir('/test')
    >>> os.path.exists('/test/file.txt')
    False
    >>> create_file('/test/file.txt')
    >>> os.path.exists('/test/file.txt')
    True
    >>> delete_file('/test/file.txt')
    >>> os.path.exists('/test/file.txt')
    False
    """
    os.remove(path)


def path_exists(path):
    """Return True if the specified file exists.

    For example:

    >>> path_exists('/test')
    False
    >>> os.mkdir('/test')
    >>> path_exists('/test')
    True
    >>>
    >>> path_exists('/test/file.txt')
    False
    >>> create_file('/test/file.txt')
    >>> path_exists('/test/file.txt')
    True
    """
    return os.path.exists(path)


def get_glob(glob_path):
    r"""Return the list of paths matching the specified glob expression.

    For example:

    >>> os.mkdir('/test')
    >>> create_file('/test/file1.txt')
    >>> create_file('/test/file2.txt')
    >>> file_names = sorted(get_glob('/test/file*.txt'))
    >>>
    >>> import sys
    >>> if sys.platform.startswith('win'):
    ...     # Windows style path
    ...     file_names == [r'/test\file1.txt', r'/test\file2.txt']
    ... else:
    ...     # UNIX style path
    ...     file_names == ['/test/file1.txt', '/test/file2.txt']
    True
    """
    return glob.glob(glob_path)


def rm_tree(path):
    """Delete the specified file hierarchy."""
    shutil.rmtree(path)


def scan_dir(path):
    """Return a list of directory entries for the given path."""
    if has_scandir:
        return list(scandir.scandir(path))
    return list(os.scandir(path))


def file_contents(path):
    """Return the contents of the given path as byte array."""
    with open(path, 'rb') as f:
        return f.read()
