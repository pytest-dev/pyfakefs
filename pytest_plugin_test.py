"""Tests that the pytest plugin properly provides the "fs" fixture"""
import os


def test_fs_fixture(fs, f):
    assert not os.path.exists(f)
    fs.CreateFile(f)
    assert os.path.exists(f)
