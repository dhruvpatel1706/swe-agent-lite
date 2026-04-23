import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "repo"))

from solution import filter_long  # noqa: E402


def test_basic():
    assert filter_long(["a", "bb", "ccc"], 1) == ["bb", "ccc"]


def test_strict_greater():
    # `min_length=2` excludes length-2 strings.
    assert filter_long(["ab", "cde", "fg"], 2) == ["cde"]


def test_empty_input():
    assert filter_long([], 5) == []


def test_nothing_matches():
    assert filter_long(["a", "b"], 5) == []


def test_preserves_order():
    assert filter_long(["xxx", "y", "zzzz"], 1) == ["xxx", "zzzz"]
