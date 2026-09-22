"""WebSocket hub. Events carry ids only; each client re-fetches over authorised REST. Delivery is scoped per role."""
import json
import logging
from datetime import datetime, timezone

from fastapi import WebSocket

log = logging.getLogger("lifeline.ws")


class Hub:
    def __init__(self):
        self.clients: list[tuple[WebSocket, dict]] = []

    async def connect(self, ws: WebSocket, scope: dict):
        await ws.accept()
        self.clients.append((ws, scope))

    def disconnect(self, ws: WebSocket):
        self.clients = [(w, s) for w, s in self.clients if w is not ws]

    @staticmethod
    def _visible(scope: dict, info: dict) -> bool:
        role = scope["role"]
        if role in ("patient", "family"):
            return scope.get("patient_id") == info["patient_id"]
        if info.get("hospital_id") is None:
            return False
        if role == "hospital":
            return scope.get("hospital_id") == info["hospital_id"]
        if role == "doctor":
            return scope.get("hospital_id") == info["hospital_id"]
        return False

    async def emit(self, event: str, info: dict, **data):
        msg = json.dumps({"type": event, "ts": datetime.now(timezone.utc).isoformat(), **info, "data": data})
        dead = []
        for ws, scope in list(self.clients):
            if not self._visible(scope, info):
                continue
            try:
                await ws.send_text(msg)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


hub = Hub()
