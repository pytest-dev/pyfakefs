#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    source ~/.venv/bin/activate
fi

if ! [[ $VM == 'Docker' ]]; then
    python -m pytest pyfakefs/pytest_tests/pytest_plugin_test.py
    if [[ $PYTHON == 'py36' ]] || [[ $PYTHON == 'py37' ]]; then
        python -m pytest pyfakefs/pytest_tests/pytest_fixture_test.py
    fi
    python -m pytest pyfakefs/pytest_tests/pytest_plugin_failing_test.py > ./testresult.txt
    python -m pytest pyfakefs/pytest_tests/pytest_check_failed_plugin_test.py
fi