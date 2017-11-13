Public Modules and Classes
==========================
*Note:* only public classes and methods interesting to the pyfakfs user
are shown. Methods that mimic the behavior of standard Python
functions are not listed - you may always use the standard functions.

*Style note:* most method names conform to the original Google style that does
not match PEP-8. In the next version, we plan to change the API to conform
to PEP-8 (maintaining upwards compatibility).

Fake filesystem module
----------------------
.. automodule:: pyfakefs.fake_filesystem

Fake filesystem classes
-----------------------
.. autoclass:: pyfakefs.fake_filesystem.FakeFilesystem
    :members: AddMountPoint,
        GetDiskUsage, SetDiskUsage, ChangeDiskUsage,
        add_real_directory, add_real_file, add_real_paths,
        CreateDirectory, CreateFile

.. autoclass:: pyfakefs.fake_filesystem.FakeFile
    :members: byte_contents, contents, GetPath, GetSize,
        IsLargeFile, SetContents, SetSize

.. autoclass:: pyfakefs.fake_filesystem.FakeDirectory
    :members: contents, GetEntry, GetSize, RemoveEntry

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

