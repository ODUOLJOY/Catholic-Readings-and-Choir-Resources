"""Suite-wide pytest configuration.

The social rate limiter keeps fixed windows in process memory, which is correct
for a running server but leaks across tests: user ids restart at 1 in each
in-memory database, so one test's allowance would otherwise be spent by an
earlier test and produce order-dependent 429s. Clearing the buckets before each
test keeps the suite deterministic without weakening the limiter itself.
"""
import pytest

from app.services.rate_limit import reset_for_tests


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    reset_for_tests()
    yield
    reset_for_tests()
