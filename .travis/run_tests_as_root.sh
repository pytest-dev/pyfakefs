#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    source ~/.venv/bin/activate
fi

if ! [[ $VM == 'Docker' ]]; then
    python --version
    echo ============================================
    echo Running tests without extra packages as root
    # provide the same path as non-root to get the correct virtualenv
    sudo env "PATH=$PATH" python -m pyfakefs.tests.all_tests_without_extra_packages
fi
