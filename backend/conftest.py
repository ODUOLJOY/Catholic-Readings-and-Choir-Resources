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


@pytest.fixture(autouse=True)
def _allow_test_client_host():
    """Let ``TestClient`` requests through ``TrustedHostMiddleware``.

    ``TestClient`` sends ``Host: testserver``, which is not a host the service is
    served on and would therefore be rejected as a Host-header injection attempt.
    It is added only in tests, so the production host allowlist stays strict
    without being weakened just to make the suite pass.

    ``add_middleware`` copies the list at import time, so the captured reference
    is updated in place rather than by rebinding ``settings.ALLOWED_HOSTS``.
    """
    from app.core.config import settings
    from app.main import app

    middleware = next(
        (
            item
            for item in app.user_middleware
            if item.cls.__name__ == "TrustedHostMiddleware"
        ),
        None,
    )
    captured = middleware.kwargs["allowed_hosts"] if middleware else None
    original = list(captured) if captured is not None else list(settings.ALLOWED_HOSTS)

    if captured is not None and "testserver" not in captured:
        captured.append("testserver")
    yield
    if captured is not None:
        captured[:] = original
    settings.ALLOWED_HOSTS = original
