import base64
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import requests
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.payment import Payment
from app.services.subscription import PENDING_PAYMENT_TTL, SUBSCRIPTION_PERIOD_DAYS


class MpesaError(RuntimeError):
    pass


def normalize_phone(phone: str) -> str:
    digits = "".join(character for character in phone if character.isdigit())
    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    elif digits.startswith("7") and len(digits) == 9:
        digits = "254" + digits
    if len(digits) != 12 or not digits.startswith("2547"):
        raise ValueError("Enter a valid Kenyan mobile number, for example 0712345678.")
    return digits


def _base_url() -> str:
    return (
        "https://sandbox.safaricom.co.ke"
        if settings.MPESA_ENVIRONMENT == "sandbox"
        else "https://api.safaricom.co.ke"
    )


def _access_token() -> str:
    if not settings.MPESA_CONSUMER_KEY or not settings.MPESA_CONSUMER_SECRET:
        raise MpesaError("M-Pesa credentials are not configured.")
    credentials = f"{settings.MPESA_CONSUMER_KEY}:{settings.MPESA_CONSUMER_SECRET}".encode()
    response = requests.get(
        f"{_base_url()}/oauth/v1/generate?grant_type=client_credentials",
        headers={"Authorization": f"Basic {base64.b64encode(credentials).decode()}"},
        timeout=20,
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise MpesaError("M-Pesa did not return an access token.")
    return token


def query_stk_status(checkout_request_id: str) -> dict[str, Any]:
    if not settings.MPESA_SHORTCODE or not settings.MPESA_PASSKEY:
        raise MpesaError("M-Pesa shortcode and passkey are not configured.")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(
        f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}".encode()
    ).decode()
    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id,
    }
    try:
        response = requests.post(
            f"{_base_url()}/mpesa/stkpushquery/v1/query",
            json=payload,
            headers={"Authorization": f"Bearer {_access_token()}"},
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as error:
        raise MpesaError("Unable to verify the M-Pesa transaction status.") from error
    except ValueError as error:
        raise MpesaError("M-Pesa returned an invalid transaction status.") from error
    if not isinstance(result, dict):
        raise MpesaError("M-Pesa returned an invalid transaction status.")
    return result


def start_stk_push(db: Session, user_id: int, phone_number: str) -> Payment:
    phone = normalize_phone(phone_number)

    # Duplicate-push guard. Every STK push is a real cost to Safaricom and can
    # double-charge the customer, so an account with an unexpired pending payment
    # is told to finish that one first. Abandoned prompts are expired by
    # :func:`app.services.subscription.expire_stale_pending_payments` so a
    # dismissed prompt cannot lock the account out permanently.
    existing = (
        db.query(Payment)
        .filter(
            Payment.user_id == user_id,
            Payment.status == "pending",
            Payment.created_at
            >= datetime.now(timezone.utc) - PENDING_PAYMENT_TTL,
        )
        .order_by(Payment.created_at.desc())
        .first()
    )
    if existing is not None:
        raise MpesaError(
            "You already have a payment awaiting confirmation. "
            "Complete it on your phone, or try again in a few minutes."
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(
        f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}".encode()
    ).decode()

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": settings.MPESA_TRANSACTION_TYPE,
        "Amount": settings.MPESA_MONTHLY_AMOUNT,
        "PartyA": phone,
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": settings.MPESA_ACCOUNT_REFERENCE,
        "TransactionDesc": settings.MPESA_TRANSACTION_DESCRIPTION,
    }

    try:
        response = requests.post(
            f"{_base_url()}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers={"Authorization": f"Bearer {_access_token()}"},
            timeout=30,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
    except requests.RequestException as error:
        raise MpesaError("Unable to reach M-Pesa to start the payment.") from error
    except ValueError as error:
        raise MpesaError("M-Pesa returned an invalid response.") from error
    if not isinstance(data, dict) or data.get("ResponseCode") not in ("0", 0):
        description = (
            data.get("ResponseDescription", "M-Pesa request failed.")
            if isinstance(data, dict)
            else "M-Pesa request failed."
        )
        raise MpesaError(description)

    payment = Payment(
        user_id=user_id,
        phone_number=phone,
        amount=settings.MPESA_MONTHLY_AMOUNT,
        currency="KES",
        status="pending",
        merchant_request_id=data.get("MerchantRequestID"),
        checkout_request_id=data.get("CheckoutRequestID"),
        result_description=data.get("ResponseDescription"),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def process_callback(db: Session, callback: dict[str, Any]) -> Payment | None:
    if not isinstance(callback, dict):
        raise ValueError("Invalid M-Pesa callback payload.")
    body = callback.get("Body", {})
    if not isinstance(body, dict):
        raise ValueError("Invalid M-Pesa callback payload.")
    stk = body.get("stkCallback", {})
    if not isinstance(stk, dict):
        raise ValueError("Invalid M-Pesa callback payload.")
    checkout_id = stk.get("CheckoutRequestID")
    if not isinstance(checkout_id, str) or not checkout_id:
        raise ValueError("Missing M-Pesa checkout request ID.")

    payment = (
        db.query(Payment)
        .filter(Payment.checkout_request_id == checkout_id)
        .first()
    )
    if not payment:
        return None
    if payment.status == "completed":
        return payment

    # Claim the row with a conditional UPDATE instead of relying on
    # ``SELECT ... FOR UPDATE``. Row locks are a no-op on SQLite, which is what the
    # test and development database uses, so two near-simultaneous callbacks for
    # one checkout could both read ``pending`` and each extend the subscription by
    # a further 30 days. A single atomic UPDATE lets exactly one callback win.
    claimed = (
        db.query(Payment)
        .filter(Payment.id == payment.id, Payment.status == "pending")
        .update({Payment.status: "processing"}, synchronize_session=False)
    )
    if not claimed:
        # Another callback is already handling this payment. Re-read so the caller
        # sees whatever that handler committed.
        db.expire_all()
        return db.query(Payment).filter(Payment.id == payment.id).first()
    db.commit()
    db.refresh(payment)

    try:
        result_code = _result_code(stk)
        provider_status = query_stk_status(checkout_id)
        verified_result_code = _result_code(provider_status)
        if verified_result_code != result_code:
            raise MpesaError(
                "M-Pesa callback does not match the confirmed transaction status."
            )

        payment.result_code = result_code
        payment.result_description = provider_status.get("ResultDesc") or stk.get(
            "ResultDesc"
        )
        payment.status = "completed" if result_code == 0 else "failed"

        if result_code == 0:
            _apply_successful_payment(db, payment, stk)

        db.commit()
    except (MpesaError, ValueError):
        # Both release the claim. They stay distinct types because the callback
        # route maps them differently: ValueError is a malformed callback (400),
        # MpesaError is a provider or state problem (503, so Safaricom retries).
        _release_claim(db, payment.id)
        raise
    except IntegrityError:
        # ``payments.mpesa_receipt_number`` is unique, so a receipt that another
        # payment already holds fails at COMMIT rather than at assignment. Left
        # unhandled this propagated out of the endpoint as a 500 -- which the
        # callback route does not catch, so Safaricom kept retrying a callback
        # that can never succeed -- and the claimed row stayed "processing"
        # forever, wedging that account's subscription.
        _release_claim(db, payment.id)
        raise MpesaError(
            "This M-Pesa receipt has already been recorded against another payment."
        ) from None
    except Exception:
        # Verification failed. Release the claim so Safaricom's retry (or the
        # customer) can still settle the payment instead of leaving it wedged in
        # "processing" forever.
        _release_claim(db, payment.id)
        raise

    db.refresh(payment)
    return payment


def _release_claim(db: Session, payment_id: int) -> None:
    """Return a claimed payment to ``pending`` so it can be retried.

    The conditional UPDATE only touches a row this handler still owns, so a
    handler that lost the claim cannot resurrect a payment another callback has
    already completed.
    """
    db.rollback()
    db.query(Payment).filter(
        Payment.id == payment_id, Payment.status == "processing"
    ).update({Payment.status: "pending"}, synchronize_session=False)
    db.commit()


def _result_code(payload: dict[str, Any]) -> int:
    try:
        return int(payload["ResultCode"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Invalid M-Pesa callback result code.") from error


def _apply_successful_payment(
    db: Session,
    payment: Payment,
    stk: dict[str, Any],
) -> None:
    """Validate the callback payload and extend the subscription."""
    metadata = stk.get("CallbackMetadata", {})
    items_list = metadata.get("Item", []) if isinstance(metadata, dict) else []
    items = {
        item.get("Name"): item.get("Value")
        for item in items_list
        if isinstance(item, dict)
    } if isinstance(items_list, list) else {}
    try:
        callback_amount = Decimal(str(items["Amount"]))
        callback_phone = normalize_phone(str(items["PhoneNumber"]))
    except (KeyError, TypeError, ValueError, InvalidOperation) as error:
        raise ValueError("M-Pesa callback is missing valid payment details.") from error

    receipt = items.get("MpesaReceiptNumber")
    if (
        callback_amount != Decimal(payment.amount)
        or callback_phone != normalize_phone(payment.phone_number)
        or not isinstance(receipt, str)
        or not receipt.strip()
    ):
        raise ValueError("M-Pesa callback payment details do not match the pending payment.")

    cleaned_receipt = receipt.strip()
    # One Safaricom receipt is one transaction. If another payment already holds
    # it, this callback is either a replay or a mismatched checkout, and extending
    # the subscription from it would grant time that was never paid for. The unique
    # constraint on the column is the backstop for a concurrent race; this check
    # produces the clear message in the ordinary case.
    already_recorded = (
        db.query(Payment.id)
        .filter(
            Payment.mpesa_receipt_number == cleaned_receipt,
            Payment.id != payment.id,
        )
        .first()
    )
    if already_recorded is not None:
        raise MpesaError(
            "This M-Pesa receipt has already been recorded against another payment."
        )

    payment.mpesa_receipt_number = cleaned_receipt
    now = datetime.now(timezone.utc)
    current = (
        db.query(Payment)
        .filter(
            Payment.user_id == payment.user_id,
            Payment.status == "completed",
            Payment.id != payment.id,
            Payment.subscription_expires_at > now,
        )
        .order_by(Payment.subscription_expires_at.desc())
        .first()
    )
    start = current.subscription_expires_at if current else now
    payment.subscription_expires_at = start + timedelta(days=SUBSCRIPTION_PERIOD_DAYS)
