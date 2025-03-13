Usage
=====

Test Scenarios
--------------
There are several approaches for implementing tests using ``pyfakefs``.


Patch using the pytest plugin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``pyfakefs`` functions as a `pytest`_ plugin that provides the `fs` fixture,
which is registered at installation time.
Using this fixture automatically patches all file system functions with
the fake file system functions. It also allows to access several
convenience methods (see :ref:`convenience_methods`).

Here is an example for a simple test:

.. code:: python

   import os


   def test_fakefs(fs):
       # "fs" is the reference to the fake file system
       fs.create_file("/var/data/xx1.txt")
       assert os.path.exists("/var/data/xx1.txt")

If you are bothered by the ``pylint`` warning,
``C0103: Argument name "fs" doesn't conform to snake_case naming style (invalid-name)``,
you can define a longer name in your ``conftest.py`` and use that in your tests:

.. code:: python

    import pytest


    @pytest.fixture
    def fake_filesystem(fs):  # pylint:disable=invalid-name
        """Variable name 'fs' causes a pylint warning. Provide a longer name
        acceptable to pylint for use in tests.
        """
        yield fs

Class-, module- and session-scoped fixtures
...........................................
For convenience, class-, module- and session-scoped fixtures with the same
functionality are provided, named ``fs_class``, ``fs_module`` and ``fs_session``,
respectively.

.. caution:: If any of these fixtures is active, any other ``fs`` fixture will
  not setup / tear down the fake filesystem in the current scope; instead, it
  will just serve as a reference to the active fake filesystem. That means that changes
  done in the fake filesystem inside a test will remain there until the respective scope
  ends (see also :ref:`nested_patcher_invocation`).

Patch using fake_filesystem_unittest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you are using the Python ``unittest`` package, the easiest approach is to
use test classes derived from ``fake_filesystem_unittest.TestCase``.

If you call ``setUpPyfakefs()`` in your ``setUp()``, ``pyfakefs`` will
automatically find all real file functions and modules, and stub these out
with the fake file system functions and modules:

.. code:: python

    import os
    from pyfakefs.fake_filesystem_unittest import TestCase


    class ExampleTestCase(TestCase):
        def setUp(self):
            self.setUpPyfakefs()

        def test_create_file(self):
            file_path = "/test/file.txt"
            self.assertFalse(os.path.exists(file_path))
            self.fs.create_file(file_path)
            self.assertTrue(os.path.exists(file_path))

The usage is explained in more detail in :ref:`auto_patch` and
demonstrated in the files `example.py`_ and `example_test.py`_.

If your setup is the same for all tests in a class, you can use the class setup
method ``setUpClassPyfakefs`` instead:

.. code:: python

    import os
    import pathlib
    from pyfakefs.fake_filesystem_unittest import TestCase


    class ExampleTestCase(TestCase):
        @classmethod
        def setUpClass(cls):
            cls.setUpClassPyfakefs()
            # setup the fake filesystem using standard functions
            path = pathlib.Path("/test")
            path.mkdir()
            (path / "file1.txt").touch()
            # you can also access the fake fs via fake_fs() if needed
            cls.fake_fs().create_file("/test/file2.txt", contents="test")

        def test1(self):
            self.assertTrue(os.path.exists("/test/file1.txt"))
            self.assertTrue(os.path.exists("/test/file2.txt"))

        def test2(self):
            self.assertTrue(os.path.exists("/test/file1.txt"))
            file_path = "/test/file3.txt"
            # self.fs is the same instance as cls.fake_fs() above
            self.fs.create_file(file_path)
            self.assertTrue(os.path.exists(file_path))

.. note:: This feature cannot be used with a Python version before Python 3.8 due to
  a missing feature in ``unittest``.

.. caution:: If this is used, any changes made in the fake filesystem inside a test
  will remain there for all following tests in the test class, if they are not reverted
  in the test itself.


Patch using fake_filesystem_unittest.Patcher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you are using other means of testing like `nose`_,
you can do the patching using ``fake_filesystem_unittest.Patcher``--the class
doing the actual work of replacing the filesystem modules with the fake modules
in the first two approaches.

The easiest way is to just use ``Patcher`` as a context manager:

.. code:: python

   from pyfakefs.fake_filesystem_unittest import Patcher

   with Patcher() as patcher:
       # access the fake_filesystem object via patcher.fs
       patcher.fs.create_file("/foo/bar", contents="test")

       # the following code works on the fake filesystem
       with open("/foo/bar") as f:
           contents = f.read()

You can also initialize ``Patcher`` manually:

.. code:: python

   from pyfakefs.fake_filesystem_unittest import Patcher

   patcher = Patcher()
   patcher.setUp()  # called in the initialization code
   ...
   patcher.tearDown()  # somewhere in the cleanup code

Patch using the fake_filesystem_unittest.patchfs decorator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This is basically a convenience wrapper for the previous method.
If you are not using ``pytest`` and  want to use the fake filesystem for a
single function, you can write:

.. code:: python

   from pyfakefs.fake_filesystem_unittest import patchfs


   @patchfs
   def test_something(fake_fs):
       # access the fake_filesystem object via fake_fs
       fake_fs.create_file("/foo/bar", contents="test")

Note that ``fake_fs`` is a positional argument and the argument name does
not matter. If there are additional ``mock.patch`` decorators that also
create positional arguments, the argument order is the same as the decorator
order, as shown here:

.. code:: python

   @patchfs
   @mock.patch("foo.bar")
   def test_something(fake_fs, mocked_bar):
       assert foo()


   @mock.patch("foo.bar")
   @patchfs
   def test_something(mocked_bar, fake_fs):
       assert foo()

.. note::
  Avoid writing the ``patchfs`` decorator *between* ``mock.patch`` operators,
  as the order will not be what you expect. Due to implementation details,
  all arguments created by ``mock.patch`` decorators are always expected to
  be contiguous, regardless of other decorators positioned between them.

.. caution::
  In previous versions, the keyword argument `fs` has been used instead,
  which had to be positioned *after* all positional arguments regardless of
  the decorator order. If you upgrade from a version before pyfakefs 4.2,
  you may have to adapt the argument order.

You can also use this to make a single unit test use the fake fs:

.. code:: python

    class TestSomething(unittest.TestCase):
        @patchfs
        def test_something(self, fs):
            fs.create_file("/foo/bar", contents="test")

.. _auto_patch:

Patch file system with unittest and doctest
-------------------------------------------
The ``fake_filesystem_unittest`` module automatically finds all real file
functions and modules, and stubs them out with the fake file system functions and modules.
The pyfakefs source code contains files that demonstrate this usage model:

- ``example.py`` is the software under test. In production, it uses the
  real file system.
- ``example_test.py`` tests ``example.py``. During testing, the pyfakefs fake
  file system is used by ``example_test.py`` and ``example.py`` alike.

.. note:: This example uses the Python ``unittest`` module for testing, but the
  functionality is similar if using the ``fs`` fixture in ``pytest``,
  the ``patchfs`` decorator, or the ``Patcher`` class.


Software Under Test
~~~~~~~~~~~~~~~~~~~
``example.py`` contains a few functions that manipulate files.  For instance:

.. code:: python

    def create_file(path):
        """Create the specified file and add some content to it.  Use the open()
        built in function.

        For example, the following file operations occur in the fake file system.
        In the real file system, we would not even have permission to write /test:

        >>> os.path.isdir('/test')
        False
        >>> os.mkdir('/test')
        >>> os.path.isdir('/test')
        True
        >>> os.path.exists('/test/file.txt')
        False
        >>> create_file('/test/file.txt')
        >>> os.path.exists('/test/file.txt')
        True
        >>> with open('/test/file.txt') as f:
        ...     f.readlines()
        ["This is test file '/test/file.txt'.\\n", 'It was created using the open() function.\\n']
        """
        with open(path, "w") as f:
            f.write("This is test file '{}'.\n".format(path))
            f.write("It was created using the open() function.\n")

No functional code in ``example.py`` even hints at a fake file system. In
production, ``create_file()`` invokes the real file functions ``open()`` and
``write()``.

Unit Tests and Doctests
~~~~~~~~~~~~~~~~~~~~~~~
``example_test.py`` contains unit tests for ``example.py``. ``example.py``
contains the doctests, as you can see above.

The module ``fake_filesystem_unittest`` contains code that finds all real file
functions and modules, and stubs these out with the fake file system functions
and modules:

.. code:: python

    import os
    import unittest
    from pyfakefs import fake_filesystem_unittest

    # The module under test is example:
    import example

Doctests
........
``example_test.py`` defines ``load_tests()``, which runs the doctests in
``example.py``:

.. code:: python

    def load_tests(loader, tests, ignore):
        """Load the pyfakefs/example.py doctest tests into unittest."""
        return fake_filesystem_unittest.load_doctests(loader, tests, ignore, example)


Everything, including all imported modules and the test, is stubbed out
with the fake filesystem. Thus you can use familiar file functions like
``os.mkdir()`` as part of your test fixture and they too will operate on the
fake file system.

Unit Test Class
...............
Next comes the ``unittest`` test class.  This class is derived from
``fake_filesystem_unittest.TestCase``, which is in turn derived from
``unittest.TestClass``:

.. code:: python

    class TestExample(fake_filesystem_unittest.TestCase):
        def setUp(self):
            self.setUpPyfakefs()

        def tearDown(self):
            # It is no longer necessary to add self.tearDownPyfakefs()
            pass

        def test_create_file(self):
            """Test example.create_file()"""
            # The os module has been replaced with the fake os module so all of the
            # following occurs in the fake filesystem.
            self.assertFalse(os.path.isdir("/test"))
            os.mkdir("/test")
            self.assertTrue(os.path.isdir("/test"))

            self.assertFalse(os.path.exists("/test/file.txt"))
            example.create_file("/test/file.txt")
            self.assertTrue(os.path.exists("/test/file.txt"))

        ...


Just add ``self.setUpPyfakefs()`` in ``setUp()``. You need add nothing to
``tearDown()``.  Write your tests as usual.  From ``self.setUpPyfakefs()`` to
the end of your ``tearDown()`` method, all file operations will use the fake
file system.

.. _`example.py`: https://github.com/pytest-dev/pyfakefs/blob/main/pyfakefs/tests/example.py
.. _`example_test.py`: https://github.com/pytest-dev/pyfakefs/blob/main/pyfakefs/tests/example_test.py
.. _`pytest`: https://doc.pytest.org
.. _`nose`: https://docs.nose2.io/en/latest/
