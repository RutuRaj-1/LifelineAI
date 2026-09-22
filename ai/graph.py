"""LangGraph orchestration of the six agents (sequential fallback if langgraph is not installed)."""
from __future__ import annotations

from typing import Any, TypedDict

from .agents import (DoctorAgent, EmergencyAgent, HospitalAgent, MedicalAgent, NotificationAgent, Services,
                     SummaryAgent)
from .rag import RagPipeline


class PipelineState(TypedDict, total=False):
    case_id: int
    patient_id: int
    emergency_type: str
    symptoms: str
    lat: float
    lng: float
    priority: int
    hospital: dict
    documents: list
    brief: dict
    specialty: str
    checklist: list
    doctor: dict
    reservation: dict
    error: str


def build_pipeline(svc: Services, rag: RagPipeline, api_key: str = "", model: str = ""):
    emergency, medical, summary = EmergencyAgent(), MedicalAgent(), SummaryAgent(rag, api_key, model)
    doctor, hospital, notify = DoctorAgent(), HospitalAgent(), NotificationAgent()

    async def n_emergency(s): return await emergency.run(s, svc)
    async def n_route(s): return await hospital.route(s, svc)
    async def n_medical(s): return await medical.run(s, svc)
    async def n_summary(s): return await summary.run(s, svc)
    async def n_doctor(s): return await doctor.run(s, svc)
    async def n_reserve(s): return await hospital.reserve(s, svc)
    async def n_notify(s): return await notify.run(s, svc)

    order = [("emergency_agent", n_emergency), ("hospital_route", n_route), ("medical_agent", n_medical),
             ("summary_agent", n_summary), ("doctor_agent", n_doctor), ("hospital_reserve", n_reserve),
             ("notification_agent", n_notify)]
    try:
        from langgraph.graph import END, StateGraph

        g = StateGraph(PipelineState)
        for name, fn in order:
            g.add_node(name, fn)
        g.set_entry_point(order[0][0])
        g.add_conditional_edges("emergency_agent", lambda s: END if s.get("error") else "hospital_route")
        for (a, _), (b, _) in list(zip(order, order[1:]))[1:]:
            g.add_edge(a, b)
        g.add_edge(order[-1][0], END)
        graph = g.compile()

        class LangGraphRunner:
            engine = "langgraph"

            async def run(self, state: dict) -> dict[str, Any]:
                return await graph.ainvoke(state)

        return LangGraphRunner()
    except ImportError:
        class SequentialRunner:
            engine = "sequential"

            async def run(self, state: dict) -> dict[str, Any]:
                for _, fn in order:
                    state = {**state, **(await fn(state))}
                    if state.get("error"):
                        break
                return state

        return SequentialRunner()
