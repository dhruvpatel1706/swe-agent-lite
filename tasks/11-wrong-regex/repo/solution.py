import re


def extract_emails(text: str) -> list[str]:
    """Find every email address in `text`."""
    return re.findall(r"\b[a-zA-Z0-9]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", text)
