from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from services.auth_service import decode_token


def get_current_user(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> User:
    header = str(authorization or "")
    token = header[7:] if header.startswith("Bearer ") else ""
    if not token:
        raise HTTPException(status_code=401, detail="Missing auth token.")

    payload = decode_token(token)
    user_id = str(payload.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized request.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session.")

    return user
