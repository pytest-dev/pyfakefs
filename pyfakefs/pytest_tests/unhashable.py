import sys
import types


class Unhashable(types.ModuleType):
    """
    Unhashable module, used for regression test for  #923.
    """

    @property
    def Unhashable(self):
        return self

    def __eq__(self, other):
        raise NotImplementedError("Cannot compare unhashable")


if sys.modules[__name__] is not Unhashable:
    sys.modules[__name__] = Unhashable("unhashable")
