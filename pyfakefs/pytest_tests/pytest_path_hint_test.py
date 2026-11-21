from pathlib import Path
from typing import get_type_hints

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


def test_union_annotations_contain_path_class(wrapper1, wrapper2):
    for wrapped in (wrapper1, wrapper2):
        hints = get_type_hints(wrapped)
        assert hints["path"] == Path | str
        assert hints["return"] == Path | str
        assert isinstance(Path("test_folder"), hints["path"])
