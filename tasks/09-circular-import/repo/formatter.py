from mathutils import add


def format_sum(a, b):
    """Add a and b, format as a dollar string."""
    total = add(a, b)
    return f"${total:.2f}"
