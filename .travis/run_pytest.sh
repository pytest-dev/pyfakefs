#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    source ~/.venv/bin/activate
fi

python -m pytest pyfakefs/tests/pytest_plugin_test.py
python -m pytest pyfakefs/tests/pytest_plugin_failing_test.py > ./testresult.txt
python -m pytest pyfakefs/tests/pytest_check_failed_plugin_test.py
