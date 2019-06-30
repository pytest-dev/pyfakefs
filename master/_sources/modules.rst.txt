Public Modules and Classes
==========================
.. note:: Only public classes and methods interesting to ``pyfakefs``
  users are shown. Methods that mimic the behavior of standard Python
  functions and classes that are only needed internally are not listed.

Fake filesystem module
----------------------
.. automodule:: pyfakefs.fake_filesystem
    :members: set_uid, set_gid

Fake filesystem classes
-----------------------
.. autoclass:: pyfakefs.fake_filesystem.FakeFilesystem
    :members: add_mount_point,
        get_disk_usage, set_disk_usage,
        add_real_directory, add_real_file, add_real_symlink, add_real_paths,
        create_dir, create_file, create_symlink,
        get_object, pause, resume

.. autoclass:: pyfakefs.fake_filesystem.FakeFile
    :members: byte_contents, contents, set_contents,
        path, size, is_large_file

.. autoclass:: pyfakefs.fake_filesystem.FakeDirectory
    :members: contents, ordered_dirs, size, get_entry, remove_entry

Unittest module classes
-----------------------

.. autoclass:: pyfakefs.fake_filesystem_unittest.TestCaseMixin
    :members: fs, setUpPyfakefs, pause, resume

.. autoclass:: pyfakefs.fake_filesystem_unittest.TestCase

.. autoclass:: pyfakefs.fake_filesystem_unittest.Patcher
    :members: setUp, tearDown, pause, resume

Faked module classes
--------------------

.. autoclass:: pyfakefs.fake_filesystem.FakeOsModule

.. autoclass:: pyfakefs.fake_filesystem.FakePathModule

.. autoclass:: pyfakefs.fake_filesystem.FakeFileOpen

.. autoclass:: pyfakefs.fake_filesystem.FakeIoModule

.. autoclass:: pyfakefs.fake_filesystem_shutil.FakeShutilModule

.. autoclass:: pyfakefs.fake_pathlib.FakePathlibModule

.. autoclass:: pyfakefs.fake_scandir.FakeScanDirModule
