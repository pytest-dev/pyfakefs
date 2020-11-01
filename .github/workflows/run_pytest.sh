#!/bin/bash

python -m pytest pyfakefs/pytest_tests/pytest_plugin_test.py
if [[ $PY_VERSION == '3.6' ]] || [[ $PY_VERSION == '3.7' ]] || [[ $PY_VERSION == '3.8' ]] || [[ $PY_VERSION == '3.9' ]] ; then
    python -m pytest pyfakefs/pytest_tests/pytest_fixture_test.py
fi
python -m pytest pyfakefs/pytest_tests/pytest_plugin_failing_helper.py > ./testresult.txt
python -m pytest pyfakefs/pytest_tests/pytest_check_failed_plugin_test.py
