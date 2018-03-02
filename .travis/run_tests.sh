#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    source ~/.venv/bin/activate
fi

python --version
pip --version
pip install flake8

EXCLUDES=''
if [[ $PYTHON == 'py27' ]]; then
    EXCLUDES='--exclude pyfakefs/fake_pathlib.py,tests/fake_pathlib_test.py'
fi

# stop the build if there are Python syntax errors or undefined names
flake8 . $EXCLUDES --count --select=E901,E999,F821,F822,F823 --show-source --statistics
# exit-zero treats all errors as warnings
flake8 . $EXCLUDES --count --exit-zero --max-complexity=10 --statistics
python -m tests.all_tests
