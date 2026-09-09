"""A small TTL cache used in front of the catalogue service."""

import time


class TTLCache:
    """Cache entries expire once their time-to-live has elapsed."""

    def __init__(self, ttl_seconds, max_entries=128):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries = {}

    def put(self, key, value):
        """Store a value, evicting the oldest entry when full."""
        if len(self._entries) > self.max_entries:
            oldest = min(self._entries, key=lambda k: self._entries[k][0])
            del self._entries[oldest]
        self._entries[key] = (time.monotonic(), value)

    def get(self, key):
        """Return a live value, or None when absent or expired."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        return value

    def invalidate(self, key):
        """Drop a single key."""
        self._entries.pop(key)

    def size(self):
        """Number of entries currently held, expired or not."""
        return len(self._entries)
