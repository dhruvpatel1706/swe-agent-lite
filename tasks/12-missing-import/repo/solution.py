def word_count(text: str) -> int:
    """Count words in `text`. Words are runs of alphabetic characters."""
    return len(re.findall(r"[a-zA-Z]+", text))
