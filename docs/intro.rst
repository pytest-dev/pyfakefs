Introduction
============

`pyfakefs <https://github.com/pytest-dev/pyfakefs>`__ implements a fake file
system that mocks the Python file system modules.
Using pyfakefs, your tests operate on a fake file system in memory without touching the real disk.
The software under test requires no modification to work with pyfakefs.

``pyfakefs`` works with CPython 3.7 and above, on Linux, Windows and macOS,
and with PyPy3.

``pyfakefs`` works with `pytest <doc.pytest.org>`__ version 6.2.5 or above by
providing the `fs` fixture that enables the fake filesystem.

Installation
------------
``pyfakefs`` is available on `PyPI <https://pypi.python.org/pypi/pyfakefs/>`__.
The latest released version can be installed from PyPI:

.. code:: bash

   pip install pyfakefs

The latest development version (main branch) can be installed from the GitHub sources:

.. code:: bash

   pip install git+https://github.com/pytest-dev/pyfakefs

Features
--------
- Code executed under ``pyfakefs`` works transparently on a memory-based file
  system without the need of special commands. The same code that works on
  the real filesystem will work on the fake filesystem if running under
  ``pyfakefs``.

- ``pyfakefs`` provides direct support for `pytest` (see :ref:`pytest_plugin`)
  and `unittest` (see :ref:`unittest_usage`), but can also be used with
  other test frameworks.

- Each ``pyfakefs`` test starts with an empty (except for the :ref:`os_temporary_directories`) file system,
  but it is possible to map files and directories from the real file system into the fake
  filesystem if needed (see :ref:`real_fs_access`).

- No files in the real file system are changed during the tests, even in the
  case of writing to mapped real files.

- ``pyfakefs`` keeps track of the filesystem size if configured. The file system
  size can be configured arbitrarily (see :ref:`set-fs-size`). It is also possible to create files
  with a defined size without setting contents.

- It is possible to pause and resume using the fake filesystem, if the
  real file system has to be used in a test step (see :ref:`pause_resume`).

- ``pyfakefs`` defaults to the OS it is running on, but can also be configured
  to test code running under another OS (Linux, macOS or Windows, see :ref:`simulate_os`).

- ``pyfakefs`` can be configured to behave as if running as a root or as a
  non-root user, independently from the actual user (see :ref:`allow_root_user`).

.. _limitations:

Limitations
-----------
- ``pyfakefs`` will not work with Python libraries (other than `os` and `io`) that
  use C libraries to access the file system, because it cannot patch the
  underlying C libraries' file access functions

- ``pyfakefs`` patches most kinds of importing file system modules automatically,
  but there are still some cases where this will not work.
  See :ref:`customizing_patcher` for more information and ways to work around
  this.

- ``pyfakefs`` does not retain the MRO for file objects, so you cannot rely on
  checks using `isinstance` for these objects (for example, to differentiate
  between binary and textual file objects).

- ``pyfakefs`` is only tested with CPython and the newest PyPy versions, other
  Python implementations will probably not work

- Differences in the behavior in different Linux distributions or different
  macOS or Windows versions may not be reflected in the implementation, as
  well as some OS-specific low-level file system behavior. The systems used
  for automatic tests in GitHub Actions are
  considered as reference systems. Additionally, the tests are run in Docker
  containers with the latest CentOS, Debian, Fedora and Ubuntu images.

- ``pyfakefs`` may not work correctly if file system functions are patched by
  other means (e.g. using `unittest.mock.patch`) - see
  :ref:`usage_with_mock_open` for more information.

- ``pyfakefs`` will not work correctly with
  `behave <https://github.com/behave/behave>`__ due to the way it loads
  the steps, if any filesystem modules are imported globally in the steps or
  environment files; as a workaround, you may load them locally inside the
  test steps (see `this issue <https://github.com/pytest-dev/pyfakefs/issues/703>`__).

- ``pyfakefs`` is not guaranteed to work correctly in multi-threading environments.
  Specifically, it does not ensure concurrent write access to a file from different
  threads, which is possible under Posix.


.. |br| raw:: html

   <br />

Alternatives
------------
Given the above limitations, it is not always possible to use `pyfakefs` to emulate the
filesystem. There are other possibilities to test the filesystem that you may consider
instead, for example:

- Use temporary files in the temp directory of your OS. |br|
  *Pros*: Is is relatively easy to setup new tests, and the temp files are not affecting the
  functionality of the actual file system. Under POSIX systems, they are also cleaned up
  periodically. |br|
  *Cons*: It is slower because the actual disk is used, cleaning up after tests can be
  a problem, and the filesystem lives in a fixed location, which cannot always be used
  in the tested code.

- Use a RAM disk. |br|
  *Pros*: It is memory-based and therefore fast, and can be set up to a clean state before
  each test. |br|
  *Cons*: The filesystem lives in a fixed location, which cannot always be used in the tested code.

- Use a filesystem abstraction like `PyFilesystem <https://github.com/PyFilesystem/pyfilesystem2/>`__. |br|
  *Pros*: You can replace the real filesystem by a memory based filesystem in your tests,
  which has the same advantages as using ``pyfakefs``. |br|
  *Cons*: Your production code must use this abstraction, so this is more a consideration
  for new projects.


History
-------
``pyfakefs`` was initially developed at Google by
`Mike Bland <https://mike-bland.com/about.html>`__ as a modest
fake implementation of core Python modules. It was introduced to all of
Google in September 2006. Since then, it has been enhanced to extend its
functionality and usefulness. At last count, ``pyfakefs`` was used in over
20,000 Python tests at Google.

Google released ``pyfakefs`` to the public in 2011 as Google Code project
`pyfakefs <http://code.google.com/p/pyfakefs/>`__:

* Fork `jmcgeheeiv-pyfakefs <http://code.google.com/p/jmcgeheeiv-pyfakefs/>`__
  added direct support for unittest and doctest as described in
  :ref:`auto_patch`
* Fork `shiffdane-jmcgeheeiv-pyfakefs <http://code.google.com/p/shiffdane-jmcgeheeiv-pyfakefs/>`__
  added further corrections

After the `shutdown of Google
Code <http://google-opensource.blogspot.com/2015/03/farewell-to-google-code.html>`__
was announced, `John McGehee <https://github.com/jmcgeheeiv>`__ merged
all three Google Code projects together `on
GitHub <https://github.com/pytest-dev/pyfakefs>`__ where an enthusiastic
community actively maintains and extends pyfakefs. In 2022, the repository has
been transferred to `pytest-dev <https://github.com/pytest-dev>`__ to ensure
continuous maintenance.
