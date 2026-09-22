const BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function token(): string | null {
  return localStorage.getItem("ll_token");
}

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string>) };
  const t = token();
  if (t) headers["Authorization"] = `Bearer ${t}`;
  const isForm = opts.body instanceof FormData;
  if (!isForm && opts.body) headers["Content-Type"] = "application/json";
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(res.status, (data && (data.detail || data.message)) || `Request failed (${res.status})`);
  }
  return data as T;
}

export const api = {
  get: <T,>(path: string) => req<T>(path),
  post: <T,>(path: string, body?: unknown) => req<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T,>(path: string, body?: unknown) => req<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  postForm: <T,>(path: string, form: FormData) => req<T>(path, { method: "POST", body: form }),
  setToken: (t: string | null) => (t ? localStorage.setItem("ll_token", t) : localStorage.removeItem("ll_token")),
  getToken: token,
};

export type Role = "patient" | "doctor" | "hospital" | "family";
export type EmergencyType = "stroke" | "cardiac" | "trauma" | "diabetic" | "accident" | "other";
export type CaseStatus = "CREATED" | "PATIENT_IDENTIFIED" | "SUMMARY_GENERATED" | "DOCTOR_ASSIGNED" |
  "ROOM_RESERVED" | "PATIENT_ARRIVED" | "COMPLETED";

export interface Me { id: number; email: string; full_name: string; role: Role; patient_id: number | null; doctor_id: number | null; hospital_id: number | null; }

export interface BriefItem { text: string; evidence: { report_id: number; title: string; date?: string; snippet: string; score?: number }[]; }
export interface AiSummary {
  major_diseases: BriefItem[]; current_medicines: BriefItem[]; allergies: BriefItem[];
  previous_surgeries: BriefItem[]; critical_risks: BriefItem[];
  reported_by_patient: { emergency_type: string; symptoms: string };
  sources: { report_id: number; title: string; date?: string }[];
  insufficient_records: boolean; generated_by: string; embedder: string; disclaimer: string;
}
export interface ChecklistItem { item: string; done: boolean; }
export interface CaseDetail {
  id: number; status: CaseStatus; priority: number; emergency_type: EmergencyType;
  lat: number; lng: number; current_lat: number | null; current_lng: number | null;
  eta_minutes: number | null; initial_eta_minutes: number | null; specialty: string | null;
  reserved_resources: string[]; created_at: string; updated_at: string;
  patient: { id: number; full_name: string; age?: number; gender?: string; blood_group?: string; phone?: string; emergency_contacts?: { name: string; phone: string; relation?: string }[] };
  hospital: { id: number; name: string; address: string; lat: number; lng: number; phone?: string } | null;
  doctor: { id: number; name: string; specialty: string } | null;
  summary_ready: boolean; symptoms?: string; checklist?: ChecklistItem[]; ai_summary?: AiSummary | null;
}
export interface TimelineEntry { event: string; detail: string; actor: string; at: string; }
export interface PatientProfile {
  id: number; full_name: string; email: string; phone?: string; dob?: string; age?: number; gender?: string;
  blood_group?: string; address?: string; known_conditions?: string; known_allergies?: string;
  current_medications?: string; consent_ai_summary: boolean;
  emergency_contacts: { name: string; phone: string; relation?: string }[]; family_code: string;
}
export interface ReportSummary { id: number; patient_id: number; title: string; report_type: string; report_date?: string; ocr_status: string; original_filename?: string; uploaded_at: string; }
export interface DoctorSummary { id: number; name: string; specialty: string; qualification?: string; hospital_id: number; is_available: boolean; }
export interface NotificationItem { id: number; case_id: number | null; title: string; message: string; channel: string; is_read: boolean; created_at: string; }
