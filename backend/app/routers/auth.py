import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Doctor, Patient, User
from ..schemas import LoginIn, RegisterIn
from ..security import create_token, current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


def user_dict(db: Session, u: User) -> dict:
    p = db.query(Patient).filter(Patient.user_id == u.id).first() if u.role == "patient" else None
    d = db.query(Doctor).filter(Doctor.user_id == u.id).first() if u.role == "doctor" else None
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role,
            "patient_id": p.id if p else u.linked_patient_id, "doctor_id": d.id if d else None,
            "hospital_id": u.hospital_id or (d.hospital_id if d else None)}


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email.lower()).first():
        raise HTTPException(409, "E-mail already registered")
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), full_name=body.full_name,
                role=body.role, phone=body.phone)
    if body.role == "family":
        patient = db.query(Patient).filter(Patient.family_code == (body.family_code or "").upper()).first()
        if not patient:
            raise HTTPException(404, "Family code not found. Ask the patient for the code on their profile.")
        user.linked_patient_id = patient.id
    db.add(user)
    db.flush()
    if body.role == "patient":
        db.add(Patient(user_id=user.id, dob=body.dob, gender=body.gender, blood_group=body.blood_group,
                       family_code=secrets.token_hex(3).upper()))
    db.commit()
    return {"access_token": create_token(user), "user": user_dict(db, user)}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect e-mail or password")
    return {"access_token": create_token(user), "user": user_dict(db, user)}


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return user_dict(db, user)
