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
"""Utilities for handling deprecated functions."""

import functools
import warnings


class Deprecator(object):
    """Decorator class for adding deprecated functions.

    Warnings are switched on by default.
    To disable deprecation warnings, use:

    >>>  from pyfakefs.deprecator import Deprecator
    >>>
    >>>  Deprecator.show_warnings = False
    """

    show_warnings = True

    def __init__(self, use_instead=None, func_name=None):
        self.use_instead = use_instead
        self.func_name = func_name

    def __call__(self, func):
        """Decorator to mark functions as deprecated. Emit warning
        when the function is used."""

        @functools.wraps(func)
        def _new_func(*args, **kwargs):
            if self.show_warnings:
                warnings.simplefilter('always', DeprecationWarning)
                message = ''
                if self.use_instead is not None:
                    message = 'Use {} instead.'.format(self.use_instead)
                warnings.warn('Call to deprecated function {}. {}'.format(
                    self.func_name or func.__name__, message),
                              category=DeprecationWarning, stacklevel=2)
                warnings.simplefilter('default', DeprecationWarning)
            return func(*args, **kwargs)

        return _new_func

    @staticmethod
    def add(clss, func, deprecated_name):
        """Add the deprecated version of a member function to the given class.
        Gives a deprecation warning on usage.

        Args:
            clss: the class where the deprecated function is to be added
            func: the actual function that is called by the deprecated version
            deprecated_name: the deprecated name of the function
        """

        @Deprecator(func.__name__, deprecated_name)
        def _old_function(*args, **kwargs):
            return func(*args, **kwargs)

        setattr(clss, deprecated_name, _old_function)
