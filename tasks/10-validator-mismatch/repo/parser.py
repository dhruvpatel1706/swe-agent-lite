def parse(s: str) -> dict:
    """Parse "key=val,key=val" into a dict. Keys are kept as-written."""
    out = {}
    for pair in s.split(","):
        pair = pair.strip()
        if not pair:
            continue
        key, _, val = pair.partition("=")
        out[key.strip()] = val.strip()
    return out
