"""Fixed-window rate limiting for abuse-sensitive social operations.

The limiter is deliberately dependency-free and in-process: the application has
no shared cache guaranteed to be reachable in every deployment (REDIS_URL points
at a host that is not always up), and correctness must not depend on it. The
trade-off is that limits are enforced per application process, so a multi-worker
deployment multiplies the effective allowance by the worker count. That is
acceptable for these ceilings because they exist to stop a single abusive client,
not to enforce a strict global quota.

Every limit is a ceiling chosen to stay well clear of ordinary parish
communication: posting 30 times a minute still allows a member to type several
long messages while reporting, and reacting 60 times a minute is far above
normal enthusiasm.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, status


@dataclass(frozen=True)
class Limit:
    """A fixed-window allowance of ``max_events`` per ``window_seconds``."""

    max_events: int
    window_seconds: int

    def describe(self) -> str:
        return f"Too many requests. Please wait before trying this action again."


# Abuse-sensitive ceilings. Ordinary parish conversation stays comfortably
# inside these numbers.
MESSAGE_SEND = Limit(max_events=30, window_seconds=60)
CONVERSATION_CREATE = Limit(max_events=20, window_seconds=300)
SUGGESTION_SUBMIT = Limit(max_events=5, window_seconds=3600)
SUGGESTION_REPLY = Limit(max_events=30, window_seconds=60)
REPORT_SUBMIT = Limit(max_events=10, window_seconds=3600)
REACTION = Limit(max_events=60, window_seconds=60)
BLOCK_CHANGE = Limit(max_events=20, window_seconds=300)
MEMBER_SEARCH = Limit(max_events=60, window_seconds=60)


_state: dict[tuple[str, int], deque[float]] = defaultdict(deque)
_lock = threading.Lock()
_MAX_TRACKED_KEYS = 20_000


def _prune_locked(now: float) -> None:
    """Drop idle buckets so a long-running process cannot grow unbounded."""
    if len(_state) <= _MAX_TRACKED_KEYS:
        return
    for key in [key for key, events in _state.items() if not events or now - events[-1] > 3600]:
        _state.pop(key, None)


def consume(key: str, subject_id: int, limit: Limit) -> None:
    """Record one event, raising HTTP 429 when the allowance is exhausted.

    ``key`` namespaces the action so that, for example, sending a message and
    submitting a report draw from separate allowances.
    """
    now = time.monotonic()
    bucket_key = (key, subject_id)
    with _lock:
        events = _state[bucket_key]
        cutoff = now - limit.window_seconds
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= limit.max_events:
            retry_after = max(1, int(limit.window_seconds - (now - events[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=limit.describe(),
                headers={"Retry-After": str(retry_after)},
            )
        events.append(now)
        _prune_locked(now)


def reset_for_tests() -> None:
    """Clear all buckets. Used by the test suite to stay order-independent."""
    with _lock:
        _state.clear()
