API Notes
=========

With ``pyfakefs 3.4``, the public API has changed to be PEP-8 conform.
The old API is deprecated, and will be removed in some future version of
pyfakefs.
You can suppress the deprecation warnings for legacy code with the following
code:

.. code:: python

    from pyfakefs.deprecator import Deprecator

    Deprecator.show_warnings = False

Here is a list of selected changes:

:pyfakefs.fake_filesystem.FakeFileSystem:

  CreateFile() -> create_file()

  CreateDirectory() -> create_dir()

  CreateLink() -> create_symlink()

  GetDiskUsage() -> get_disk_usage()

  SetDiskUsage() -> set_disk_usage()

:pyfakefs.fake_filesystem.FakeFile:

  GetSize(), SetSize() -> size (property)

  SetContents() -> set_contents()

  SetATime() -> st_atime (property)

  SetMTime() -> st_mtime (property)

  SetCTime() -> st_ctime (property)
