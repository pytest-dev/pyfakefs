"""Regression test for #947.
Ensures that reloading the `pandas.core.arrays.arrow.extension_types` module succeeds.
"""

from pathlib import Path

import pandas as pd


def test_1(fs):
    dir_ = Path(__file__).parent / "data"
    fs.add_real_directory(dir_)
    pd.read_parquet(dir_ / "test.parquet")


def test_2():
    dir_ = Path(__file__).parent / "data"
    pd.read_parquet(dir_ / "test.parquet")
