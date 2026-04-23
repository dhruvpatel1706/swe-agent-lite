REQUIRED_FIELDS = ("Name", "Age")


def validate(record: dict) -> bool:
    """True iff `record` has every required field."""
    return all(field in record for field in REQUIRED_FIELDS)
