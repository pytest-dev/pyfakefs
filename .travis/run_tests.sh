#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    source ~/.venv/bin/activate
fi

if ! [[ $VM == 'Docker' ]]; then
    python --version
    pip --version
    pip install flake8

    EXCLUDES='--exclude get-pip.py'
    if [[ $PYTHON == 'py27' ]] || [[ $PYTHON == 'pypy2' ]]; then
        EXCLUDES=$EXCLUDES',pyfakefs/fake_pathlib.py,pyfakefs/tests/fake_pathlib_test.py'
    fi

    # stop the build if there are Python syntax errors or undefined names
    flake8 . $EXCLUDES --count --select=E901,E999,F821,F822,F823 --show-source --statistics
    # exit-zero treats all errors as warnings
    flake8 . $EXCLUDES --count --exit-zero --max-complexity=12 --statistics
    echo =======================================================
    echo Running unit tests with extra packages as non-root user
    python -m pyfakefs.tests.all_tests
    echo ==========================================================
    echo Running unit tests without extra packages as non-root user
    python -m pyfakefs.tests.all_tests_without_extra_packages
    echo ============================================
    echo Running tests without extra packages as root
    # provide the same path as non-root to get the correct virtualenv
    sudo env "PATH=$PATH" python -m pyfakefs.tests.all_tests_without_extra_packages
fi
