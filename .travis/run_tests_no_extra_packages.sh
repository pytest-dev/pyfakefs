#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    source ~/.venv/bin/activate
fi

export TEST_REAL_FS=1
echo ==========================================================
echo Running unit tests without extra packages as non-root user
python -m pyfakefs.tests.all_tests_without_extra_packages
