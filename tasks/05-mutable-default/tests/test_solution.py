import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "repo"))

from solution import add_item  # noqa: E402


def test_no_state_leakage_across_calls():
    a = add_item("x")
    b = add_item("y")
    assert a == ["x"]
    assert b == ["y"]


def test_append_to_provided_list_returns_new_list_semantics():
    start = [1, 2]
    out = add_item(3, start)
    assert out == [1, 2, 3]


def test_default_is_fresh_every_call():
    first = add_item("a")
    second = add_item("b")
    third = add_item("c")
    assert first == ["a"]
    assert second == ["b"]
    assert third == ["c"]
