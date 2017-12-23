# Copyright 2017 John McGehee
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

"""This module is for testing pyfakefs
:py:class:`fake_filesystem_unittest.Patcher`.  It defines attributes that have
the same names as file modules, sudh as 'io` and `path`.  Since these are not
modules, :py:class:`fake_filesystem_unittest.Patcher` should not patch them.

Whenever a new module is added to
:py:meth:`fake_filesystem_unittest.Patcher._findModules`, the corresponding
attribute should be added here and in the test
:py:class:`fake_filesystem_unittest_test.TestAttributesWithFakeModuleNames`.
"""

os = 'os attribute value'
path = 'path attribute value'
pathlib = 'pathlib attribute value'
shutil = 'shutil attribute value'
io = 'io attribute value'
