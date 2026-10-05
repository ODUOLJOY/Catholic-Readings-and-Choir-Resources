from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.payment import Payment
from app.models.user import User
from app.routes.auth_dependency import get_current_user
from app.services import rate_limit
from app.services.mpesa import MpesaError, normalize_phone, process_callback, start_stk_push
from app.services.subscription import expire_stale_pending_payments, get_subscription_state

router = APIRouter(tags=["Payments"])

PAYMENT_START = rate_limit.Limit(max_events=5, window_seconds=3600)


class PaymentRequest(BaseModel):
    phone_number: str = Field(min_length=9, max_length=15)


@router.get("/plans")
def subscription_plans():
    """Public plan description sourced from configuration, never hard-coded.

    The frontend previously rendered "KES 10 / month" and a hard-coded M-Pesa
    shortcode as literal strings, which meant changing the price or shortcode in
    configuration silently produced a lie on screen.
    """
    return {
        "plans": [
            {
                "id": "monthly",
                "name": settings.MPESA_TRANSACTION_DESCRIPTION or "Monthly Subscription",
                "amount": settings.MPESA_MONTHLY_AMOUNT,
                "currency": "KES",
                "period_days": 30,
                "features": list(settings.SUBSCRIPTION_FEATURES or []),
                "payment_method": "M-Pesa",
                "paybill": settings.MPESA_SHORTCODE or None,
            }
        ]
    }


@router.post("/subscribe", status_code=status.HTTP_202_ACCEPTED)
def subscribe(
    request: Request,
    payload: PaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rate_limit.consume("payments:subscribe", current_user.id, PAYMENT_START)
    try:
        normalize_phone(payload.phone_number)
        # Clear abandoned prompts first so the duplicate guard inside
        # start_stk_push cannot trap an account whose earlier payment was
        # dismissed on the handset.
        expire_stale_pending_payments(db)
        payment = start_stk_push(db, current_user.id, payload.phone_number)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except MpesaError as error:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(error)) from error
    except Exception as error:
        db.rollback()
        raise HTTPException(status_code=502, detail="Unable to start the M-Pesa payment.") from error

    return {
        "payment_id": payment.id,
        "status": payment.status,
        "amount": payment.amount,
        "currency": payment.currency,
        "message": "Check your phone and enter your M-Pesa PIN to complete payment.",
    }


@router.get("/status")
def subscription_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expire_stale_pending_payments(db)
    return get_subscription_state(db, current_user.id).as_dict()


@router.get("/history")
def payment_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Transaction records for the signed-in account.

    Required for the "payment history" half of the subscription feature: without
    it a member who has been charged can see only whether they are active, not
    what they paid or whether a payment failed.
    """
    payments = (
        db.query(Payment)
        .filter(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
        .limit(50)
        .all()
    )
    return {
        "payments": [
            {
                "id": payment.id,
                "amount": payment.amount,
                "currency": payment.currency,
                "status": payment.status,
                "phone_number": payment.phone_number,
                "mpesa_receipt_number": payment.mpesa_receipt_number,
                "result_code": payment.result_code,
                "result_description": payment.result_description,
                "subscription_expires_at": payment.subscription_expires_at,
                "created_at": payment.created_at,
            }
            for payment in payments
        ]
    }


@router.post("/mpesa/callback")
async def mpesa_callback(request: Request, db: Session = Depends(get_db)):
    try:
        callback = await request.json()
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from error
    try:
        process_callback(db, callback)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except MpesaError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {"ResultCode": 0, "ResultDesc": "Accepted"}