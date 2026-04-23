def factorial(n: int) -> int:
    """Compute n! for n >= 0. factorial(0) is 1 by convention."""
    return n * factorial(n - 1)
