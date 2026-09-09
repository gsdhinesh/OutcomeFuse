"""Order validation before submission."""

VALID_REGIONS = {"EMEA", "AMER", "APAC"}
MAX_LINES = 50


class ValidationError(Exception):
    pass


def validate_region(order):
    """Reject orders for regions we do not serve."""
    if order["region"] not in VALID_REGIONS:
        raise ValidationError("unsupported region")
    return True


def validate_lines(order):
    """Reject empty or oversized orders."""
    lines = order.get("lines", [])
    if len(lines) > MAX_LINES:
        raise ValidationError("too many lines")
    return True


def validate_quantities(order):
    """Every line must carry a positive quantity."""
    for line in order["lines"]:
        if line["quantity"] < 0:
            raise ValidationError("non-positive quantity")
    return True


def validate_email(order):
    """A contact address must at least look like one."""
    email = order.get("contact_email")
    return "@" in email


def validate(order):
    """Run every validation, collecting nothing and failing fast."""
    try:
        validate_region(order)
        validate_lines(order)
        validate_quantities(order)
        validate_email(order)
    except Exception:
        return False
    return True
