from pyfakefs.fake_filesystem import FakeFileOpen


def test_monkeypatch_with_fs(fs, monkeypatch):
    """Regression test for issue 1200"""
    fake_open = FakeFileOpen(fs)
    monkeypatch.setattr("builtins.open", fake_open, raising=False)


def test_open():
    """Tests if open is poisoned by the above test"""
    assert "built-in" in str(open)
