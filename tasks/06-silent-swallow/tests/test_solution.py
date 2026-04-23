import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "repo"))

from solution import parse_int  # noqa: E402


def test_valid_int():
    assert parse_int("42") == 42


def test_valid_negative():
    assert parse_int("-7") == -7


def test_valid_zero():
    # Zero is a real parse, NOT a failure sentinel.
    assert parse_int("0") == 0


def test_invalid_returns_none():
    assert parse_int("abc") is None


def test_empty_returns_none():
    assert parse_int("") is None


def test_none_input_returns_none():
    assert parse_int(None) is None
