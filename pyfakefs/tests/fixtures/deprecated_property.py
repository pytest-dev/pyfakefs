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

"""Used for testing suppression of deprecation warnings while iterating
over modules. The code is modeled after code in xmlbuilder.py in Python 3.6.
See issue #542.
"""
import warnings


class DeprecatedProperty:

    def __get__(self, instance, cls):
        warnings.warn("async is deprecated", DeprecationWarning)
        warnings.warn("async will be replaced", FutureWarning)
        return instance


class DeprecationTest:
    locals()['async'] = DeprecatedProperty()
