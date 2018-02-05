Usage
=====

Test Scenarios
--------------
There are several approaches to implementing tests using ``pyfakefs``.

Patch using fake_filesystem_unittest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you are using the ``python unittest`` package, the easiest approach is to use test classes
derived from ``fake_filesystem_unittest.TestCase``.

This allows ``pyfakefs`` to automatically find all real file functions and
modules, and stub these out with the fake file system functions and modules.

The usage is explained in more detail in the ``pyfakefs`` wiki page
`Automatically find and patch file functions and modules <https://github.com/jmcgeheeiv/pyfakefs/wiki/Automatically-find-and-patch-file-functions-and-modules>`__
and demonstrated in the files ``example.py`` and ``example_test.py``.

Patch using the PyTest plugin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you use `PyTest <https://doc.pytest.org>`__, you will be interested in
the PyTest plugin in ``pyfakefs``.
This automatically patches all file system functions and modules in a
similar manner as described above.

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

Patch using unittest.mock (deprecated)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You can also use ``mock.patch()`` to patch the modules manually. This approach will
only work for the directly imported modules, therefore it is not suited for testing
larger code bases. As the other approaches are more convenient, this one is considered
deprecated and will not be described in detail.

Customizing Patcher and TestCase
--------------------------------
Both ``fake_filesystem_unittest.Patcher`` and ``fake_filesystem_unittest.TestCase``
provide a few additional arguments for fine-tuning. These are only needed if
patching does not work for some module.

*Note for PyTest users:* if you need these arguments in ``PyTest``, you have to
use ``Patcher`` directly instead of the ``fs`` fixture. Alternatively, you can
add your own fixture with the needed parameters (see ``pytest_plugin.py``
for the implementation).

modules_to_reload
~~~~~~~~~~~~~~~~~
This allows to pass a list of modules that shall be reloaded, thus allowing
to patch modules not imported directly.

The following imports of ``os`` and ``pathlib.Path`` will not be patched by
``pyfakefs`` directly:

.. code:: python

  import os as my_os
  from pathlib import Path

If adding the module containing these imports to ``modules_to_reload``, they
will be correctly patched.
Ther is one exception to that: importing ``os.path`` like
``from os import path`` will works, because it is handled by ``pyfakefs``
(see also ``patch_path`` below).

modules_to_patch
~~~~~~~~~~~~~~~~
This also allows patching modules that are not patched out of the box, i
this case by adding a fake module implementation for a module name. The
argument is a dictionary of fake modules mapped to the names to be faked.
This can be used to fake modules imported as another name directly. For the
``os`` import above you could also use:

.. code:: python

  with Patcher(modules_to_patch={'my_os': fake_filesystem.FakeOsModule}):
      test_something()

For the second example (``from pathlib import Path``) the syntax is slightly
different:

.. code:: python

  with Patcher(modules_to_patch={'pathlib.Path': MyFakePath}):
      test_something()

Here is an example how to implement ``MyFakePath``:

.. code:: python

    class MyFakePath():
        """Patches `pathlib.Path` by passing all calls to FakePathlibModule."""
        fake_pathlib = None

        def __init__(self, filesystem):
            if self.fake_pathlib is None:
                from pyfakefs.fake_pathlib import FakePathlibModule
                self.__class__.fake_pathlib = FakePathlibModule(filesystem)

        def __call__(self, *args, **kwargs):
            return self.fake_pathlib.Path(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self.fake_pathlib.Path, name)

patch_path
~~~~~~~~~~
This is True by default, meaning that modules named ``path`` are patched as
``os.path``. If this clashes with another module of the same name, it can be switched
off (and imports like ``from os import path`` will not be patched).


additional_skip_names
~~~~~~~~~~~~~~~~~~~~~
This may be used to add modules that shall not be patched. This is mostly
used to avoid patching the Python file system modules themselves, but may be
helpful in some special situations.

use_dynamic_patch
~~~~~~~~~~~~~~~~~
If ``True`` (the default), dynamic patching after setup is used (for example
for modules loaded locally inside of functions).
Can be switched off if it causes unwanted side effects.
