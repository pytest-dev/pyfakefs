"""Tests that the pytest plugin properly provides the "fs" fixture"""
import os
import tempfile


def test_fs_fixture(fs):
    fs.create_file('/var/data/xx1.txt')
    assert os.path.exists('/var/data/xx1.txt')


def test_pause_resume(fs):
    fake_temp_file = tempfile.NamedTemporaryFile()
    assert fs.exists(fake_temp_file.name)
    assert os.path.exists(fake_temp_file.name)
    fs.pause()
    assert fs.exists(fake_temp_file.name)
    assert not os.path.exists(fake_temp_file.name)
    real_temp_file = tempfile.NamedTemporaryFile()
    assert not fs.exists(real_temp_file.name)
    assert os.path.exists(real_temp_file.name)
    fs.resume()
    assert not os.path.exists(real_temp_file.name)
    assert os.path.exists(fake_temp_file.name)

