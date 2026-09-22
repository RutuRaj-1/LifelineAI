# LifeLine AI — API Reference

Base URL: `/api` (interactive Swagger UI at `/docs`, ReDoc at `/redoc` when the backend is running).
Auth: `Authorization: Bearer <token>` (JWT from `/auth/login` or `/auth/register`).

## Authentication
| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/auth/register` | — | `role`: `patient` or `family` (family requires the patient's `family_code`) |
| POST | `/auth/login` | — | Returns `{ access_token, user }` |
| GET | `/auth/me` | any | Current user + role-specific ids |

## Patient & Reports
| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/patient/me` | patient | Own profile |
| GET | `/patient/{id}` | consent-checked | Family/hospital/doctor only with an active case or link |
| PUT | `/patient/{id}` | patient (self) | Update medical profile, contacts, AI-consent |
| POST | `/report/upload` | patient | multipart: `file`, `title`, `report_type`, `report_date?`. Runs OCR immediately. |
| GET | `/report/patient/{id}` | consent-checked, not family | List reports |
| GET | `/report/{id}` | consent-checked | Metadata + extracted text |
| GET | `/report/{id}/file` | consent-checked | Original file (redirects to a signed URL if stored on Firebase) |

## Emergency
| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/emergency` | patient | Triggers SOS → starts the async agent pipeline |
| GET | `/emergency/active` | patient, family | Current active case, or `null` |
| GET | `/emergency/{id}` | consent-checked | Full case (family view omits symptoms/AI summary) |
| GET | `/emergency/{id}/timeline` | consent-checked | Ordered activity log |
| PUT | `/emergency/{id}/location` | patient | Manual GPS ping |
| POST | `/emergency/{id}/checklist` | doctor, hospital | `{ index, done }` |
| POST | `/emergency/{id}/complete` | doctor, hospital | Closes the case, releases resources |

## Doctor
| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/doctors` | hospital, doctor | `?hospital_id=&specialty=` |
| POST | `/doctor/assign` | hospital | `{ case_id, doctor_id }` |
| GET | `/doctor/cases` | doctor | Own assigned cases |

## Hospital
| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/hospital/resources` | hospital, doctor | Bed/OT/scanner counts |
| POST | `/hospital/reserve` | hospital | `{ case_id, resource_type }` |
| GET | `/hospital/queue` | hospital | Active cases, priority-sorted |
| GET | `/hospital/cases/history` | hospital | Last 50 completed cases |

## AI
| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/ai/summary` | consent-checked, not family | `{ patient_id, reported? }` → evidence-backed brief |
| POST | `/ai/recommend` | consent-checked | `{ case_id }` or `{ emergency_type }` → specialty + checklist |

## Notifications
| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/notifications` | any | `?unread_only=true` |
| POST | `/notifications/{id}/read` | any | Mark read |

## Demo
| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/demo/scenarios` | hospital | The 5 seeded scenarios |
| POST | `/demo/scenarios/{key}/trigger` | hospital | Fires an SOS for the matching seeded patient |

## WebSocket
`GET /ws?token=<jwt>` — role-scoped live events: `PatientIdentified`, `HospitalAlerted`, `SummaryGenerated`,
`DoctorAssigned`, `RoomReserved`, `EtaUpdated`, `PatientArrived`, `NotificationsSent`, `ResourceUpdated`.
Each frame carries ids only (`case_id`, `patient_id`, `hospital_id`, `status`); clients re-fetch the relevant
REST endpoint, which re-applies permission checks server-side.

## Emergency status flow
```
CREATED → PATIENT_IDENTIFIED → SUMMARY_GENERATED → DOCTOR_ASSIGNED → ROOM_RESERVED → PATIENT_ARRIVED → COMPLETED
```
