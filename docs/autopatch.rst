.. _auto_patch:

Automatically find and patch file functions and modules
=======================================================
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
-------------------
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
-----------------------
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
~~~~~~~~
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
~~~~~~~~~~~~~~~
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
