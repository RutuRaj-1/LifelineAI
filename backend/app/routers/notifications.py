from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Notification, User
from ..security import current_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("")
def list_notifications(unread_only: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(Notification).filter(Notification.user_id == user.id)
    q = q.filter(Notification.is_read.is_(False)) if unread_only else q
    rows = q.order_by(Notification.created_at.desc()).limit(100).all()
    return [{"id": n.id, "case_id": n.case_id, "title": n.title, "message": n.message, "channel": n.channel,
            "is_read": n.is_read, "created_at": n.created_at.isoformat()} for n in rows]


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if n and n.user_id == user.id:
        n.is_read = True
        db.commit()
    return {"ok": True}
