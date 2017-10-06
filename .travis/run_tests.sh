#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    source ~/.venv/bin/activate
fi

python --version
python ./all_tests.py
