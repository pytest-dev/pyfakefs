"""Tests that the pytest plugin properly provides the "fs" fixture"""
import os
import tempfile

from pyfakefs.fake_filesystem_unittest import Pause
import pyfakefs.pytest_tests.io


def test_fs_fixture(fs):
    fs.create_file('/var/data/xx1.txt')
    assert os.path.exists('/var/data/xx1.txt')


def test_fs_fixture_alias(fake_filesystem):
    fake_filesystem.create_file('/var/data/xx1.txt')
    assert os.path.exists('/var/data/xx1.txt')


def test_both_fixtures(fs, fake_filesystem):
    fake_filesystem.create_file('/var/data/xx1.txt')
    fs.create_file('/var/data/xx2.txt')
    assert os.path.exists('/var/data/xx1.txt')
    assert os.path.exists('/var/data/xx2.txt')
    assert fs == fake_filesystem


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


def test_pause_resume_contextmanager(fs):
    fake_temp_file = tempfile.NamedTemporaryFile()
    assert fs.exists(fake_temp_file.name)
    assert os.path.exists(fake_temp_file.name)
    with Pause(fs):
        assert fs.exists(fake_temp_file.name)
        assert not os.path.exists(fake_temp_file.name)
        real_temp_file = tempfile.NamedTemporaryFile()
        assert not fs.exists(real_temp_file.name)
        assert os.path.exists(real_temp_file.name)
    assert not os.path.exists(real_temp_file.name)
    assert os.path.exists(fake_temp_file.name)


def test_use_own_io_module(fs):
    filepath = 'foo.txt'
    with open(filepath, 'w') as f:
        f.write('bar')

    stream = pyfakefs.pytest_tests.io.InputStream(filepath)
    assert stream.read() == 'bar'
