"""Tests that the pytest plugin properly provides the "fs" fixture"""
import os


import pytest


@pytest.mark.parametrize('f', ['/var/data/xx1.txt', '/var/data/xx1.txt'])
def test_fs_fixture(fs, f):
    assert not os.path.exists(f)
    fs.CreateFile(f)
    assert os.path.exists(f)


def test_fs_fixture2(fs):
    assert not os.path.exists('/var/data/xx1.txt')
    fs.CreateFile('/var/data/xx1.txt')
    assert os.path.exists('/var/data/xx1.txt')
