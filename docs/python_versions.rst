Python version support
======================

Policy for Python version support
---------------------------------

* support for new versions is usually added preliminarily during the Python release beta phase,
  official support shortly after the final release
* support for EOL versions is removed as soon as the CI (GitHub actions) does no longer provide
  these versions (usually several months after the official EOL); if the support is removed earlier
  (as with the change to version 6), patches for previous versions are provided if requested

Supported Python versions
-------------------------

================  ===================  ===================
pyfakefs version  min. Python version  max. Python version
================  ===================  ===================
6.0+              3.10                 3.14
5.10+             3.7                  3.14
5.7+              3.7                  3.13
5.3+              3.7                  3.12
4.6+              3.7                  3.11
4.5+              3.6                  3.10
4.4+              3.5                  3.9
4.0+              3.5                  3.8
3.7+              2.7/3.4              3.8
3.5+              2.7/3.4              3.7
3.0+              2.7/3.3              3.6
================  ===================  ===================
