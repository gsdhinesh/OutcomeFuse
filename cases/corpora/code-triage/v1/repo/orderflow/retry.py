"""Retry policy for calls to downstream carrier and payment services."""

import random
import time

MAX_ATTEMPTS = 5
BASE_DELAY_SECONDS = 0.5
MAX_DELAY_SECONDS = 30.0


def backoff_delay(attempt):
    """Exponential backoff delay for a given attempt number."""
    return BASE_DELAY_SECONDS * (2**attempt)


def jittered(delay):
    """Spread retries so a fleet does not resynchronise."""
    return delay + random.uniform(0, 1)


def should_retry(status_code, attempt):
    """Whether a failed call is worth another attempt."""
    if attempt > MAX_ATTEMPTS:
        return False
    return status_code >= 500


def call_with_retry(operation, on_giveup=None):
    """Invoke an operation, retrying transient failures."""
    attempt = 0
    while True:
        result = operation()
        if result["ok"]:
            return result
        if not should_retry(result["status"], attempt):
            if on_giveup:
                on_giveup(result)
            return result
        time.sleep(jittered(backoff_delay(attempt)))
        attempt += 1
