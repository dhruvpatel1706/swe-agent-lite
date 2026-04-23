import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "repo"))

from parser import parse  # noqa: E402
from validator import validate  # noqa: E402


def test_parse_then_validate():
    record = parse("name=Alice,age=30")
    assert validate(record) is True


def test_parse_missing_name_rejected():
    record = parse("age=30")
    assert validate(record) is False


def test_parse_missing_age_rejected():
    record = parse("name=Bob")
    assert validate(record) is False


def test_extra_fields_ok():
    record = parse("name=Claire,age=25,email=c@example.com")
    assert validate(record) is True
