import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "repo"))

from solution import factorial  # noqa: E402


def test_zero():
    assert factorial(0) == 1


def test_one():
    assert factorial(1) == 1


def test_five():
    assert factorial(5) == 120


def test_ten():
    assert factorial(10) == 3628800
