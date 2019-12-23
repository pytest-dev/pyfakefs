#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    source ~/.venv/bin/activate
fi

python -m pytest pyfakefs/pytest_tests/pytest_fixture_param_test.py
