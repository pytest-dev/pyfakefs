Troubleshooting
===============
This is a collection of problems with ``pyfakefs`` and possible solutions.
It will be expanded continuously based on issues and problems found by users.

Modules not working with pyfakefs
---------------------------------

Modules may not work with ``pyfakefs`` for several reasons. ``pyfakefs``
works by patching some file system related modules and functions, specifically:

- most file system related functions in the ``os`` and ``os.path`` modules
- the ``pathlib`` module
- the built-in ``open`` function and ``io.open``
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

`multiprocessing`_ (built-in)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This module has several issues (related to points 1 and 3 above).
Currently there are no plans to fix this, but this may change in case of
sufficient demand.

`subprocess`_ (built-in)
~~~~~~~~~~~~~~~~~~~~~~~~
This has very similar problems to ``multiprocessing`` and cannot be used with
``pyfakefs`` to start a process. ``subprocess`` can either be mocked, if
the process is not needed for the test, or patching can be paused to start
a process if needed, and resumed afterwards
(see `this issue <https://github.com/pytest-dev/pyfakefs/issues/447>`__).

Modules that rely on ``subprocess`` or ``multiprocessing``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This includes a number of modules that need to start other executables to
function correctly. Examples that have shown this problem include `GitPython`_
and `plumbum`_. Calling ``find_library`` also uses ``subprocess`` and does not work in
the fake filesystem.

`sqlite3`_ (built-in)
~~~~~~~~~~~~~~~~~~~~~~~~
This is a database adapter written in C, which uses the database C API to access files.
This (and similar database adapters) will not work with ``pyfakefs``, as it will always
access the real filesystem.

The `Pillow`_ Imaging Library
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This library partly works with ``pyfakefs``, but it is known to not work at
least if writing JPEG files
(see `this issue <https://github.com/pytest-dev/pyfakefs/issues/529>`__)

The `pandas`_ data analysis toolkit
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This uses its own internal file system access written in C, thus much of
``pandas`` will not work with ``pyfakefs`` out of the box. Having said that,
``pyfakefs`` patches ``pandas`` to use standard file-system access instead,
so that many of the ``read_xxx`` functions, including ``read_csv`` and
``read_excel``, as well as some writer functions, do work with the fake file
system. If you use only these functions, ``pyfakefs`` should work fine with
``pandas``.

`xlrd`_
~~~~~~~
This library is used by ``pandas`` to read Excel files in the `.xls` format,
and can also be used stand-alone. Similar to ``pandas``, it is by default
patched by ``pyfakefs`` to use normal file system functions that can be
patched.

`openpyxl`_
~~~~~~~~~~~
This is another library that reads and writes Excel files, and is also
used by ``pandas`` if installed. ``openpyxl`` uses ``lxml`` for some file-system
access if it is installed--in this case ``pyfakefs`` will not be able to patch
it correctly (``lxml`` uses C functions for file system access). It will `not`
use ``lxml`` however, if the environment variable ``OPENPYXL_LXML`` is set to
"False" (or anything other than "True"), so if you set this variable `before`
running the tests, it can work fine with ``pyfakefs``.

If you encounter a module not working with ``pyfakefs``, and you are not sure
if the module can be handled or how to do it, please write a new issue. We
will check if it can be made to work, and at least add it to this list.

Pyfakefs behaves differently than the real filesystem
-----------------------------------------------------
There are at least the following kinds of deviations from the actual behavior:

- unwanted deviations that we didn't notice--if you find any of these, please
  write an issue and we will try to fix it
- behavior that depends on different OS versions and editions--as mentioned
  in :ref:`limitations`, ``pyfakefs`` uses the systems used for CI tests in
  GitHub Actions as reference system and will not replicate all system-specific behavior
- behavior that depends on low-level OS functionality that ``pyfakefs`` is not
  able to emulate; examples are the ``fcntl.ioctl`` and ``fcntl.fcntl``
  functions that are patched to do nothing

The test code tries to access files in the real filesystem
----------------------------------------------------------
The loading of the actual Python code from the real filesystem does not use
the filesystem functions that ``pyfakefs`` patches, but in some cases it may
access other files in the packages. An example is the ``pytz`` module, which is loading timezone information
from configuration files. In these cases, you have to map the respective files
or directories from the real into the fake filesystem as described in
:ref:`real_fs_access`. For the timezone example, this could look like the following::

.. code:: python

    from pathlib import Path
    import pytz
    from pyfakefs.fake_filesystem_unittest import TestCase


    class ExampleTestCase(TestCase):
        def setUp(self):
            self.setUpPyfakefs()
            info_dir = Path(pytz.__file__).parent / "zoneinfo"
            self.fs.add_real_directory(info_dir)

.. note:: In newer django versions, `tzdata` is used instead of `pytz`, but the usage will be the same.

If you are using Django, various dependencies may expect both the project
directory and the ``site-packages`` installation to exist in the fake filesystem.

Here's an example of how to add these using pytest:

.. code:: python

    import os
    import django
    import pytest


    @pytest.fixture
    def fake_fs(fs):
        PROJECT_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        fs.add_real_paths(
            [
                PROJECT_BASE_DIR,
                os.path.dirname(django.__file__),
            ]
        )
        return fs

OS temporary directories
------------------------
Tests relying on a completely empty file system on test start will fail.
As ``pyfakefs`` does not fake the ``tempfile`` module (as described above),
a temporary directory is required to ensure that ``tempfile`` works correctly,
e.g., that ``tempfile.gettempdir()`` will return a valid value. This
means that any newly created fake file system will always have either a
directory named ``/tmp`` when running on POSIX systems, or
``C:\Users\<user>\AppData\Local\Temp`` on Windows:

.. code:: python

  import os


  def test_something(fs):
      # the temp directory is always present at test start
      assert len(os.listdir("/")) == 1

Under macOS and linux, if the actual temp path is not `/tmp` (which will be the case if an environment variable
`TEMPDIR`, `TEMP` or `TMP` points to another path), a symlink to the actual temp directory is additionally created
as `/tmp` in the fake filesystem. Note that the file size of this link is ignored while
calculating the fake filesystem size, so that the used size with an otherwise empty
fake filesystem can always be assumed to be 0.
Note also that the temp directory may not be what you expect, if you emulate another file system. For example,
if you emulate Windows under Linux, the default temp directory will be at `C:\\tmp`.


User rights
-----------
If you run ``pyfakefs`` tests as root (this happens by default if run in a
docker container), ``pyfakefs`` also behaves as a root user, for example can
write to write-protected files. This may not be the expected behavior, and
can be changed.
``Pyfakefs`` has a rudimentary concept of user rights, which differentiates
between root user (with the user id 0) and any other user. By default,
``pyfakefs`` assumes the user id of the current user, but you can change
that using ``pyfakefs.helpers.set_uid()`` in your setup. This allows to run
tests as non-root user in a root user environment and vice verse.
Another possibility to run tests as non-root user in a root user environment
is the convenience argument :ref:`allow_root_user`:

.. code:: python

  from pyfakefs.fake_filesystem_unittest import TestCase


  class SomeTest(TestCase):
      def setUp(self):
          self.setUpPyfakefs(allow_root_user=False)

``Pyfakefs`` also handles file permissions under UNIX systems while accessing files.
If accessing files as another user and/or group, the respective group/other file
permissions are considered.

.. _usage_with_mock_open:

Pyfakefs and mock_open
----------------------
If you patch ``open`` using ``mock_open`` before the initialization of
``pyfakefs``, it will not work properly, because the ``pyfakefs``
initialization relies on ``open`` working correctly.
Generally, you should not need ``mock_open`` if using ``pyfakefs``, because you
always can create the files with the needed content using ``create_file``.
This is true for patching any filesystem functions--avoid patching them
while working with ``pyfakefs``.
If you still want to use ``mock_open``, make sure it is only used while
patching is in progress. For example, if you are using ``pytest`` with the
``mocker`` fixture used to patch ``open``, make sure that the ``fs`` fixture is
passed before the ``mocker`` fixture to ensure this:

.. code:: python

  def test_mock_open_incorrect(mocker, fs):
      # causes a recursion error
      mocker.patch("builtins.open", mocker.mock_open(read_data="content"))


  def test_mock_open_correct(fs, mocker):
      # works correctly
      mocker.patch("builtins.open", mocker.mock_open(read_data="content"))

Pathlib.Path objects created outside of tests
---------------------------------------------
An pattern which is more often seen with the increased usage of ``pathlib`` is the
creation of global ``pathlib.Path`` objects (instead of string paths) that are imported
into the tests. As these objects are created in the real filesystem,
they do not have the same attributes as fake ``pathlib.Path`` objects,
and both will always compare as not equal,
regardless of the path they point to:

.. code:: python

  import pathlib

  # This Path was made in the real filesystem, before the test
  # stands up the fake filesystem
  FILE_PATH = pathlib.Path(__file__).parent / "file.csv"


  def test_path_equality(fs):
      # This Path was made after the fake filesystem is set up,
      # and thus patching within pathlib is in effect
      fake_file_path = pathlib.Path(str(FILE_PATH))

      assert FILE_PATH == fake_file_path  # fails, compares different objects
      assert str(FILE_PATH) == str(fake_file_path)  # succeeds, compares the actual paths

Generally, mixing objects in the real filesystem and the fake filesystem
is problematic and better avoided.

.. note:: This problem only happens in Python versions up to 3.10. In Python 3.11,
  `pathlib` has been restructured so that a pathlib path no longer contains a reference
  to the original filesystem accessor, and it can safely be used in the fake filesystem.

.. _nested_patcher_invocation:

Nested file system fixtures and Patcher invocations
---------------------------------------------------
``pyfakefs`` does not support nested faked file systems. Instead, it uses reference counting
on the single fake filesystem instance. That means, if you are trying to create a fake filesystem
inside a fake filesystem, only the reference count will increase, and any arguments you may pass
to the patcher or fixture are ignored. Likewise, if you leave a nested fake filesystem,
only the reference count is decreased and nothing is reverted.

There are some situations where that may happen, probably without you noticing:

* If you use the module- or session based variants of the ``fs`` fixture (e.g. ``fs_module`` or
  ``fs_session``), you may still use the ``fs`` fixture in single tests. This will practically
  reference the module- or session based fake filesystem, instead of creating a new one.

.. code:: python

  @pytest.fixture(scope="module", autouse=True)
  def use_fs(fs_module):
      # do some setup...
      yield fs_module


  def test_something(fs):
      do_more_fs_setup()
      test_something()
      # the fs setup done in this test is not reverted!

* If you invoke a ``Patcher`` instance inside a test with the ``fs`` fixture (or with an active
  ``fs_module`` or ``fs_session`` fixture), this will be ignored. For example:

.. code:: python

  def test_something(fs):
      with Patcher(allow_root_user=False):
          # root user is still allowed
          do_stuff()

* The same is true, if you use ``setUpPyfakefs`` or ``setUpClassPyfakefs`` in a unittest context, or if you use
  the ``patchfs`` decorator. ``Patcher`` instances created in the tests will be ignored likewise.

.. _failing_dyn_patcher:

Tests failing after a test using pyfakefs
-----------------------------------------
If previously passing tests fail after a test using ``pyfakefs``, something may be wrong with reverting the
patches. The most likely cause is a problem with the dynamic patcher, which is invoked if modules are loaded
dynamically during the tests. These modules are removed after the test, and reloaded the next time they are
imported, to avoid any remaining patched functions or variables. Sometimes, there is a problem with that reload.

If you want to know if your problem is indeed with the dynamic patcher, you can switch it off by setting
:ref:`use_dynamic_patch` to `False` (here an example with pytest):

.. code:: python

  @pytest.fixture
  def fs_no_dyn_patch():
      with Patcher(use_dynamic_patch=False):
          yield


  def test_something(fs_no_dyn_patch):
      ...  # do the testing

If in this case the following tests pass as expected, the dynamic patcher is indeed the problem.
If your ``pyfakefs`` test also works with that setting, you may just use this. Otherwise,
the dynamic patcher is needed, and the concrete problem has to be fixed. There is the possibility
to add a hook for the cleanup of a specific module, which allows to change the process of unloading
the module. This is currently used in ``pyfakefs`` for two cases: to reload ``django`` views instead of
just unloading them (needed due to some django internals), and for the reload of a specific module
in ``pandas``, which does not work out of the box.

A cleanup handler takes the module name as an argument, and returns a Boolean that indicates if the
cleanup was handled (by returning `True`), or if the module should still be unloaded. This handler has to
be added to the patcher:

.. code:: python

  def handler_no_cleanup(_name):
      # This is the simplest case: no cleanup is done at all.
      # This makes only sense if you are sure that no file system functions are called.
      return True


  @pytest.fixture
  def my_fs():
      with Patcher():
          patcher["modulename"] = handler_no_cleanup
          yield

As this may not be trivial, we recommend to write an issue in ``pyfakefs`` with a reproducible example.
We will analyze the problem, and if we find a solution we will either get this fixed in ``pyfakefs``
(if it is related to a commonly used module), or help you to resolve it.


.. _`multiprocessing`: https://docs.python.org/3/library/multiprocessing.html
.. _`subprocess`: https://docs.python.org/3/library/subprocess.html
.. _`sqlite3`: https://docs.python.org/3/library/sqlite3.html
.. _`GitPython`: https://pypi.org/project/GitPython/
.. _`plumbum`: https://pypi.org/project/plumbum/
.. _`Pillow`: https://pypi.org/project/Pillow/
.. _`pandas`: https://pypi.org/project/pandas/
.. _`xlrd`: https://pypi.org/project/xlrd/
.. _`openpyxl`: https://pypi.org/project/openpyxl/
