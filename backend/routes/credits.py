from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from routes.deps import get_current_user
from services.auth_service import ensure_active_subscription


router = APIRouter(tags=["credits"])


@router.get("/credits")
async def get_credits(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subscription = ensure_active_subscription(db, current_user.id)
    return {
        "plan": subscription.plan,
        "creditsRemaining": int(subscription.creditsRemaining or 0),
        "monthlyCredits": int(subscription.monthlyCredits or 0),
        "nextResetAt": subscription.nextResetAt,
    }


@router.post("/credits/consume")
async def consume_credits(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    amount = max(1, int(payload.get("amount") or 5))
    subscription = ensure_active_subscription(db, current_user.id)

    if int(subscription.creditsRemaining or 0) < amount:
        raise HTTPException(
            status_code=402,
            detail={
                "message": "Insufficient credits for this ICP run.",
                "creditsRemaining": int(subscription.creditsRemaining or 0),
                "monthlyCredits": int(subscription.monthlyCredits or 0),
            },
        )

    subscription.creditsRemaining = int(subscription.creditsRemaining or 0) - amount
    db.commit()
    db.refresh(subscription)

    return {
        "plan": subscription.plan,
        "creditsRemaining": int(subscription.creditsRemaining or 0),
        "monthlyCredits": int(subscription.monthlyCredits or 0),
        "nextResetAt": subscription.nextResetAt,
        "deducted": amount,
    }
