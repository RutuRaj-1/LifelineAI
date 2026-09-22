from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from .events import hub
from .security import decode_token
from .db import SessionLocal
from .models import Doctor, User

router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket, token: str = Query(...)):
    try:
        user_id = decode_token(token)
    except Exception:  # noqa: BLE001
        await ws.close(code=4401)
        return
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            await ws.close(code=4401)
            return
        hospital_id = user.hospital_id
        if user.role == "doctor":
            d = db.query(Doctor).filter(Doctor.user_id == user.id).first()
            hospital_id = d.hospital_id if d else None
        from .models import Patient
        patient_id = user.linked_patient_id
        if user.role == "patient":
            patient_id = db.query(Patient).filter(Patient.user_id == user.id).first().id
        scope = {"role": user.role, "patient_id": patient_id, "hospital_id": hospital_id}
    await hub.connect(ws, scope)
    try:
        while True:
            await ws.receive_text()  # client doesn't need to send anything; keeps the socket alive
    except WebSocketDisconnect:
        hub.disconnect(ws)
