"""Tests that a failed pytest properly displays the call stack.
Uses the output from running pytest with pytest_plugin_failing_helper.py.
Regression test for #381.
"""
import os

import pytest


@pytest.mark.skipif(not os.path.exists('testresult.txt'),
                    reason='Only run in CI tests')
def test_failed_testresult_stacktrace():
    with open('testresult.txt') as f:
        contents = f.read()
    # before the fix, a triple question mark has been displayed
    # instead of the stacktrace
    assert contents
    print('contents', contents)
    assert '???' not in contents
    assert 'AttributeError' not in contents
    assert 'def test_fs(fs):' in contents
