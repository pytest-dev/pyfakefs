"""Regression test for #947.
Ensures that reloading the `pandas.core.arrays.arrow.extension_types` module succeeds.
"""

from pathlib import Path

import pytest

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import parquet
except ImportError:
    parquet = None


@pytest.mark.skipif(
    pd is None or parquet is None, reason="pandas or parquet not installed"
)
def test_1(fs):
    dir_ = Path(__file__).parent / "data"
    fs.add_real_directory(dir_)
    pd.read_parquet(dir_ / "test.parquet")


@pytest.mark.skipif(
    pd is None or parquet is None, reason="pandas or parquet not installed"
)
def test_2():
    dir_ = Path(__file__).parent / "data"
    pd.read_parquet(dir_ / "test.parquet")
