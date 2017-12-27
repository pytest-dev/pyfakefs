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
Example module that is used for testing the functionality of
:py:class`pyfakefs.mox_stubout.StubOutForTesting`.
"""
import datetime
import math
import os


def check_if_exists(filepath):
    return os.path.exists(filepath)


def fabs(x):
    return math.fabs(x)


def tomorrow():
    return datetime.date.today() + datetime.timedelta(days=1)
