import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "repo"))

from formatter import format_sum  # noqa: E402


def test_basic():
    assert format_sum(1, 2) == "$3.00"


def test_floats():
    assert format_sum(1.5, 2.25) == "$3.75"


def test_negative():
    assert format_sum(-5, 3) == "$-2.00"


def test_zero():
    assert format_sum(0, 0) == "$0.00"
