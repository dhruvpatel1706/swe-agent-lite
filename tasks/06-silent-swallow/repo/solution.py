def parse_int(s):
    """Parse a string to int. Return the int on success, None on failure."""
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0
