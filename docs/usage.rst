Usage
=====

Test Scenarios
--------------
There are several approaches for implementing tests using ``pyfakefs``.

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
demonstrated in the files `example.py`_ and `example_test.py`_.

Patch using the pytest plugin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you use `pytest`_, you will be interested in the pytest plugin in
``pyfakefs``.
This automatically patches all file system functions and modules in a
similar manner as described above.

The pytest plugin provides the ``fs`` fixture for use in your test. The plugin
is registered for pytest on installing ``pyfakefs`` as usual for pytest
plugins, so you can just use it:

.. code:: python

   def my_fakefs_test(fs):
       # "fs" is the reference to the fake file system
       fs.create_file('/var/data/xx1.txt')
       assert os.path.exists('/var/data/xx1.txt')

If you are bothered by the ``pylint`` warning,
``C0103: Argument name "fs" doesn't conform to snake_case naming style
(invalid-name)``,
you can define a longer name in your ``conftest.py`` and use that in your
tests:

.. code:: python

    @pytest.fixture
    def fake_filesystem(fs):  # pylint:disable=invalid-name
        """Variable name 'fs' causes a pylint warning. Provide a longer name
        acceptable to pylint for use in tests.
        """
        yield fs

For convenience, module- and session-scoped fixtures with the same
functionality are provided, named ``fs_module`` and ``fs_session``,
respectively.


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
If you are not using ``pytest`` and  want to use the fake filesystem for a
single function, you can write:

.. code:: python

   from pyfakefs.fake_filesystem_unittest import patchfs

   @patchfs
   def test_something(fake_fs):
       # access the fake_filesystem object via fake_fs
       fake_fs.create_file('/foo/bar', contents='test')

Note that ``fake_fs`` is a positional argument and the argument name does
not matter. If there are additional ``mock.patch`` decorators that also
create positional arguments, the argument order is the same as the decorator
order, as shown here:

.. code:: python

   @patchfs
   @mock.patch('foo.bar')
   def test_something(fake_fs, mocked_bar):
       ...

   @mock.patch('foo.bar')
   @patchfs
   def test_something(mocked_bar, fake_fs):
       ...

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
            fs.create_file('/foo/bar', contents='test')


.. _customizing_patcher:

Customizing patching
--------------------

``fake_filesystem_unittest.Patcher`` provides a few arguments to adapt
patching for cases where it does not work out of the box. These arguments
can also be used with ``unittest`` and ``pytest``.

Using custom arguments
~~~~~~~~~~~~~~~~~~~~~~
The following sections describe how to apply these arguments in different
scenarios, using the argument :ref:`allow_root_user` as an example.

Patcher
.......
If you use the ``Patcher`` directly, you can just pass the arguments in the
constructor:

.. code:: python

  from pyfakefs.fake_filesystem_unittest import Patcher

  with Patcher(allow_root_user=False) as patcher:
      ...

Unittest
........
If you are using ``fake_filesystem_unittest.TestCase``, the arguments can be
passed to ``setUpPyfakefs()``, which will pass them to the ``Patcher``
instance:

.. code:: python

  from pyfakefs.fake_filesystem_unittest import TestCase

  class SomeTest(TestCase):
      def setUp(self):
          self.setUpPyfakefs(allow_root_user=False)

      def testSomething(self):
          ...

Pytest
......

In case of ``pytest``, you have two possibilities:

- The standard way to customize the ``fs`` fixture is to write your own
  fixture which uses the ``Patcher`` with arguments as has been shown above:

.. code:: python

  import pytest
  from pyfakefs.fake_filesystem_unittest import Patcher

  @pytest.fixture
  def fs_no_root():
      with Patcher(allow_root_user=False) as patcher:
          yield patcher.fs

  def test_something(fs_no_root):
      ...

- You can also pass the arguments using ``@pytest.mark.parametrize``. Note that
  you have to provide `all Patcher arguments`_ before the needed ones, as
  keyword arguments cannot be used, and you have to add ``indirect=True``.
  This makes it less readable, but gives you a quick possibility to adapt a
  single test:

.. code:: python

  import pytest

  @pytest.mark.parametrize('fs', [[None, None, None, False]], indirect=True)
  def test_something(fs):
      ...


patchfs
.......
If you use the ``patchfs`` decorator, you can pass the arguments directly to
the decorator:

.. code:: python

  from pyfakefs.fake_filesystem_unittest import patchfs

  @patchfs(allow_root_user=False)
  def test_something(fake_fs):
      ...


List of custom arguments
~~~~~~~~~~~~~~~~~~~~~~~~

Following is a description of the optional arguments that can be used to
customize ``pyfakefs``.

.. _modules_to_reload:

modules_to_reload
.................
``Pyfakefs`` patches modules that are imported before starting the test by
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

There are a few cases where automatic patching does not work. We know of at
least two specific cases where this is the case:

Initializing a default argument with a file system function is not patched
automatically due to performance reasons (though it can be switched on using
:ref:`patch_default_args`):

.. code:: python

  import os

  def check_if_exists(filepath, file_exists=os.path.exists):
      return file_exists(filepath)


If initializing a global variable using a file system function, the
initialization will be done using the real file system:

.. code:: python

  from pathlib import Path

  path = Path("/example_home")

In this case, ``path`` will hold the real file system path inside the test.
The same is true, if a file system function is used in a decorator (this is
an example from a related issue):

.. code:: python

  import pathlib

  @click.command()
  @click.argument('foo', type=click.Path(path_type=pathlib.Path))
  def hello(foo):
      pass

To get these cases to work as expected under test, the respective modules
containing the code shall be added to the ``modules_to_reload`` argument (a
module list).
The passed modules will be reloaded, thus allowing ``pyfakefs`` to patch them
dynamically. All modules loaded after the initial patching described above
will be patched using this second mechanism.

Given that the example function ``check_if_exists`` shown above is located in
the file ``example/sut.py``, the following code will work:

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

      
.. note:: If the reloaded modules depend on each other (e.g. one imports the other), 
  the order in which they are reloaded matters. The dependent module should be reloaded 
  first, so that on reloading the depending module it is already correctly patched. 


modules_to_patch
................
Sometimes there are file system modules in other packages that are not
patched in standard ``pyfakefs``. To allow patching such modules,
``modules_to_patch`` can be used by adding a fake module implementation for
a module name. The argument is a dictionary of fake modules mapped to the
names to be faked.

This mechanism is used in ``pyfakefs`` itself to patch the external modules
`pathlib2` and `scandir` if present, and the following example shows how to
fake a module in Django that uses OS file system functions (note that this
has now been been integrated into ``pyfakefs``):

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
  def test_django_stuff(fake_fs):
      ...

additional_skip_names
.....................
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

.. _allow_root_user:

allow_root_user
...............
This is ``True`` by default, meaning that the user is considered a root user
if the real user is a root user (e.g. has the user ID 0). If you want to run
your tests as a non-root user regardless of the actual user rights, you may
want to set this to ``False``.

use_known_patches
.................
Some libraries are known to require patching in order to work with
``pyfakefs``.
If ``use_known_patches`` is set to ``True`` (the default), ``pyfakefs`` patches
these libraries so that they will work with the fake filesystem. Currently, this
includes patches for ``pandas`` read methods like ``read_csv`` and
``read_excel``, and for ``Django`` file locks--more may follow. Ordinarily,
the default value of ``use_known_patches`` should be used, but it is present
to allow users to disable this patching in case it causes any problems. It
may be removed or replaced by more fine-grained arguments in future releases.

patch_open_code
...............
Since Python 3.8, the ``io`` module has the function ``open_code``, which
opens a file read-only and is used to open Python code files. By default, this
function is not patched, because the files it opens usually belong to the
executed library code and are not present in the fake file system.
Under some circumstances, this may not be the case, and the opened file
lives in the fake filesystem. For these cases, you can set ``patch_open_code``
to ``PatchMode.ON``. If you just want to patch ``open_case`` for files that
live in the fake filesystem, and use the real function for the rest, you can
set ``patch_open_code`` to ``PatchMode.AUTO``:

.. code:: python

  from pyfakefs.fake_filesystem_unittest import PatchMode

  @patchfs(patch_open_code=PatchMode.AUTO)
  def test_something(fs):
      ...

.. note:: This argument is subject to change or removal in future
  versions of ``pyfakefs``, depending on the upcoming use cases.

.. _patch_default_args:

patch_default_args
..................
As already mentioned, a default argument that is initialized with a file
system function is not patched automatically:

.. code:: python

  import os

  def check_if_exists(filepath, file_exists=os.path.exists):
      return file_exists(filepath)

As this is rarely needed, and the check to patch this automatically is quite
expansive, it is not done by default. Using ``patch_default_args`` will
search for this kind of default arguments and patch them automatically.
You could also use the :ref:`modules_to_reload` option with the module that
contains the default argument instead, if you want to avoid the overhead.

.. note:: There are some cases where this option dees not work:

  - if default arguments are *computed* using file system functions:

    .. code:: python

      import os

      def some_function(use_bar=os.path.exists("/foo/bar")):
          return do_something() if use_bar else do_something_else()

  - if the default argument is an instance of ``pathlib.Path``:

    .. code:: python

      import pathlib

      def foobar(dir_arg = pathlib.Path.cwd() / 'logs'):
          do_something(dir_arg)

  In both cases the default arguments behave like global variables that use a file system function
  (which they basically are), and can only be handled using :ref:`modules_to_reload`.


use_cache
.........
If True (the default), patched and non-patched modules are cached between tests
to avoid the performance hit of the file system function lookup (the
patching itself is reverted after each test). As this is a new
feature, this argument allows to turn it off in case it causes any problems:

.. code:: python

  @patchfs(use_cache=False)
  def test_something(fake_fs):
      fake_fs.create_file("foo", contents="test")
      ...

Please write an issue if you encounter any problem that can be fixed by using
this parameter. Note that this argument may be removed in a later version, if
no problems come up.

If you want to clear the cache just for a specific test instead, you can call
``clear_cache`` on the ``Patcher`` or the ``fake_filesystem`` instance:

.. code:: python

  def test_something(fs):  # using pytest fixture
      fs.clear_cache()
      ...


Using convenience methods
-------------------------
While ``pyfakefs`` can be used just with the standard Python file system
functions, there are few convenience methods in ``fake_filesystem`` that can
help you setting up your tests. The methods can be accessed via the
``fake_filesystem`` instance in your tests: ``Patcher.fs``, the ``fs``
fixture in pytest, ``TestCase.fs`` for ``unittest``, and the ``fs`` argument
for the ``patchfs`` decorator.

File creation helpers
~~~~~~~~~~~~~~~~~~~~~
To create files, directories or symlinks together with all the directories
in the path, you may use ``create_file()``, ``create_dir()``,
``create_symlink()`` and ``create_link()``, respectively.

``create_file()`` also allows you to set the file mode and the file contents
together with the encoding if needed. Alternatively, you can define a file
size without contents--in this case, you will not be able to perform
standard I\O operations on the file (may be used to fill up the file system
with large files, see also :ref:`set-fs-size`).

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
``create_symlink`` and ``create_link`` behave like ``os.symlink`` and
``os.link``, with any missing parent directories of the link created
automatically.

.. caution::
  The first two arguments in ``create_symlink`` are reverted in relation to
  ``os.symlink`` for historical reasons.

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

.. _set-fs-size:

Setting the file system size
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you need to know the file system size in your tests (for example for
testing cleanup scripts), you can set the fake file system size using
``set_disk_usage()``. By default, this sets the total size in bytes of the
root partition; if you add a path as parameter, the size will be related to
the mount point (see above) the path is related to.

By default, the size of the fake file system is set to 1 TB (which
for most tests can be considered as infinite). As soon as you set a
size, all files will occupy the space according to their size,
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
                    f.flush()

To get the file system size, you may use ``get_disk_usage()``, which is
modeled after ``shutil.disk_usage()``.

Suspending patching
~~~~~~~~~~~~~~~~~~~
Sometimes, you may want to access the real filesystem inside the test with
no patching applied. This can be achieved by using the ``pause/resume``
functions, which exist in ``fake_filesystem_unittest.Patcher``,
``fake_filesystem_unittest.TestCase`` and ``fake_filesystem.FakeFilesystem``.
There is also a context manager class ``fake_filesystem_unittest.Pause``
which encapsulates the calls to ``pause()`` and ``resume()``.

Here is an example that tests the usage with the ``pyfakefs`` pytest fixture:

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

Simulating other file systems
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``Pyfakefs`` supports Linux, MacOS and Windows operating systems. By default,
the file system of the OS where the tests run is assumed, but it is possible
to simulate other file systems to some extent. To set a specific file
system, you can change ``pyfakefs.FakeFilesystem.os`` to one of
``OSType.LINUX``, ``OSType.MACOS`` and ``OSType.WINDOWS``. On doing so, the
behavior of ``pyfakefs`` is adapted to the respective file system. Note that
setting this causes the fake file system to be reset, so you should call it
before adding any files.

Setting the ``os`` attributes changes a number of ``pyfakefs.FakeFilesystem``
attributes, which can also be set separately if needed:

  - ``is_windows_fs`` -  if ``True`` a Windows file system (NTFS) is assumed
  - ``is_macos`` - if ``True`` and ``is_windows_fs`` is ``False``, the
    standard MacOS file system (HFS+) is assumed
  - if ``is_windows_fs`` and ``is_macos`` are ``False``, a Linux file system
    (something like ext3) is assumed
  - ``is_case_sensitive`` is set to ``True`` under Linux and to ``False``
    under Windows and MacOS by default - you can change it to change the
    respective behavior
  - ``path_separator`` is set to ``\`` under Windows and to ``/`` under Posix,
    ``alternative_path_separator`` is set to ``/`` under Windows and to
    ``None`` under Posix--these can also be adapted if needed

The following test works both under Windows and Linux:

.. code:: python

  from pyfakefs.fake_filesystem import OSType

  def test_windows_paths(fs):
      fs.os = OSType.WINDOWS
      assert r"C:\foo\bar" == os.path.join('C:\\', 'foo', 'bar'))
      assert os.path.splitdrive(r"C:\foo\bar") == ("C:", r"\foo\bar")
      assert os.path.ismount("C:")

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
  parameter (see the example for file locks in Django above), or by using
  ``unittest.patch`` if you don't need to simulate the functions. We
  added some of these patches to ``pyfakefs``, so that they are applied
  automatically (currently done for some ``pandas`` and ``Django``
  functionality).
- It uses C libraries to access the file system. There is no way no make
  such a module work with ``pyfakefs``--if you want to use it, you
  have to patch the whole module. In some cases, a library implemented in
  Python with a similar interface already exists. An example is ``lxml``,
  which can be substituted with ``ElementTree`` in most cases for testing.

A list of Python modules that are known to not work correctly with
``pyfakefs`` will be collected here:

- `multiprocessing`_ has several issues (related to points 1 and 3 above).
  Currently there are no plans to fix this, but this may change in case of
  sufficient demand.
- `subprocess`_ has very similar problems and cannot be used with
  ``pyfakefs`` to start a process. ``subprocess`` can either be mocked, if
  the process is not needed for the test, or patching can be paused to start
  a process if needed, and resumed afterwards
  (see `this issue <https://github.com/jmcgeheeiv/pyfakefs/issues/447>`__).
- Modules that rely on ``subprocess`` or ``multiprocessing`` to work
  correctly, e.g. need to start other executables. Examples that have shown
  this problem include `GitPython`_ and `plumbum`_.
- the `Pillow`_ image library does not work with pyfakefs at least if writing
  JPEG files (see `this issue <https://github.com/jmcgeheeiv/pyfakefs/issues/529>`__)
- `pandas`_ (the Python data analysis library) uses its own internal file
  system access written in C. Thus much of ``pandas`` will not work with
  ``pyfakefs``. Having said that, ``pyfakefs`` patches ``pandas`` so that many
  of the ``read_xxx`` functions, including ``read_csv`` and ``read_excel``,
  as well as some writer functions, do work with the fake file system. If
  you use only these functions, ``pyfakefs`` will work with ``pandas``.

If you are not sure if a module can be handled, or how to do it, you can
always write a new issue, of course!

Pyfakefs behaves differently than the real filesystem
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
There are basically two kinds of deviations from the actual behavior:

- unwanted deviations that we didn't notice--if you find any of these, please
  write an issue and will try to fix it
- behavior that depends on different OS versions and editions--as mentioned
  in :ref:`limitations`, ``pyfakefs`` uses the TravisCI systems as reference
  system and will not replicate all system-specific behavior

OS temporary directories
~~~~~~~~~~~~~~~~~~~~~~~~

Tests relying on a completely empty file system on test start will fail.
As ``pyfakefs`` does not fake the ``tempfile`` module (as described above),
a temporary directory is required to ensure ``tempfile`` works correctly,
e.g., that ``tempfile.gettempdir()`` will return a valid value. This
means that any newly created fake file system will always have either a
directory named ``/tmp`` when running on Linux or Unix systems,
``/var/folders/<hash>/T`` when running on MacOs, or
``C:\Users\<user>\AppData\Local\Temp`` on Windows.

User rights
~~~~~~~~~~~

If you run ``pyfakefs`` tests as root (this happens by default if run in a
docker container), ``pyfakefs`` also behaves as a root user, for example can
write to write-protected files. This may not be the expected behavior, and
can be changed.
``Pyfakefs`` has a rudimentary concept of user rights, which differentiates
between root user (with the user id 0) and any other user. By default,
``pyfakefs`` assumes the user id of the current user, but you can change
that using ``fake_filesystem.set_uid()`` in your setup. This allows to run
tests as non-root user in a root user environment and vice verse.
Another possibility to run tests as non-root user in a root user environment
is the convenience argument :ref:`allow_root_user`.

.. _usage_with_mock_open:

Pyfakefs and mock_open
~~~~~~~~~~~~~~~~~~~~~~
If you patch ``open`` using ``mock_open`` before the initialization of
``pyfakefs``, it will not work properly, because the ``pyfakefs``
initialization relies on ``open`` working correctly.
Generally, you should not need ``mock_open`` if using ``pyfakefs``, because you
always can create the files with the needed content using ``create_file``.
This is true for patching any filesystem functions - avoid patching them
while working with ``pyfakefs``.
If you still want to use ``mock_open``, make sure it is only used while
patching is in progress. For example, if you are using ``pytest`` with the
``mocker`` fixture used to patch ``open``, make sure that the ``fs`` fixture is
passed before the ``mocker`` fixture to ensure this.

.. _`example.py`: https://github.com/jmcgeheeiv/pyfakefs/blob/master/pyfakefs/tests/example.py
.. _`example_test.py`: https://github.com/jmcgeheeiv/pyfakefs/blob/master/pyfakefs/tests/example_test.py
.. _`pytest`: https://doc.pytest.org
.. _`nose`: https://docs.nose2.io/en/latest/
.. _`all Patcher arguments`: https://jmcgeheeiv.github.io/pyfakefs/master/modules.html#pyfakefs.fake_filesystem_unittest.Patcher
.. _`multiprocessing`: https://docs.python.org/3/library/multiprocessing.html
.. _`subprocess`: https://docs.python.org/3/library/subprocess.html
.. _`GitPython`: https://pypi.org/project/GitPython/
.. _`plumbum`: https://pypi.org/project/plumbum/
.. _`Pillow`: https://pypi.org/project/Pillow/
.. _`pandas`: https://pypi.org/project/pandas/