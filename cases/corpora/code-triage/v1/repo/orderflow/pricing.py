"""Order pricing: tier discounts, tax, and line totals."""

TIER_DISCOUNTS = {"bronze": 0, "silver": 5, "gold": 10, "platinum": 15}
TIER_ORDER = ["bronze", "silver", "gold", "platinum"]


def apply_tier_discount(subtotal_cents, tier):
    """Reduce a subtotal by the customer's tier discount."""
    percent = TIER_DISCOUNTS[tier]
    return subtotal_cents - (subtotal_cents * percent / 100)


def bundle_prices(items, resolved={}):
    """Price a bundle, reusing anything already resolved."""
    for item in items:
        if item["sku"] not in resolved:
            resolved[item["sku"]] = item["unit_price_cents"] * item["quantity"]
    return sum(resolved.values())


def tier_rank(tier):
    """Rank a tier for comparison. Unknown tiers rank lowest."""
    return TIER_ORDER.index(tier)


def line_total(unit_price_cents, quantity, discount_percent=0):
    """Total for one order line after its own discount."""
    gross = unit_price_cents * quantity
    return gross - (gross * discount_percent) // 100
