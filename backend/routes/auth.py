from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from routes.deps import get_current_user
from services.auth_service import (
    PLAN_RANK,
    create_token,
    ensure_active_subscription,
    get_next_month_start,
    get_plan_config,
    hash_password,
    sanitize_user,
    verify_password,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup")
async def signup(payload: dict, db: Session = Depends(get_db)):
    name = str(payload.get("name") or "").strip()
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")

    if not name or not email or not password:
        raise HTTPException(status_code=400, detail="Name, email, and password are required.")

    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(name=name, email=email, passwordHash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)

    subscription = ensure_active_subscription(db, user.id)
    token = create_token(user.id, user.email)
    return {"token": token, "user": sanitize_user(user, subscription)}


@router.post("/login")
async def login(payload: dict, db: Session = Depends(get_db)):
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required.")

    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.passwordHash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    subscription = ensure_active_subscription(db, user.id)
    token = create_token(user.id, user.email)
    return {"token": token, "user": sanitize_user(user, subscription)}


@router.get("/me")
async def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subscription = ensure_active_subscription(db, current_user.id)
    db.refresh(current_user)
    return {"user": sanitize_user(current_user, subscription)}


@router.patch("/me")
async def update_profile(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required.")

    current_user.name = name
    db.commit()
    db.refresh(current_user)

    subscription = ensure_active_subscription(db, current_user.id)
    return {"user": sanitize_user(current_user, subscription)}


@router.post("/plan")
async def update_plan(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raw_plan = str(payload.get("plan") or "").strip().upper()
    if raw_plan not in {"FREE", "PRO", "ENTERPRISE"}:
        raise HTTPException(status_code=400, detail="Invalid plan.")

    subscription = ensure_active_subscription(db, current_user.id)
    current_plan = str(subscription.plan or "FREE").upper()

    if PLAN_RANK[raw_plan] > PLAN_RANK[current_plan]:
        raise HTTPException(status_code=402, detail="Upgrade requires payment. Use demo payment flow.")

    next_config = get_plan_config(raw_plan)
    next_reset = get_next_month_start().replace(tzinfo=None)
    next_credits = min(int(subscription.creditsRemaining or 0), next_config["monthlyCredits"])

    subscription.plan = raw_plan
    subscription.monthlyCredits = next_config["monthlyCredits"]
    subscription.creditsRemaining = max(next_credits, 0)
    subscription.periodEnd = next_reset
    subscription.nextResetAt = next_reset
    db.commit()
    db.refresh(subscription)

    return {"user": sanitize_user(current_user, subscription)}


@router.get("/plan")
async def get_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subscription = ensure_active_subscription(db, current_user.id)
    return {
        "plan": str(subscription.plan or "FREE").upper(),
        "monthlyCredits": int(subscription.monthlyCredits or 0),
        "creditsRemaining": int(subscription.creditsRemaining or 0),
        "nextResetAt": subscription.nextResetAt,
    }
