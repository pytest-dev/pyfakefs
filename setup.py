#! /usr/bin/env python

from fake_filesystem import __version__

import os


NAME = 'pyfakefs'
MODULES = ['fake_filesystem',
           'fake_filesystem_glob',
           'fake_filesystem_shutil',
           'fake_tempfile',
           'fake_filesystem_unittest']
DESCRIPTION = 'Fakes file system modules for automated developer testing.'

URL = "https://code.google.com/p/pyfakefs"

readme = os.path.join(os.path.dirname(__file__), 'README.md')
LONG_DESCRIPTION = open(readme).read()

CLASSIFIERS = [
    'Development Status :: 5 - Production/Stable',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Programming Language :: Python',
    'Programming Language :: Python :: 2.6',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3',
    'Operating System :: POSIX',
    'Operating System :: MacOS',
    'Operating System :: Microsoft :: Windows',
    'Topic :: Software Development :: Libraries',
    'Topic :: Software Development :: Libraries :: Python Modules',
    'Topic :: Software Development :: Testing',
    'Topic :: System :: Filesystems',
]

AUTHOR = 'Google'
AUTHOR_EMAIL = 'google-pyfakefs@google.com'
KEYWORDS = ("testing test file os shutil glob mocking unittest "
            "fakes filesystem unit").split(' ')

params = dict(
    name=NAME,
    version=__version__,
    py_modules=MODULES,

    # metadata for upload to PyPI
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    keywords=KEYWORDS,
    url=URL,
    classifiers=CLASSIFIERS,
)

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
else:
    params['tests_require'] = ['unittest2']
    params['test_suite'] = 'unittest2.collector'

setup(**params) # pylint: disable = W0142
