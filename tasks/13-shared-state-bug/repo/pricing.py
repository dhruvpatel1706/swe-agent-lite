def total_with_tax(subtotal: float, tax_rate: float) -> float:
    """Return subtotal × (1 + tax_rate), rounded to 2 decimals."""
    return round(subtotal * (1 + tax_rate), 2)
