import { useCallback, useEffect, useState } from "react";
import {
  api,
  ApiError,
  CaseDetail,
  EmergencyType,
  emergencyOrchApi,
  IncidentReportItem,
  TimelineEntry,
  postEmergencyApi,
  EmergencyOutcome,
} from "../lib/api";
import { useEmergencyEvents } from "../lib/ws";
import { TYPE_LABEL, timeAgo } from "../lib/format";
import StatusStepper from "../components/StatusStepper";
import EtaCard from "../components/EtaCard";
import Banner from "../components/Banner";

const TYPES: EmergencyType[] = ["stroke", "cardiac", "trauma", "diabetic", "accident", "other"];

export default function FamilyPortal() {
  const [active, setActive] = useState<CaseDetail | null | undefined>(undefined);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [incidents, setIncidents] = useState<IncidentReportItem[]>([]);
  const [familyOutcome, setFamilyOutcome] = useState<EmergencyOutcome | null>(null);
  const [loading, setLoading] = useState(true);

  // Family-assisted SOS form
  const [emergencyType, setEmergencyType] = useState<EmergencyType>("stroke");
  const [symptoms, setSymptoms] = useState("");
  const [triggeringSos, setTriggeringSos] = useState(false);
  const [sosError, setSosError] = useState<string | null>(null);

  // Incident update form
  const [familyNote, setFamilyNote] = useState("");
  const [submittingNote, setSubmittingNote] = useState(false);

  const refresh = useCallback(() => {
    api.get<CaseDetail | null>("/emergency/active")
      .then(setActive)
      .catch(() => setActive(null))
      .finally(() => setLoading(false));
  }, []);

  useEffect(refresh, [refresh]);
  useEmergencyEvents(() => refresh());

  useEffect(() => {
    if (!active) {
      setFamilyOutcome(null);
      return;
    }
    api.get<TimelineEntry[]>(`/emergency/${active.id}/timeline`)
      .then(setTimeline)
      .catch(() => {});
    emergencyOrchApi.getIncidents(active.id)
      .then(setIncidents)
      .catch(() => {});
    postEmergencyApi.getOutcome(active.id)
      .then(setFamilyOutcome)
      .catch(() => setFamilyOutcome(null));
  }, [active?.id, active?.updated_at]);

  function handleTriggerFamilySos() {
    setTriggeringSos(true);
    setSosError(null);
    const done = (lat: number, lng: number, accuracy?: number) => {
      emergencyOrchApi
        .triggerSos({
          emergency_type: emergencyType,
          symptoms: symptoms.trim() || undefined,
          lat,
          lng,
          origin_type: "FAMILY_DELEGATE",
          location_source: "FAMILY_DEVICE_GEOLOCATION",
          location_accuracy_meters: accuracy,
          idempotency_key: crypto.randomUUID(),
        })
        .then(() => {
          setSymptoms("");
          refresh();
        })
        .catch((e) => setSosError(e instanceof ApiError ? e.message : "Failed to initiate emergency SOS"))
        .finally(() => setTriggeringSos(false));
    };

    if (!navigator.geolocation) return done(18.5204, 73.8567, 100);
    navigator.geolocation.getCurrentPosition(
      (pos) => done(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy),
      () => done(18.5204, 73.8567, 100),
      { timeout: 4000 }
    );
  }

  async function handleSendFamilyUpdate(e: React.FormEvent) {
    e.preventDefault();
    if (!active || !familyNote.trim()) return;
    setSubmittingNote(true);
    try {
      await emergencyOrchApi.submitIncident(active.id, {
        reported_text: familyNote.trim(),
        reporter_type: "FAMILY_WITNESS",
        report_type: "FAMILY_OBSERVATION",
        idempotency_key: crypto.randomUUID(),
      });
      setFamilyNote("");
      emergencyOrchApi.getIncidents(active.id).then(setIncidents).catch(() => {});
    } catch {
      // ignore
    } finally {
      setSubmittingNote(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl px-5 py-16 text-center text-navy-900/50 text-sm">
        Connecting to family coordination network…
      </div>
    );
  }

  // --- No Active Emergency: Family Home & Assisted SOS Station ---
  if (!active) {
    return (
      <div className="mx-auto max-w-3xl px-5 py-10 space-y-6">
        <div className="card p-6 text-center">
          <p className="text-4xl" aria-hidden>
            🛡️
          </p>
          <h1 className="mt-3 font-display text-2xl font-bold text-navy-900">
            Family Emergency Coordination Portal
          </h1>
          <p className="mt-2 text-sm text-navy-900/60 max-w-lg mx-auto">
            You are securely linked to your family member's LifeLine AI account. When an emergency is active, you can monitor transit, hospital routing, and arrival in real time.
          </p>
        </div>

        {/* Family-Assisted SOS Trigger Box */}
        <div className="card p-6 border-coral-200 bg-coral-50/20 space-y-4">
          <div className="flex items-center gap-2">
            <span className="text-xl">🆘</span>
            <div>
              <h2 className="font-display text-lg font-bold text-navy-900">
                Trigger Emergency on Behalf of Relative
              </h2>
              <p className="text-xs text-navy-900/60">
                If your relative is incapacitated or unable to reach their device, you can trigger an immediate emergency alert here.
              </p>
            </div>
          </div>

          {sosError && <Banner>{sosError}</Banner>}

          <div>
            <label className="text-xs font-semibold text-navy-900/70 block mb-1">
              Select Suspected Medical Emergency
            </label>
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
              {TYPES.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setEmergencyType(t)}
                  className={`rounded-md border px-3 py-2 text-xs font-semibold capitalize transition ${
                    emergencyType === t
                      ? "border-coral-600 bg-coral-50 text-coral-700 font-bold"
                      : "border-navy-900/15 bg-white text-navy-900/70 hover:bg-navy-50"
                  }`}
                >
                  {TYPE_LABEL[t]}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-navy-900/70 block mb-1">
              Observed Symptoms or Situation (optional)
            </label>
            <textarea
              className="input text-xs w-full"
              rows={3}
              placeholder="e.g. Relative collapsed suddenly, slurred speech, unable to move left arm"
              value={symptoms}
              onChange={(e) => setSymptoms(e.target.value)}
            />
          </div>

          <button
            onClick={handleTriggerFamilySos}
            disabled={triggeringSos}
            className="btn-danger w-full py-3 text-sm font-bold shadow-md"
          >
            {triggeringSos ? "Broadcasting Emergency SOS…" : "🆘  TRIGGER FAMILY-ASSISTED SOS"}
          </button>
        </div>
      </div>
    );
  }

  // --- Active Emergency View ---
  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-8 sm:px-6">
      {/* Header card */}
      <div className="card p-6 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-navy-900/10 pb-3">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-coral-600">
              Active Family Emergency Case #{active.id}
            </span>
            <h1 className="font-display text-xl font-bold text-navy-900">
              {active.patient.full_name} · {TYPE_LABEL[active.emergency_type] || active.emergency_type}
            </h1>
          </div>
          <span className="pill bg-coral-50 text-coral-700 font-bold text-xs border border-coral-200">
            Live Emergency Tracking
          </span>
        </div>

        <StatusStepper status={active.status} />
      </div>

      {/* Transit & Destination Grid */}
      <div className="grid gap-5 sm:grid-cols-2">
        <EtaCard c={active} />
        <div className="card p-5 space-y-2">
          <h3 className="font-display text-base font-semibold text-navy-900">Receiving Hospital</h3>
          {active.hospital ? (
            <div className="text-sm text-navy-900/80 space-y-1">
              <span className="pill bg-emerald-100 text-emerald-800 text-[11px] font-bold">
                ✓ Confirmed Destination
              </span>
              <p className="font-bold text-navy-900 text-base">{active.hospital.name}</p>
              <p className="text-xs text-navy-900/70">{active.hospital.address}</p>
              {active.hospital.phone && (
                <p className="text-xs text-navy-900/60">Phone: {active.hospital.phone}</p>
              )}
              {active.doctor && (
                <p className="text-xs text-navy-900/60 pt-1 border-t border-navy-900/10">
                  Attending: Dr. {active.doctor.name} ({active.doctor.specialty})
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-navy-900/50 italic">
              Emergency coordination in progress. Routing to the nearest facility with verified capacity…
            </p>
          )}
        </div>
      </div>

      {/* Post-Emergency Status & Care Disposition (Privacy-Protected Family View) */}
      {familyOutcome && (
        <div className="card p-5 border-teal-200 bg-teal-50/30 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-teal-800">
              Care Continuity Status
            </span>
            <span className={`pill text-[10px] font-bold ${
              familyOutcome.disposition === "DISCHARGED"
                ? "bg-teal-100 text-teal-900"
                : familyOutcome.disposition === "ADMITTED"
                ? "bg-indigo-100 text-indigo-900"
                : "bg-amber-100 text-amber-900"
            }`}>
              {familyOutcome.disposition}
            </span>
          </div>

          <p className="text-sm font-semibold text-navy-900">
            {familyOutcome.disposition === "ADMITTED"
              ? `Patient has been admitted for inpatient care${familyOutcome.admitted_department ? ` in ${familyOutcome.admitted_department}` : ""} at the treating hospital.`
              : familyOutcome.disposition === "DISCHARGED"
              ? "Patient has safely completed emergency treatment and been discharged home."
              : familyOutcome.disposition === "TRANSFERRED"
              ? `Patient has been transferred to ${familyOutcome.transferred_to_facility || "a specialized facility"} for continued care.`
              : `Care Status: ${familyOutcome.disposition}`}
          </p>

          <p className="text-xs text-navy-900/70">
            {familyOutcome.disposition_notes}
          </p>

          <p className="text-[10px] text-navy-900/50 pt-1 border-t border-teal-200/50">
            Updated: {new Date(familyOutcome.outcome_at).toLocaleString()}
          </p>
        </div>
      )}

      {/* Family Bystander Update Form */}
      <div className="card p-5 space-y-3">
        <h3 className="font-display text-base font-semibold text-navy-900">
          Provide Family / Bystander Update
        </h3>
        <p className="text-xs text-navy-900/60">
          Share relevant observations (e.g. "We are with the patient", "Ambulance has departed with patient") with the attending emergency team.
        </p>
        <form onSubmit={handleSendFamilyUpdate} className="flex gap-2">
          <input
            className="input text-xs"
            placeholder="Enter family observation or location update..."
            value={familyNote}
            onChange={(e) => setFamilyNote(e.target.value)}
          />
          <button
            type="submit"
            disabled={submittingNote || !familyNote.trim()}
            className="btn-primary text-xs shrink-0"
          >
            {submittingNote ? "Submitting…" : "Post Update"}
          </button>
        </form>

        {incidents.length > 0 && (
          <div className="mt-3 space-y-2 max-h-40 overflow-y-auto pt-2 border-t border-navy-900/10">
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

      {/* Redacted Timeline Log */}
      <div className="card p-5">
        <h3 className="font-display text-base font-semibold text-navy-900">Progress Timeline</h3>
        <ul className="mt-3 space-y-2.5">
          {timeline.map((t, i) => (
            <li key={i} className="flex justify-between gap-4 text-sm">
              <span className="text-navy-900/80">{t.detail}</span>
              <span className="shrink-0 text-navy-900/40 text-xs">{timeAgo(t.at)}</span>
            </li>
          ))}
          {!timeline.length && (
            <li className="text-xs text-navy-900/40 italic">Waiting for initial telemetry updates…</li>
          )}
        </ul>
        <div className="mt-4 rounded bg-navy-900/5 p-3 text-[11px] text-navy-900/60 border border-navy-900/10">
          🔒 <strong>Privacy Notice:</strong> Clinical diagnoses and internal physician records are confidential and visible to hospital medical staff only.
        </div>
      </div>
    </div>
  );
}
