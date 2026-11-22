import { useEffect, useState, useCallback } from "react";
import {
  api,
  ApiError,
  CaseDetail,
  ClinicalFact,
  EmergencyType,
  emergencyOrchApi,
  HealthTimelineEvent,
  HealthVaultOverview,
  IncidentReportItem,
  PatientProfile,
  ReportSummary,
  TimelineEntry,
  postEmergencyApi,
  EmergencyHistoryItem,
  DischargeSummary,
  MedicationReconciliationItem,
  FollowUpPlanItem,
} from "../lib/api";
import { useEmergencyEvents } from "../lib/ws";
import { TYPE_LABEL, priorityLabel, timeAgo } from "../lib/format";
import StatusStepper from "../components/StatusStepper";
import EtaCard from "../components/EtaCard";
import SummaryCard from "../components/SummaryCard";
import ChecklistCard from "../components/ChecklistCard";
import Banner from "../components/Banner";

type Tab = "sos" | "vault" | "facts" | "timeline" | "reports" | "continuity" | "profile";
const TYPES: EmergencyType[] = ["stroke", "cardiac", "trauma", "diabetic", "accident", "other"];

export default function PatientHome() {
  const [tab, setTab] = useState<Tab>("vault");
  const [active, setActive] = useState<CaseDetail | null | undefined>(undefined);

  const refresh = useCallback(() => {
    api.get<CaseDetail | null>("/emergency/active")
      .then(setActive)
      .catch(() => setActive(null));
  }, []);

  useEffect(refresh, [refresh]);
  useEmergencyEvents(() => refresh());

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      {active ? (
        <ActiveEmergency c={active} onChange={refresh} />
      ) : (
        <>
          {/* Header navigation bar */}
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-navy-900/10 pb-4">
            <div>
              <h1 className="font-display text-2xl font-bold tracking-tight text-navy-900">
                Patient Intelligence Workspace
              </h1>
              <p className="text-xs text-navy-900/60">
                Move Information Before the Patient, Not After · Pre-Emergency Readiness
              </p>
            </div>
            <button
              onClick={() => setTab("sos")}
              className="btn-danger flex items-center gap-1.5 px-4 py-2 font-semibold shadow-sm"
            >
              <span>🆘</span> Trigger SOS
            </button>
          </div>

          <nav className="mb-6 flex flex-wrap gap-2">
            {[
              { id: "vault", label: "Health Vault" },
              { id: "facts", label: "Clinical Facts" },
              { id: "timeline", label: "Health Timeline" },
              { id: "reports", label: "Medical Reports" },
              { id: "continuity", label: "Care Continuity & Records" },
              { id: "profile", label: "Profile & Consent" },
              { id: "sos", label: "SOS Station" },
            ].map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id as Tab)}
                className={`btn text-xs font-semibold sm:text-sm ${
                  tab === t.id ? "btn-primary" : "btn-secondary"
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>

          {tab === "vault" && <HealthVaultPanel onNavigate={(t) => setTab(t)} />}
          {tab === "facts" && <ClinicalFactsPanel />}
          {tab === "timeline" && <HealthTimelinePanel />}
          {tab === "reports" && <ReportsPanel />}
          {tab === "continuity" && <CareContinuityPanel />}
          {tab === "profile" && <ProfilePanel />}
          {tab === "sos" && <SosPanel onCreated={refresh} />}
        </>
      )}
    </div>
  );
}

// --- Tab 1: Health Vault Overview ---
function HealthVaultPanel({ onNavigate }: { onNavigate: (t: Tab) => void }) {
  const [data, setData] = useState<HealthVaultOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<HealthVaultOverview>("/patient/health-vault")
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load health vault"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="card p-8 text-center text-sm text-navy-900/50">Loading Health Vault…</div>;
  if (error) return <Banner>{error}</Banner>;
  if (!data) return null;

  return (
    <div className="space-y-6">
      {/* Metric Cards Grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="card p-4">
          <p className="text-xs font-medium text-navy-900/60 uppercase tracking-wider">Reports Uploaded</p>
          <p className="mt-1 font-display text-2xl font-bold text-teal-700">{data.total_reports}</p>
          <button onClick={() => onNavigate("reports")} className="mt-2 text-xs font-medium text-teal-600 hover:underline">
            View documents →
          </button>
        </div>
        <div className="card p-4">
          <p className="text-xs font-medium text-navy-900/60 uppercase tracking-wider">Active Conditions</p>
          <p className="mt-1 font-display text-2xl font-bold text-navy-900">{data.conditions_count}</p>
          <button onClick={() => onNavigate("facts")} className="mt-2 text-xs font-medium text-teal-600 hover:underline">
            View conditions →
          </button>
        </div>
        <div className="card p-4">
          <p className="text-xs font-medium text-navy-900/60 uppercase tracking-wider">Known Allergies</p>
          <p className="mt-1 font-display text-2xl font-bold text-coral-600">{data.allergies_count}</p>
          <button onClick={() => onNavigate("facts")} className="mt-2 text-xs font-medium text-teal-600 hover:underline">
            Safety flags →
          </button>
        </div>
        <div className="card p-4">
          <p className="text-xs font-medium text-navy-900/60 uppercase tracking-wider">Active Medications</p>
          <p className="mt-1 font-display text-2xl font-bold text-navy-900">{data.medications_count}</p>
          <button onClick={() => onNavigate("facts")} className="mt-2 text-xs font-medium text-teal-600 hover:underline">
            View prescriptions →
          </button>
        </div>
      </div>

      {/* Verification & Data Provenance Status */}
      <div className="card p-5">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-navy-900/10 pb-3">
          <h2 className="font-display text-base font-semibold text-navy-900">
            Data Provenance & Clinical Verification
          </h2>
          <div className="flex items-center gap-2">
            <span className="pill bg-teal-50 text-teal-700 border border-teal-200">
              Verified: {data.verification_summary["VERIFIED"] || 0}
            </span>
            <span className="pill bg-blue-50 text-blue-700 border border-blue-200">
              Reviewed: {data.verification_summary["REVIEWED"] || 0}
            </span>
            <span className="pill bg-amber-50 text-amber-700 border border-amber-200">
              Unverified: {data.verification_summary["UNVERIFIED"] || 0}
            </span>
          </div>
        </div>
        <p className="mt-3 text-xs text-navy-900/70 leading-relaxed">
          Every clinical fact in your LifeLine AI Vault retains an audit trail linking it to its source
          (patient registration, uploaded OCR medical report, or attending physician validation).
          OCR-extracted data is maintained separately from doctor-verified records to prevent clinical errors.
        </p>
      </div>

      {/* Non-Diagnostic Grounded Factual Summary */}
      <div className="card p-6 bg-gradient-to-br from-white to-navy-50/50">
        <div className="flex items-center justify-between border-b border-navy-900/10 pb-3">
          <div>
            <h3 className="font-display text-base font-semibold text-navy-900">
              Structured Health Intelligence Summary
            </h3>
            <p className="text-xs text-navy-900/50">
              Evidence-cited summary derived from {data.health_summary.total_source_documents} source reports
            </p>
          </div>
          <span className="pill bg-navy-900/5 text-navy-900/60 text-[11px]">Non-Diagnostic Record</span>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <h4 className="text-xs font-semibold text-navy-900/70 uppercase tracking-wide">Recorded Conditions</h4>
            <ul className="mt-1.5 space-y-1">
              {data.health_summary.recorded_conditions.map((c, i) => (
                <li key={i} className="flex items-center gap-2 text-sm text-navy-900">
                  <span className="h-1.5 w-1.5 rounded-full bg-teal-600" />
                  {c}
                </li>
              ))}
              {!data.health_summary.recorded_conditions.length && (
                <li className="text-xs text-navy-900/40">None recorded</li>
              )}
            </ul>
          </div>

          <div>
            <h4 className="text-xs font-semibold text-coral-600 uppercase tracking-wide">Critical Allergies</h4>
            <ul className="mt-1.5 space-y-1">
              {data.health_summary.recorded_allergies.map((a, i) => (
                <li key={i} className="flex items-center gap-2 text-sm text-coral-700 font-medium">
                  <span className="h-1.5 w-1.5 rounded-full bg-coral-600" />
                  {a}
                </li>
              ))}
              {!data.health_summary.recorded_allergies.length && (
                <li className="text-xs text-navy-900/40">No known drug allergies</li>
              )}
            </ul>
          </div>

          <div>
            <h4 className="text-xs font-semibold text-navy-900/70 uppercase tracking-wide">Current Medications</h4>
            <ul className="mt-1.5 space-y-1">
              {data.health_summary.recorded_medications.map((m, i) => (
                <li key={i} className="flex items-center gap-2 text-sm text-navy-900">
                  <span className="h-1.5 w-1.5 rounded-full bg-blue-600" />
                  {m}
                </li>
              ))}
              {!data.health_summary.recorded_medications.length && (
                <li className="text-xs text-navy-900/40">None recorded</li>
              )}
            </ul>
          </div>

          <div>
            <h4 className="text-xs font-semibold text-navy-900/70 uppercase tracking-wide">Surgeries & Procedures</h4>
            <ul className="mt-1.5 space-y-1">
              {data.health_summary.recorded_surgeries.map((s, i) => (
                <li key={i} className="flex items-center gap-2 text-sm text-navy-900">
                  <span className="h-1.5 w-1.5 rounded-full bg-navy-400" />
                  {s}
                </li>
              ))}
              {!data.health_summary.recorded_surgeries.length && (
                <li className="text-xs text-navy-900/40">No prior surgeries recorded</li>
              )}
            </ul>
          </div>
        </div>

        <div className="mt-5 rounded-md bg-navy-900/5 p-3 text-[11px] text-navy-900/70 italic border border-navy-900/10">
          ⚠️ {data.health_summary.disclaimer}
        </div>
      </div>
    </div>
  );
}

// --- Tab 2: Structured Clinical Facts Workspace ---
function ClinicalFactsPanel() {
  const [facts, setFacts] = useState<ClinicalFact[]>([]);
  const [filterType, setFilterType] = useState<string>("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New fact form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [factType, setFactType] = useState<string>("CONDITION");
  const [factValue, setFactValue] = useState("");
  const [factNotes, setFactNotes] = useState("");
  const [saving, setSaving] = useState(false);

  const loadFacts = useCallback(() => {
    setLoading(true);
    const path = filterType === "ALL" ? "/patient/clinical-facts" : `/patient/clinical-facts?fact_type=${filterType}`;
    api.get<ClinicalFact[]>(path)
      .then(setFacts)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load clinical facts"))
      .finally(() => setLoading(false));
  }, [filterType]);

  useEffect(loadFacts, [loadFacts]);

  async function handleAddFact(e: React.FormEvent) {
    e.preventDefault();
    if (!factValue.trim()) return;
    setSaving(true);
    try {
      await api.post("/patient/clinical-facts", {
        fact_type: factType,
        fact_value: factValue.trim(),
        notes: factNotes.trim() || undefined,
      });
      setFactValue("");
      setFactNotes("");
      setShowAddForm(false);
      loadFacts();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to record clinical fact");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivate(id: number) {
    if (!confirm("Are you sure you want to deactivate this medical record item?")) return;
    try {
      await api.delete(`/patient/clinical-facts/${id}`);
      loadFacts();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to deactivate item");
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-lg font-semibold text-navy-900">Structured Clinical Facts</h2>
          <p className="text-xs text-navy-900/60">
            Searchable, categorized clinical data points with cryptographic source provenance.
          </p>
        </div>
        <button onClick={() => setShowAddForm(!showAddForm)} className="btn-primary text-xs">
          {showAddForm ? "Cancel" : "+ Add Personal Medical Fact"}
        </button>
      </div>

      {error && <Banner>{error}</Banner>}

      {/* Add Fact Inline Form */}
      {showAddForm && (
        <form onSubmit={handleAddFact} className="card p-5 border-teal-200 bg-teal-50/20 space-y-3">
          <h3 className="font-display text-sm font-semibold text-navy-900">Record a Health Fact</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="label">Category</label>
              <select className="input" value={factType} onChange={(e) => setFactType(e.target.value)}>
                <option value="CONDITION">Condition / Diagnosis</option>
                <option value="ALLERGY">Allergy</option>
                <option value="MEDICATION">Medication</option>
                <option value="SURGERY">Surgery / Procedure</option>
                <option value="DEVICE">Medical Device / Implant</option>
                <option value="RISK">Special Risk</option>
              </select>
            </div>
            <div>
              <label className="label">Description / Name</label>
              <input
                className="input"
                placeholder="e.g. Hypertension or Metformin 500mg"
                value={factValue}
                onChange={(e) => setFactValue(e.target.value)}
                required
              />
            </div>
          </div>
          <div>
            <label className="label">Notes / Context (optional)</label>
            <input
              className="input"
              placeholder="e.g. Diagnosed in 2021, taking regularly"
              value={factNotes}
              onChange={(e) => setFactNotes(e.target.value)}
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={() => setShowAddForm(false)} className="btn-secondary text-xs">
              Cancel
            </button>
            <button type="submit" disabled={saving || !factValue.trim()} className="btn-primary text-xs">
              {saving ? "Saving…" : "Save Record"}
            </button>
          </div>
        </form>
      )}

      {/* Category Filter Chips */}
      <div className="flex flex-wrap gap-1.5 border-b border-navy-900/10 pb-3">
        {["ALL", "CONDITION", "ALLERGY", "MEDICATION", "SURGERY", "RISK"].map((cat) => (
          <button
            key={cat}
            onClick={() => setFilterType(cat)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              filterType === cat ? "bg-navy-900 text-white" : "bg-white text-navy-900/70 border border-navy-900/10 hover:bg-navy-50"
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {loading && <div className="p-8 text-center text-sm text-navy-900/50">Loading clinical facts…</div>}

      {/* Fact Cards */}
      <div className="grid gap-3 sm:grid-cols-2">
        {facts.map((f) => {
          const prov = f.provenance_records[0];
          return (
            <div key={f.id} className="card p-4 hover:border-navy-900/20 transition-all">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="pill bg-navy-900/5 text-navy-900/60 text-[10px] uppercase font-bold tracking-wider">
                    {f.fact_type}
                  </span>
                  <h4 className="mt-1 font-display text-base font-semibold text-navy-900">{f.fact_value}</h4>
                  {f.clinical_status !== "ACTIVE" && (
                    <span className="pill bg-gray-100 text-gray-600 text-[10px] mt-1">Status: {f.clinical_status}</span>
                  )}
                </div>
                {f.clinical_status === "ACTIVE" && (
                  <button
                    onClick={() => handleDeactivate(f.id)}
                    className="text-[11px] text-navy-900/40 hover:text-coral-600"
                    title="Archive/Deactivate"
                  >
                    Archive
                  </button>
                )}
              </div>

              {/* Provenance Footer */}
              {prov && (
                <div className="mt-3 border-t border-navy-900/5 pt-2 flex flex-wrap items-center justify-between gap-1 text-[11px]">
                  <span className="text-navy-900/50">
                    Source: <span className="font-medium text-navy-900/70">{prov.source_type.replace(/_/g, " ")}</span>
                  </span>
                  <span
                    className={`pill text-[10px] ${
                      prov.verification_status === "VERIFIED"
                        ? "bg-teal-50 text-teal-700 border border-teal-200"
                        : prov.verification_status === "REVIEWED"
                        ? "bg-blue-50 text-blue-700 border border-blue-200"
                        : "bg-amber-50 text-amber-700 border border-amber-200"
                    }`}
                  >
                    {prov.verification_status}
                  </span>
                </div>
              )}
            </div>
          );
        })}
        {!loading && !facts.length && (
          <div className="col-span-full card p-8 text-center text-sm text-navy-900/50">
            No clinical facts recorded in this category.
          </div>
        )}
      </div>
    </div>
  );
}

// --- Tab 3: Longitudinal Health Timeline ---
function HealthTimelinePanel() {
  const [events, setEvents] = useState<HealthTimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<{ events: HealthTimelineEvent[] }>("/patient/health-timeline?limit=50")
      .then((res) => setEvents(res.events))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load timeline"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-display text-lg font-semibold text-navy-900">Longitudinal Health Timeline</h2>
        <p className="text-xs text-navy-900/60">
          Chronological record merging medical document uploads, clinical facts, and emergency events.
        </p>
      </div>

      {error && <Banner>{error}</Banner>}
      {loading && <div className="card p-8 text-center text-sm text-navy-900/50">Loading timeline events…</div>}

      <div className="relative border-l-2 border-navy-900/10 ml-4 pl-6 space-y-6">
        {events.map((ev) => (
          <div key={ev.id} className="relative group">
            {/* Timeline node icon */}
            <div
              className={`absolute -left-[31px] top-1 h-4 w-4 rounded-full border-2 border-white ${
                ev.event_type === "EMERGENCY_VISIT"
                  ? "bg-coral-500 ring-4 ring-coral-100"
                  : ev.event_type === "REPORT_UPLOADED"
                  ? "bg-teal-600 ring-4 ring-teal-100"
                  : "bg-navy-600 ring-4 ring-navy-100"
              }`}
            />

            <div className="card p-4 hover:shadow-md transition-shadow">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span
                    className={`pill text-[10px] font-bold uppercase tracking-wider ${
                      ev.event_type === "EMERGENCY_VISIT"
                        ? "bg-coral-50 text-coral-700 border border-coral-200"
                        : ev.event_type === "REPORT_UPLOADED"
                        ? "bg-teal-50 text-teal-700 border border-teal-200"
                        : "bg-navy-50 text-navy-700 border border-navy-200"
                    }`}
                  >
                    {ev.event_type.replace(/_/g, " ")}
                  </span>
                  <span className="text-xs font-semibold text-navy-900">{ev.event_date || "Undated"}</span>
                </div>
                {ev.verification_status && (
                  <span className="text-[11px] text-navy-900/40">Verified: {ev.verification_status}</span>
                )}
              </div>

              <h4 className="mt-2 font-display text-base font-semibold text-navy-900">{ev.title}</h4>
              <p className="mt-1 text-sm text-navy-900/70">{ev.description}</p>

              {ev.source_reference && (
                <div className="mt-3 text-[11px] text-navy-900/50 flex items-center justify-between border-t border-navy-900/5 pt-2">
                  <span>Source: {ev.source_reference}</span>
                  {ev.provenance_source && (
                    <span className="pill bg-navy-900/5 text-navy-900/60 text-[10px]">
                      {ev.provenance_source}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {!loading && !events.length && (
          <div className="card p-8 text-center text-sm text-navy-900/50">
            No chronological timeline events recorded yet.
          </div>
        )}
      </div>
    </div>
  );
}

// --- Tab 4: Medical Reports Workspace ---
function ReportsPanel() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [title, setTitle] = useState("");
  const [reportType, setReportType] = useState("Discharge Summary");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Detail drawer state
  const [selectedReport, setSelectedReport] = useState<(ReportSummary & { extracted_text?: string }) | null>(null);

  const load = useCallback(() => {
    api.get<ReportSummary[]>("/patient/medical-reports")
      .then(setReports)
      .catch(() => {});
  }, []);

  useEffect(load, [load]);

  async function upload() {
    if (!file || !title) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    form.append("title", title);
    form.append("report_type", reportType);
    try {
      await api.postForm("/report/upload", form);
      setTitle("");
      setFile(null);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function openReportDetail(reportId: number) {
    try {
      const detail = await api.get<ReportSummary & { extracted_text?: string }>(`/patient/medical-reports/${reportId}`);
      setSelectedReport(detail);
    } catch {
      // Fallback
    }
  }

  return (
    <div className="space-y-6">
      {/* Upload Box */}
      <div className="card p-6">
        <h2 className="font-display text-lg font-semibold text-navy-900">Upload a Medical Document</h2>
        <p className="mt-1 text-xs text-navy-900/60">
          Upload hospital discharge summaries, laboratory reports, or prescriptions. Text is securely extracted
          (OCR) to support pre-arrival emergency briefs.
        </p>

        {error && <div className="mt-3"><Banner>{error}</Banner></div>}

        <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_180px_auto]">
          <input
            className="input"
            placeholder="Report title (e.g. Cardiology Consultation - Aug 2025)"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <select className="input" value={reportType} onChange={(e) => setReportType(e.target.value)}>
            <option value="Discharge Summary">Discharge Summary</option>
            <option value="Prescription">Prescription</option>
            <option value="Lab Report">Lab Report</option>
            <option value="Diagnostic Imaging">Diagnostic Imaging</option>
            <option value="Consultation Note">Consultation Note</option>
            <option value="Other">Other</option>
          </select>
          <div className="flex gap-2">
            <input
              className="input text-xs"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.txt"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            <button
              className="btn-primary"
              disabled={busy || !file || !title}
              onClick={upload}
            >
              {busy ? "Uploading…" : "Upload"}
            </button>
          </div>
        </div>
      </div>

      {/* Reports List */}
      <div className="card p-6">
        <h3 className="font-display text-base font-semibold text-navy-900">
          Your Uploaded Documents ({reports.length})
        </h3>
        <ul className="mt-3 divide-y divide-navy-900/10">
          {reports.map((r) => (
            <li key={r.id} className="flex items-center justify-between py-3 text-sm hover:bg-navy-50/50 px-2 rounded-md">
              <div>
                <p className="font-medium text-navy-900">{r.title}</p>
                <p className="text-xs text-navy-900/50">
                  {r.report_type} · {r.report_date || "Date unspecified"} · Uploaded: {r.uploaded_at?.slice(0, 10)}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={`pill text-xs ${
                    r.ocr_status === "ok" ? "bg-teal-500/10 text-teal-700" : "bg-amber-500/10 text-amber-700"
                  }`}
                >
                  OCR: {r.ocr_status}
                </span>
                <button
                  onClick={() => openReportDetail(r.id)}
                  className="btn-secondary text-xs px-2.5 py-1"
                >
                  View Details
                </button>
              </div>
            </li>
          ))}
          {!reports.length && <p className="py-3 text-sm text-navy-900/50">No reports uploaded yet.</p>}
        </ul>
      </div>

      {/* Report Extracted Text Modal */}
      {selectedReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-950/60 p-4">
          <div className="card max-h-[85vh] w-full max-w-2xl overflow-y-auto p-6 space-y-4">
            <div className="flex items-start justify-between border-b border-navy-900/10 pb-3">
              <div>
                <h3 className="font-display text-lg font-bold text-navy-900">{selectedReport.title}</h3>
                <p className="text-xs text-navy-900/60">
                  {selectedReport.report_type} · {selectedReport.report_date || "No date recorded"}
                </p>
              </div>
              <button onClick={() => setSelectedReport(null)} className="btn-secondary text-xs px-2 py-1">
                ✕ Close
              </button>
            </div>

            <div>
              <h4 className="text-xs font-semibold text-navy-900 uppercase tracking-wider mb-2">
                Extracted Clinical Content (OCR)
              </h4>
              <div className="rounded-md bg-navy-900/5 p-4 text-xs font-mono text-navy-900 whitespace-pre-wrap leading-relaxed max-h-96 overflow-y-auto">
                {selectedReport.extracted_text || "No text extracted from this document."}
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button onClick={() => setSelectedReport(null)} className="btn-secondary text-xs">
                Close Viewer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// --- Tab 5: Profile & Consent ---
function ProfilePanel() {
  const [p, setP] = useState<PatientProfile | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get<PatientProfile>("/patient/me").then(setP);
  }, []);

  if (!p) return <p className="text-sm text-navy-900/50">Loading profile…</p>;

  function set<K extends keyof PatientProfile>(k: K, v: PatientProfile[K]) {
    setP((cur) => cur && { ...cur, [k]: v });
  }

  async function save() {
    if (!p) return;
    await api.put(`/patient/${p.id}`, {
      full_name: p.full_name,
      phone: p.phone,
      gender: p.gender,
      blood_group: p.blood_group,
      address: p.address,
      known_conditions: p.known_conditions,
      known_allergies: p.known_allergies,
      current_medications: p.current_medications,
      consent_ai_summary: p.consent_ai_summary,
      emergency_contacts: p.emergency_contacts,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="card space-y-4 p-6">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-lg font-semibold text-navy-900">Medical Profile & Consent</h2>
        <span className="pill bg-navy-900/5 text-navy-900/60">
          Family Code: <span className="ml-1 font-mono font-bold">{p.family_code}</span>
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="label">Full Name</label>
          <input className="input" value={p.full_name} onChange={(e) => set("full_name", e.target.value)} />
        </div>
        <div>
          <label className="label">Phone</label>
          <input className="input" value={p.phone || ""} onChange={(e) => set("phone", e.target.value)} />
        </div>
        <div>
          <label className="label">Blood Group</label>
          <input className="input" value={p.blood_group || ""} onChange={(e) => set("blood_group", e.target.value)} />
        </div>
        <div>
          <label className="label">Address</label>
          <input className="input" value={p.address || ""} onChange={(e) => set("address", e.target.value)} />
        </div>
      </div>

      <div>
        <label className="label">Known Conditions (Self-Reported Baseline)</label>
        <textarea
          className="input"
          rows={2}
          value={p.known_conditions || ""}
          onChange={(e) => set("known_conditions", e.target.value)}
        />
      </div>
      <div>
        <label className="label">Known Allergies</label>
        <textarea
          className="input"
          rows={2}
          value={p.known_allergies || ""}
          onChange={(e) => set("known_allergies", e.target.value)}
        />
      </div>
      <div>
        <label className="label">Current Medications</label>
        <textarea
          className="input"
          rows={2}
          value={p.current_medications || ""}
          onChange={(e) => set("current_medications", e.target.value)}
        />
      </div>

      <div className="rounded-md border border-navy-900/10 p-3 bg-navy-50/50">
        <label className="flex items-center gap-2 text-sm text-navy-900/80 cursor-pointer">
          <input
            type="checkbox"
            checked={p.consent_ai_summary}
            onChange={(e) => set("consent_ai_summary", e.target.checked)}
          />
          <span className="font-medium text-navy-900">
            Authorize Emergency Pre-Arrival AI Summary
          </span>
        </label>
        <p className="mt-1 text-xs text-navy-900/60 pl-6">
          Allows the AI orchestration pipeline to synthesize evidence-cited briefs from uploaded documents
          for attending trauma teams when an SOS is triggered.
        </p>
      </div>

      <div className="flex items-center gap-3 pt-2">
        <button className="btn-primary" onClick={save}>
          Save Profile
        </button>
        {saved && <span className="text-sm font-medium text-teal-700">✓ Profile Updated</span>}
      </div>
    </div>
  );
}

// --- Tab 6: SOS Trigger Panel ---
function SosPanel({ onCreated }: { onCreated: () => void }) {
  const [type, setType] = useState<EmergencyType>("stroke");
  const [symptoms, setSymptoms] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function trigger() {
    setBusy(true);
    setError(null);
    const done = (lat: number, lng: number, accuracy?: number) =>
      emergencyOrchApi
        .triggerSos({
          emergency_type: type,
          symptoms: symptoms.trim() || undefined,
          lat,
          lng,
          origin_type: "PATIENT_APP",
          location_source: "BROWSER_GEOLOCATION",
          location_accuracy_meters: accuracy,
          idempotency_key: crypto.randomUUID(),
        })
        .then(onCreated)
        .catch((e) => setError(e instanceof ApiError ? e.message : "Could not trigger SOS"))
        .finally(() => setBusy(false));

    if (!navigator.geolocation) return done(18.5204, 73.8567, 100); // Pune fallback
    navigator.geolocation.getCurrentPosition(
      (pos) => done(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy),
      () => done(18.5204, 73.8567, 100),
      { timeout: 4000 }
    );
  }

  return (
    <div className="card p-6">
      <h2 className="font-display text-lg font-semibold text-navy-900">Trigger Emergency SOS</h2>
      <p className="mt-1 text-sm text-navy-900/60">
        Captures your live GPS coordinates and instantly alerts nearby hospitals with pre-arrival clinical context.
      </p>

      {error && <div className="mt-3"><Banner>{error}</Banner></div>}

      <div className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-6">
        {TYPES.map((t) => (
          <button
            key={t}
            onClick={() => setType(t)}
            className={`rounded-md border px-3 py-2 text-xs font-medium capitalize ${
              type === t
                ? "border-teal-600 bg-teal-50 text-teal-700 font-bold"
                : "border-navy-900/15 text-navy-900/70 hover:bg-navy-50"
            }`}
          >
            {TYPE_LABEL[t]}
          </button>
        ))}
      </div>

      <textarea
        className="input mt-4"
        rows={3}
        placeholder="Describe what is happening (optional, e.g. severe chest pain or sudden loss of speech)"
        value={symptoms}
        onChange={(e) => setSymptoms(e.target.value)}
      />

      <button onClick={trigger} disabled={busy} className="btn-danger mt-4 w-full py-3 text-base font-bold shadow-md">
        {busy ? "Broadcasting Emergency SOS…" : "🆘  TRIGGER EMERGENCY SOS NOW"}
      </button>
    </div>
  );
}

// --- Active Emergency View ---
function ActiveEmergency({ c, onChange }: { c: CaseDetail; onChange: () => void }) {
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [incidents, setIncidents] = useState<IncidentReportItem[]>([]);
  const [updateText, setUpdateText] = useState("");
  const [submittingUpdate, setSubmittingUpdate] = useState(false);

  const loadData = useCallback(() => {
    api.get<TimelineEntry[]>(`/emergency/${c.id}/timeline`)
      .then(setTimeline)
      .catch(() => {});
    emergencyOrchApi.getIncidents(c.id)
      .then(setIncidents)
      .catch(() => {});
  }, [c.id]);

  useEffect(loadData, [loadData, c.updated_at]);

  async function handleSendUpdate(e: React.FormEvent) {
    e.preventDefault();
    if (!updateText.trim()) return;
    setSubmittingUpdate(true);
    try {
      await emergencyOrchApi.submitIncident(c.id, {
        reported_text: updateText.trim(),
        reporter_type: "PATIENT_WITNESS",
        report_type: "SYMPTOM_UPDATE",
        idempotency_key: crypto.randomUUID(),
      });
      setUpdateText("");
      loadData();
    } catch {
      // ignore
    } finally {
      setSubmittingUpdate(false);
    }
  }

  const prio = priorityLabel(c.priority);

  return (
    <div className="space-y-5">
      <div className="card p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-display text-lg font-semibold text-navy-900">
            {TYPE_LABEL[c.emergency_type]} Emergency Case #{c.id}
          </h2>
          <span className={`pill ${prio.className}`}>{prio.label}</span>
        </div>
        <div className="mt-3">
          <StatusStepper status={c.status} />
        </div>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <EtaCard c={c} />
        <div className="card p-5">
          <h3 className="font-display text-base font-semibold text-navy-900">Hospital Destination</h3>
          {c.hospital ? (
            <div className="mt-2 text-sm text-navy-900/80">
              <span className="pill bg-emerald-100 text-emerald-800 text-[11px] font-bold mb-1">
                ✓ Confirmed Receiving Facility
              </span>
              <p className="font-bold text-navy-900 mt-1">{c.hospital.name}</p>
              <p>{c.hospital.address}</p>
              {c.hospital.phone && <p className="text-xs text-navy-900/50 mt-1">Phone: {c.hospital.phone}</p>}
              {c.doctor && (
                <p className="mt-2">
                  Attending Specialist: <span className="font-medium text-navy-900">{c.doctor.name}</span> ({c.doctor.specialty})
                </p>
              )}
            </div>
          ) : (
            <p className="mt-2 text-sm text-navy-900/50">
              Referral broadcast in progress. Coordinating with nearby facilities for immediate bed & capability reservation…
            </p>
          )}
        </div>
      </div>

      {/* Real-time incident updates panel */}
      <div className="card p-5 space-y-3">
        <h3 className="font-display text-base font-semibold text-navy-900">
          Live Symptom & Status Updates
        </h3>
        <p className="text-xs text-navy-900/60">
          Submit updates on patient condition, changes in consciousness, or ambulance arrival.
        </p>
        <form onSubmit={handleSendUpdate} className="flex gap-2">
          <input
            className="input text-xs"
            placeholder="e.g. Paramedics have arrived / patient is resting"
            value={updateText}
            onChange={(e) => setUpdateText(e.target.value)}
          />
          <button
            type="submit"
            disabled={submittingUpdate || !updateText.trim()}
            className="btn-primary text-xs shrink-0"
          >
            {submittingUpdate ? "Posting…" : "Send Update"}
          </button>
        </form>

        {incidents.length > 0 && (
          <div className="mt-3 space-y-2 max-h-48 overflow-y-auto pt-2 border-t border-navy-900/10">
            {incidents.map((inc) => (
              <div key={inc.id} className="rounded bg-navy-900/[0.03] p-2.5 text-xs">
                <div className="flex justify-between text-[10px] text-navy-900/50 mb-0.5">
                  <span className="font-semibold uppercase">{inc.reporter_type.replace(/_/g, " ")}</span>
                  <span>{timeAgo(inc.received_at)}</span>
                </div>
                <p className="text-navy-900">{inc.reported_text}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <SummaryCard s={c.ai_summary} />
      {!!c.checklist?.length && <ChecklistCard items={c.checklist} />}

      <div className="card p-5">
        <h3 className="font-display text-base font-semibold text-navy-900">Incident Event Log</h3>
        <ul className="mt-3 space-y-2">
          {timeline.map((t, i) => (
            <li key={i} className="flex justify-between gap-4 text-sm">
              <span className="text-navy-900/80">{t.detail}</span>
              <span className="shrink-0 text-navy-900/40">{timeAgo(t.at)}</span>
            </li>
          ))}
        </ul>
      </div>

      <button onClick={onChange} className="btn-secondary w-full">
        Refresh Status
      </button>
    </div>
  );
}

// --- Tab 7: Care Continuity & Records (Prompt 10) ---
function CareContinuityPanel() {
  const [history, setHistory] = useState<EmergencyHistoryItem[]>([]);
  const [summaries, setSummaries] = useState<DischargeSummary[]>([]);
  const [medications, setMedications] = useState<MedicationReconciliationItem[]>([]);
  const [followUps, setFollowUps] = useState<FollowUpPlanItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [schedulingPlanId, setSchedulingPlanId] = useState<number | null>(null);
  const [scheduledDateInput, setScheduledDateInput] = useState("");
  const [updatingPlan, setUpdatingPlan] = useState(false);

  const loadData = useCallback(() => {
    setLoading(true);
    Promise.all([
      postEmergencyApi.getPatientEmergencyHistory().catch(() => []),
      postEmergencyApi.getPatientDischargeSummaries().catch(() => []),
      postEmergencyApi.getPatientMedications().catch(() => []),
      postEmergencyApi.getPatientFollowUps().catch(() => []),
    ]).then(([h, s, m, f]) => {
      setHistory(h);
      setSummaries(s);
      setMedications(m);
      setFollowUps(f);
    }).finally(() => setLoading(false));
  }, []);

  useEffect(loadData, [loadData]);

  async function handleScheduleSubmit(planId: number) {
    if (!scheduledDateInput) return;
    setUpdatingPlan(true);
    try {
      await postEmergencyApi.updateFollowUpStatus(planId, {
        status: "SCHEDULED",
        scheduled_date: scheduledDateInput,
      });
      setSchedulingPlanId(null);
      setScheduledDateInput("");
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to update appointment date");
    } finally {
      setUpdatingPlan(false);
    }
  }

  if (loading) {
    return <div className="card p-8 text-center text-xs text-navy-900/50">Loading post-emergency continuity records...</div>;
  }

  return (
    <div className="space-y-6">
      {/* 1. Emergency Encounters & Outcomes */}
      <div className="card p-6 space-y-4">
        <div>
          <h3 className="font-display text-base font-bold text-navy-900">
            Emergency Care History & Outcomes
          </h3>
          <p className="text-xs text-navy-900/60">
            Chronological log of past emergency episodes, treating hospitals, and documented clinical dispositions.
          </p>
        </div>

        {history.length > 0 ? (
          <div className="space-y-3">
            {history.map((h) => (
              <div key={h.case_id} className="rounded-lg bg-navy-900/[0.02] p-4 border border-navy-900/10 space-y-2 text-xs">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-navy-900 text-sm">
                      {TYPE_LABEL[h.emergency_type] || h.emergency_type}
                    </span>
                    <span className="text-[11px] text-navy-900/50">Emergency #{h.case_id}</span>
                  </div>
                  {h.outcome ? (
                    <span className={`pill text-[10px] font-bold ${
                      h.outcome.disposition === "DISCHARGED"
                        ? "bg-teal-100 text-teal-900"
                        : h.outcome.disposition === "ADMITTED"
                        ? "bg-indigo-100 text-indigo-900"
                        : "bg-amber-100 text-amber-900"
                    }`}>
                      {h.outcome.disposition}
                    </span>
                  ) : (
                    <span className="pill bg-navy-900/10 text-navy-900/70 text-[10px]">Active Emergency</span>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-navy-900/80">
                  <p><span className="font-semibold text-navy-900/60 uppercase text-[10px] block">Treating Hospital</span>{h.hospital_name || "Emergency Department"} {h.hospital_address ? `(${h.hospital_address})` : ""}</p>
                  <p><span className="font-semibold text-navy-900/60 uppercase text-[10px] block">Date & Time</span>{new Date(h.created_at).toLocaleString()}</p>
                </div>

                {h.outcome && (
                  <div className="pt-2 border-t border-navy-900/5">
                    <span className="font-semibold text-navy-900/60 uppercase text-[10px] block">Clinical Disposition Notes</span>
                    <p className="text-navy-900 mt-0.5">{h.outcome.disposition_notes}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-navy-900/50 italic py-2">
            No past emergency episodes recorded for your profile.
          </p>
        )}
      </div>

      {/* 2. Clinically Approved Discharge Summaries */}
      <div className="card p-6 space-y-4">
        <div>
          <h3 className="font-display text-base font-bold text-navy-900">
            Approved Hospital Discharge Summaries
          </h3>
          <p className="text-xs text-navy-900/60">
            Physician-signed evidence summaries synthesizing diagnoses, clinical course, and precautions.
          </p>
        </div>

        {summaries.length > 0 ? (
          <div className="space-y-4">
            {summaries.map((s) => (
              <div key={s.id} className="rounded-lg bg-teal-50/40 p-5 border border-teal-200/70 space-y-3 text-xs">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-teal-200/50 pb-2">
                  <div>
                    <span className="font-bold text-teal-950 text-sm">{s.primary_diagnosis}</span>
                    <p className="text-[11px] text-teal-900/70">
                      Discharged on {s.discharge_date} · Hospital: {s.hospital_name || "Treating Facility"}
                    </p>
                  </div>
                  <span className="pill bg-teal-100 text-teal-900 font-bold text-[10px]">
                    ✓ Clinician Approved (v{s.version})
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-navy-900">
                  <div>
                    <span className="font-bold text-navy-900/60 uppercase text-[10px] block">Discharge Condition</span>
                    <p className="mt-0.5 font-medium">{s.discharge_condition}</p>

                    <span className="font-bold text-navy-900/60 uppercase text-[10px] block pt-2">Clinical Course Summary</span>
                    <p className="mt-0.5 text-navy-900/80 leading-relaxed">{s.clinical_course}</p>
                  </div>

                  <div className="space-y-2">
                    {s.precautions && s.precautions.length > 0 && (
                      <div>
                        <span className="font-bold text-navy-900/60 uppercase text-[10px] block">Precautions & Red Flags</span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {s.precautions.map((p, idx) => (
                            <span key={idx} className="rounded bg-rose-50 px-2 py-0.5 text-[11px] font-medium text-rose-800 border border-rose-200">
                              ⚠️ {p}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {s.follow_up_instructions && (
                      <div>
                        <span className="font-bold text-navy-900/60 uppercase text-[10px] block">Doctor's Follow-up Instructions</span>
                        <p className="mt-0.5 text-navy-900/80">{s.follow_up_instructions}</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Evidence Disclaimer */}
                <div className="rounded bg-white/70 p-2.5 border border-teal-200/50 text-[10px] text-teal-900">
                  <span className="font-bold uppercase tracking-wider text-teal-800">Clinical Governance Notice: </span>
                  {s.non_diagnostic_disclaimer}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-navy-900/50 italic py-2">
            No approved discharge summaries on file.
          </p>
        )}
      </div>

      {/* 3. Reconciled Medications */}
      <div className="card p-6 space-y-4">
        <div>
          <h3 className="font-display text-base font-bold text-navy-900">
            Reconciled Medications
          </h3>
          <p className="text-xs text-navy-900/60">
            Verified medication changes from hospital release. Reconciled medications are promoted to your longitudinal health record.
          </p>
        </div>

        {medications.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-navy-900/10 text-[10px] uppercase font-bold text-navy-900/60">
                  <th className="py-2">Medication</th>
                  <th className="py-2">Dosage</th>
                  <th className="py-2">Frequency</th>
                  <th className="py-2">Action</th>
                  <th className="py-2">Indication</th>
                  <th className="py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-900/5">
                {medications.map((m) => (
                  <tr key={m.id} className="hover:bg-navy-900/[0.01]">
                    <td className="py-2.5 font-semibold text-navy-900">{m.medication_name}</td>
                    <td className="py-2.5 text-navy-900/70">{m.dosage}</td>
                    <td className="py-2.5 text-navy-900/70">{m.frequency}</td>
                    <td className="py-2.5">
                      <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                        m.action === "START"
                          ? "bg-teal-100 text-teal-800"
                          : m.action === "STOP"
                          ? "bg-rose-100 text-rose-800"
                          : m.action === "CHANGE"
                          ? "bg-purple-100 text-purple-800"
                          : "bg-blue-100 text-blue-800"
                      }`}>
                        {m.action}
                      </span>
                    </td>
                    <td className="py-2.5 text-navy-900/60">{m.clinical_indication || "—"}</td>
                    <td className="py-2.5">
                      <span className="text-[10px] font-semibold text-teal-800">
                        ✓ {m.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-navy-900/50 italic py-2">
            No reconciled medications documented yet.
          </p>
        )}
      </div>

      {/* 4. Longitudinal Follow-Up Appointments */}
      <div className="card p-6 space-y-4">
        <div>
          <h3 className="font-display text-base font-bold text-navy-900">
            Scheduled Follow-Up Care Plans
          </h3>
          <p className="text-xs text-navy-900/60">
            Structured follow-up appointments and specialist consultations recommended by your treating physicians.
          </p>
        </div>

        {followUps.length > 0 ? (
          <div className="space-y-3">
            {followUps.map((f) => (
              <div key={f.id} className="rounded-lg bg-navy-900/[0.02] p-4 border border-navy-900/10 flex flex-wrap items-center justify-between gap-3 text-xs">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-navy-900 text-sm">{f.specialty}</span>
                    <span className="pill bg-indigo-50 text-indigo-800 text-[10px]">{f.timeframe}</span>
                    <span className={`pill text-[10px] font-semibold ${
                      f.status === "COMPLETED"
                        ? "bg-teal-100 text-teal-900"
                        : f.status === "SCHEDULED"
                        ? "bg-blue-100 text-blue-900"
                        : "bg-amber-100 text-amber-900"
                    }`}>
                      {f.status}
                    </span>
                  </div>
                  <p className="text-navy-900/80">{f.instructions}</p>
                  {f.provider_name && <p className="text-navy-900/50 text-[11px]">Recommended Clinic/Provider: {f.provider_name}</p>}
                  {f.scheduled_date && (
                    <p className="text-teal-800 font-semibold text-[11px]">
                      🗓 Confirmed Appointment Date: {f.scheduled_date}
                    </p>
                  )}
                </div>

                <div className="shrink-0">
                  {f.status === "PLANNED" && (
                    <div>
                      {schedulingPlanId === f.id ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="date"
                            className="input text-xs"
                            value={scheduledDateInput}
                            onChange={(e) => setScheduledDateInput(e.target.value)}
                          />
                          <button
                            onClick={() => handleScheduleSubmit(f.id)}
                            disabled={updatingPlan || !scheduledDateInput}
                            className="btn-primary text-xs"
                          >
                            Save
                          </button>
                          <button
                            onClick={() => setSchedulingPlanId(null)}
                            className="btn-secondary text-xs"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => {
                            setSchedulingPlanId(f.id);
                            setScheduledDateInput(f.scheduled_date || "");
                          }}
                          className="btn-secondary text-xs"
                        >
                          📅 Set Appointment Date
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-navy-900/50 italic py-2">
            No scheduled follow-up plans at this time.
          </p>
        )}
      </div>
    </div>
  );
}
