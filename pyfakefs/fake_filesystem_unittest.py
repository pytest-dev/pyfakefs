# Copyright 2014 Altera Corporation. All Rights Reserved.
# Copyright 2015-2017 John McGehee
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

"""A base class for unit tests using the :py:class:`pyfakefs` module.

This class searches `sys.modules` for modules that import the `os`, `io`,
`path`, and `tempfile` modules.

The `setUp()` method binds these modules to the corresponding fake
modules from `pyfakefs`.  Further, the built in functions `file()` and
`open()` are bound to fake functions.

The `tearDownPyfakefs()` method returns the module bindings to their original
state.

It is expected that `setUp()` be invoked at the beginning of the derived
class' `setUp()` method, and `tearDownPyfakefs()` be invoked at the end of the
derived class' `tearDown()` method.

During the test, everything uses the fake file system and modules.  This means
that even in your test, you can use familiar functions like `open()` and
`os.makedirs()` to manipulate the fake file system.

This also means existing unit tests that use the real file system can be
retrofitted to use `pyfakefs` by simply changing their base class from
`:py:class`unittest.TestCase` to
`:py:class`pyfakefs.fake_filesystem_unittest.TestCase`.
"""

import os
import sys
import doctest
import inspect

import mox3.stubout

from pyfakefs import fake_filesystem
from pyfakefs import fake_filesystem_shutil
from pyfakefs import fake_tempfile
if sys.version_info >= (3, 4):
    from pyfakefs import fake_pathlib

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

if sys.version_info < (3,):
    import __builtin__ as builtins  # pylint: disable=import-error
else:
    import builtins

REAL_OPEN = builtins.open
"""The real (not faked) `open` builtin."""
REAL_OS = os
"""The real (not faked) `os` module."""


def load_doctests(loader, tests, ignore, module):  # pylint: disable=unused-argument
    """Load the doctest tests for the specified module into unittest."""
    _patcher = Patcher()
    globs = _patcher.replaceGlobs(vars(module))
    tests.addTests(doctest.DocTestSuite(module,
                                        globs=globs,
                                        setUp=_patcher.setUp,
                                        tearDown=_patcher.tearDown))
    return tests


class TestCase(unittest.TestCase):
    """Test case class that automatically replaces file-system related
    modules by fake implementations.
    """

    def __init__(self, methodName='runTest', additional_skip_names=None, patch_path=True):
        """Creates the test class instance and the stubber used to stub out
        file system related modules.

        Args:
            methodName: the name of the test method (as in unittest.TestCase)
            additional_skip_names: names of modules inside of which no module replacement
                shall be done
                (additionally to the hard-coded list: 'os', 'glob', 'path', 'tempfile', 'io')
            patch_path: if False, modules named 'path' will not be patched with the
                fake 'os.path' module. Set this to False when you need to import
                some other module named 'path', for example,
                   `from my_module import path`
               Irrespective of patch_path, module 'os.path' is still correctly faked
               if imported the usual way using `import os` or `import os.path`.

          Example usage in a derived test class:

          class MyTestCase(fake_filesystem_unittest.TestCase):
            def __init__(self, methodName='runTest'):
              super(MyTestCase, self).__init__(
                    methodName=methodName, additional_skip_names=['posixpath'])
        """
        super(TestCase, self).__init__(methodName)
        self._stubber = Patcher(additional_skip_names=additional_skip_names,
                                patch_path=patch_path)

    @property
    def fs(self):
        return self._stubber.fs

    @property
    def patches(self):
        return self._stubber.patches

    def CopyRealFile(self, real_file_path, fake_file_path=None,
                     create_missing_dirs=True):
        """Copy the file `real_file_path` from the real file system to the fake
        file system file `fake_file_path`.

        This is a helper method you can use to set up your test more easily.

        The permissions, gid, uid, ctime, mtime and atime of the real file are
        copied to the fake file.  nlink, dev, and inode are not copied because
        their values depend on the fake file system, not the real file system
        from which the file was copied.

        Args:
          real_file_path: Path to the source file in the real file system.
          fake_file_path: path to the destination file in the fake file system.
          create_missing_dirs: if True, auto create missing directories.

        Returns:
          The newly created FakeFile object.

        Raises:
          IOError: if the file already exists.
          IOError: if the containing directory is required and missing.
        """
        real_stat = REAL_OS.stat(real_file_path)
        with REAL_OPEN(real_file_path, 'rb') as real_file:
            real_contents = real_file.read()
        fake_file = self.fs.CreateFile(fake_file_path, st_mode=real_stat.st_mode,
                                    contents=real_contents,
                                    create_missing_dirs=create_missing_dirs)
        fake_file.st_ctime = real_stat.st_ctime
        fake_file.st_atime = real_stat.st_atime
        fake_file.st_mtime = real_stat.st_mtime
        fake_file.st_gid = real_stat.st_gid
        fake_file.st_uid = real_stat.st_uid
        return fake_file

    def setUpPyfakefs(self):
        """Bind the file-related modules to the :py:class:`pyfakefs` fake file
        system instead of the real file system.  Also bind the fake `file()` and
        `open()` functions.

        Invoke this at the beginning of the `setUp()` method in your unit test
        class.
        """
        self._stubber.setUp()
        self.addCleanup(self._stubber.tearDown)

    def tearDownPyfakefs(self):
        """:meth:`pyfakefs.fake_filesystem_unittest.setUpPyfakefs` registers the
        tear down procedure using :py:meth:`unittest.TestCase.addCleanup`.  Thus this
        method is deprecated, and remains just for backward compatibility.
        """
        pass


class Patcher(object):
    """
    Instantiate a stub creator to bind and un-bind the file-related modules to
    the :py:mod:`pyfakefs` fake modules.
    For usage outside of TestCase (for example with pytest) use:
    >>> with Patcher():
    >>>     doStuff()
    """
    SKIPMODULES = set([None, fake_filesystem, fake_filesystem_shutil,
                       fake_tempfile, sys])
    '''Stub nothing that is imported within these modules.
    `sys` is included to prevent `sys.path` from being stubbed with the fake
    `os.path`.
    '''
    assert None in SKIPMODULES, "sys.modules contains 'None' values; must skip them."

    HAS_PATHLIB = sys.version_info >= (3, 4)

    # To add py.test support per issue https://github.com/jmcgeheeiv/pyfakefs/issues/43,
    # it appears that adding  'py', 'pytest', '_pytest' to SKIPNAMES will help
    SKIPNAMES = set(['os', 'path', 'tempfile', 'io'])
    if HAS_PATHLIB:
        SKIPNAMES.add('pathlib')

    def __init__(self, additional_skip_names=None, patch_path=True):
        """For a description of the arguments, see TestCase.__init__"""

        self._skipNames = self.SKIPNAMES.copy()
        if additional_skip_names is not None:
            self._skipNames.update(additional_skip_names)
        self._patchPath = patch_path
        if not patch_path:
            self._skipNames.discard('path')

        # Attributes set by _findModules()
        self._os_modules = None
        self._path_modules = None
        if self.HAS_PATHLIB:
            self._pathlib_modules = None
        self._shutil_modules = None
        self._tempfile_modules = None
        self._io_modules = None
        self._findModules()
        assert None not in vars(self).values(), \
            "_findModules() missed the initialization of an instance variable"

        # Attributes set by _refresh()
        self._stubs = None
        self.fs = None
        self.fake_os = None
        self.fake_path = None
        if self.HAS_PATHLIB:
            self.fake_pathlib = None
        self.fake_shutil = None
        self.fake_tempfile_ = None
        self.fake_open = None
        self.fake_io = None
        # _isStale is set by tearDown(), reset by _refresh()
        self._isStale = True
        self._refresh()
        assert None not in vars(self).values(), \
            "_refresh() missed the initialization of an instance variable"
        assert self._isStale == False, "_refresh() did not reset _isStale"

    def __enter__(self):
        """Context manager for usage outside of fake_filesystem_unittest.TestCase.
        Ensure that all patched modules are removed in case of an unhandled exception.
        """
        self.setUp()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.tearDown()

    def _findModules(self):
        """Find and cache all modules that import file system modules.
        Later, `setUp()` will stub these with the fake file system
        modules.
        """
        self._os_modules = set()
        self._path_modules = set()
        if self.HAS_PATHLIB:
            self._pathlib_modules = set()
        self._shutil_modules = set()
        self._tempfile_modules = set()
        self._io_modules = set()
        for name, module in set(sys.modules.items()):
            if (module in self.SKIPMODULES or
                    (not inspect.ismodule(module)) or
                    name.split('.')[0] in self._skipNames):
                continue
            if 'os' in module.__dict__:
                self._os_modules.add(module)
            if self._patchPath and 'path' in module.__dict__:
                self._path_modules.add(module)
            if self.HAS_PATHLIB and 'pathlib' in module.__dict__:
                self._pathlib_modules.add(module)
            if 'shutil' in module.__dict__:
                self._shutil_modules.add(module)
            if 'tempfile' in module.__dict__:
                self._tempfile_modules.add(module)
            if 'io' in module.__dict__:
                self._io_modules.add(module)

    def _refresh(self):
        """Renew the fake file system and set the _isStale flag to `False`."""
        if self._stubs is not None:
            self._stubs.SmartUnsetAll()
        self._stubs = mox3.stubout.StubOutForTesting()

        self.fs = fake_filesystem.FakeFilesystem()
        self.fake_os = fake_filesystem.FakeOsModule(self.fs)
        self.fake_path = self.fake_os.path
        if self.HAS_PATHLIB:
            self.fake_pathlib = fake_pathlib.FakePathlibModule(self.fs)
        self.fake_shutil = fake_filesystem_shutil.FakeShutilModule(self.fs)
        self.fake_tempfile_ = fake_tempfile.FakeTempfileModule(self.fs)
        self.fake_open = fake_filesystem.FakeFileOpen(self.fs)
        self.fake_io = fake_filesystem.FakeIoModule(self.fs)

        self._isStale = False

    def setUp(self, doctester=None):
        """Bind the file-related modules to the :py:mod:`pyfakefs` fake
        modules real ones.  Also bind the fake `file()` and `open()` functions.
        """
        self._refresh()

        if doctester is not None:
            doctester.globs = self.replaceGlobs(doctester.globs)

        if sys.version_info < (3,):
            # file() was eliminated in Python3
            self._stubs.SmartSet(builtins, 'file', self.fake_open)
        self._stubs.SmartSet(builtins, 'open', self.fake_open)

        for module in self._os_modules:
            self._stubs.SmartSet(module, 'os', self.fake_os)
        for module in self._path_modules:
            self._stubs.SmartSet(module, 'path', self.fake_path)
        if self.HAS_PATHLIB:
            for module in self._pathlib_modules:
                self._stubs.SmartSet(module, 'pathlib', self.fake_pathlib)
        for module in self._shutil_modules:
            self._stubs.SmartSet(module, 'shutil', self.fake_shutil)
        for module in self._tempfile_modules:
            self._stubs.SmartSet(module, 'tempfile', self.fake_tempfile_)
        for module in self._io_modules:
            self._stubs.SmartSet(module, 'io', self.fake_io)

    def replaceGlobs(self, globs_):
        globs = globs_.copy()
        if self._isStale:
            self._refresh()
        if 'os' in globs:
            globs['os'] = fake_filesystem.FakeOsModule(self.fs)
        if 'path' in globs:
            fake_os = globs['os'] if 'os' in globs \
                else fake_filesystem.FakeOsModule(self.fs)
            globs['path'] = fake_os.path
        if 'shutil' in globs:
            globs['shutil'] = fake_filesystem_shutil.FakeShutilModule(self.fs)
        if 'tempfile' in globs:
            globs['tempfile'] = fake_tempfile.FakeTempfileModule(self.fs)
        if 'io' in globs:
            globs['io'] = fake_filesystem.FakeIoModule(self.fs)
        return globs

    def tearDown(self, doctester=None):
        """Clear the fake filesystem bindings created by `setUp()`."""
        self._isStale = True
        self._stubs.SmartUnsetAll()
