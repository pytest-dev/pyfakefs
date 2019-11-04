#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    source ~/.venv/bin/activate
fi

if ! [[ $VM == 'Docker' ]]; then
    python --version
    echo ==========================================================
    echo Running unit tests without extra packages as non-root user
    python -m pyfakefs.tests.all_tests_without_extra_packages
fi
