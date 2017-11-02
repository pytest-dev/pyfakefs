# Copyright 2014 Altera Corporation. All Rights Reserved.
# Copyright 2015-2017 John McGehee
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

"""This module provides a base class derived from `unittest.TestClass`
for unit tests using the :py:class:`pyfakefs` module.

`fake_filesystem_unittest.TestCase` searches `sys.modules` for modules
that import the `os`, `io`, `path` `shutil`, and `pathlib` modules.

The `setUpPyfakefs()` method binds these modules to the corresponding fake
modules from `pyfakefs`.  Further, the `open()` built-in is bound to a fake
`open()`.  In Python 2, built-in `file()` is similarly bound to the fake
`open()`.

It is expected that `setUpPyfakefs()` be invoked at the beginning of the derived
class' `setUp()` method.  There is no need to add anything to the derived
class' `tearDown()` method.

During the test, everything uses the fake file system and modules.  This means
that even in your test fixture, familiar functions like `open()` and
`os.makedirs()` manipulate the fake file system.

Existing unit tests that use the real file system can be retrofitted to use
pyfakefs by simply changing their base class from `:py:class`unittest.TestCase`
to `:py:class`pyfakefs.fake_filesystem_unittest.TestCase`.
"""
import doctest
import importlib
import inspect
import shutil
import sys
import tempfile

try:
    from importlib.machinery import ModuleSpec
except ImportError:
    ModuleSpec = object

try:
    # python >= 3.4
    from importlib import reload
except ImportError:
    try:
        # python 3.0 - 3.3
        from imp import reload
    except ImportError:
        # python 2 - reload is built-in
        pass

from pyfakefs import fake_filesystem
from pyfakefs import fake_filesystem_shutil
from pyfakefs import mox3_stubout

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


def load_doctests(loader, tests, ignore, module,
                  additional_skip_names=None,
                  patch_path=True, special_names=None):  # pylint: disable=unused-argument
    """Load the doctest tests for the specified module into unittest.
        Args:
            loader, tests, ignore : arguments passed in from `load_tests()`
            module: module under test 
            additional_skip_names: see :py:class:`TestCase` for an explanation
            patch_path: see :py:class:`TestCase` for an explanation

    File `example_test.py` in the pyfakefs release provides a usage example.
    """
    _patcher = Patcher(additional_skip_names=additional_skip_names,
                       patch_path=patch_path, special_names=special_names)
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

    def __init__(self, methodName='runTest', additional_skip_names=None,
                 patch_path=True, special_names=None,
                 modules_to_reload=None,
                 use_dynamic_patch=False):
        """Creates the test class instance and the stubber used to stub out
        file system related modules.

        Args:
            methodName: the name of the test method (same as unittest.TestCase)
            additional_skip_names: names of modules inside of which no module
                replacement shall be performed, in addition to the names in
                attribute :py:attr:`fake_filesystem_unittest.Patcher.SKIPNAMES`.
            patch_path: if False, modules named 'path' will not be patched with the
                fake 'os.path' module. Set this to False when you need to import
                some other module named 'path', for example::
                    from my_module import path

                Irrespective of patch_path, module 'os.path' is still correctly faked
                if imported the usual way using `import os` or `import os.path`.
            special_names: A dictionary with module names as key and a dictionary as
                value, where the key is the original name of the module to be patched,
                and the value is the name as it is imported.
                This allows to patch modules where some of the file system modules are
                imported as another name (e.g. `import os as _os`).
            modules_to_reload (experimental): A list of modules that need to be reloaded
                to be patched dynamically; may be needed if the module
                imports file system modules under an alias
                Note: this is done independently of `use_dynamic_patch`
                Caution: this may not work with some Python versions
                or have unwanted side effects.
            use_dynamic_patch (experimental): If `True`, dynamic patching
                after setup is used (for example for modules loaded locally
                inside of functions).
                Caution: this may not work with some Python versions
                or have unwanted side effects.

        If you specify arguments `additional_skip_names` or `patch_path` here
        and you have DocTests, consider also specifying the same arguments to
        :py:func:`load_doctests`.
        
        Example usage in derived test classes::

            class MyTestCase(fake_filesystem_unittest.TestCase):
                def __init__(self, methodName='runTest'):
                    super(MyTestCase, self).__init__(
                        methodName=methodName, additional_skip_names=['posixpath'])


            class AnotherTestCase(fake_filesystem_unittest.TestCase):
                def __init__(self, methodName='runTest'):
                    # allow patching a module that imports `os` as `my_os`
                    special_names = {'amodule': {'os': 'my_os'}}
                    super(MyTestCase, self).__init__(
                        methodName=methodName, special_names=special_names)
        """
        super(TestCase, self).__init__(methodName)
        self._stubber = Patcher(additional_skip_names=additional_skip_names,
                                patch_path=patch_path,
                                special_names=special_names)
        self._modules_to_reload = modules_to_reload or []
        self._use_dynamic_patch = use_dynamic_patch

    @property
    def fs(self):
        return self._stubber.fs

    @property
    def patches(self):
        return self._stubber.patches

    def copyRealFile(self, real_file_path, fake_file_path=None,
                     create_missing_dirs=True):
        """Add the file `real_file_path` in the real file system to the same
        path in the fake file system.

        **This method is deprecated** in favor of :py:meth:`FakeFilesystem..add_real_file`.
        `copyRealFile()` is retained with limited functionality for backward
        compatability only.

        Args:
          real_file_path: Path to the file in both the real and fake file systems
          fake_file_path: Deprecated.  Use the default, which is `real_file_path`.
            If a value other than `real_file_path` is specified, an `ValueError`
            exception will be raised.  
          create_missing_dirs: Deprecated.  Use the default, which creates missing
            directories in the fake file system.  If `False` is specified, an
            `ValueError` exception is raised.

        Returns:
          The newly created FakeFile object.

        Raises:
          IOError: If the file already exists in the fake file system.
          ValueError: If deprecated argument values are specified

        See:
          :py:meth:`FakeFileSystem.add_real_file`
        """
        if fake_file_path is not None and real_file_path != fake_file_path:
            raise ValueError("CopyRealFile() is deprecated and no longer supports "
                             "different real and fake file paths")
        if not create_missing_dirs:
            raise ValueError("CopyRealFile() is deprecated and no longer supports "
                             "NOT creating missing directories")
        return self._stubber.fs.add_real_file(real_file_path, read_only=False)

    def setUpPyfakefs(self):
        """Bind the file-related modules to the :py:class:`pyfakefs` fake file
        system instead of the real file system.  Also bind the fake `open()`
        function, and on Python 2, the `file()` function.

        Invoke this at the beginning of the `setUp()` method in your unit test
        class.
        """
        self._stubber.setUp()
        self.addCleanup(self._stubber.tearDown)
        dyn_patcher = DynamicPatcher(self._stubber)
        sys.meta_path.insert(0, dyn_patcher)
        for module in self._modules_to_reload:
            if module.__name__ in sys.modules:
                reload(module)
        if self._use_dynamic_patch:
            self.addCleanup(lambda: sys.meta_path.pop(0))
        else:
            sys.meta_path.pop(0)

    def tearDownPyfakefs(self):
        """This method is deprecated and exists only for backward compatibility.
        It does nothing.
        """
        pass


class Patcher(object):
    """
    Instantiate a stub creator to bind and un-bind the file-related modules to
    the :py:mod:`pyfakefs` fake modules.
    
    The arguments are explained in :py:class:`TestCase`.

    :py:class:`Patcher` is used in :py:class:`TestCase`.  :py:class:`Patcher`
    also works as a context manager for PyTest::
    
        with Patcher():
            doStuff()
    """
    SKIPMODULES = set([None, fake_filesystem, fake_filesystem_shutil, sys])
    '''Stub nothing that is imported within these modules.
    `sys` is included to prevent `sys.path` from being stubbed with the fake
    `os.path`.
    '''
    assert None in SKIPMODULES, "sys.modules contains 'None' values; must skip them."

    HAS_PATHLIB = sys.version_info >= (3, 4)
    IS_WINDOWS = sys.platform in ('win32', 'cygwin')

    # To add py.test support per issue https://github.com/jmcgeheeiv/pyfakefs/issues/43,
    # it appears that adding  'py', 'pytest', '_pytest' to SKIPNAMES will help
    SKIPNAMES = set(['os', 'path', 'io', 'genericpath'])
    if HAS_PATHLIB:
        SKIPNAMES.add('pathlib')

    def __init__(self, additional_skip_names=None, patch_path=True,
                 special_names=None):
        """For a description of the arguments, see TestCase.__init__"""

        self._skipNames = self.SKIPNAMES.copy()
        self._special_names = special_names or {}
        self._special_names['tempfile'] = {'os': '_os', 'io': '_io'}

        if additional_skip_names is not None:
            self._skipNames.update(additional_skip_names)
        self._patchPath = patch_path
        if not patch_path:
            self._skipNames.discard('path')
            self._skipNames.discard('genericpath')

        # Attributes set by _findModules()
        self._os_modules = set()
        self._path_modules = set()
        if self.HAS_PATHLIB:
            self._pathlib_modules = set()
        self._shutil_modules = set()
        self._io_modules = set()
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
        self.fake_open = None
        self.fake_io = None

        # _isStale is set by tearDown(), reset by _refresh()
        self._isStale = True

    def __enter__(self):
        """Context manager for usage outside of fake_filesystem_unittest.TestCase.
        Ensure that all patched modules are removed in case of an unhandled exception.
        """
        self.setUp()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.tearDown()

    def _findModules(self):
        """Find and cache all modules that import file system modules.
        Later, `setUp()` will stub these with the fake file system
        modules.
        """
        for name, module in set(sys.modules.items()):
            if (module in self.SKIPMODULES or
                    (not inspect.ismodule(module)) or
                        name.split('.')[0] in self._skipNames):
                continue
            # IMPORTANT TESTING NOTE: Whenever you add a new module below, test
            # it by adding an attribute in fixtures/module_with_attributes.py
            # and a test in fake_filesystem_unittest_test.py, class
            # TestAttributesWithFakeModuleNames.
            if inspect.ismodule(module.__dict__.get('os')):
                self._os_modules.add((module, 'os'))
            if self._patchPath and inspect.ismodule(module.__dict__.get('path')):
                self._path_modules.add((module, 'path'))
            if self.HAS_PATHLIB and inspect.ismodule(module.__dict__.get('pathlib')):
                self._pathlib_modules.add((module, 'pathlib'))
            if inspect.ismodule(module.__dict__.get('shutil')):
                self._shutil_modules.add((module, 'shutil'))
            if inspect.ismodule(module.__dict__.get('io')):
                self._io_modules.add((module, 'io'))
            if '__name__' in module.__dict__ and module.__name__ in self._special_names:
                module_names = self._special_names[module.__name__]
                if 'os' in module_names:
                    if inspect.ismodule(module.__dict__.get(module_names['os'])):
                        self._os_modules.add((module, module_names['os']))
                if self._patchPath and 'path' in module_names:
                    if inspect.ismodule(module.__dict__.get(module_names['path'])):
                        self._path_modules.add((module, module_names['path']))
                if self.HAS_PATHLIB and 'pathlib' in module_names:
                    if inspect.ismodule(module.__dict__.get(module_names['pathlib'])):
                        self._pathlib_modules.add((module, module_names['pathlib']))
                if 'io' in module_names:
                    if inspect.ismodule(module.__dict__.get(module_names['io'])):
                        self._io_modules.add((module, module_names['io']))

    def _refresh(self):
        """Renew the fake file system and set the _isStale flag to `False`."""
        if self._stubs is not None:
            self._stubs.SmartUnsetAll()
        self._stubs = mox3_stubout.StubOutForTesting()

        self.fs = fake_filesystem.FakeFilesystem()
        self.fake_os = fake_filesystem.FakeOsModule(self.fs)
        self.fake_path = self.fake_os.path
        if self.HAS_PATHLIB:
            self.fake_pathlib = fake_pathlib.FakePathlibModule(self.fs)
        self.fake_shutil = fake_filesystem_shutil.FakeShutilModule(self.fs)
        self.fake_open = fake_filesystem.FakeFileOpen(self.fs)
        self.fake_io = fake_filesystem.FakeIoModule(self.fs)

        if not self.IS_WINDOWS and 'tempfile' in sys.modules:
            self._patch_tempfile()

        self._isStale = False

    def _patch_tempfile(self):
        """Hack to work around cached `os` functions in `tempfile`.
         Shall be replaced by a more generic mechanism.
        """
        if 'unlink' in tempfile._TemporaryFileWrapper.__dict__:
            # Python 2.6 to 3.2: unlink is a class method of _TemporaryFileWrapper
            tempfile._TemporaryFileWrapper.unlink = self.fake_os.unlink

            #  Python 3.0 to 3.2 (and PyPy3 based on Python 3.2):
            # `TemporaryDirectory._rmtree` is used instead of `shutil.rmtree`
            # which uses several cached os functions - replace it with `shutil.rmtree`
            if 'TemporaryDirectory' in tempfile.__dict__:
                tempfile.TemporaryDirectory._rmtree = lambda o, path: shutil.rmtree(path)
        else:
            # Python > 3.2 - unlink is a default parameter of _TemporaryFileCloser
            tempfile._TemporaryFileCloser.close.__defaults__ = (self.fake_os.unlink,)

    def setUp(self, doctester=None):
        """Bind the file-related modules to the :py:mod:`pyfakefs` fake
        modules real ones.  Also bind the fake `file()` and `open()` functions.
        """
        temp_dir = tempfile.gettempdir()
        self._findModules()
        self._refresh()
        assert None not in vars(self).values(), \
            "_findModules() missed the initialization of an instance variable"

        if doctester is not None:
            doctester.globs = self.replaceGlobs(doctester.globs)

        if sys.version_info < (3,):
            # file() was eliminated in Python3
            self._stubs.SmartSet(builtins, 'file', self.fake_open)
        self._stubs.SmartSet(builtins, 'open', self.fake_open)
        for module, attr in self._os_modules:
            self._stubs.SmartSet(module, attr, self.fake_os)
        for module, attr in self._path_modules:
            self._stubs.SmartSet(module, attr, self.fake_path)
        if self.HAS_PATHLIB:
            for module, attr in self._pathlib_modules:
                self._stubs.SmartSet(module, attr, self.fake_pathlib)
        for module, attr in self._shutil_modules:
            self._stubs.SmartSet(module, attr, self.fake_shutil)
        for module, attr in self._io_modules:
            self._stubs.SmartSet(module, attr, self.fake_io)

        # the temp directory is assumed to exist at least in `tempfile1,
        # so we create it here for convenience
        self.fs.CreateDirectory(temp_dir)


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
        if 'io' in globs:
            globs['io'] = fake_filesystem.FakeIoModule(self.fs)
        return globs

    def tearDown(self, doctester=None):
        """Clear the fake filesystem bindings created by `setUp()`."""
        self._isStale = True
        self._stubs.SmartUnsetAll()


class DynamicPatcher(object):
    """A file loader that replaces file system related modules by their
    fake implementation if they are loaded after calling `setupPyFakefs()`.
    Implements the protocol needed for import hooks.
    """
    def __init__(self, patcher):
        self._patcher = patcher
        self._patching = False
        self.modules = {
            'os': self._patcher.fake_os,
            'os.path': self._patcher.fake_path,
            'io': self._patcher.fake_io,
            'shutil': self._patcher.fake_shutil
        }
        if sys.version_info >= (3, 4):
            self.modules['pathlib'] = fake_pathlib.FakePathlibModule

        # remove all modules that have to be patched from `sys.modules`,
        # otherwise the find_... methods will not be called
        for module in self.modules:
            if self.needs_patch(module) and module in sys.modules:
                del sys.modules[module]

    def needs_patch(self, name):
        """Check if the module with the given name shall be replaced."""
        if self._patching or name not in self.modules:
            return False
        if (name in sys.modules and
                    type(sys.modules[name]) == self.modules[name]):
            return False
        return True

    def find_spec(self, fullname, path, target=None):
        """Module finder for Python 3."""
        if self.needs_patch(fullname):
            return ModuleSpec(fullname, self)

    def find_module(self, fullname, path=None):
        """Module finder for Python 2."""
        if self.needs_patch(fullname):
            return self

    def load_module(self, fullname):
        """Replaces the module by its fake implementation."""

        # prevent re-entry via the finder
        self._patching = True
        importlib.import_module(fullname)
        self._patching = False
        # preserve the original module (currently not used)
        sys.modules['original_' + fullname] = sys.modules[fullname]
        # replace with fake implementation
        sys.modules[fullname] = self.modules[fullname]
        return self.modules[fullname]
