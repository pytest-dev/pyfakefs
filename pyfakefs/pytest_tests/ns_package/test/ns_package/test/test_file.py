import pyfakefs.fake_filesystem


def test_foo(fs):
    """Regression test for #814 - must run in namespace package with cli logging."""
    fs.os = pyfakefs.fake_filesystem.OSType.WINDOWS
    assert True
