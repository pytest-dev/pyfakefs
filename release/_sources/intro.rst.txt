Introduction
============

`pyfakefs <https://github.com/jmcgeheeiv/pyfakefs>`__ implements a fake file system that mocks the Python file system modules.
Using pyfakefs, your tests operate on a fake file system in memory without touching the real disk.
The software under test requires no modification to work with pyfakefs.

Note that pyfakefs will not work with Python libraries that use C libraries to access the
file system, because it cannot patch the underlying C libraries' file access functions.

pyfakefs works with Python 2.6 and above, on Linux, Windows and MacOS.

pyfakefs works with `PyTest <doc.pytest.org>`__ version 2.8.6 or above.

Installation
------------
pyfakefs is available on `PyPi <https://pypi.python.org/pypi/pyfakefs/>`__.
It can be installed using pip:

.. code:: bash

   pip install pyfakefs

History
-------
pyfakefs.py was initially developed at Google by Mike Bland as a modest
fake implementation of core Python modules. It was introduced to all of
Google in September 2006. Since then, it has been enhanced to extend its
functionality and usefulness. At last count, pyfakefs is used in over
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
