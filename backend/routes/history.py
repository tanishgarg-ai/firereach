from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.history import SearchHistory
from models.user import User
from routes.deps import get_current_user


router = APIRouter(tags=["history"])


@router.post("/history")
async def save_history(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    icp = str(payload.get("icp") or "").strip()
    send_mode = str(payload.get("send_mode") or "auto").strip().lower()
    target_company = str(payload.get("target_company") or "").strip() or None
    test_recipient_email = str(payload.get("test_recipient_email") or "").strip() or None
    result = payload.get("result")

    if not icp:
        raise HTTPException(status_code=400, detail="ICP is required.")

    if not isinstance(result, dict):
        raise HTTPException(status_code=400, detail="Workflow result payload is required.")

    saved = SearchHistory(
        userId=current_user.id,
        icp=icp,
        sendMode=send_mode,
        targetCompany=target_company,
        testRecipientEmail=test_recipient_email,
        result=result,
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)

    return {
        "history": {
            "id": saved.id,
            "icp": saved.icp,
            "sendMode": saved.sendMode,
            "targetCompany": saved.targetCompany,
            "testRecipientEmail": saved.testRecipientEmail,
            "result": saved.result,
            "createdAt": saved.createdAt.isoformat(),
            "updatedAt": saved.updatedAt.isoformat(),
        }
    }


@router.get("/history")
async def get_history(
    limit: int = 15,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    safe_limit = max(1, min(50, int(limit or 15)))
    rows = (
        db.query(SearchHistory)
        .filter(SearchHistory.userId == current_user.id)
        .order_by(SearchHistory.createdAt.desc())
        .limit(safe_limit)
        .all()
    )

    compact = []
    for item in rows:
        result = item.result if isinstance(item.result, dict) else {}
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        compact.append(
            {
                "id": item.id,
                "icp": item.icp,
                "sendMode": item.sendMode,
                "targetCompany": item.targetCompany,
                "testRecipientEmail": item.testRecipientEmail,
                "createdAt": item.createdAt.isoformat(),
                "status": result.get("status") or "unknown",
                "selectedCompany": result.get("selected_company_name") or "",
                "companyCount": summary.get("company_count") or 0,
            }
        )

    return {"history": compact}


@router.get("/history/{history_id}")
async def get_history_item(
    history_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(SearchHistory)
        .filter(SearchHistory.id == str(history_id), SearchHistory.userId == current_user.id)
        .first()
    )

    if not item:
        raise HTTPException(status_code=404, detail="History item not found.")

    return {
        "history": {
            "id": item.id,
            "icp": item.icp,
            "sendMode": item.sendMode,
            "targetCompany": item.targetCompany,
            "testRecipientEmail": item.testRecipientEmail,
            "result": item.result,
            "createdAt": item.createdAt.isoformat(),
            "updatedAt": item.updatedAt.isoformat(),
        }
    }


@router.patch("/history/{history_id}")
async def rename_history_item(
    history_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    history_id = str(history_id or "").strip()
    icp = str(payload.get("icp") or "").strip()

    if not history_id:
        raise HTTPException(status_code=400, detail="History id is required.")

    if not icp:
        raise HTTPException(status_code=400, detail="ICP is required.")

    item = (
        db.query(SearchHistory)
        .filter(SearchHistory.id == history_id, SearchHistory.userId == current_user.id)
        .first()
    )

    if not item:
        raise HTTPException(status_code=404, detail="History item not found.")

    item.icp = icp
    db.commit()
    db.refresh(item)

    return {
        "history": {
            "id": item.id,
            "icp": item.icp,
            "sendMode": item.sendMode,
            "targetCompany": item.targetCompany,
            "testRecipientEmail": item.testRecipientEmail,
            "result": item.result,
            "createdAt": item.createdAt.isoformat(),
            "updatedAt": item.updatedAt.isoformat(),
        }
    }


@router.delete("/history/{history_id}")
async def delete_history_item(
    history_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    history_id = str(history_id or "").strip()
    if not history_id:
        raise HTTPException(status_code=400, detail="History id is required.")

    item = (
        db.query(SearchHistory)
        .filter(SearchHistory.id == history_id, SearchHistory.userId == current_user.id)
        .first()
    )

    if not item:
        raise HTTPException(status_code=404, detail="History item not found.")

    db.delete(item)
    db.commit()
    return {"success": True, "id": history_id}
