Usage
=====

Test Scenarios
--------------
There are several approaches to implementing tests using ``pyfakefs``.

Patch using fake_filesystem_unittest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you are using the Python ``unittest`` package, the easiest approach is to
use test classes derived from ``fake_filesystem_unittest.TestCase``.

If you call ``setUpPyfakefs()`` in your ``SetUp()``, ``pyfakefs`` will
automatically find all real file functions and modules, and stub these out
with the fake file system functions and modules:

.. code:: python

    from fake_filesystem_unittest import TestCase

    class ExampleTestCase(TestCase):
        def setUp(self):
            self.setUpPyfakefs()

        def test_create_file(self):
            file_path = '/test/file.txt'
            self.assertFalse(os.path.exists(file_path))
            self.fs.create_file(file_path)
            self.assertTrue(os.path.exists(file_path))

The usage is explained in more detail in the ``pyfakefs`` wiki page
`Automatically find and patch file functions and modules <https://github.com/jmcgeheeiv/pyfakefs/wiki/Automatically-find-and-patch-file-functions-and-modules>`__
and demonstrated in the files ``example.py`` and ``example_test.py``.

Patch using the PyTest plugin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you use `PyTest <https://doc.pytest.org>`__, you will be interested in
the PyTest plugin in ``pyfakefs``.
This automatically patches all file system functions and modules in a
similar manner as described above.

The PyTest plugin provides the ``fs`` fixture for use in your test. For example:

.. code:: python

   def my_fakefs_test(fs):
       # "fs" is the reference to the fake file system
       fs.create_file('/var/data/xx1.txt')
       assert os.path.exists('/var/data/xx1.txt')

Patch using fake_filesystem_unittest.Patcher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you are using other means of testing like `nose <http://nose2.readthedocs.io>`__, you can do the
patching using ``fake_filesystem_unittest.Patcher`` - the class doing the actual work
of replacing the filesystem modules with the fake modules in the first two approaches.

The easiest way is to just use ``Patcher`` as a context manager:

.. code:: python

   from fake_filesystem_unittest import Patcher

   with Patcher() as patcher:
       # access the fake_filesystem object via patcher.fs
       patcher.fs.create_file('/foo/bar', contents='test')

       # the following code works on the fake filesystem
       with open('/foo/bar') as f:
           contents = f.read()

You can also initialize ``Patcher`` manually:

.. code:: python

   from fake_filesystem_unittest import Patcher

   patcher = Patcher()
   patcher.setUp()     # called in the initialization code
   ...
   patcher.tearDown()  # somewhere in the cleanup code

Patch using unittest.mock (deprecated)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You can also use ``mock.patch()`` to patch the modules manually. This approach will
only work for the directly imported modules, therefore it is not suited for testing
larger code bases. As the other approaches are more convenient, this one is considered
deprecated and will not be described in detail.

Customizing Patcher and TestCase
--------------------------------
Both ``fake_filesystem_unittest.Patcher`` and ``fake_filesystem_unittest.TestCase``
provide a few additional arguments for fine-tuning. These are only needed if
patching does not work for some module.

*Note for PyTest users:* if you need these arguments in ``PyTest``, you have to
use ``Patcher`` directly instead of the ``fs`` fixture. Alternatively, you can
add your own fixture with the needed parameters (see ``pytest_plugin.py``
for a possible implementation).

modules_to_reload
~~~~~~~~~~~~~~~~~
This allows to pass a list of modules that shall be reloaded, thus allowing
to patch modules not imported directly.

Pyfakefs automatically patches modules only if they are imported directly, e.g:

.. code:: python

  import os
  import pathlib.Path

The following imports of ``os`` and ``pathlib.Path`` will not be patched by
``pyfakefs``, however:

.. code:: python

  import os as my_os
  from pathlib import Path

.. note:: There is one exception to that: importing ``os.path`` like
  ``from os import path`` will work, because it is handled by ``pyfakefs``
  (see also ``patch_path`` below).

If adding the module containing these imports to ``modules_to_reload``, they
will be correctly patched.

modules_to_patch
~~~~~~~~~~~~~~~~
This also allows patching modules that are not patched out of the box, in
this case by adding a fake module implementation for a module name. The
argument is a dictionary of fake modules mapped to the names to be faked.
This can be used to fake modules imported as another name directly. For the
``os`` import above you could also use:

.. code:: python

  with Patcher(modules_to_patch={'my_os': fake_filesystem.FakeOsModule}):
      test_something()

For the second example (``from pathlib import Path``) the syntax is slightly
different:

.. code:: python

  with Patcher(modules_to_patch={'pathlib.Path': MyFakePath}):
      test_something()

This will fake the class ``Path`` inside the module ``pathlib``, if imported
as ``Path``.
Here is an example of how to implement ``MyFakePath``:

.. code:: python

    class MyFakePath():
        """Patches `pathlib.Path` by passing all calls to FakePathlibModule."""
        fake_pathlib = None

        def __init__(self, filesystem):
            if self.fake_pathlib is None:
                from pyfakefs.fake_pathlib import FakePathlibModule
                self.__class__.fake_pathlib = FakePathlibModule(filesystem)

        def __call__(self, *args, **kwargs):
            return self.fake_pathlib.Path(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self.fake_pathlib.Path, name)

patch_path
~~~~~~~~~~
This is True by default, meaning that modules named ``path`` are patched as
``os.path``. If this clashes with another module of the same name, it can be
switched off (and imports like ``from os import path`` will not be patched).


additional_skip_names
~~~~~~~~~~~~~~~~~~~~~
This may be used to add modules that shall not be patched. This is mostly
used to avoid patching the Python file system modules themselves, but may be
helpful in some special situations.

use_dynamic_patch
~~~~~~~~~~~~~~~~~
If ``True`` (the default), dynamic patching after setup is used (for example
for modules loaded locally inside of functions).
Can be switched off if it causes unwanted side effects.

Using convenience methods
-------------------------
While ``pyfakefs`` can be used just with the standard Python file system
functions, there are few convenience methods in ``fake_filesystem`` that can
help you setting up your tests. The methods can be accessed via the
``fake_filesystem`` instance in your tests: ``Patcher.fs``, the ``fs``
fixture in PyTest, or ``TestCase.fs``.

File creation helpers
~~~~~~~~~~~~~~~~~~~~~
To create files, directories or symlinks together with all the directories
in the path, you may use ``create_file()``, ``create_dir()`` and
``create_symlink()``, respectively.

``create_file()`` also allows you to set the file mode and the file contents
together with the encoding if needed. Alternatively, you can define a file
size without contents - in this case, you will not be able to perform
standard I\O operations on the file (may be used to "fill up" the file system
with large files).

.. code:: python

    from fake_filesystem_unittest import TestCase

    class ExampleTestCase(TestCase):
        def setUp(self):
            self.setUpPyfakefs()

        def test_create_file(self):
            file_path = '/foo/bar/test.txt'
            self.fs.create_file(file_path, contents = 'test')
            with open(file_path) as f:
                self.assertEqual('test', f.read())

``create_dir()`` behaves like ``os.makedirs()``, but can also be used in
Python 2.

Access to files in the real file system
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you want to have read access to real files or directories , you can map
them into the fake file system using ``add_real_file()``,
``add_real_directory()`` and ``add_real_paths()``. They take a file path, a
directory path, or a list of paths, respectively, and make them accessible
from the fake file system. By default, the contents of the mapped files and
directories are read only on demand, so that mapping them is relatively
cheap. The access to the files is by default read-only, but even even if you
add them using ``read_only=False``, the files are written only in the fake
system (e.g. in memory). The real files are never changed.

``add_real_file()`` and ``add_real_directory()`` also allow you to map a
file or a directory tree into another location in the fake filesystem via the
argument ``target_path``.

.. code:: python

    from fake_filesystem_unittest import TestCase

    class ExampleTestCase(TestCase):

        fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures')
        def setUp(self):
            self.setUpPyfakefs()
            # make the file accessible in the fake file system
            self.fs.add_real_directory(self.templates_dirname)

        def test_using_fixture1(self):
            with open(os.path.join(self.fixture_path, 'fixture1.txt') as f:
                # file contents are copied to the fake file system
                # only at this point
                contents = f.read()

Setting the file system size
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you need to know the file system size in your tests (for example for
testing cleanup scripts), you can set the fake file system size using
``set_disk_usage()``. By default, this sets the total size in bytes of the
root partition; if you add a path as parameter, the size will be related to
the mount point (or drive under Windows) the path is related to.

By default, the size of the fake file system is considered infinite. As soon
as you set a size, all files will occupy the space according to their size,
and you may fail to create new files if the fake file system is full.

.. code:: python

    from fake_filesystem_unittest import TestCase

    class ExampleTestCase(TestCase):

        def setUp(self):
            self.setUpPyfakefs()
            self.fs.set_disk_usage(100)

        def test_disk_full(self):
            with open('/foo/bar.txt', 'w') as f:
                self.assertRaises(OSError, f.write, 'a' * 200)

To get the file system size, you may use ``get_disk_usage()``, which is
modeled after ``shutil.disk_usage()``.
