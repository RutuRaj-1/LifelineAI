"""Modular agents. Each agent is a small class with async methods over a shared state dict.
All side effects go through the injected `svc` object so agents stay testable and DB-agnostic."""
from __future__ import annotations

import re
from typing import Any, Protocol

from .rag import RagPipeline
from .summarizer import build_brief

EMERGENCY_TYPES = {"stroke", "cardiac", "trauma", "diabetic", "accident", "other"}
BASE_PRIORITY = {"stroke": 1, "cardiac": 1, "trauma": 1, "accident": 1, "diabetic": 2, "other": 3}
ESCALATE = re.compile(r"unconscious|unresponsive|not breathing|severe bleeding|seizure|slurred|paralys|"
                      r"chest pain|collapsed|drooping", re.I)
SPECIALTY = {"stroke": "Neurology", "cardiac": "Cardiology", "trauma": "Trauma Surgery",
             "accident": "Trauma Surgery", "diabetic": "Endocrinology", "other": "Emergency Medicine"}
RESOURCE_NEEDS = {"stroke": ["ER_BED", "CT_SCANNER"], "cardiac": ["ER_BED", "CATH_LAB"],
                  "trauma": ["ER_BED", "OT"], "accident": ["ER_BED", "OT", "CT_SCANNER"],
                  "diabetic": ["ER_BED", "ICU_BED"], "other": ["ER_BED"]}
PREP = {  # logistics preparation only - never treatment instructions
    "stroke": ["Alert stroke / neurology team", "Hold CT scanner slot", "Ask family for last-known-well time"],
    "cardiac": ["Alert cardiology team", "Prepare ECG station", "Keep cath lab on standby"],
    "trauma": ["Alert trauma team", "Prepare trauma bay", "Notify blood bank"],
    "accident": ["Alert trauma team", "Prepare trauma bay and imaging", "Notify blood bank"],
    "diabetic": ["Alert emergency physician", "Prepare point-of-care glucose testing", "Confirm insulin details with family"],
    "other": ["Alert emergency physician", "Prepare triage bay"],
}


class Services(Protocol):  # implemented by backend/app/services/pipeline_services.py
    async def set_status(self, case_id: int, status: str, detail: str, event: str) -> None: ...
    async def log(self, case_id: int, event: str, detail: str) -> None: ...
    async def route_hospital(self, case_id: int) -> dict: ...
    async def load_reports(self, patient_id: int) -> list[dict]: ...
    async def save_summary(self, case_id: int, brief: dict) -> None: ...
    async def assign_doctor(self, case_id: int, specialty: str, checklist: list[dict]) -> dict | None: ...
    async def reserve(self, case_id: int, needs: list[str]) -> dict: ...
    async def notify_all(self, case_id: int, event: str, message: str) -> None: ...


class EmergencyAgent:
    """Validate the SOS and determine priority (rule-based triage of the patient-reported type)."""

    async def run(self, s: dict, svc: Services) -> dict:
        etype = s["emergency_type"]
        if etype not in EMERGENCY_TYPES or not (-90 <= s["lat"] <= 90 and -180 <= s["lng"] <= 180):
            await svc.log(s["case_id"], "SOS_REJECTED", "Invalid emergency type or GPS coordinates")
            return {"error": "invalid_sos"}
        prio = BASE_PRIORITY[etype]
        if ESCALATE.search(s.get("symptoms") or ""):
            prio = 1
        await svc.set_status(s["case_id"], "PATIENT_IDENTIFIED",
                             f"SOS validated. Priority P{prio} (rule-based, not a diagnosis)", "PatientIdentified")
        return {"priority": prio}


class MedicalAgent:
    """Retrieve the patient's uploaded records (already OCR'd at upload time)."""

    async def run(self, s: dict, svc: Services) -> dict:
        docs = await svc.load_reports(s["patient_id"])
        await svc.log(s["case_id"], "RECORDS_RETRIEVED", f"{len(docs)} uploaded report(s) retrieved")
        return {"documents": docs}


class SummaryAgent:
    """RAG over the records -> evidence-backed emergency brief."""

    def __init__(self, rag: RagPipeline, api_key: str = "", model: str = ""):
        self.rag, self.api_key, self.model = rag, api_key, model

    async def run(self, s: dict, svc: Services) -> dict:
        import asyncio

        reported = {"emergency_type": s["emergency_type"], "symptoms": s.get("symptoms") or ""}
        brief = await asyncio.to_thread(build_brief, s["documents"], self.rag, reported,
                                        api_key=self.api_key, model=self.model)
        await svc.save_summary(s["case_id"], brief)
        await svc.set_status(s["case_id"], "SUMMARY_GENERATED",
                             f"Emergency brief generated ({brief['generated_by']})", "SummaryGenerated")
        return {"brief": brief}


class DoctorAgent:
    """Recommend a specialty, build a preparation checklist, assign an available doctor."""

    @staticmethod
    def recommend(etype: str, brief: dict | None) -> dict:
        checklist = list(PREP[etype])
        for a in (brief or {}).get("allergies", [])[:3]:
            checklist.append(f"Flag allergy on chart: {a['text']}")
        for r in (brief or {}).get("critical_risks", [])[:3]:
            checklist.append(f"Review record flag: {r['text']}")
        return {"specialty": SPECIALTY[etype], "checklist": [{"item": c, "done": False} for c in checklist]}

    async def run(self, s: dict, svc: Services) -> dict:
        rec = self.recommend(s["emergency_type"], s.get("brief"))
        doctor = await svc.assign_doctor(s["case_id"], rec["specialty"], rec["checklist"])
        return {"specialty": rec["specialty"], "checklist": rec["checklist"], "doctor": doctor}


class HospitalAgent:
    """Route to a suitable hospital, then reserve (simulated) resources."""

    async def route(self, s: dict, svc: Services) -> dict:
        h = await svc.route_hospital(s["case_id"])
        return {"hospital": h}

    async def reserve(self, s: dict, svc: Services) -> dict:
        res = await svc.reserve(s["case_id"], RESOURCE_NEEDS[s["emergency_type"]])
        return {"reservation": res}


class NotificationAgent:
    """Fan out notifications (dashboards, push, SMS mock) and finish the pipeline."""

    async def run(self, s: dict, svc: Services) -> dict:
        h = (s.get("hospital") or {}).get("name", "the hospital")
        await svc.notify_all(s["case_id"], "PipelineComplete",
                             f"{h} is prepared: team alerted, room reserved. Follow live ETA in the app.")
        return {}
