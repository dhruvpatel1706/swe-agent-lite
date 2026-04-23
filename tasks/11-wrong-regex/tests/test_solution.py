import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "repo"))

from solution import extract_emails  # noqa: E402


def test_simple_email():
    assert extract_emails("Contact bob@example.com today") == ["bob@example.com"]


def test_email_with_period_in_local_part():
    result = extract_emails("Mail alice.smith@example.com please")
    assert "alice.smith@example.com" in result


def test_email_with_hyphen():
    result = extract_emails("Write to jean-luc@ship.fr")
    assert "jean-luc@ship.fr" in result


def test_email_with_plus():
    result = extract_emails("Newsletter: bob+newsletter@example.com")
    assert "bob+newsletter@example.com" in result


def test_multiple_emails():
    text = "cc: a@x.com, b.c@y.org, d-e@z.co"
    result = extract_emails(text)
    assert set(result) == {"a@x.com", "b.c@y.org", "d-e@z.co"}


def test_no_emails_returns_empty():
    assert extract_emails("no emails here, just text") == []
