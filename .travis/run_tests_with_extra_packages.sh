#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    source ~/.venv/bin/activate
fi

python --version
export TEST_REAL_FS=1
echo =======================================================
echo Running unit tests with extra packages as non-root user
python -m pyfakefs.tests.all_tests
