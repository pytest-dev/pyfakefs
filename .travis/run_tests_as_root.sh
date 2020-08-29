#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    source ~/.venv/bin/activate
fi

python --version
export TEST_REAL_FS=1
echo ============================================
echo Running tests without extra packages as root
sudo env "PATH=$PATH" python -m pyfakefs.tests.all_tests_without_extra_packages
