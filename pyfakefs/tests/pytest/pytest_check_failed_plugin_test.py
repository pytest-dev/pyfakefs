"""Tests that a failed pytest properly displays the call stack.
Uses the output from running pytest with pytest_plugin_failing_test.py.
Regression test for #381.
"""
import pytest
import sys


@pytest.mark.skipif(sys.version_info[0] == 3 and sys.version_info[1] == 3,
                    reason='linecache uses fake fs in Python 3.3')
def test_failed_testresult_stacktrace():
    with open('testresult.txt') as f:
        contents = f.read()
    # before the fix, a triple question mark has been displayed
    # instead of the stacktrace
    assert contents
    print('contents', contents)
    assert '???' not in contents
    assert 'def test_fs(fs):' in contents
