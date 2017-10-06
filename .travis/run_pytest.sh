#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    source ~/.venv/bin/activate
fi

py.test pytest_plugin_test.py
