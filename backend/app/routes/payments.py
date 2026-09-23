from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.payment import Payment
from app.models.user import User
from app.routes.auth_dependency import get_current_user
from app.services.mpesa import MpesaError, normalize_phone, process_callback, start_stk_push

router = APIRouter(tags=["Payments"])


class PaymentRequest(BaseModel):
    phone_number: str = Field(min_length=9, max_length=15)


@router.post("/subscribe", status_code=status.HTTP_202_ACCEPTED)
def subscribe(
    payload: PaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        normalize_phone(payload.phone_number)
        payment = start_stk_push(db, current_user.id, payload.phone_number)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except MpesaError as error:
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
    payment = (
        db.query(Payment)
        .filter(
            Payment.user_id == current_user.id,
            Payment.status == "completed",
        )
        .order_by(Payment.subscription_expires_at.desc())
        .first()
    )
    now = datetime.now(timezone.utc)
    expires_at = payment.subscription_expires_at if payment else None
    active = bool(expires_at and expires_at > now)
    return {
        "active": active,
        "expires_at": expires_at,
        "amount": settings.MPESA_MONTHLY_AMOUNT,
        "currency": "KES",
    }


@router.post("/mpesa/callback")
async def mpesa_callback(request: Request, db: Session = Depends(get_db)):
    callback = await request.json()
    process_callback(db, callback)
    return {"ResultCode": 0, "ResultDesc": "Accepted"}
