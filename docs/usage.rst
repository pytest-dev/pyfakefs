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

    from pyfakefs.fake_filesystem_unittest import TestCase

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

   from pyfakefs.fake_filesystem_unittest import Patcher

   with Patcher() as patcher:
       # access the fake_filesystem object via patcher.fs
       patcher.fs.create_file('/foo/bar', contents='test')

       # the following code works on the fake filesystem
       with open('/foo/bar') as f:
           contents = f.read()

You can also initialize ``Patcher`` manually:

.. code:: python

   from pyfakefs.fake_filesystem_unittest import Patcher

   patcher = Patcher()
   patcher.setUp()     # called in the initialization code
   ...
   patcher.tearDown()  # somewhere in the cleanup code

Patch using fake_filesystem_unittest.patchfs decorator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This is basically a convenience wrapper for the previous method.
If you want to use the fake filesystem for a single function, you can write:

.. code:: python

   from pyfakefs.fake_filesystem_unittest import patchfs

   @patchfs
   def test_something(fs):
       # access the fake_filesystem object via fs
       fs.create_file('/foo/bar', contents='test')

Note the argument name ``fs``, which is mandatory.

Don't confuse this with pytest tests, where ``fs`` is the fixture name (with
the same functionality). If you use pytest, you don't need this decorator.

You can also use this to make a single unit test use the fake fs:

.. code:: python

    class TestSomething(unittest.TestCase):

        @patchfs
        def test_something(self, fs):
            fs.create_file('/foo/bar', contents='test')

If you want to pass additional arguments to the patcher you can just
pass them to the decorator:

.. code:: python

    @patchfs(allow_root_user=False)
    def test_something(fs):
        # now always called as non-root user
        os.makedirs('/foo/bar')

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

.. note:: If you need these arguments in ``PyTest``, you can pass them using
  ``@pytest.mark.parametrize``. Note that you have to also provide
  `all Patcher arguments <http://jmcgeheeiv.github.io/pyfakefs/master/modules.html#pyfakefs.fake_filesystem_unittest.Patcher>`__
  before the needed ones, as keyword arguments cannot be used, and you have to
  add ``indirect=True`` as argument.
  Alternatively, you can add your own fixture with the needed parameters.

  Examples for the first approach can be found below, and in
  `pytest_fixture_param_test.py <https://github.com/jmcgeheeiv/pyfakefs/blob/master/pyfakefs/pytest_tests/pytest_fixture_param_test.py>`__.
  The second approach is shown in
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

Initializing a default argument with a file system function is also patched
automatically:

.. code:: python

  import os

  def check_if_exists(filepath, file_exists=os.path.exists):
      return file_exists(filepath)

There are a few cases where automatic patching does not work. We know of at
least one specific case where this is the case:

If initializing a global variable using a file system function, the
initialization will be done using the real file system:

.. code:: python

  from pathlib import Path

  path = Path("/example_home")

In this case, ``path`` will hold the real file system path inside the test.

To get these cases to work as expected under test, the respective modules
containing the code shall be added to the ``modules_to_reload`` argument (a
module list).
The passed modules will be reloaded, thus allowing pyfakefs to patch them
dynamically. All modules loaded after the initial patching described above
will be patched using this second mechanism.

Given that the example code shown above is located in the file
``example/sut.py``, the following code will work:

.. code:: python

  import example

  # example using unittest
  class ReloadModuleTest(fake_filesystem_unittest.TestCase):
      def setUp(self):
          self.setUpPyfakefs(modules_to_reload=[example.sut])

      def test_path_exists(self):
          file_path = '/foo/bar'
          self.fs.create_dir(file_path)
          self.assertTrue(example.sut.check_if_exists(file_path))

  # example using pytest
  @pytest.mark.parametrize('fs', [[None, [example.sut]]], indirect=True)
  def test_path_exists(fs):
      file_path = '/foo/bar'
      fs.create_dir(file_path)
      assert example.sut.check_if_exists(file_path)

  # example using Patcher
  def test_path_exists():
      with Patcher(modules_to_reload=[example.sut]) as patcher:
        file_path = '/foo/bar'
        patcher.fs.create_dir(file_path)
        assert example.sut.check_if_exists(file_path)

  # example using patchfs decorator
  @patchfs(modules_to_reload=[example.sut])
  def test_path_exists(fs):
      file_path = '/foo/bar'
      fs.create_dir(file_path)
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
fake a module in Django that uses OS file system functions (note that this
has now been been integrated into pyfakefs):

.. code:: python

  class FakeLocks:
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

      def test_django_stuff(self)
          ...

  # test code using pytest
  @pytest.mark.parametrize('fs', [[None, None,
    {'django.core.files.locks': FakeLocks}]], indirect=True)
  def test_django_stuff(fs):
      ...

  # test code using patchfs decorator
  @patchfs(modules_to_patch={'django.core.files.locks': FakeLocks})
  def test_django_stuff(fs):
      ...

additional_skip_names
~~~~~~~~~~~~~~~~~~~~~
This may be used to add modules that shall not be patched. This is mostly
used to avoid patching the Python file system modules themselves, but may be
helpful in some special situations, for example if a testrunner needs to access
the file system after test setup. To make this possible, the affected module
can be added to ``additional_skip_names``:

.. code:: python

  with Patcher(additional_skip_names=['pydevd']) as patcher:
      patcher.fs.create_file('foo')

Alternatively to the module names, the modules themselves may be used:

.. code:: python

  import pydevd

  with Patcher(additional_skip_names=[pydevd]) as patcher:
      patcher.fs.create_file('foo')

There is also the global variable ``Patcher.SKIPNAMES`` that can be extended
for that purpose, though this seldom shall be needed (except for own pytest
plugins, as shown in the example mentioned above).

allow_root_user
~~~~~~~~~~~~~~~
This is ``True`` by default, meaning that the user is considered a root user
if the real user is a root user (e.g. has the user ID 0). If you want to run
your tests as a non-root user regardless of the actual user rights, you may
want to set this to ``False``.

use_known_patches
~~~~~~~~~~~~~~~~~
If this is set to ``True`` (the default), ``pyfakefs`` patches some
libraries that are known to not work out of the box, to be able to work with
the fake filesystem. Currently, this includes patches for some ``pandas``
read methods like ``read_csv`` and ``read_excel`` - more may follow. This
flag is there to allow to disable this functionality in case it causes any
problems. It may be removed or replaced by a more fine-grained argument in
future releases.


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

    from pyfakefs.fake_filesystem_unittest import TestCase

    class ExampleTestCase(TestCase):
        def setUp(self):
            self.setUpPyfakefs()

        def test_create_file(self):
            file_path = '/foo/bar/test.txt'
            self.fs.create_file(file_path, contents = 'test')
            with open(file_path) as f:
                self.assertEqual('test', f.read())

``create_dir()`` behaves like ``os.makedirs()``.

Access to files in the real file system
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you want to have read access to real files or directories, you can map
them into the fake file system using ``add_real_file()``,
``add_real_directory()``, ``add_real_symlink()`` and ``add_real_paths()``.
They take a file path, a directory path, a symlink path, or a list of paths,
respectively, and make them accessible from the fake file system. By
default, the contents of the mapped files and directories are read only on
demand, so that mapping them is relatively cheap. The access to the files is
by default read-only, but even if you add them using ``read_only=False``,
the files are written only in the fake system (e.g. in memory). The real
files are never changed.

``add_real_file()``, ``add_real_directory()`` and ``add_real_symlink()`` also
allow you to map a file or a directory tree into another location in the
fake filesystem via the argument ``target_path``.

.. code:: python

    from pyfakefs.fake_filesystem_unittest import TestCase

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

You can do the same using ``pytest`` by using a fixture for test setup:

.. code:: python

    import pytest
    import os

    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures')

    @pytest.fixture
    def my_fs(fs):
        fs.add_real_directory(fixture_path)
        yield fs

    def test_using_fixture1(my_fs):
        with open(os.path.join(fixture_path, 'fixture1.txt') as f:
            contents = f.read()

When using ``pytest`` another option is to load the contents of the real file
in a fixture and pass this fixture to the test function **before** passing
the ``fs`` fixture.

.. code:: python

    import pytest
    import os

    @pytest.fixture
    def content():
        fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures')
        with open(os.path.join(fixture_path, 'fixture1.txt') as f:
            contents = f.read()
        return contents

    def test_using_file_contents(content, fs):
        fs.create_file("fake/path.txt")
        assert content != ""


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

    from pyfakefs.fake_filesystem_unittest import TestCase

    class ExampleTestCase(TestCase):

        def setUp(self):
            self.setUpPyfakefs()
            self.fs.set_disk_usage(100)

        def test_disk_full(self):
            with open('/foo/bar.txt', 'w') as f:
                with self.assertRaises(OSError):
                    f.write('a' * 200)

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

Modules not working with pyfakefs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modules may not work with ``pyfakefs`` for several reasons. ``pyfakefs``
works by patching some file system related modules and functions, specifically:

- most file system related functions in the ``os`` and ``os.path`` modules
- the ``pathlib`` module
- the build-in ``open`` function and ``io.open``
- ``shutil.disk_usage``

Other file system related modules work with ``pyfakefs``, because they use
exclusively these patched functions, specifically ``shutil`` (except for
``disk_usage``), ``tempfile``, ``glob`` and ``zipfile``.

A module may not work with ``pyfakefs`` because of one of the following
reasons:

- It uses a file system related function of the mentioned modules that is
  not or not correctly patched. Mostly these are functions that are seldom
  used, but may be used in Python libraries (this has happened for example
  with a changed implementation of ``shutil`` in Python 3.7). Generally,
  these shall be handled in issues and we are happy to fix them.
- It uses file system related functions in a way that will not be patched
  automatically. This is the case for functions that are executed while
  reading a module. This case and a possibility to make them work is
  documented above under ``modules_to_reload``.
- It uses OS specific file system functions not contained in the Python
  libraries. These will not work out of the box, and we generally will not
  support them in ``pyfakefs``. If these functions are used in isolated
  functions or classes, they may be patched by using the ``modules_to_patch``
  parameter (see the example for file locks in Django above), and if there
  are more examples for patches that may be useful, we may add them in the
  documentation.
- It uses C libraries to access the file system. There is no way no make
  such a module work with ``pyfakefs`` - if you want to use it, you have to
  patch the whole module. In some cases, a library implemented in Python with
  a similar interface already exists. An example is ``lxml``,
  which can be substituted with ``ElementTree`` in most cases for testing.

A list of Python modules that are known to not work correctly with
``pyfakefs`` will be collected here:

- ``multiprocessing`` has several issues (related to points 1 and 3 above).
  Currently there are no plans to fix this, but this may change in case of
  sufficient demand.
- the ``Pillow`` image library does not work with pyfakefs at least if writing
  JPEG files (see `this issue <https://github.com/jmcgeheeiv/pyfakefs/issues/529>`__)
- ``pandas`` (the Python data analysis library) uses its own internal file
  system access, written in C, and does therefore not work with pyfakefs out
   of the box. ``pyfakefs`` adds some patches so that many of the
   ``read_xxx`` functions will work with the fake system (including
   ``read_csv`` and ``read_excel``).

If you are not sure if a module can be handled, or how to do it, you can
always write a new issue, of course!

OS temporary directories
~~~~~~~~~~~~~~~~~~~~~~~~

Tests relying on a completely empty file system on test start will fail.
As ``pyfakefs`` does not fake the ``tempfile`` module (as described above),
a temporary directory is required to ensure ``tempfile`` works correctly,
e.g., that ``tempfile.gettempdir()`` will return a valid value. This
means that any newly created fake file system will always have either a
directory named ``/tmp`` when running on Linux or Unix systems,
``/var/folders/<hash>/T`` when running on MacOs and
``C:\Users\<user>\AppData\Local\Temp`` on Windows.

User rights
~~~~~~~~~~~

If you run pyfakefs tests as root (this happens by default if run in a
docker container), pyfakefs also behaves as a root user, for example can
write to write-protected files. This may not be the expected behavior, and
can be changed.
Pyfakefs has a rudimentary concept of user rights, which differentiates
between root user (with the user id 0) and any other user. By default,
pyfakefs assumes the user id of the current user, but you can change
that using ``fake_filesystem.set_uid()`` in your setup. This allows to run
tests as non-root user in a root user environment and vice verse.
Another possibility is the convenience argument ``allow_root_user``
described above.
