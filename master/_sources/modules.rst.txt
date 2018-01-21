Public Modules and Classes
==========================
*Note:* only public classes and methods interesting to the pyfakfs user
are shown. Methods that mimic the behavior of standard Python
functions are not listed - you may always use the standard functions.

Fake filesystem module
----------------------
.. automodule:: pyfakefs.fake_filesystem

Fake filesystem classes
-----------------------
.. autoclass:: pyfakefs.fake_filesystem.FakeFilesystem
    :members: add_mount_point,
        get_disk_usage, set_disk_usage, change_disk_usage,
        add_real_directory, add_real_file, add_real_paths,
        create_dir, create_file, create_symlink

.. autoclass:: pyfakefs.fake_filesystem.FakeFile
    :members: byte_contents, contents, path, size,
        is_large_file, set_contents

.. autoclass:: pyfakefs.fake_filesystem.FakeDirectory
    :members: contents, get_entry, size, remove_entry

Unittest module classes
-----------------------

.. autoclass:: pyfakefs.fake_filesystem_unittest.TestCase
    :members: fs, patches, setUpPyfakefs

.. autoclass:: pyfakefs.fake_filesystem_unittest.Patcher
    :members: setUp, tearDown

Faked module classes
--------------------

.. autoclass:: pyfakefs.fake_filesystem.FakeOsModule

.. autoclass:: pyfakefs.fake_filesystem.FakePathModule

.. autoclass:: pyfakefs.fake_filesystem.FakeFileOpen

.. autoclass:: pyfakefs.fake_filesystem.FakeIoModule

.. autoclass:: pyfakefs.fake_filesystem_shutil.FakeShutilModule

.. autoclass:: pyfakefs.fake_pathlib.FakePathlibModule

.. autoclass:: pyfakefs.fake_scandir.FakeScanDirModule
