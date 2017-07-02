Usage
=====
There are several approaches to implementing tests using pyfakefs.

Automatically find and patch using fake_filesystem_unittest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The first approach is to allow pyfakefs to automatically find all real file functions and modules,
and stub these out with the fake file system functions and modules.
This is the simplest approach if you are using separate unit tests.
The usage is explained in the pyfakefs wiki page
`Automatically find and patch file functions and modules <https://github.com/jmcgeheeiv/pyfakefs/wiki/Automatically-find-and-patch-file-functions-and-modules>`__
and demonstrated in files ``example.py`` and ``example_test.py``.

Patch using the PyTest plugin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you use `PyTest <https://doc.pytest.org>`__, you will be interested in the PyTest plugin in pyfakefs.
This automatically patches all file system functions and modules in a manner similar to the
`automatic find and patch approach <https://github.com/jmcgeheeiv/pyfakefs/wiki/Automatically-find-and-patch-file-functions-and-modules>`__
described above.

The PyTest plugin provides the ``fs`` fixture for use in your test. For example:

.. code:: python

   def my_fakefs_test(fs):
       # "fs" is the reference to the fake file system
       fs.CreateFile('/var/data/xx1.txt')
       assert os.path.exists('/var/data/xx1.txt')

Patch using fake_filesystem_unittest.Patcher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you are using other means of testing like `nose <http://nose2.readthedocs.io>`__, you can do the
patching using ``fake_filesystem_unittest.Patcher`` - the class doing the the actual work
of replacing the filesystem modules with the fake modules in the first two approaches.


Patch using unittest.mock (deprecated)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You can also use ``mock.patch()`` to patch the modules manually. This approach will
only work for the directly imported modules
You have to create a fake filesystem object, and afterwards fake modules based on this file system
for the modules you want to patch.

The following modules and functions can be patched:
- os by fake_filessystem.FakeOsModule
- os.path by fake_filessystem.FakePathModule
- io by fake_filessystem.FakeIoModule
- pathlib by fake_pathlib.FakePathlibModule
- build-in open() by fake_filessystem.FakeFileOpen


.. code:: python

   import pyfakefs.fake_filesystem as fake_fs

   # Create a faked file system
   fs = fake_fs.FakeFilesystem()

   # Do some setup on the faked file system
   fs.CreateFile('/var/data/xx1.txt')
   fs.CreateFile('/var/data/xx2.txt')

   # Replace some built-in file system related modules you use with faked ones

   # Assuming you are using the mock library to ... mock things
   try:
       from unittest.mock import patch  # In Python 3, mock is built-in
   except ImportError:
       from mock import patch  # Python 2

   import pyfakefs.fake_filesystem_shutil as fake_shutil

   # Note that this fake module is based on the fake fs you just created
   os = fake_filesystem.FakeOsModule(fs)
   with patch('mymodule.os', os):
       os.makedirs('/foo/bar')
