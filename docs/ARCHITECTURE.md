# LifeLine AI — Architecture

## Why patient-triggered

Most emergency systems assume an ambulance is the starting point. In practice most patients reach
hospitals by private car, auto, or bystander — with no pre-arrival intelligence at all. LifeLine AI
starts the moment a patient (or a bystander using their phone) presses SOS, regardless of how they
get to the hospital.

## Request flow

```
Patient App ──SOS──▶ FastAPI /emergency ──creates case──▶ background pipeline (LangGraph)
                                                              │
                     ┌────────────────────────────────────────┤
                     ▼                                        ▼
            EmergencyAgent (validate + triage)     HospitalAgent.route (nearest capable, ER free)
                     │                                        │
                     ▼                                        ▼
            MedicalAgent (load consented reports)     WebSocket: HospitalAlerted
                     │
                     ▼
     SummaryAgent → ai/rag.py → ai/summarizer.py (OCR text → chunks → embeddings → FAISS →
     top-k → evidence-cited brief; OpenAI if configured, else deterministic extractive RAG)
                     │
                     ▼
     DoctorAgent (specialty + checklist) → HospitalAgent.reserve (atomic resource decrement)
                     │
                     ▼
     NotificationAgent → dashboards (WebSocket) + mock push/SMS
```

Every step writes to `activity_logs` and emits a WebSocket event scoped to the patient, their linked
family, and the routed hospital's staff (`backend/app/events.py`). The frontend never trusts the
WebSocket payload for data — it only uses it as a "something changed, re-fetch" signal, so every
permission check still happens server-side on the REST call that follows.

## Safety boundaries (enforced in code, not just prompted)

- `ai/summarizer.py` only restates facts already present in a source chunk. Every bullet in the
  brief carries `evidence: [{report_id, snippet}]`; items without evidence are dropped before they
  reach the API. A regex denylist (`DIAGNOSIS_LANGUAGE`) strips any inferential wording ("likely",
  "suspected", "rule out"...) from LLM output, and a lexical grounding check rejects any LLM claim
  whose key words don't appear in the cited source.
- Doctor/hospital assignment is a rules-based recommendation (`ai/agents.py: DoctorAgent`); a human
  (hospital staff) makes the actual assignment via `POST /doctor/assign`.
- `MedicalAgent` only loads reports if `Patient.consent_ai_summary` is true.
- `can_access_patient()` (`backend/app/security.py`) is the single source of truth for who can see a
  patient's data: the patient, their linked family (status/ETA only, no clinical detail), or clinical
  staff with an **active, non-completed** case for that patient at their own hospital.

## Failure-tolerant by design

Every external dependency degrades gracefully instead of crashing the emergency pipeline:
- No `OPENAI_API_KEY` → `ai/embeddings.py` uses a deterministic hashing embedder and
  `ai/summarizer.py` uses extractive regex/heading-based extraction instead of an LLM call.
- No `faiss-cpu` wheel available → `ai/vectorstore.py` falls back to a pure-numpy cosine search.
- No `GOOGLE_MAPS_API_KEY` → `services/maps.py` estimates ETA from haversine distance at 25 km/h.
- No Redis → `app/cache.py` falls back to an in-process dict.
- No `langgraph` → `ai/graph.py` falls back to a plain sequential runner with the same node functions.

This is what lets `docker compose up` produce a fully working demo with zero API keys.
