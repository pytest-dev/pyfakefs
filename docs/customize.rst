.. _customizing_patcher:

Customizing patching
====================

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
      assert foo()

- You can also pass the arguments using ``@pytest.mark.parametrize``. Note that
  you have to provide `all Patcher arguments`_ before the needed ones, as
  keyword arguments cannot be used, and you have to add ``indirect=True``.
  This makes it less readable, but gives you a quick possibility to adapt a
  single test:

.. code:: python

  import pytest


  @pytest.mark.parametrize("fs", [[None, None, None, False]], indirect=True)
  def test_something(fs):
      assert foo()

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
          assert foo()

patchfs
.......
If you use the ``patchfs`` decorator, you can pass the arguments directly to
the decorator:

.. code:: python

  from pyfakefs.fake_filesystem_unittest import patchfs


  @patchfs(allow_root_user=False)
  def test_something(fake_fs):
      assert foo()


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
  import click


  @click.command()
  @click.argument("foo", type=click.Path(path_type=pathlib.Path))
  def hello(foo):
      pass

To get these cases to work as expected under test, the respective modules
containing the code shall be added to the ``modules_to_reload`` argument (a
module list).
The passed modules will be reloaded, thus allowing ``pyfakefs`` to patch them
dynamically. All modules loaded after the initial patching described above
will be patched using this second mechanism.

Given that the example function ``check_if_exists`` shown above is located in
the file ``example/sut.py``, the following code will work (imports are omitted):

.. code:: python

  import example


  # example using unittest
  class ReloadModuleTest(fake_filesystem_unittest.TestCase):
      def setUp(self):
          self.setUpPyfakefs(modules_to_reload=[example.sut])

      def test_path_exists(self):
          file_path = "/foo/bar"
          self.fs.create_dir(file_path)
          self.assertTrue(example.sut.check_if_exists(file_path))


  # example using pytest
  @pytest.mark.parametrize("fs", [[None, [example.sut]]], indirect=True)
  def test_path_exists(fs):
      file_path = "/foo/bar"
      fs.create_dir(file_path)
      assert example.sut.check_if_exists(file_path)


  # example using Patcher
  def test_path_exists():
      with Patcher(modules_to_reload=[example.sut]) as patcher:
          file_path = "/foo/bar"
          patcher.fs.create_dir(file_path)
          assert example.sut.check_if_exists(file_path)


  # example using patchfs decorator
  @patchfs(modules_to_reload=[example.sut])
  def test_path_exists(fs):
      file_path = "/foo/bar"
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

  import django


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
  with Patcher(modules_to_patch={"django.core.files.locks": FakeLocks}):
      test_django_stuff()


  # test code using unittest
  class TestUsingDjango(fake_filesystem_unittest.TestCase):
      def setUp(self):
          self.setUpPyfakefs(modules_to_patch={"django.core.files.locks": FakeLocks})

      def test_django_stuff(self):
          assert foo()


  # test code using pytest
  @pytest.mark.parametrize(
      "fs", [[None, None, {"django.core.files.locks": FakeLocks}]], indirect=True
  )
  def test_django_stuff(fs):
      assert foo()


  # test code using patchfs decorator
  @patchfs(modules_to_patch={"django.core.files.locks": FakeLocks})
  def test_django_stuff(fake_fs):
      assert foo()

additional_skip_names
.....................
This may be used to add modules that shall not be patched. This is mostly
used to avoid patching the Python file system modules themselves, but may be
helpful in some special situations, for example if a testrunner needs to access
the file system after test setup. To make this possible, the affected module
can be added to ``additional_skip_names``:

.. code:: python

  with Patcher(additional_skip_names=["pydevd"]) as patcher:
      patcher.fs.create_file("foo")

Alternatively to the module names, the modules themselves may be used:

.. code:: python

  import pydevd
  from pyfakefs.fake_filesystem_unittest import Patcher

  with Patcher(additional_skip_names=[pydevd]) as patcher:
      patcher.fs.create_file("foo")

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
to allow users to disable this patching in case it causes any problems.

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
      assert foo()

In this mode, it is also possible to import modules created in the fake filesystem
using `importlib.import_module`. Make sure that the `sys.path` contains the parent path in this case:

.. code:: python

  @patchfs(patch_open_code=PatchMode.AUTO)
  def test_fake_import(fs):
      fake_module_path = Path("/") / "site-packages" / "fake_module.py"
      self.fs.create_file(fake_module_path, contents="x = 5")
      sys.path.insert(0, str(fake_module_path.parent))
      module = importlib.import_module("fake_module")
      assert module.x == 5


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

.. note:: There are some cases where this option does *not* work:

  - if default arguments are *computed* using file system functions:

    .. code:: python

      import os


      def some_function(use_bar=os.path.exists("/foo/bar")):
          return do_something() if use_bar else do_something_else()

  - if the default argument is an instance of ``pathlib.Path``:

    .. code:: python

      import pathlib


      def foobar(dir_arg=pathlib.Path.cwd() / "logs"):
          do_something(dir_arg)

  In both cases the default arguments behave like global variables that use a file system function
  (which they basically are), and can only be handled using :ref:`modules_to_reload`.


use_cache
.........
If True (the default), patched and non-patched modules are cached between tests
to avoid the performance hit of the file system function lookup (the
patching itself is reverted after each test). This argument allows to turn it off in case it causes any problems:

.. code:: python

  @patchfs(use_cache=False)
  def test_something(fake_fs):
      fake_fs.create_file("foo", contents="test")
      ...

If using ``pytest``, the cache is always cleared before the final test shutdown, as there has been a problem
happening on shutdown related to removing the cached modules.
This does not happen for other test methods so far.

If you think you have encountered a similar problem with ``unittest``, you may try to clear the cache
during module shutdown using the class method for clearing the cache:

.. code:: python

  from pyfakefs.fake_filesystem_unittest import Patcher


  def tearDownModule():
      Patcher.clear_fs_cache()

Please write an issue if you encounter any problem that can be fixed by using this parameter.

If you want to clear the cache just for a specific test instead, you can call
``clear_cache`` on the ``Patcher`` or the ``fake_filesystem`` instance:

.. code:: python

  def test_something(fs):  # using pytest fixture
      fs.clear_cache()
      ...

.. _use_dynamic_patch:

use_dynamic_patch
.................
If ``True`` (the default), dynamic patching after setup is used (for example
for modules loaded locally inside of functions).
Can be switched off if it causes unwanted side effects, though that would mean that
dynamically loaded modules are no longer patched, if they use file system functions.
See also :ref:`failing_dyn_patcher` in the troubleshooting guide for more information.


.. _`all Patcher arguments`: https://pytest-pyfakefs.readthedocs.io/en/latest/modules.html#pyfakefs.fake_filesystem_unittest.Patcher
