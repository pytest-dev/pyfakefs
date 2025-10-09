"""Regression test for #947.
Ensures that reloading the `pandas.core.arrays.arrow.extension_types` module succeeds.
"""

import sys
from pathlib import Path

import pytest

try:
    import pandas as pd
    import parquet
except ImportError:
    pd = None
    parquet = None


@pytest.mark.skipif(pd is None, reason="pandas or parquet not installed")
@pytest.mark.skipif(sys.version_info >= (3, 14), reason="parquet not available yet")
def test_1(fs):
    dir_ = Path(__file__).parent / "data"
    fs.add_real_directory(dir_)
    pd.read_parquet(dir_ / "test.parquet")


@pytest.mark.skipif(pd is None, reason="pandas or parquet not installed")
@pytest.mark.skipif(sys.version_info >= (3, 14), reason="parquet not available yet")
def test_2():
    dir_ = Path(__file__).parent / "data"
    pd.read_parquet(dir_ / "test.parquet")
