Usage
=====
There are several approaches to implementing tests using pyfakefs.

Automatically find and patch using fake_filesystem_unittest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you are using the ``python unittest`` package, the easiest approach is to use test classes
derived from ``fake_filesystem_unittest.TestCase``.

This allows pyfakefs to automatically find all real file functions and modules,
and stub these out with the fake file system functions and modules.

The usage is explained in the pyfakefs wiki page
`Automatically find and patch file functions and modules <https://github.com/jmcgeheeiv/pyfakefs/wiki/Automatically-find-and-patch-file-functions-and-modules>`__
and demonstrated in files ``example.py`` and ``example_test.py``.

Patch using the PyTest plugin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you use `PyTest <https://doc.pytest.org>`__, you will be interested in the PyTest plugin in pyfakefs.
This automatically patches all file system functions and modules in a similar manner as desribed above.

The PyTest plugin provides the ``fs`` fixture for use in your test. For example:

.. code:: python

   def my_fakefs_test(fs):
       # "fs" is the reference to the fake file system
       fs.create_file('/var/data/xx1.txt')
       assert os.path.exists('/var/data/xx1.txt')

Patch using fake_filesystem_unittest.Patcher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you are using other means of testing like `nose <http://nose2.readthedocs.io>`__, you can do the
patching using ``fake_filesystem_unittest.Patcher`` - the class doing the actual work
of replacing the filesystem modules with the fake modules in the first two approaches.

The easiest way is to just use ``Patcher`` as a context manager:

.. code:: python

   from fake_filesystem_unittest import Patcher

   with Patcher() as patcher:
       # access the fake_filesystem object via patcher.fs
       patcher.fs.create_file('/foo/bar', contents='test')

       # the following code works on the fake filesystem
       with open('/foo/bar') as f:
           contents = f.read()

You can also initialize ``Patcher`` manually:

.. code:: python

   from fake_filesystem_unittest import Patcher

   patcher = Patcher()
   patcher.setUp()     # called in the initialization code
   ...
   patcher.tearDown()  # somewhere in the cleanup code


Additional parameters to Patcher and TestCase
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Both ``fake_filesystem_unittest.Patcher`` and ``fake_filesystem_unittest.TestCase``
provide a few additional arguments for fine-tuning.

The most helpful maybe ``modules_to_reload``. This allows to pass a list of modules
that shall be reloaded, thus allowing to patch modules not imported directly.
If a module imports modules to be patched like this:

.. code:: python

  import os as _os
  from pathlib import Path

the modules ``os`` and ``pathlib.Path`` will not be patched (the only exception is
importing ``os.path`` like ``from os import path``, see also below). If adding the module
containing these imports to ``modules_to_reload``, they will be correctly patched.

``additional_skip_names`` may be used to add modules that shall not be patched. This
is mostly used to avoid patching the Python file system modules themselves, but may be
helpful in some special situations.

``patch_path`` is True by default, meaning that modules named `path` are patched as
``os.path``. If this clashes with another module of the same name, it can be switched
off (and imports like ``from os import path`` will not be patched).


Patch using unittest.mock (deprecated)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You can also use ``mock.patch()`` to patch the modules manually. This approach will
only work for the directly imported modules, therefore it is not suited for testing
larger code bases. As the other approaches are more convenient, this one is considered
deprecated and will not be described in detail.
