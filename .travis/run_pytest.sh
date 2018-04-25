#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    source ~/.venv/bin/activate
fi

python -m pytest pyfakefs/tests/pytest_plugin_test.py
