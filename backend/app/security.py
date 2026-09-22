from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import Doctor, EmergencyCase, User

bearer = HTTPBearer(auto_error=False)


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except ValueError:
        return False


def create_token(user: User) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expire_minutes)
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": exp}, s.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> int:
    try:
        return int(jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user = db.get(User, decode_token(cred.credentials))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return user


def require_roles(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role: {', '.join(roles)}")
        return user
    return dep


def doctor_of(db: Session, user: User) -> Doctor | None:
    return db.query(Doctor).filter(Doctor.user_id == user.id).first() if user.role == "doctor" else None


def can_access_patient(db: Session, user: User, patient_id: int) -> bool:
    """Consent-first access: patient (self), linked family, or clinical staff with an ACTIVE case for that patient."""
    if user.role == "patient":
        from .models import Patient
        p = db.query(Patient).filter(Patient.user_id == user.id).first()
        return bool(p and p.id == patient_id)
    if user.role == "family":
        return user.linked_patient_id == patient_id
    q = db.query(EmergencyCase).filter(EmergencyCase.patient_id == patient_id, EmergencyCase.status != "COMPLETED")
    if user.role == "hospital":
        return q.filter(EmergencyCase.hospital_id == user.hospital_id).first() is not None
    if user.role == "doctor":
        d = doctor_of(db, user)
        return bool(d and q.filter(EmergencyCase.doctor_id == d.id).first())
    return False
