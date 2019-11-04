#!/bin/bash

if [[ $PYTHON == 'py36' ]] || [[ $PYTHON == 'py37' ]]; then
    if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
        source ~/.venv/bin/activate
    fi

    if ! [[ $VM == 'Docker' ]]; then
            python -m pytest pyfakefs/pytest_tests/pytest_fixture_test.py
    fi
fi