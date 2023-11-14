# Copyright 2008 Google Inc.
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
This is a fork of the pymox library intended to work with Python 3.
The file was modified by quermit@gmail.com and dawid.fatyga@gmail.com

Previously, pyfakefs used just this file from the mox3 library.
However, mox3 will soon be decommissioned, yet standard mock cannot
be used because of the problem described in pyfakefs #182 and
mock issue 250 (https://github.com/testing-cabal/mock/issues/250).
Therefore just this file was forked from mox3 and incorporated
into pyfakefs.
"""

from enum import Enum, auto
from typing import Any
import inspect


class AccessMethod(Enum):
    GETATTR = auto()
    DICT = auto()
    SLOT = auto()


def universal_getattr(obj: Any, attr_name: str) -> tuple[Any, AccessMethod]:
    """Get an attribute's value in a universal way

    Can read any normal attributes, as well as attributes specified in
    custom `__getattr__` methods, or stored in `obj.__dict__` or `obj.__slot__`.
    Returns the attribute's value and the method used to access it, which can
    then be used with the `set_attribute_safely` method to set it if needed.

    Warning: If the AccessMethod returned is AccessMethod.GETATTR, if the attribute
    has wrappers, such as staticmethod or classmethod, these will be stripped.
    """
    try:
        attr_value = getattr(obj, attr_name)
        access_method = AccessMethod.GETATTR
    except AttributeError as e:
        if hasattr(obj, '__dict__') and attr_name in obj.__dict__:
            attr_value = obj.__dict__[attr_name]
            access_method = AccessMethod.DICT
        elif hasattr(obj, '__slot__') and attr_name in obj.__slot__:
            attr_value = obj.__slot__[attr_name]
            access_method = AccessMethod.SLOT
        else:
            raise e

    return attr_value, access_method


def universal_setattr(obj: Any, attr_name: str, attr_value: Any, access_method: AccessMethod):
    """Set an attribute's value in a universal way

    Can set any normal attributes, as well as attributes stored in `obj.__dict__`
    or `obj.__slot__`, depending on the value of `access_method`.
    """
    if access_method == AccessMethod.GETATTR:
        setattr(obj, attr_name, attr_value)
    elif access_method == AccessMethod.DICT:
        try:
            obj.__dict__[attr_name] = attr_value
        except KeyError:
            raise AttributeError(f"Attribute {attr_name} not found in __dict__")
    elif access_method == AccessMethod.SLOT:
        try:
            obj.__slot__[attr_name] = attr_value
        except KeyError:
            raise AttributeError(f"Attribute {attr_name} not found in __slot__")
    else:
        raise NotImplementedError(f'Unknown {access_method = } has not been implemented')


class StubOutForTesting:
    """Sample Usage:

    You want os.path.exists() to always return true during testing.

    stubs = StubOutForTesting()
    stubs.Set(os.path, 'exists', lambda x: 1)
        ...
    stubs.UnsetAll()

    The above changes os.path.exists into a lambda that returns 1.    Once
    the ... part of the code finishes, the UnsetAll() looks up the old value
    of os.path.exists and restores it.

    """

    def __init__(self):
        self.cache = []
        self.stubs = []

    def __del__(self):
        self.smart_unset_all()
        self.unset_all()

    def smart_set(self, obj, attr_name, new_attr):
        """Replace obj.attr_name with new_attr.

        This method is smart and works at the module, class, and instance level
        while preserving proper inheritance. It will not stub out C types
        however unless that has been explicitly allowed by the type.

        This method supports the case where attr_name is a staticmethod or a
        classmethod of obj.

        If obj is an instance, then it is its class that will actually be
        stubbed. Note that the method Set() does not do that: if obj is an
        instance, it (and not its class) will be stubbed.

        Raises AttributeError if the attribute cannot be found.
        """
        orig_obj = None
        orig_attr = None
        access_method = None

        if inspect.ismodule(obj) or (
            not inspect.isclass(obj) and attr_name in obj.__dict__
        ):
            orig_obj = obj
            try:
                orig_attr, access_method = universal_getattr(obj, attr_name)
            except AttributeError:
                pass
        else:
            if not inspect.isclass(obj):
                mro = list(inspect.getmro(obj.__class__))
            else:
                mro = list(inspect.getmro(obj))

            mro.reverse()

            for cls in mro:
                try:
                    orig_obj = cls
                    orig_attr, access_method = universal_getattr(obj, attr_name)
                except AttributeError:
                    continue

        if orig_obj is None or access_method is None:
            raise AttributeError("Attribute not found.")

        self.stubs.append((orig_obj, attr_name, orig_attr, access_method))
        universal_setattr(orig_obj, attr_name, new_attr, access_method)

    def smart_unset_all(self):
        """Reverses all the SmartSet() calls.

        Restores things to their original definition. Its okay to call
        SmartUnsetAll() repeatedly, as later calls have no effect if no
        SmartSet() calls have been made.
        """
        self.stubs.reverse()

        for obj, attr_name, old_attr, access_method in self.stubs:
            universal_setattr(obj, attr_name, old_attr, access_method)

        self.stubs = []

    def set(self, parent, child_name, new_child):
        """Replace child_name's old definition with new_child.

        Replace definition in the context of the given parent. The parent could
        be a module when the child is a function at module scope. Or the parent
        could be a class when a class' method is being replaced. The named
        child is set to new_child, while the prior definition is saved away
        for later, when unset_all() is called.

        This method supports the case where child_name is a staticmethod or a
        classmethod of parent.
        """
        # Get the child value
        old_child, access_method = universal_getattr(parent, child_name)

        # Try getting it again directly from the __dict__, to preserve any decorators
        if child_name in parent.__dict__:
            old_attribute = parent.__dict__.get(child_name)

            if old_attribute is not None:
                if isinstance(old_attribute, staticmethod):
                    old_child = staticmethod(old_child)
                elif isinstance(old_attribute, classmethod):
                    old_child = classmethod(old_child.__func__)

        self.cache.append((parent, old_child, child_name, access_method))
        universal_setattr(parent, child_name, new_child, access_method)

    def unset_all(self):
        """Reverses all the Set() calls.

        Restores things to their original definition. Its okay to call
        unset_all() repeatedly, as later calls have no effect if no Set()
        calls have been made.
        """
        # Undo calls to set() in reverse order, in case set() was called on the
        # same arguments repeatedly (want the original call to be last one
        # undone)
        self.cache.reverse()

        for parent, old_child, child_name, access_method in self.cache:
            universal_setattr(parent, child_name, old_child, access_method)
        self.cache = []
