"""Tests that the pytest plugin properly provides the "fs" fixture"""
import os


def test_fs_fixture(fs):
    fs.CreateFile('/var/data/xx1.txt')
    assert os.path.exists('/var/data/xx1.txt')
