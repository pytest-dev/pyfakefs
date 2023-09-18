Public Modules and Classes
==========================
.. note:: Only public classes and methods interesting to ``pyfakefs``
  users are shown. Methods that mimic the behavior of standard Python
  functions and classes that are only needed internally are not listed.

Fake filesystem module
----------------------
.. automodule:: pyfakefs.helpers
    :members: get_uid, set_uid, get_gid, set_gid, reset_ids, is_root

Fake filesystem classes
-----------------------
.. autoclass:: pyfakefs.fake_filesystem.FakeFilesystem
    :members: add_mount_point,
        get_disk_usage, set_disk_usage, change_disk_usage,
        add_real_directory, add_real_file, add_real_symlink, add_real_paths,
        create_dir, create_file, create_symlink, create_link,
        get_object, pause, resume

.. autoclass:: pyfakefs.fake_file.FakeFile
    :members: byte_contents, contents, set_contents,
        path, size, is_large_file

.. autoclass:: pyfakefs.fake_file.FakeDirectory
    :members: contents, ordered_dirs, size, get_entry, remove_entry

Unittest module classes
-----------------------

.. autoclass:: pyfakefs.fake_filesystem_unittest.TestCaseMixin
    :members: fs, setUpPyfakefs, setUpClassPyfakefs, pause, resume

.. autoclass:: pyfakefs.fake_filesystem_unittest.TestCase

.. autoclass:: pyfakefs.fake_filesystem_unittest.Patcher
    :members: setUp, tearDown, pause, resume

.. automodule:: pyfakefs.fake_filesystem_unittest
    :members: patchfs


Faked module classes
--------------------

.. autoclass:: pyfakefs.fake_os.FakeOsModule

.. autoclass:: pyfakefs.fake_path.FakePathModule

.. autoclass:: pyfakefs.fake_open.FakeFileOpen

.. autoclass:: pyfakefs.fake_io.FakeIoModule

.. autoclass:: pyfakefs.fake_filesystem_shutil.FakeShutilModule

.. autoclass:: pyfakefs.fake_pathlib.FakePathlibModule

.. autoclass:: pyfakefs.fake_scandir.FakeScanDirModule
