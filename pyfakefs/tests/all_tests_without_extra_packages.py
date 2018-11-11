import sys
import unittest

from pyfakefs import extra_packages

if extra_packages.pathlib2:
    extra_packages.pathlib = None
    extra_packages.pathlib2 = None

if extra_packages.use_scandir_package:
    extra_packages.use_scandir = False
    extra_packages.use_scandir_package = False

from pyfakefs.tests.all_tests import AllTests  # noqa: E402


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(AllTests().suite())
    sys.exit(int(not result.wasSuccessful()))
