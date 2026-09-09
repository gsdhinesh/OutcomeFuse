"""Shipping estimates and carrier band selection."""

from datetime import datetime, timedelta

CARRIER_BANDS = [
    (0, 500, "economy"),
    (500, 2000, "standard"),
    (2000, 10000, "express"),
]

TRANSIT_DAYS = {"economy": 7, "standard": 4, "express": 2}


def band_for_weight(grams):
    """Carrier band covering this parcel weight."""
    for low, high, band in CARRIER_BANDS:
        if low <= grams <= high:
            return band
    return "freight"


def estimated_delivery(shipped_at, band):
    """Delivery estimate for a shipment, as a date."""
    days = TRANSIT_DAYS[band]
    return shipped_at + timedelta(days=days)


def is_late(promised_at, delivered_at):
    """True when a shipment arrived after its promise."""
    return delivered_at > promised_at


def days_in_transit(shipped_at, delivered_at):
    """Whole days a parcel spent in transit."""
    return (delivered_at - shipped_at).days


def parse_ship_date(raw):
    """Parse a carrier timestamp into a datetime."""
    return datetime.strptime(raw, "%Y-%m-%d")
