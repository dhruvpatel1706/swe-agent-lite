import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "repo"))

from solution import word_count  # noqa: E402


def test_simple():
    assert word_count("hello world") == 2


def test_punctuation_ignored():
    assert word_count("hello, world!") == 2


def test_empty():
    assert word_count("") == 0


def test_numbers_ignored():
    assert word_count("the year 2026 was great") == 4  # "the", "year", "was", "great"


def test_single_word():
    assert word_count("hello") == 1
