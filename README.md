# LifeLine AI — Patient-Triggered Emergency Pre-Arrival Intelligence

> Move information before the patient, not after. Preparing the hospital before the patient
> arrives — even when there is no ambulance.

A working 60% MVP: patient SOS → AI-assisted, evidence-cited medical brief from uploaded records →
hospital routing → doctor assignment → room reservation → live tracking for the family — all with
**AI that only summarizes, never diagnoses**, and a doctor in the loop for every clinical decision.

## Quick start (Docker, zero API keys required)

```bash
cp .env.example .env
docker compose up --build
docker compose exec backend python database/seed.py   # first run only
```
- App: http://localhost:3000 · API docs: http://localhost:8000/docs

## Quick start (local dev)

```bash
# Backend
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
python ../database/seed.py
uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /api and /ws to :8000
```

## Demo logins
| Role | Email | Password |
|---|---|---|
| Patient | `patient1@lifeline.demo` … `patient10@lifeline.demo` | `Patient@123` |
| Doctor | `doctor1@lifeline.demo` … `doctor8@lifeline.demo` | `Doctor@123` |
| Hospital staff | `hospital1@lifeline.demo` … `hospital3@lifeline.demo` | `Hospital@123` |
| Family (linked to patient1) | `family1@lifeline.demo` | `Family@123` |

**Fastest way to see the full pipeline:** log in as a hospital, click one of the **▶ Demo** buttons
(stroke / cardiac / trauma / diabetic / accident) on the dashboard. Watch the case move through
`CREATED → PATIENT_IDENTIFIED → SUMMARY_GENERATED → DOCTOR_ASSIGNED → ROOM_RESERVED →
PATIENT_ARRIVED` in real time over WebSockets, with an evidence-cited AI brief generated from that
patient's 5 seeded medical reports.

## What's implemented

- **Patient app**: register/login, medical profile (conditions, allergies, meds, emergency
  contacts, AI-summary consent), report upload with OCR, one-tap SOS with GPS capture, live status
  + ETA + AI brief + timeline.
- **Hospital dashboard**: priority-sorted emergency queue, live resource counts, doctor assignment,
  preparation checklist, room reservation, case history.
- **Doctor dashboard**: assigned cases, AI medical summary (with source citations), uploaded
  reports, timeline, preparation checklist.
- **Family portal**: live tracking, status timeline, notifications — deliberately **without**
  symptoms or the AI medical brief (clinical detail is staff-only).
- **AI pipeline**: OCR (Tesseract, with a pypdf/pdf2image fallback chain) → chunking → embeddings
  → FAISS → RAG retrieval → evidence-cited brief (major diseases, current medicines, allergies,
  previous surgeries, critical risks) — see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for how
  it stays non-diagnostic even when nothing in the request explicitly asks it to.
- **6 modular agents** (Emergency, Medical, Summary, Doctor, Hospital, Notification) orchestrated
  with LangGraph.
- **Realtime**: WebSocket dashboard updates + a demo travel simulator that moves the patient marker
  and counts down ETA.
- **Everything works offline**: no OpenAI, Google Maps, Twilio, or Firebase credentials required —
  every external dependency has a deterministic fallback (see Architecture doc).

## Project structure

```
lifeLineAI/
├── frontend/        React + TypeScript + Tailwind (Vite)
├── backend/         FastAPI + SQLAlchemy + JWT auth
│   └── tests/       pytest — auth + full emergency-pipeline end-to-end test
├── ai/              OCR, chunking, embeddings, FAISS, RAG, summarizer, agents, LangGraph
├── database/        seed.py (10 patients / 8 doctors / 3 hospitals / 50 reports / 5 scenarios), schema.sql
├── docker/          Docker notes (see also docker-compose.yml, backend/Dockerfile, frontend/Dockerfile)
├── docs/            API.md, ARCHITECTURE.md
└── .github/workflows/ci.yml
```

## Environment variables

See [`.env.example`](.env.example). Every AI/maps/notification key is optional — the app runs a
full offline demo without any of them; set them to move to real OpenAI summaries, live-traffic ETA,
real push/SMS, and Postgres/Firebase storage in production.

## Tests

```bash
cd backend && pytest -q
```

## Non-negotiable safety rules (see docs/ARCHITECTURE.md for how these are enforced in code)

1. AI never diagnoses disease — it only restates facts found in uploaded records, with a citation
   for every item.
2. Doctors make all final clinical decisions; AI output is decision support only.
3. Family members never see symptoms or the AI medical brief — only status, ETA, and hospital.
