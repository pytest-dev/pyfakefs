.. _convenience_methods:

Using convenience methods
=========================
While ``pyfakefs`` can be used just with the standard Python file system
functions, there are a few convenience methods in ``fake_filesystem`` that can
help you setting up your tests. The methods can be accessed via the
``fake_filesystem`` instance in your tests: ``Patcher.fs``, the ``fs``
fixture in pytest, ``TestCase.fs`` for ``unittest``, and the positional argument
for the ``patchfs`` decorator.

File creation helpers
~~~~~~~~~~~~~~~~~~~~~
To create files, directories or symlinks together with all the directories
in the path, you may use :py:meth:`create_file()<pyfakefs.fake_filesystem.FakeFilesystem.create_file>`,
:py:meth:`create_dir()<pyfakefs.fake_filesystem.FakeFilesystem.create_dir>`,
:py:meth:`create_symlink()<pyfakefs.fake_filesystem.FakeFilesystem.create_symlink>` and
:py:meth:`create_link()<pyfakefs.fake_filesystem.FakeFilesystem.create_link>`, respectively.

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
            file_path = "/foo/bar/test.txt"
            self.fs.create_file(file_path, contents="test")
            with open(file_path) as f:
                self.assertEqual("test", f.read())

``create_dir()`` behaves like ``os.makedirs()``.
``create_symlink`` and ``create_link`` behave like ``os.symlink`` and
``os.link``, with any missing parent directories of the link created
automatically.

.. caution::
  The first two arguments in ``create_symlink`` are reverted in relation to
  ``os.symlink`` for historical reasons.

.. _real_fs_access:

Access to files in the real file system
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you want to have read access to real files or directories, you can map
them into the fake file system using :py:meth:`add_real_file()<pyfakefs.fake_filesystem.FakeFilesystem.add_real_file>`,
:py:meth:`add_real_directory()<pyfakefs.fake_filesystem.FakeFilesystem.add_real_directory>`,
:py:meth:`add_real_symlink()<pyfakefs.fake_filesystem.FakeFilesystem.add_real_symlink>` and
:py:meth:`add_real_paths()<pyfakefs.fake_filesystem.FakeFilesystem.add_real_paths>`.
They take a file path, a directory path, a symlink path, or a list of paths,
respectively, and make them accessible from the fake file system. By
default, the contents of the mapped files and directories are read only on
demand, so that mapping them is relatively cheap. The access to the files is
by default read-only, but even if you add them using ``read_only=False``,
the files are written only in the fake system (e.g. in memory). The real
files are never changed.

``add_real_file()``, ``add_real_directory()`` and ``add_real_symlink()`` also
allow you to map a file or a directory tree into another location in the
fake filesystem via the argument ``target_path``. If the target directory already exists
in the fake filesystem, the directory contents are merged. If a file in the fake filesystem
would be overwritten by a file from the real filesystem, an exception is raised.

.. code:: python

    import os
    from pyfakefs.fake_filesystem_unittest import TestCase


    class ExampleTestCase(TestCase):

        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures")

        def setUp(self):
            self.setUpPyfakefs()
            # make the file accessible in the fake file system
            self.fs.add_real_directory(self.fixture_path)

        def test_using_fixture(self):
            with open(os.path.join(self.fixture_path, "fixture1.txt")) as f:
                # file contents are copied to the fake file system
                # only at this point
                contents = f.read()

You can do the same using ``pytest`` by using a fixture for test setup:

.. code:: python

    import pytest
    import os

    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures")


    @pytest.fixture
    def my_fs(fs):
        fs.add_real_directory(fixture_path)
        yield fs


    @pytest.mark.usefixtures("my_fs")
    def test_using_fixture():
        with open(os.path.join(fixture_path, "fixture1.txt")) as f:
            contents = f.read()

.. note::
  If you are not using the fixture directly in the test, you can use
  `@pytest.mark.usefixtures`_ instead of passing the fixture as an argument.
  This avoids warnings about unused arguments from linters.

When using ``pytest`` another option is to load the contents of the real file
in a fixture and pass this fixture to the test function **before** passing
the ``fs`` fixture.

.. code:: python

    import pytest
    import os


    @pytest.fixture
    def content():
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures")
        with open(os.path.join(fixture_path, "fixture1.txt")) as f:
            contents = f.read()
        return contents


    def test_using_file_contents(content, fs):
        fs.create_file("fake/path.txt")
        assert content != ""

.. _map-metadata:

Map package metadata files into fake filesystem
...............................................
A more specialized function for adding real files to the fake filesystem is
:py:meth:`add_package_metadata() <pyfakefs.fake_filesystem.FakeFilesystem.add_package_metadata>`.
It adds the metadata distribution files for a given package to the fake filesystem,
so that it can be accessed by modules like `importlib.metadata`_. This is needed
for example if using `flask.testing`_ with ``pyfakefs``.

.. code:: python

    import pytest


    @pytest.fixture(autouse=True)
    def add_werkzeug_metadata(fs):
        # flask.testing accesses Werkzeug metadata, map it
        fs.add_package_metadata("Werkzeug")
        yield


Handling mount points
~~~~~~~~~~~~~~~~~~~~~
Under Linux and macOS, the root path (``/``) is the only mount point created
in the fake file system. If you need support for more mount points, you can add
them using :py:meth:`add_mount_point()<pyfakefs.fake_filesystem.FakeFilesystem.add_mount_point>`.

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
:py:meth:`set_disk_usage()<pyfakefs.fake_filesystem.FakeFilesystem.set_disk_usage>`. By default, this sets the total size in bytes of the
root partition; if you add a path as parameter, the size will be related to
the mount point (see above) the path is related to.

By default, the size of the fake file system is set to 1 TB (which
for most tests can be considered as infinite). As soon as you set a
size, all files will occupy the space according to their size,
and you may fail to create new files if the fake file system is full.

.. code:: python

    import errno
    import os
    from pyfakefs.fake_filesystem_unittest import TestCase


    class ExampleTestCase(TestCase):
        def setUp(self):
            self.setUpPyfakefs()
            self.fs.set_disk_usage(100)

        def test_disk_full(self):
            os.mkdir("/foo")
            with self.assertRaises(OSError) as e:
                with open("/foo/bar.txt", "w") as f:
                    f.write("a" * 200)
            self.assertEqual(errno.ENOSPC, e.exception.errno)

To get the file system size, you may use :py:meth:`get_disk_usage()<pyfakefs.fake_filesystem.FakeFilesystem.get_disk_usage>`, which is
modeled after ``shutil.disk_usage()``.

.. _pause_resume:

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

    import os
    import tempfile
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

    import os
    import tempfile
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

.. _simulate_os:

Simulating other file systems
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``Pyfakefs`` supports Linux, macOS and Windows operating systems. By default,
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
    standard macOS file system (HFS+) is assumed
  - if ``is_windows_fs`` and ``is_macos`` are ``False``, a Linux file system
    (something like ext3) is assumed
  - ``is_case_sensitive`` is set to ``True`` under Linux and to ``False``
    under Windows and macOS by default - you can change it to change the
    respective behavior
  - ``path_separator`` is set to ``\`` under Windows and to ``/`` under Posix,
    ``alternative_path_separator`` is set to ``/`` under Windows and to
    ``None`` under Posix--these can also be adapted if needed

The following test works both under Windows and Linux:

.. code:: python

  import os
  from pyfakefs.fake_filesystem import OSType


  def test_windows_paths(fs):
      fs.os = OSType.WINDOWS
      assert r"C:\foo\bar" == os.path.join("C:\\", "foo", "bar")
      assert os.path.splitdrive(r"C:\foo\bar") == ("C:", r"\foo\bar")
      assert os.path.ismount("C:")

.. note:: Only behavior not relying on OS-specific functionality is emulated on another system.
  For example, if you use the Linux-specific functionality of extended attributes (``os.getxattr`` etc.)
  in your code, you have to test this under Linux.

Set file as inaccessible under Windows
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Normally, if you try to set a file or directory as inaccessible using ``chmod`` under
Windows, the value you provide is masked by a value that always ensures that no read
permissions for any user are removed. In reality, there is the possibility to make
a file or directory unreadable using the Windows ACL API, which is not directly
supported in the Python filesystem API. To make this possible to test, there is the
possibility to use the ``force_unix_mode`` argument to ``FakeFilesystem.chmod``:

.. code:: python

    import pathlib
    import pytest
    from pyfakefs.fake_filesystem import OSType


    def test_is_file_for_unreadable_dir_windows(fs):
        fs.os = OSType.WINDOWS
        path = pathlib.Path("/foo/bar")
        fs.create_file(path)
        # normal chmod does not really set the mode to 0
        fs.chmod("/foo", 0o000)
        assert path.is_file()
        # but it does in forced UNIX mode
        fs.chmod("/foo", 0o000, force_unix_mode=True)
        with pytest.raises(PermissionError):
            path.is_file()


.. _`importlib.metadata`: https://docs.python.org/3/library/importlib.metadata.html
.. _`@pytest.mark.usefixtures`: https://docs.pytest.org/en/stable/reference/reference.html#pytest-mark-usefixtures
.. _`flask.testing`: https://flask-testing.readthedocs.io/en/latest/
