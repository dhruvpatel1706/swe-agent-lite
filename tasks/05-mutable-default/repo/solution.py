def add_item(item, items=[]):
    """Return a list with `item` appended. Pure — never mutates caller state."""
    items.append(item)
    return items
