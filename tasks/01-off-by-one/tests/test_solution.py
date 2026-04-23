import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "repo"))

from solution import sum_first_n  # noqa: E402


def test_small():
    assert sum_first_n(5) == 15  # 1+2+3+4+5


def test_one():
    assert sum_first_n(1) == 1


def test_ten():
    assert sum_first_n(10) == 55


def test_zero():
    # Edge case: zero positive integers sum to 0.
    assert sum_first_n(0) == 0
