Usage
=====

Test Scenarios
--------------
There are several approaches to implementing tests using ``pyfakefs``.

Patch using fake_filesystem_unittest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you are using the Python ``unittest`` package, the easiest approach is to
use test classes derived from ``fake_filesystem_unittest.TestCase``.

If you call ``setUpPyfakefs()`` in your ``setUp()``, ``pyfakefs`` will
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

The usage is explained in more detail in :ref:`auto_patch` and
demonstrated in the files ``example.py`` and ``example_test.py``.

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

.. _customizing_patcher:

Customizing Patcher and TestCase
--------------------------------

Both ``fake_filesystem_unittest.Patcher`` and ``fake_filesystem_unittest.TestCase``
provide a few arguments to handle cases where patching does not work out of
the box.
In case of ``fake_filesystem_unittest.TestCase``, these arguments can either
be set in the TestCase instance initialization, or passed to ``setUpPyfakefs()``.

.. note:: If you need these arguments in ``PyTest``, you must
  use ``Patcher`` directly instead of the ``fs`` fixture. Alternatively,
  you can add your own fixture with the needed parameters.

  An example for both approaches can be found in
  `pytest_fixture_test.py <https://github.com/jmcgeheeiv/pyfakefs/blob/master/pyfakefs/pytest_tests/pytest_fixture_test.py>`__
  with the example fixture in `conftest.py <https://github.com/jmcgeheeiv/pyfakefs/blob/master/pyfakefs/pytest_tests/conftest.py>`__.
  We advice to use this example fixture code as a template for your customized
  pytest plugins.

modules_to_reload
~~~~~~~~~~~~~~~~~
Pyfakefs patches modules that are imported before starting the test by
finding and replacing file system modules in all loaded modules at test
initialization time.
This allows to automatically patch file system related modules that are:

- imported directly, for example:

.. code:: python

  import os
  import pathlib.Path

- imported as another name:

.. code:: python

  import os as my_os

- imported using one of these two specially handled statements:

.. code:: python

  from os import path
  from pathlib import Path

Additionally, functions from file system related modules are patched
automatically if imported like:

.. code:: python

  from os.path import exists
  from os import stat

This also works if importing the functions as another name:

.. code:: python

  from os.path import exists as my_exists
  from io import open as io_open
  from builtins import open as bltn_open

There are a few cases where automatic patching does not work. We know of two
specific cases where this is the case:

- initializing global variables:

.. code:: python

  from pathlib import Path

  path = Path("/example_home")

In this case, ``path`` will hold the real file system path inside the test.

- initializing a default argument:

.. code:: python

  import os

  def check_if_exists(filepath, file_exists=os.path.exists):
      return file_exists(filepath)

Here, ``file_exists`` will not be patched in the test.

To get these cases to work as expected under test, the respective modules
containing the code shall be added to the ``modules_to_reload`` argument (a
module list).
The passed modules will be reloaded, thus allowing pyfakefs to patch them
dynamically. All modules loaded after the initial patching described above
will be patched using this second mechanism.

Given tat the example code shown above is located in the file ``example/sut.py``,
the following code will work:

.. code:: python

  # example using unittest
  class ReloadModuleTest(fake_filesystem_unittest.TestCase):
      def setUp(self):
          self.setUpPyfakefs(modules_to_reload=[example.sut])

      def test_path_exists(self):
          file_path = '/foo/bar'
          self.fs.create_dir(file_path)
          self.assertTrue(example.sut.check_if_exists(file_path))

  # example using Patcher
  def test_path_exists():
      with Patcher() as patcher:
        file_path = '/foo/bar'
        patcher.fs.create_dir(file_path)
        assert example.sut.check_if_exists(file_path)

Example using pytest:

.. code:: python

  # conftest.py
  ...
  from example import sut

  @pytest.fixture
  def fs_reload_sut():
      patcher = Patcher(modules_to_reload=[sut])
      patcher.setUp()
      linecache.open = patcher.original_open
      tokenize._builtin_open = patcher.original_open
      yield patcher.fs
      patcher.tearDown()

  # test_code.py
  ...
  def test_path_exists(fs_reload_sut):
      file_path = '/foo/bar'
      fs_reload_sut.create_dir(file_path)
      assert example.sut.check_if_exists(file_path)


modules_to_patch
~~~~~~~~~~~~~~~~
Sometimes there are file system modules in other packages that are not
patched in standard pyfakefs. To allow patching such modules,
``modules_to_patch`` can be used by adding a fake module implementation for
a module name. The argument is a dictionary of fake modules mapped to the
names to be faked.

This mechanism is used in pyfakefs itself to patch the external modules
`pathlib2` and `scandir` if present, and the following example shows how to
fake a module in Django that uses OS file system functions:

.. code:: python

  class FakeLocks(object):
      """django.core.files.locks uses low level OS functions, fake it."""
      _locks_module = django.core.files.locks

      def __init__(self, fs):
          """Each fake module expects the fake file system as an __init__
          parameter."""
          # fs represents the fake filesystem; for a real example, it can be
          # saved here and used in the implementation
          pass

      @staticmethod
      def lock(f, flags):
          return True

      @staticmethod
      def unlock(f):
          return True

      def __getattr__(self, name):
          return getattr(self._locks_module, name)

  ...
  # test code using Patcher
  with Patcher(modules_to_patch={'django.core.files.locks': FakeLocks}):
      test_django_stuff()

  # test code using unittest
  class TestUsingDjango(fake_filesystem_unittest.TestCase):
      def setUp(self):
          self.setUpPyfakefs(modules_to_patch={'django.core.files.locks': FakeLocks})

      def test_django_stuff()
          ...

additional_skip_names
~~~~~~~~~~~~~~~~~~~~~
This may be used to add modules that shall not be patched. This is mostly
used to avoid patching the Python file system modules themselves, but may be
helpful in some special situations, for example if a testrunner is accessing
the file system after test setup. A known case is erratic behavior if running a
debug session in PyCharm with Python 2.7, which can be avoided by adding the
offending module to ``additional_skip_names``:

.. code:: python

  with Patcher(additional_skip_names=['pydevd']) as patcher:
      patcher.fs.create_file('foo')

There is also the global variable ``Patcher.SKIPNAMES`` that can be extended
for that purpose, though this seldom shall be needed (except for own pytest
plugins, as shown in the example mentioned above). Other than in
``additional_skip_names``, which is a list of modules names, this is a list
of modules that have to be imported before.

allow_root_user
~~~~~~~~~~~~~~~
This is ``True`` by default, meaning that the user is considered a root user
if the real user is a root user (e.g. has the user ID 0). If you want to run
your tests as a non-root user regardless of the actual user rights, you may
want to set this to ``False``.

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
If you want to have read access to real files or directories, you can map
them into the fake file system using ``add_real_file()``,
``add_real_directory()`` and ``add_real_paths()``. They take a file path, a
directory path, or a list of paths, respectively, and make them accessible
from the fake file system. By default, the contents of the mapped files and
directories are read only on demand, so that mapping them is relatively
cheap. The access to the files is by default read-only, but even if you
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
            self.fs.add_real_directory(self.fixture_path)

        def test_using_fixture1(self):
            with open(os.path.join(self.fixture_path, 'fixture1.txt') as f:
                # file contents are copied to the fake file system
                # only at this point
                contents = f.read()

Handling mount points
~~~~~~~~~~~~~~~~~~~~~
Under Linux and MacOS, the root path (``/``) is the only mount point created
in the fake file system. If you need support for more mount points, you can add
them using ``add_mount_point()``.

Under Windows, drives and UNC paths are internally handled as mount points.
Adding a file or directory on another drive or UNC path automatically
adds a mount point for that drive or UNC path root if needed. Explicitly
adding mount points shall not be needed under Windows.

A mount point has a separate device ID (``st_dev``) under all systems, and
some operations (like ``rename``) are not possible for files located on
different mount points. The fake file system size (if used) is also set per
mount point.

Setting the file system size
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you need to know the file system size in your tests (for example for
testing cleanup scripts), you can set the fake file system size using
``set_disk_usage()``. By default, this sets the total size in bytes of the
root partition; if you add a path as parameter, the size will be related to
the mount point (see above) the path is related to.

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

Pausing patching
~~~~~~~~~~~~~~~~
Sometimes, you may want to access the real filesystem inside the test with
no patching applied. This can be achieved by using the ``pause/resume``
functions, which exist in ``fake_filesystem_unittest.Patcher``,
``fake_filesystem_unittest.TestCase`` and ``fake_filesystem.FakeFilesystem``.
There is also a context manager class ``fake_filesystem_unittest.Pause``
which encapsulates the calls to ``pause()`` and ``resume()``.

Here is an example that tests the usage with the pyfakefs pytest fixture:

.. code:: python

    from pyfakefs.fake_filesystem_unittest import Pause

    def test_pause_resume_contextmanager(fs):
        fake_temp_file = tempfile.NamedTemporaryFile()
        assert os.path.exists(fake_temp_file.name)
        fs.pause()
        assert not os.path.exists(fake_temp_file.name)
        real_temp_file = tempfile.NamedTemporaryFile()
        assert os.path.exists(real_temp_file.name)
        fs.resume()
        assert not os.path.exists(real_temp_file.name)
        assert os.path.exists(fake_temp_file.name)

Here is the same code using a context manager:

.. code:: python

    from pyfakefs.fake_filesystem_unittest import Pause

    def test_pause_resume_contextmanager(fs):
        fake_temp_file = tempfile.NamedTemporaryFile()
        assert os.path.exists(fake_temp_file.name)
        with Pause(fs):
            assert not os.path.exists(fake_temp_file.name)
            real_temp_file = tempfile.NamedTemporaryFile()
            assert os.path.exists(real_temp_file.name)
        assert not os.path.exists(real_temp_file.name)
        assert os.path.exists(fake_temp_file.name)

Troubleshooting
---------------

OS temporary directories
~~~~~~~~~~~~~~~~~~~~~~~~

As ``pyfakefs`` does not fake the ``tempfile`` module this means that a
temporary directory is required to ensure ``tempfile`` works correctly, e.g.,
``tempfile.gettempdir()`` will return a valid value. This means that any
newly created fake file system will always have either a directory named
``/tmp`` when running on Linux or Unix systems, ``/var/folders/<hash>/T``
when running on MacOs and ``C:\Users\<user>\AppData\Local\Temp`` on Windows.