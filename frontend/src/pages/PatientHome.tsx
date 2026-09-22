import { useEffect, useState, useCallback } from "react";
import { api, ApiError, CaseDetail, EmergencyType, PatientProfile, ReportSummary, TimelineEntry } from "../lib/api";
import { useEmergencyEvents } from "../lib/ws";
import { TYPE_LABEL, priorityLabel, timeAgo } from "../lib/format";
import StatusStepper from "../components/StatusStepper";
import EtaCard from "../components/EtaCard";
import SummaryCard from "../components/SummaryCard";
import ChecklistCard from "../components/ChecklistCard";
import Banner from "../components/Banner";

type Tab = "sos" | "profile" | "reports";
const TYPES: EmergencyType[] = ["stroke", "cardiac", "trauma", "diabetic", "accident", "other"];

export default function PatientHome() {
  const [tab, setTab] = useState<Tab>("sos");
  const [active, setActive] = useState<CaseDetail | null | undefined>(undefined);

  const refresh = useCallback(() => {
    api.get<CaseDetail | null>("/emergency/active").then(setActive).catch(() => setActive(null));
  }, []);
  useEffect(refresh, [refresh]);
  useEmergencyEvents(() => refresh());

  return (
    <div className="mx-auto max-w-4xl px-5 py-8">
      {active ? (
        <ActiveEmergency c={active} onChange={refresh} />
      ) : (
        <>
          <nav className="mb-6 flex gap-2">
            {(["sos", "profile", "reports"] as Tab[]).map((t) => (
              <button key={t} onClick={() => setTab(t)}
                className={`btn ${tab === t ? "btn-primary" : "btn-secondary"} capitalize`}>{t}</button>
            ))}
          </nav>
          {tab === "sos" && <SosPanel onCreated={refresh} />}
          {tab === "profile" && <ProfilePanel />}
          {tab === "reports" && <ReportsPanel />}
        </>
      )}
    </div>
  );
}

function SosPanel({ onCreated }: { onCreated: () => void }) {
  const [type, setType] = useState<EmergencyType>("stroke");
  const [symptoms, setSymptoms] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function trigger() {
    setBusy(true);
    setError(null);
    const done = (lat: number, lng: number) =>
      api.post("/emergency", { lat, lng, emergency_type: type, symptoms: symptoms || undefined })
        .then(onCreated).catch((e) => setError(e instanceof ApiError ? e.message : "Could not create SOS")).finally(() => setBusy(false));
    if (!navigator.geolocation) return done(18.5204, 73.8567); // Pune fallback
    navigator.geolocation.getCurrentPosition((pos) => done(pos.coords.latitude, pos.coords.longitude),
      () => done(18.5204, 73.8567), { timeout: 4000 });
  }

  return (
    <div className="card p-6">
      <h2 className="font-display text-lg font-semibold text-navy-900">Emergency SOS</h2>
      <p className="mt-1 text-sm text-navy-900/60">Your GPS location is captured automatically. Choose what best matches what's happening.</p>
      {error && <div className="mt-3"><Banner>{error}</Banner></div>}
      <div className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-6">
        {TYPES.map((t) => (
          <button key={t} onClick={() => setType(t)}
            className={`rounded-md border px-3 py-2 text-xs font-medium capitalize ${type === t ? "border-teal-600 bg-teal-50 text-teal-700" : "border-navy-900/15 text-navy-900/70 hover:bg-navy-50"}`}>
            {TYPE_LABEL[t]}
          </button>
        ))}
      </div>
      <textarea className="input mt-4" rows={3} placeholder="Describe symptoms (optional)"
        value={symptoms} onChange={(e) => setSymptoms(e.target.value)} />
      <button onClick={trigger} disabled={busy} className="btn-danger mt-4 w-full text-base py-3">
        {busy ? "Sending SOS…" : "🆘  Trigger Emergency SOS"}
      </button>
    </div>
  );
}

function ActiveEmergency({ c, onChange }: { c: CaseDetail; onChange: () => void }) {
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  useEffect(() => { api.get<TimelineEntry[]>(`/emergency/${c.id}/timeline`).then(setTimeline).catch(() => {}); }, [c.id, c.updated_at]);
  const prio = priorityLabel(c.priority);

  return (
    <div className="space-y-5">
      <div className="card p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-display text-lg font-semibold text-navy-900">{TYPE_LABEL[c.emergency_type]} emergency</h2>
          <span className={`pill ${prio.className}`}>{prio.label}</span>
        </div>
        <div className="mt-3"><StatusStepper status={c.status} /></div>
      </div>
      <div className="grid gap-5 sm:grid-cols-2">
        <EtaCard c={c} />
        <div className="card p-5">
          <h3 className="font-display text-base font-semibold text-navy-900">Hospital</h3>
          {c.hospital ? (
            <div className="mt-2 text-sm text-navy-900/80">
              <p className="font-medium text-navy-900">{c.hospital.name}</p>
              <p>{c.hospital.address}</p>
              {c.doctor && <p className="mt-2">Doctor: <span className="font-medium">{c.doctor.name}</span> ({c.doctor.specialty})</p>}
            </div>
          ) : <p className="mt-2 text-sm text-navy-900/50">Finding the nearest capable hospital…</p>}
        </div>
      </div>
      <SummaryCard s={c.ai_summary} />
      {!!c.checklist?.length && <ChecklistCard items={c.checklist} />}
      <div className="card p-5">
        <h3 className="font-display text-base font-semibold text-navy-900">Timeline</h3>
        <ul className="mt-3 space-y-2">
          {timeline.map((t, i) => (
            <li key={i} className="flex justify-between gap-4 text-sm">
              <span className="text-navy-900/80">{t.detail}</span>
              <span className="shrink-0 text-navy-900/40">{timeAgo(t.at)}</span>
            </li>
          ))}
        </ul>
      </div>
      <button onClick={onChange} className="btn-secondary w-full">Refresh</button>
    </div>
  );
}

function ProfilePanel() {
  const [p, setP] = useState<PatientProfile | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => { api.get<PatientProfile>("/patient/me").then(setP); }, []);
  if (!p) return <p className="text-sm text-navy-900/50">Loading…</p>;

  function set<K extends keyof PatientProfile>(k: K, v: PatientProfile[K]) { setP((cur) => cur && { ...cur, [k]: v }); }

  async function save() {
    if (!p) return;
    await api.put(`/patient/${p.id}`, {
      full_name: p.full_name, phone: p.phone, gender: p.gender, blood_group: p.blood_group, address: p.address,
      known_conditions: p.known_conditions, known_allergies: p.known_allergies, current_medications: p.current_medications,
      consent_ai_summary: p.consent_ai_summary, emergency_contacts: p.emergency_contacts,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="card space-y-4 p-6">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-lg font-semibold text-navy-900">Medical profile</h2>
        <span className="pill bg-navy-900/5 text-navy-900/60">Family code: <span className="ml-1 font-mono">{p.family_code}</span></span>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div><label className="label">Full name</label><input className="input" value={p.full_name} onChange={(e) => set("full_name", e.target.value)} /></div>
        <div><label className="label">Phone</label><input className="input" value={p.phone || ""} onChange={(e) => set("phone", e.target.value)} /></div>
        <div><label className="label">Blood group</label><input className="input" value={p.blood_group || ""} onChange={(e) => set("blood_group", e.target.value)} /></div>
        <div><label className="label">Address</label><input className="input" value={p.address || ""} onChange={(e) => set("address", e.target.value)} /></div>
      </div>
      <div><label className="label">Known conditions (self-reported)</label><textarea className="input" rows={2} value={p.known_conditions || ""} onChange={(e) => set("known_conditions", e.target.value)} /></div>
      <div><label className="label">Known allergies</label><textarea className="input" rows={2} value={p.known_allergies || ""} onChange={(e) => set("known_allergies", e.target.value)} /></div>
      <div><label className="label">Current medications</label><textarea className="input" rows={2} value={p.current_medications || ""} onChange={(e) => set("current_medications", e.target.value)} /></div>
      <label className="flex items-center gap-2 text-sm text-navy-900/80">
        <input type="checkbox" checked={p.consent_ai_summary} onChange={(e) => set("consent_ai_summary", e.target.checked)} />
        Allow AI to summarize my uploaded reports during an emergency
      </label>
      <div className="flex items-center gap-3">
        <button className="btn-primary" onClick={save}>Save changes</button>
        {saved && <span className="text-sm text-teal-700">Saved</span>}
      </div>
    </div>
  );
}

function ReportsPanel() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => { api.get<{ id: number }>("/patient/me").then((p) => api.get<ReportSummary[]>(`/report/patient/${p.id}`).then(setReports)); }, []);
  useEffect(load, [load]);

  async function upload() {
    if (!file || !title) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    form.append("title", title);
    form.append("report_type", "other");
    try {
      await api.postForm("/report/upload", form);
      setTitle(""); setFile(null); load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed");
    } finally { setBusy(false); }
  }

  return (
    <div className="space-y-5">
      <div className="card p-6">
        <h2 className="font-display text-lg font-semibold text-navy-900">Upload a medical report</h2>
        {error && <div className="mt-3"><Banner>{error}</Banner></div>}
        <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_auto_auto]">
          <input className="input" placeholder="Title (e.g. Discharge summary - Aug 2025)" value={title} onChange={(e) => setTitle(e.target.value)} />
          <input className="input" type="file" accept=".pdf,.png,.jpg,.jpeg,.txt" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          <button className="btn-primary" disabled={busy || !file || !title} onClick={upload}>{busy ? "Uploading…" : "Upload"}</button>
        </div>
        <p className="mt-2 text-xs text-navy-900/50">PDF, image or text, up to 10 MB. Text is extracted automatically (OCR) for the AI emergency brief.</p>
      </div>
      <div className="card p-6">
        <h3 className="font-display text-base font-semibold text-navy-900">Your reports ({reports.length})</h3>
        <ul className="mt-3 divide-y divide-navy-900/10">
          {reports.map((r) => (
            <li key={r.id} className="flex items-center justify-between py-2 text-sm">
              <div>
                <p className="font-medium text-navy-900">{r.title}</p>
                <p className="text-navy-900/50">{r.report_type} · {r.report_date || "no date"}</p>
              </div>
              <span className={`pill ${r.ocr_status === "ok" ? "bg-teal-500/10 text-teal-700" : "bg-amber-500/10 text-amber-700"}`}>{r.ocr_status}</span>
            </li>
          ))}
          {!reports.length && <p className="py-3 text-sm text-navy-900/50">No reports uploaded yet.</p>}
        </ul>
      </div>
    </div>
  );
}
