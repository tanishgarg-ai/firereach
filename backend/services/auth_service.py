import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.subscription import Subscription


JWT_SECRET = str(os.getenv("JWT_SECRET", "firereach_dev_secret_change_me")).strip()
JWT_ALGORITHM = "HS256"

PLAN_CONFIG = {
    "FREE": {"monthlyCredits": 30, "amount": 0},
    "STARTER": {"monthlyCredits": 150, "amount": 299},
    "GROWTH": {"monthlyCredits": 400, "amount": 599},
    "SCALE": {"monthlyCredits": 1200, "amount": 1299},
    "PRO": {"monthlyCredits": 2000, "amount": 599},
    "ENTERPRISE": {"monthlyCredits": 9999, "amount": 999},
}

PLAN_RANK = {
    "FREE": 1,
    "STARTER": 2,
    "GROWTH": 3,
    "PRO": 3,
    "SCALE": 4,
    "ENTERPRISE": 4,
}


def hash_password(password: str) -> str:
    password_bytes = _normalize_password_bytes(password)
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        password_bytes = _normalize_password_bytes(password)
        return bcrypt.checkpw(password_bytes, str(password_hash or "").encode("utf-8"))
    except Exception:
        return False


def _normalize_password_bytes(password: str) -> bytes:
    # bcrypt operates on max 72 bytes; truncate deterministically for hash/verify parity.
    return str(password or "").encode("utf-8")[:72]


def create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(tz=timezone.utc) + timedelta(days=14),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Unauthorized request.") from exc


def get_next_month_start(value: datetime | None = None) -> datetime:
    now = value or datetime.now(tz=timezone.utc)
    year = now.year
    month = now.month + 1
    if month == 13:
        month = 1
        year += 1
    return now.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


def get_plan_config(plan: str):
    return PLAN_CONFIG.get(str(plan or "FREE").upper(), PLAN_CONFIG["FREE"])


def is_reset_due(subscription: Subscription) -> bool:
    if not subscription or not subscription.nextResetAt:
        return True
    return datetime.now(tz=timezone.utc).replace(tzinfo=None) >= subscription.nextResetAt


def ensure_active_subscription(db: Session, user_id: str) -> Subscription:
    subscription = (
        db.query(Subscription)
        .filter(Subscription.userId == user_id, Subscription.status == "active")
        .order_by(Subscription.periodEnd.desc())
        .first()
    )

    if not subscription:
        config = get_plan_config("FREE")
        next_reset = get_next_month_start().replace(tzinfo=None)
        subscription = Subscription(
            userId=user_id,
            plan="FREE",
            monthlyCredits=config["monthlyCredits"],
            creditsRemaining=config["monthlyCredits"],
            nextResetAt=next_reset,
            periodEnd=next_reset,
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        return subscription

    plan_config = get_plan_config(subscription.plan)
    dirty = False

    if not subscription.monthlyCredits or subscription.monthlyCredits <= 0:
        subscription.monthlyCredits = plan_config["monthlyCredits"]
        dirty = True

    if subscription.creditsRemaining is None or subscription.creditsRemaining < 0:
        subscription.creditsRemaining = plan_config["monthlyCredits"]
        dirty = True

    if not subscription.nextResetAt:
        subscription.nextResetAt = get_next_month_start().replace(tzinfo=None)
        dirty = True

    if is_reset_due(subscription):
        next_reset = get_next_month_start().replace(tzinfo=None)
        subscription.monthlyCredits = plan_config["monthlyCredits"]
        subscription.creditsRemaining = plan_config["monthlyCredits"]
        subscription.periodStart = datetime.utcnow()
        subscription.periodEnd = next_reset
        subscription.nextResetAt = next_reset
        dirty = True

    if dirty:
        db.commit()
        db.refresh(subscription)

    return subscription


def sanitize_user(user, subscription: Subscription) -> dict:
    plan = str(subscription.plan or "FREE").upper()
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "plan": plan,
        "monthlyCredits": int(subscription.monthlyCredits or 30),
        "creditsRemaining": int(subscription.creditsRemaining or 30),
        "nextResetAt": subscription.nextResetAt,
        "plus": plan in {"STARTER", "GROWTH", "SCALE", "PRO", "ENTERPRISE"},
        "createdAt": user.createdAt,
        "updatedAt": user.updatedAt,
    }
