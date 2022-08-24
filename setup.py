#! /usr/bin/env python

# Copyright 2009 Google Inc. All Rights Reserved.
# Copyright 2014 Altera Corporation. All Rights Reserved.
# Copyright 2014-2018 John McGehee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
from typing import List

from setuptools import setup, find_packages

from pyfakefs import __version__

NAME = 'pyfakefs'
REQUIRES: List[str] = []
DESCRIPTION = ('pyfakefs implements a fake file system that mocks '
               'the Python file system modules.')

URL = "http://pyfakefs.org"

BASE_PATH = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(BASE_PATH, 'README.md')) as f:
    LONG_DESCRIPTION = f.read()

CLASSIFIERS = [
    'Development Status :: 5 - Production/Stable',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    "Programming Language :: Python :: 3",
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
    'Programming Language :: Python :: 3.10',
    'Programming Language :: Python :: 3.11',
    'Programming Language :: Python :: Implementation :: CPython',
    'Programming Language :: Python :: Implementation :: PyPy',
    'Operating System :: POSIX',
    'Operating System :: MacOS',
    'Operating System :: Microsoft :: Windows',
    'Topic :: Software Development :: Libraries',
    'Topic :: Software Development :: Libraries :: Python Modules',
    'Topic :: Software Development :: Testing',
    'Topic :: System :: Filesystems',
    'Framework :: Pytest',
]

AUTHOR = 'Google'
AUTHOR_EMAIL = 'google-pyfakefs@google.com'
MAINTAINER = 'John McGehee'
MAINTAINER_EMAIL = 'pyfakefs@johnnado.com'
KEYWORDS = ("testing test file os shutil glob mocking unittest "
            "fakes filesystem unit").split(' ')

params = dict(
    name=NAME,
    entry_points={
        'pytest11': ['pytest_fakefs = pyfakefs.pytest_plugin'],
    },
    version=__version__,
    install_requires=REQUIRES,

    # metadata for upload to PyPI
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    maintainer=MAINTAINER,
    maintainer_email=MAINTAINER_EMAIL,
    license='http://www.apache.org/licenses/LICENSE-2.0',
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    keywords=KEYWORDS,
    url=URL,
    classifiers=CLASSIFIERS,
    python_requires='>=3.7',
    test_suite='pyfakefs.tests',
    packages=find_packages(exclude=['docs'])
)

setup(**params)
