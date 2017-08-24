Public Classes
==============

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

