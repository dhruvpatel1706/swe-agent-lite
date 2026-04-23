import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "repo"))

from solution import is_adult  # noqa: E402


def test_seventeen_is_not_adult():
    assert is_adult(17) is False


def test_eighteen_is_adult():
    assert is_adult(18) is True


def test_nineteen_is_adult():
    assert is_adult(19) is True


def test_zero_is_not_adult():
    assert is_adult(0) is False
