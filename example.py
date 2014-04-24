#!/usr/bin/python2.7.1
#
# Copyright 2014 Altera Corporation. All Rights Reserved.
# Author: John McGehee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Example module that is tested in :py:class`pyfakefs.example_test.TestExample`.
This demonstrates the usage of the
:py:class`pyfakefs.fake_filesystem_unittest.TestCase` base class.
"""

import os
import glob
import shutil

def create_file(path):
    '''Create the specified file and add some content to it.  Use the `open()`
    built in function.'''
    with open(path, 'w') as f:
        f.write("This is test file '{}'.".format(path))
        f.write("It was created using the open() function.\n")
        
def delete_file(path):
    '''Delete the specified file.'''
    os.remove(path)
    
def file_exists(path):
    '''Return True if the specified file exists.'''
    return os.path.exists(path)

def get_globs(glob_path):
    '''Return the list of paths matching the specified glob expression.'''
    return glob.glob(glob_path)

def rm_tree(path):
    '''Delete the specified file hierarchy.'''
    shutil.rmtree(path)
    
     