from pathlib import Path

import pytest

# Regression test for #1242. Using a type hint in a wrapped function in a fixture dependent
# on the 'fs' fixture that uses the union of 'Path' with another type using pipe symbol caused
# "TypeError: unsupported operand type(s) for |: 'FakePathlibPathModule' and 'type'"


@pytest.fixture
def wrapper1(fs):
    def wrapped(path: Path | str) -> Path | str:
        return path

    return wrapped


@pytest.fixture
def wrapper2(fs):
    def wrapped(path: str | Path) -> Path | str:
        return path

    return wrapped


def test_wrapped1(wrapper1):
    assert wrapper1("test_folder") == "test_folder"


def test_wrapped2(wrapper2):
    assert wrapper2(Path("test_folder")) == Path("test_folder")
