Introduction
============

`pyfakefs <https://github.com/jmcgeheeiv/pyfakefs>`__ implements a fake file system that mocks the Python file system modules.
Using pyfakefs, your tests operate on a fake file system in memory without touching the real disk.
The software under test requires no modification to work with pyfakefs.

pyfakefs works with CPython 2.7, 3.4 and above, on Linux, Windows and OSX
(MacOS), and with PyPy2 and PyPy3.

pyfakefs works with `PyTest <doc.pytest.org>`__ version 2.8.6 or above.

Installation
------------
pyfakefs is available on `PyPi <https://pypi.python.org/pypi/pyfakefs/>`__.
The latest released version can be installed from pypi:

.. code:: bash

   pip install pyfakefs

The latest master can be installed from the GitHub sources:

.. code:: bash

   pip install git+https://github.com/jmcgeheeiv/pyfakefs

Limitations
-----------
pyfakefs will not work with Python libraries that use C libraries to access the
file system, because it cannot patch the underlying C libraries' file access functions.

Depending on the kind of import statements used, pyfakefs may not patch the
file system modules automatically. See :ref:`customizing_patcher` for more
information and ways to work around this.

pyfakefs is only tested with CPython and newest PyPy versions, other Python implementations
will probably not work.

Differences in the behavior in different Linux distributions or different MacOS or Windows versions
may not be reflected in the implementation, as well as some OS-specific low-level file
system behavior. The systems used for automatic tests in `Travis.CI
<https://travis-ci.org/jmcgeheeiv/pyfakefs>`__ and `AppVeyor <https://ci
.appveyor.com/project/jmcgeheeiv/pyfakefs>`__ are considered as reference
systems.

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
  added `direct support for unittest and doctest <../../wiki/Automatically-find-and-patch-file-functions-and-modules>`__
* Fork `shiffdane-jmcgeheeiv-pyfakefs <http://code.google.com/p/shiffdane-jmcgeheeiv-pyfakefs/>`__
  added further corrections

After the `shutdown of Google
Code <http://google-opensource.blogspot.com/2015/03/farewell-to-google-code.html>`__
was announced, `John McGehee <https://github.com/jmcgeheeiv>`__ merged
all three Google Code projects together `on
GitHub <https://github.com/jmcgeheeiv/pyfakefs>`__ where an enthusiastic
community actively maintains and extends pyfakefs.
