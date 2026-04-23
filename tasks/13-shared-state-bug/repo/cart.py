from pricing import total_with_tax


class Cart:
    items = []  # BUG: class-level attribute shared across instances

    def add_item(self, name: str, price: float) -> None:
        self.items.append({"name": name, "price": price})

    def total(self, tax_rate: float = 0.0) -> float:
        subtotal = sum(item["price"] for item in self.items)
        return total_with_tax(subtotal, tax_rate)
