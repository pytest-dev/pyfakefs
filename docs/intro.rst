Introduction
============

`pyfakefs <https://github.com/jmcgeheeiv/pyfakefs>`__ implements a fake file
system that mocks the Python file system modules.
Using pyfakefs, your tests operate on a fake file system in memory without touching the real disk.
The software under test requires no modification to work with pyfakefs.

pyfakefs works with CPython 3.7 and above, on Linux, Windows and OSX
(MacOS), and with PyPy3.

pyfakefs works with `pytest <doc.pytest.org>`__ version 3.0.0 or above.

Installation
------------
pyfakefs is available on `PyPi <https://pypi.python.org/pypi/pyfakefs/>`__.
The latest released version can be installed from pypi:

.. code:: bash

   pip install pyfakefs

The latest master can be installed from the GitHub sources:

.. code:: bash

   pip install git+https://github.com/jmcgeheeiv/pyfakefs

Features
--------
- Code executed under pyfakefs works transparently on a memory-based file
  system without the need of special commands. The same code that works on
  the real filesystem will work on the fake filesystem if running under
  pyfakefs.

- pyfakefs provides direct support for `unittest` (via a `TestCase` base
  class) and `pytest` (via a fixture), but can also be used with other test
  frameworks.

- Each pyfakefs test starts with an empty file system, but it is possible to
  map files and directories from the real file system into the fake
  filesystem if needed.

- No files in the real file system are changed during the tests, even in the
  case of writing to mapped real files.

- pyfakefs keeps track of the filesystem size if configured. The file system
  size can be configured arbitrarily.

- it is possible to pause and resume using the fake filesystem, if the
  real file system has to be used in a test step

- pyfakefs defaults to the OS it is running on, but can also be configured
  to test code running under another OS (Linux, MacOS or Windows).

- pyfakefs can be configured to behave as if running as a root or as a
  non-root user, independently from the actual user.

.. _limitations:

Limitations
-----------
- pyfakefs will not work with Python libraries (other than `os` and `io`) that
  use C libraries to access the file system, because it cannot patch the
  underlying C libraries' file access functions

- pyfakefs patches most kinds of importing file system modules automatically,
  but there are still some cases where this will not work.
  See :ref:`customizing_patcher` for more information and ways to work around
  this.

- pyfakefs does not retain the MRO for file objects, so you cannot rely on
  checks using `isinstance` for these objects (for example, to differentiate
  between binary and textual file objects).

- pyfakefs is only tested with CPython and the newest PyPy versions, other
  Python implementations will probably not work

- Differences in the behavior in different Linux distributions or different
  MacOS or Windows versions may not be reflected in the implementation, as
  well as some OS-specific low-level file system behavior. The systems used
  for automatic tests in
  `Travis.CI <https://travis-ci.org/jmcgeheeiv/pyfakefs>`__ and
  `AppVeyor <https://ci.appveyor.com/project/jmcgeheeiv/pyfakefs>`__ are
  considered as reference systems, additionally the tests are run in Docker
  containers with the latest CentOS, Debian, Fedora and Ubuntu images.

- pyfakefs may not work correctly if file system functions are patched by
  other means (e.g. using `unittest.mock.patch`) - see
  :ref:`usage_with_mock_open` for more information

History
-------
pyfakefs was initially developed at Google by
`Mike Bland <https://mike-bland.com/about.html>`__ as a modest
fake implementation of core Python modules. It was introduced to all of
Google in September 2006. Since then, it has been enhanced to extend its
functionality and usefulness. At last count, pyfakefs was used in over
2,000 Python tests at Google.

Google released pyfakefs to the public in 2011 as Google Code project
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
GitHub <https://github.com/jmcgeheeiv/pyfakefs>`__ where an enthusiastic
community actively maintains and extends pyfakefs.
