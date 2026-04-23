import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "repo"))

from cart import Cart  # noqa: E402


def test_single_cart_basic():
    c = Cart()
    c.add_item("apple", 1.50)
    c.add_item("bread", 3.25)
    assert c.total() == 4.75


def test_two_carts_independent_items():
    a = Cart()
    a.add_item("apple", 1.50)
    b = Cart()
    # b hasn't had anything added — should be empty
    assert b.total() == 0.0
    assert a.total() == 1.50


def test_two_carts_independent_totals_with_tax():
    a = Cart()
    a.add_item("apple", 1.00)
    b = Cart()
    b.add_item("bread", 2.00)
    # 10% tax
    assert a.total(0.10) == 1.10
    assert b.total(0.10) == 2.20


def test_three_carts_sequential():
    a = Cart()
    a.add_item("x", 5.00)
    b = Cart()
    b.add_item("y", 10.00)
    c = Cart()
    c.add_item("z", 15.00)
    # All three must stay independent
    assert a.total() == 5.00
    assert b.total() == 10.00
    assert c.total() == 15.00
