import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "repo"))

from solution import average  # noqa: E402


def test_empty_returns_zero():
    assert average([]) == 0


def test_basic():
    assert average([1, 2, 3, 4, 5]) == 3


def test_floats():
    assert abs(average([1.5, 2.5]) - 2.0) < 1e-9


def test_single():
    assert average([42]) == 42
