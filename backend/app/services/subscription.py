"""Server-authoritative subscription state and entitlements.

Why this module exists
----------------------
``Payment.subscription_expires_at`` was written by the M-Pesa callback handler but
read by nothing except the status endpoint. A subscription therefore "activated"
and then unlocked nothing, and the only place that decided whether a user was
subscribed was a query inside a route function.

Everything that needs to know "is this account subscribed?" must ask this module,
so there is exactly one definition of the answer. The source of truth stays the
``payments`` table, which is only ever written after Safaricom's transaction
status has been confirmed by :func:`app.services.mpesa.process_callback`. A
successful call to the subscribe endpoint therefore cannot activate anything on
its own.

Entitlements are read from configuration rather than hard-coded so pricing and
feature limits can change without a code change, and so no content is silently
locked behind a feature flag that nobody configured.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.payment import Payment

# A payment that never received a callback expires out of the pending state after
# this long. Safaricom sends the notification within a few seconds, so anything
# still pending after a day was abandoned by the customer.
PENDING_PAYMENT_TTL = timedelta(days=1)

SUBSCRIPTION_PERIOD_DAYS = 30


@dataclass(frozen=True)
class SubscriptionState:
    """The authoritative subscription answer for one account."""

    active: bool
    plan: str
    expires_at: datetime | None
    amount: int
    currency: str
    features: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict:
        return {
            "active": self.active,
            "plan": self.plan,
            "expires_at": self.expires_at,
            "amount": self.amount,
            "currency": self.currency,
            "features": list(self.features),
        }


def _as_aware(value: datetime | None) -> datetime | None:
    """Return ``value`` as a timezone-aware UTC datetime.

    ``DateTime(timezone=True)`` only preserves the offset on backends that support
    it. SQLite -- the database used by the test suite and the local development
    server -- hands back a naive datetime, and comparing that against an aware
    ``datetime.now(timezone.utc)`` raises ``TypeError``. The previous
    ``/api/payments/status`` implementation performed exactly that comparison, so
    the status endpoint returned a 500 for any account that had ever paid.
    Naive values are stored in UTC, so attaching the UTC offset is correct.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _active_payment(db: Session, user_id: int, now: datetime) -> Payment | None:
    """Return the payment granting the longest current subscription, if any."""
    return (
        db.query(Payment)
        .filter(
            Payment.user_id == user_id,
            Payment.status == "completed",
            Payment.subscription_expires_at.isnot(None),
            Payment.subscription_expires_at > now,
        )
        .order_by(Payment.subscription_expires_at.desc())
        .first()
    )


def _plan_features(active: bool) -> tuple[str, ...]:
    """Entitlement names granted to this account.

    Sourced from configuration so the product team can widen or narrow them
    without a deploy, and so an unconfigured feature is never assumed to exist.
    """
    configured = settings.SUBSCRIPTION_FEATURES or []
    return tuple(configured) if active else ()


def get_subscription_state(db: Session, user_id: int) -> SubscriptionState:
    """Compute the current subscription for ``user_id``.

    Deliberately derives state on read rather than storing an ``is_active`` flag,
    so a subscription cannot drift out of sync with the payments that produced it
    and an expired subscription cannot stay active because a flag was missed.
    """
    now = datetime.now(timezone.utc)
    payment = _active_payment(db, user_id, now)
    expires_at = _as_aware(payment.subscription_expires_at) if payment else None
    active = bool(expires_at and expires_at > now)
    return SubscriptionState(
        active=active,
        plan=settings.MPESA_TRANSACTION_DESCRIPTION or "Monthly Subscription",
        expires_at=expires_at,
        amount=settings.MPESA_MONTHLY_AMOUNT,
        currency="KES",
        features=_plan_features(active),
    )


def require_active_subscription(db: Session, user_id: int) -> SubscriptionState:
    """Raise if the account has no current subscription.

    Use as a FastAPI dependency for genuinely premium endpoints. It is not
    applied to any existing route: every piece of content in this application is
    currently free, and gating content that is not marked premium would break
    paying members' access without a product decision behind it.
    """
    from fastapi import HTTPException, status as http_status

    state = get_subscription_state(db, user_id)
    if not state.active:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="An active subscription is required for this feature.",
        )
    return state


def expire_stale_pending_payments(db: Session, now: datetime | None = None) -> int:
    """Mark abandoned pending payments as expired. Returns the number changed.

    Without this a customer who dismisses the M-Pesa prompt leaves a permanent
    ``pending`` row, which then blocks the duplicate-push guard in
    :func:`app.services.mpesa.start_stk_push` from ever letting them retry.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - PENDING_PAYMENT_TTL
    changed = (
        db.query(Payment)
        .filter(Payment.status == "pending", Payment.created_at < cutoff)
        .update({Payment.status: "expired"}, synchronize_session=False)
    )
    if changed:
        db.commit()
    return changed