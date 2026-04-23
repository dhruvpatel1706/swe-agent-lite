import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "repo"))

from solution import get_user_name  # noqa: E402


def test_with_name():
    assert get_user_name({"name": "Alice"}) == "Alice"


def test_missing_name_returns_anonymous():
    assert get_user_name({}) == "anonymous"


def test_other_fields_ignored():
    assert get_user_name({"name": "Bob", "email": "b@example.com"}) == "Bob"


def test_empty_name_is_returned_as_is():
    # Empty string is a set value, so we return it (don't fall through to default).
    assert get_user_name({"name": ""}) == ""
