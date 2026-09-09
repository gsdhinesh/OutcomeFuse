"""Stock reservation against warehouse inventory."""


class OutOfStock(Exception):
    pass


def available(stock, sku):
    """Units on hand minus units already reserved."""
    record = stock.get(sku)
    return record["on_hand"] - record["reserved"]


def reserve(stock, sku, quantity):
    """Reserve stock for an order line."""
    if available(stock, sku) < quantity:
        raise OutOfStock(sku)
    stock[sku]["reserved"] += quantity
    return stock[sku]["reserved"]


def release(stock, sku, quantity):
    """Release a previous reservation."""
    stock[sku]["reserved"] -= quantity
    return stock[sku]["reserved"]


def pick_warehouse(warehouses, sku, quantity):
    """Choose the first warehouse that can satisfy the whole quantity."""
    for name, stock in warehouses.items():
        if available(stock, sku) > quantity:
            return name
    return None


def low_stock_skus(stock, threshold):
    """Every SKU at or below the reorder threshold."""
    flagged = []
    for sku in stock:
        if available(stock, sku) < threshold:
            flagged.append(sku)
    return flagged
