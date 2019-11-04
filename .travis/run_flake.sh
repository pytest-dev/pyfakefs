#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    source ~/.venv/bin/activate
fi

if ! [[ $VM == 'Docker' ]]; then
    pip install flake8

    EXCLUDES='--exclude get-pip.py'
    if [[ $PYTHON == 'py27' ]] || [[ $PYTHON == 'pypy2' ]]; then
        EXCLUDES=$EXCLUDES',pyfakefs/fake_pathlib.py,pyfakefs/tests/fake_pathlib_test.py'
    fi

    # stop the build if there are Python syntax errors or undefined names
    # exit-zero treats all errors as warnings
    flake8 . $EXCLUDES --count --select=E901,E999,F821,F822,F823 --show-source --statistics && flake8 . $EXCLUDES --count --exit-zero --max-complexity=12 --statistics --per-file-ignores='pyfakefs/tests/fake_pathlib_test.py:E303'
fi
