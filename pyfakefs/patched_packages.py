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
Provides patches for some commonly used modules that enable them to work
with pyfakefs.
"""
import sys

try:
    import pandas.io.parsers as parsers
except ImportError:
    parsers = None

try:
    import xlrd
except ImportError:
    xlrd = None

try:
    from django.core.files import locks
except ImportError:
    locks = None


def get_modules_to_patch():
    modules_to_patch = {}
    if xlrd is not None:
        modules_to_patch['xlrd'] = XLRDModule
    if locks is not None:
        modules_to_patch['django.core.files.locks'] = FakeLocks
    return modules_to_patch


def get_classes_to_patch():
    classes_to_patch = {}
    if parsers is not None:
        classes_to_patch[
            'TextFileReader'
        ] = 'pandas.io.parsers'
    return classes_to_patch


def get_fake_module_classes():
    fake_module_classes = {}
    if parsers is not None:
        fake_module_classes[
            'TextFileReader'
        ] = FakeTextFileReader
    return fake_module_classes


if xlrd is not None:
    class XLRDModule:
        """Patches the xlrd module, which is used as the default Excel file
        reader by pandas. Disables using memory mapped files, which are
        implemented platform-specific on OS level."""

        def __init__(self, _):
            self._xlrd_module = xlrd

        def open_workbook(self, filename=None,
                          logfile=sys.stdout,
                          verbosity=0,
                          use_mmap=False,
                          file_contents=None,
                          encoding_override=None,
                          formatting_info=False,
                          on_demand=False,
                          ragged_rows=False):
            return self._xlrd_module.open_workbook(
                filename, logfile, verbosity, False, file_contents,
                encoding_override, formatting_info, on_demand, ragged_rows)

        def __getattr__(self, name):
            """Forwards any unfaked calls to the standard xlrd module."""
            return getattr(self._xlrd_module, name)

if parsers is not None:
    # we currently need to add fake modules for both the parser module and
    # the contained text reader - maybe this can be simplified

    class FakeTextFileReader:
        fake_parsers = None

        def __init__(self, filesystem):
            if self.fake_parsers is None:
                self.__class__.fake_parsers = ParsersModule(filesystem)

        def __call__(self, *args, **kwargs):
            return self.fake_parsers.TextFileReader(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self.fake_parsers.TextFileReader, name)

    class ParsersModule:
        def __init__(self, _):
            self._parsers_module = parsers

        class TextFileReader(parsers.TextFileReader):
            def __init__(self, *args, **kwargs):
                kwargs['engine'] = 'python'
                super().__init__(*args, **kwargs)

        def __getattr__(self, name):
            """Forwards any unfaked calls to the standard xlrd module."""
            return getattr(self._parsers_module, name)

if locks is not None:
    class FakeLocks:
        """django.core.files.locks uses low level OS functions, fake it."""
        _locks_module = locks

        def __init__(self, _):
            pass

        @staticmethod
        def lock(f, flags):
            return True

        @staticmethod
        def unlock(f):
            return True

        def __getattr__(self, name):
            return getattr(self._locks_module, name)
