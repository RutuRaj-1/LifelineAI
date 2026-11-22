import { useCallback, useEffect, useState } from "react";
import {
  api,
  ApiError,
  CaseDetail,
  ClinicalHandoverItem,
  EligibleHospitalItem,
  EmergencyType,
  IncidentReportItem,
  ReferralEligibilityResponse,
  ReferralItem,
  referralApi,
  emergencyOrchApi,
} from "../lib/api";
import { useEmergencyEvents } from "../lib/ws";
import { TYPE_LABEL, priorityLabel, timeAgo } from "../lib/format";
import StatusStepper from "../components/StatusStepper";
import SummaryCard from "../components/SummaryCard";
import ChecklistCard from "../components/ChecklistCard";
import Banner from "../components/Banner";
import {
  EmergencyStatusBadge,
  ReferralStatusBadge,
  HandoverStatusBadge,
  FreshnessBadge,
} from "../components/StatusBadges";

type DetailTab = "intake" | "handover" | "referrals" | "summary";

export default function DoctorDashboard() {
  const [cases, setCases] = useState<CaseDetail[]>([]);
  const [selected, setSelected] = useState<CaseDetail | null>(null);
  const [activeTab, setActiveTab] = useState<DetailTab>("intake");
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Incident reports state
  const [incidents, setIncidents] = useState<IncidentReportItem[]>([]);
  const [newIncidentText, setNewIncidentText] = useState("");
  const [incidentReportType, setIncidentReportType] = useState("CLINICAL_OBSERVATION");
  const [submittingIncident, setSubmittingIncident] = useState(false);

  // Handover state
  const [handover, setHandover] = useState<ClinicalHandoverItem | null>(null);
  const [generatingHandover, setGeneratingHandover] = useState(false);
  const [handoverNotes, setHandoverNotes] = useState("");
  const [rejectionModalOpen, setRejectionModalOpen] = useState(false);
  const [rejectionReason, setRejectionReason] = useState("");
  const [approvingHandover, setApprovingHandover] = useState(false);

  // Referral coordination state
  const [eligibility, setEligibility] = useState<ReferralEligibilityResponse | null>(null);
  const [caseReferrals, setCaseReferrals] = useState<ReferralItem[]>([]);
  const [selectedHospitalIds, setSelectedHospitalIds] = useState<number[]>([]);
  const [requestedResource, setRequestedResource] = useState("ICU_BED");
  const [referralPriority, setReferralPriority] = useState<number>(1);
  const [referralNotes, setReferralNotes] = useState("");
  const [broadcasting, setBroadcasting] = useState(false);
  const [clarificationModal, setClarificationModal] = useState<{ referralId: number; question: string } | null>(null);
  const [clarificationAnswer, setClarificationAnswer] = useState("");

  const refreshCases = useCallback(() => {
    api.get<CaseDetail[]>("/doctor/cases")
      .then((rows) => {
        setCases(rows);
        setSelected((cur) => {
          if (!cur) return rows.find((r) => r.status !== "COMPLETED") || rows[0] || null;
          return rows.find((r) => r.id === cur.id) || rows[0] || null;
        });
      })
      .catch((err) => setErrorMessage(err instanceof ApiError ? err.message : "Failed to load cases"))
      .finally(() => setLoading(false));
  }, []);

  const loadCaseDetails = useCallback((caseId: number) => {
    emergencyOrchApi.getIncidents(caseId).then(setIncidents).catch(() => setIncidents([]));
    emergencyOrchApi.getHandover(caseId).then(setHandover).catch(() => setHandover(null));
    referralApi.getCaseReferrals(caseId)
      .then((res) => setCaseReferrals(res.referrals))
      .catch(() => setCaseReferrals([]));
    referralApi.getEligibility(caseId, requestedResource)
      .then(setEligibility)
      .catch(() => setEligibility(null));
  }, [requestedResource]);

  useEffect(refreshCases, [refreshCases]);

  useEffect(() => {
    if (selected) {
      loadCaseDetails(selected.id);
    }
  }, [selected?.id, loadCaseDetails]);

  useEmergencyEvents(() => {
    refreshCases();
    if (selected) {
      loadCaseDetails(selected.id);
    }
  });

  async function toggleChecklist(i: number, done: boolean) {
    if (!selected) return;
    await api.post(`/emergency/${selected.id}/checklist`, { index: i, done });
    refreshCases();
  }

  // --- Incident Reporting Action ---
  async function handleAddIncident(e: React.FormEvent) {
    e.preventDefault();
    if (!selected || !newIncidentText.trim()) return;
    setSubmittingIncident(true);
    try {
      await emergencyOrchApi.submitIncident(selected.id, {
        reported_text: newIncidentText.trim(),
        reporter_type: "PHYSICIAN",
        report_type: incidentReportType,
        idempotency_key: crypto.randomUUID(),
      });
      setNewIncidentText("");
      loadCaseDetails(selected.id);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to submit incident observation");
    } finally {
      setSubmittingIncident(false);
    }
  }

  // --- Handover Actions ---
  async function handleGenerateHandover() {
    if (!selected) return;
    setGeneratingHandover(true);
    setErrorMessage(null);
    try {
      const generated = await emergencyOrchApi.generateHandover(selected.id, "Attending physician emergency brief");
      setHandover(generated);
      setActiveTab("handover");
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to generate clinical handover");
    } finally {
      setGeneratingHandover(false);
    }
  }

  async function handleApproveHandover() {
    if (!selected || !handover) return;
    setApprovingHandover(true);
    setErrorMessage(null);
    try {
      const approved = await emergencyOrchApi.approveHandover(selected.id, handover.id, handoverNotes.trim() || undefined);
      setHandover(approved);
      setHandoverNotes("");
      refreshCases();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to approve handover");
    } finally {
      setApprovingHandover(false);
    }
  }

  async function handleRejectHandover() {
    if (!selected || !handover || !rejectionReason.trim()) return;
    setApprovingHandover(true);
    setErrorMessage(null);
    try {
      const rejected = await emergencyOrchApi.rejectHandover(selected.id, handover.id, rejectionReason.trim());
      setHandover(rejected);
      setRejectionModalOpen(false);
      setRejectionReason("");
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to reject handover");
    } finally {
      setApprovingHandover(false);
    }
  }

  // --- Referral Actions ---
  async function handleBroadcastReferrals() {
    if (!selected || !selectedHospitalIds.length) return;
    setBroadcasting(true);
    setErrorMessage(null);
    try {
      await referralApi.broadcast(selected.id, {
        hospital_ids: selectedHospitalIds,
        requested_resource_type: requestedResource,
        priority: referralPriority,
        notes: referralNotes.trim() || undefined,
        idempotency_key: crypto.randomUUID(),
      });
      setSelectedHospitalIds([]);
      setReferralNotes("");
      loadCaseDetails(selected.id);
      refreshCases();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to broadcast referral requests");
    } finally {
      setBroadcasting(false);
    }
  }

  async function handleRespondClarification() {
    if (!clarificationModal || !clarificationAnswer.trim()) return;
    try {
      await referralApi.respondClarification(clarificationModal.referralId, clarificationAnswer.trim());
      setClarificationModal(null);
      setClarificationAnswer("");
      if (selected) loadCaseDetails(selected.id);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to provide clarification answer");
    }
  }

  function toggleHospitalSelection(id: number) {
    setSelectedHospitalIds((prev) =>
      prev.includes(id) ? prev.filter((h) => h !== id) : [...prev, id]
    );
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl px-5 py-12 text-center text-sm text-navy-900/50">
        Loading clinical cases and emergency telemetry…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      {/* Top Banner */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-navy-900/10 pb-4">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-navy-900">
            Attending Physician & Emergency Coordination Console
          </h1>
          <p className="text-xs text-navy-900/60">
            Pre-Emergency Intelligence · Evidence-Grounded Handover · Multi-Hospital Referral Coordination
          </p>
        </div>
        {selected && (
          <button
            onClick={handleGenerateHandover}
            disabled={generatingHandover}
            className="btn-primary text-xs font-semibold px-3.5 py-2 shadow-sm"
          >
            {generatingHandover ? "Synthesizing…" : "📋 Generate Clinical Handover"}
          </button>
        )}
      </div>

      {errorMessage && (
        <div className="mb-4">
          <Banner>{errorMessage}</Banner>
        </div>
      )}

      {/* Main Two-Column Layout */}
      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        {/* Left Column: Active Cases Queue */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-wider text-navy-900/60">
              Assigned Cases ({cases.length})
            </h2>
            <button onClick={refreshCases} className="text-xs text-teal-700 hover:underline">
              🔄 Refresh
            </button>
          </div>

          {cases.map((c) => {
            const prio = priorityLabel(c.priority);
            const isSelected = selected?.id === c.id;
            return (
              <button
                key={c.id}
                onClick={() => setSelected(c)}
                className={`card block w-full p-4 text-left transition ${
                  isSelected ? "ring-2 ring-teal-600 bg-teal-50/20 shadow-sm" : "hover:border-navy-900/20"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-navy-900">{c.patient.full_name}</span>
                  <span className={`pill ${prio.className}`}>{prio.label}</span>
                </div>
                <div className="mt-1 flex items-center justify-between text-xs text-navy-900/60">
                  <span>{TYPE_LABEL[c.emergency_type] || c.emergency_type}</span>
                  <EmergencyStatusBadge status={c.status} />
                </div>
                <p className="mt-1.5 text-[11px] text-navy-900/40">
                  Dispatched {timeAgo(c.created_at)}
                </p>
              </button>
            );
          })}

          {!cases.length && (
            <div className="card p-6 text-center text-sm text-navy-900/50">
              No emergency cases assigned to your queue.
            </div>
          )}
        </div>

        {/* Right Column: Case Details & Clinical Workspaces */}
        {selected ? (
          <div className="space-y-5">
            {/* Case Header Card */}
            <div className="card p-6 space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="font-display text-xl font-bold text-navy-900">
                      {selected.patient.full_name}
                    </h2>
                    <EmergencyStatusBadge status={selected.status} />
                  </div>
                  <p className="text-xs text-navy-900/60 mt-1">
                    {selected.patient.age ? `${selected.patient.age}y` : "Age unspecified"} · {selected.patient.gender || "—"} · Blood Group: <span className="font-semibold text-navy-900">{selected.patient.blood_group || "Unknown"}</span>
                  </p>
                  {selected.patient.phone && (
                    <p className="text-xs text-navy-900/50">Phone: {selected.patient.phone}</p>
                  )}
                </div>

                <div className="flex flex-col items-end gap-1">
                  <span className={`pill ${priorityLabel(selected.priority).className}`}>
                    {priorityLabel(selected.priority).label}
                  </span>
                  <span className="text-[11px] text-navy-900/50">
                    Emergency ID #{selected.id}
                  </span>
                </div>
              </div>

              {/* Status Stepper */}
              <div className="pt-2 border-t border-navy-900/10">
                <StatusStepper status={selected.status} />
              </div>

              {/* Patient Location & Hospital Allocation Details */}
              <div className="grid gap-3 sm:grid-cols-2 rounded-lg bg-navy-900/[0.02] p-3 text-xs border border-navy-900/5">
                <div>
                  <span className="font-bold text-navy-900/60 uppercase text-[10px]">Incident Location</span>
                  <p className="mt-0.5 text-navy-900">
                    Lat: {selected.lat.toFixed(4)}, Lng: {selected.lng.toFixed(4)}
                  </p>
                  <p className="text-[10px] text-navy-900/50">GPS Coordinates verified</p>
                </div>
                <div>
                  <span className="font-bold text-navy-900/60 uppercase text-[10px]">Confirmed Destination</span>
                  {selected.hospital ? (
                    <p className="mt-0.5 font-semibold text-teal-800">
                      {selected.hospital.name} ({selected.hospital.address})
                    </p>
                  ) : (
                    <p className="mt-0.5 text-navy-900/50 italic">
                      Multi-hospital referral evaluation active
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Navigation Tabs for Selected Case */}
            <nav className="flex flex-wrap gap-2 border-b border-navy-900/10 pb-2">
              {[
                { id: "intake", label: `Live Intake & Field Reports (${incidents.length})` },
                { id: "handover", label: `Clinical Handover ${handover ? `(v${handover.version})` : ""}` },
                { id: "referrals", label: `Referral Dispatch (${caseReferrals.length})` },
                { id: "summary", label: "Patient Health Vault & Checklist" },
              ].map((t) => (
                <button
                  key={t.id}
                  onClick={() => setActiveTab(t.id as DetailTab)}
                  className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
                    activeTab === t.id
                      ? "bg-teal-700 text-white shadow-sm"
                      : "bg-navy-900/5 text-navy-900/70 hover:bg-navy-900/10"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </nav>

            {/* Tab 1: Live Intake & Field Incident Reports */}
            {activeTab === "intake" && (
              <div className="space-y-5">
                <div className="card p-6 space-y-4">
                  <h3 className="font-display text-base font-semibold text-navy-900">
                    Live Incident Intake Feed
                  </h3>
                  <p className="text-xs text-navy-900/60">
                    Sequential, timestamped observations submitted by paramedics, bystanders, and attending clinicians.
                  </p>

                  {/* Add Clinician Note Form */}
                  <form onSubmit={handleAddIncident} className="rounded-lg bg-teal-50/50 p-4 border border-teal-200 space-y-3">
                    <span className="font-bold text-teal-900 text-xs">Record Field / Clinical Update</span>
                    <div className="grid gap-3 sm:grid-cols-[1fr_180px]">
                      <input
                        className="input text-xs"
                        placeholder="e.g. Patient conscious; bilateral pupil equality confirmed; oxygen saturation 96%."
                        value={newIncidentText}
                        onChange={(e) => setNewIncidentText(e.target.value)}
                        required
                      />
                      <select
                        className="input text-xs"
                        value={incidentReportType}
                        onChange={(e) => setIncidentReportType(e.target.value)}
                      >
                        <option value="CLINICAL_OBSERVATION">Clinical Observation</option>
                        <option value="SYMPTOM_UPDATE">Symptom Update</option>
                        <option value="VITALS_REPORT">Vitals Record</option>
                        <option value="HANDOVER_NOTE">Handover Note</option>
                      </select>
                    </div>
                    <div className="flex justify-end">
                      <button
                        type="submit"
                        disabled={submittingIncident || !newIncidentText.trim()}
                        className="btn-primary text-xs"
                      >
                        {submittingIncident ? "Recording…" : "Post Observation"}
                      </button>
                    </div>
                  </form>

                  {/* Incident List */}
                  <div className="space-y-3">
                    {incidents.map((inc) => (
                      <div key={inc.id} className="rounded-lg border border-navy-900/10 p-3.5 space-y-1 text-xs">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="font-bold uppercase tracking-wider text-[10px] text-teal-800 bg-teal-100 px-2 py-0.5 rounded">
                              {inc.reporter_type.replace(/_/g, " ")}
                            </span>
                            <span className="font-semibold text-navy-900">{inc.report_type.replace(/_/g, " ")}</span>
                            {inc.verification_status === "UNVERIFIED" && (
                              <span className="pill bg-amber-50 text-amber-700 text-[10px]">Unverified</span>
                            )}
                          </div>
                          <span className="text-[11px] text-navy-900/40">{timeAgo(inc.received_at)}</span>
                        </div>
                        <p className="text-navy-900 font-medium whitespace-pre-wrap">{inc.reported_text}</p>
                        {inc.reporter_user_name && (
                          <p className="text-[10px] text-navy-900/40">Reported by: {inc.reporter_user_name}</p>
                        )}
                      </div>
                    ))}
                    {!incidents.length && (
                      <p className="text-xs text-navy-900/40 italic py-3">
                        No additional incident reports submitted for this emergency yet.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Tab 2: Structured Clinical Handover Workspace */}
            {activeTab === "handover" && (
              <div className="space-y-5">
                <div className="card p-6 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-navy-900/10 pb-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-display text-base font-bold text-navy-900">
                          Structured Clinical Handover Brief
                        </h3>
                        {handover && <HandoverStatusBadge status={handover.status} />}
                      </div>
                      <p className="text-xs text-navy-900/60 mt-0.5">
                        {handover ? `Version ${handover.version} · Created ${timeAgo(handover.created_at)}` : "No handover generated yet"}
                      </p>
                    </div>

                    {!handover && (
                      <button
                        onClick={handleGenerateHandover}
                        disabled={generatingHandover}
                        className="btn-primary text-xs"
                      >
                        {generatingHandover ? "Synthesizing…" : "Generate Handover Now"}
                      </button>
                    )}
                  </div>

                  {handover ? (
                    <div className="space-y-4">
                      {/* Safety Disclaimer Banner */}
                      <div className="rounded-lg bg-navy-900/5 p-3 text-xs text-navy-900/80 border border-navy-900/10">
                        <strong>Clinical Safety Notice:</strong> Synthesized clinical record for pre-arrival emergency handover only.
                        Not a diagnostic prescription. Requires attending physician approval before transmission.
                      </div>

                      {/* Handover Data Content */}
                      <div className="grid gap-4 sm:grid-cols-2">
                        {/* Allergies Highlight Box */}
                        <div className="rounded-lg bg-rose-50 p-4 border border-rose-200">
                          <h4 className="font-bold text-rose-900 uppercase text-xs tracking-wider mb-2">
                            Critical Allergies Alert
                          </h4>
                          <ul className="space-y-1 text-xs">
                            {handover.handover_data?.known_allergies?.map((a: any, idx: number) => (
                              <li key={idx} className="font-bold text-rose-800">⚠️ {typeof a === "string" ? a : a.fact_value || a.value}</li>
                            ))}
                            {(!handover.handover_data?.known_allergies || !handover.handover_data.known_allergies.length) && (
                              <li className="text-navy-900/50">No verified drug allergies on record</li>
                            )}
                          </ul>
                        </div>

                        {/* Baseline Conditions Box */}
                        <div className="rounded-lg bg-teal-50/50 p-4 border border-teal-200">
                          <h4 className="font-bold text-teal-900 uppercase text-xs tracking-wider mb-2">
                            Chronic Conditions
                          </h4>
                          <ul className="space-y-1 text-xs text-navy-900">
                            {handover.handover_data?.known_conditions?.map((c: any, idx: number) => (
                              <li key={idx} className="font-medium">• {typeof c === "string" ? c : c.fact_value || c.value}</li>
                            ))}
                            {(!handover.handover_data?.known_conditions || !handover.handover_data.known_conditions.length) && (
                              <li className="text-navy-900/50">No chronic conditions recorded</li>
                            )}
                          </ul>
                        </div>

                        {/* Active Prescriptions Box */}
                        <div className="rounded-lg bg-navy-900/[0.02] p-4 border border-navy-900/10">
                          <h4 className="font-bold text-navy-900 uppercase text-xs tracking-wider mb-2">
                            Current Medications
                          </h4>
                          <ul className="space-y-1 text-xs text-navy-900">
                            {handover.handover_data?.current_medications?.map((m: any, idx: number) => (
                              <li key={idx}>• {typeof m === "string" ? m : m.fact_value || m.value}</li>
                            ))}
                            {(!handover.handover_data?.current_medications || !handover.handover_data.current_medications.length) && (
                              <li className="text-navy-900/50">No active prescriptions listed</li>
                            )}
                          </ul>
                        </div>

                        {/* Surgeries Box */}
                        <div className="rounded-lg bg-navy-900/[0.02] p-4 border border-navy-900/10">
                          <h4 className="font-bold text-navy-900 uppercase text-xs tracking-wider mb-2">
                            Past Surgeries & Implants
                          </h4>
                          <ul className="space-y-1 text-xs text-navy-900">
                            {handover.handover_data?.past_surgeries?.map((s: any, idx: number) => (
                              <li key={idx}>• {typeof s === "string" ? s : s.fact_value || s.value}</li>
                            ))}
                            {(!handover.handover_data?.past_surgeries || !handover.handover_data.past_surgeries.length) && (
                              <li className="text-navy-900/50">None on record</li>
                            )}
                          </ul>
                        </div>
                      </div>

                      {/* Incompleteness / Missing Data Warnings */}
                      {handover.handover_data?.missing_data_warnings && handover.handover_data.missing_data_warnings.length > 0 && (
                        <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900 border border-amber-200">
                          <strong>⚠️ Incomplete Data Warnings:</strong>
                          <ul className="mt-1 list-disc list-inside space-y-0.5">
                            {handover.handover_data.missing_data_warnings.map((w: string, idx: number) => (
                              <li key={idx}>{w}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Physician Approval Gate */}
                      <div className="rounded-lg bg-teal-50 p-4 border border-teal-200 space-y-3">
                        <div className="flex items-center justify-between">
                          <h4 className="font-bold text-teal-900 text-xs uppercase tracking-wider">
                            Attending Physician Verification Gate
                          </h4>
                          {handover.is_current_approved && (
                            <span className="pill bg-emerald-100 text-emerald-800 font-bold text-xs">
                              ✓ Approved by {handover.approved_by_name || "Doctor"}
                            </span>
                          )}
                        </div>

                        {handover.status === "PENDING_REVIEW" ? (
                          <div className="space-y-3">
                            <input
                              className="input text-xs"
                              placeholder="Clinical review notes (optional, e.g. 'Airway secured, candidate for immediate thrombolysis')"
                              value={handoverNotes}
                              onChange={(e) => setHandoverNotes(e.target.value)}
                            />
                            <div className="flex gap-2 justify-end">
                              <button
                                onClick={() => setRejectionModalOpen(true)}
                                disabled={approvingHandover}
                                className="rounded-lg bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-100 border border-rose-200"
                              >
                                ✕ Reject Handover
                              </button>
                              <button
                                onClick={handleApproveHandover}
                                disabled={approvingHandover}
                                className="btn-primary text-xs"
                              >
                                {approvingHandover ? "Approving…" : "✓ Approve Clinical Handover"}
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="text-xs text-navy-900/70">
                            {handover.approved_at && (
                              <p>Approved at {new Date(handover.approved_at).toLocaleString()}</p>
                            )}
                            {handover.approval_notes && (
                              <p className="mt-1 font-medium">Notes: {handover.approval_notes}</p>
                            )}
                            {handover.rejection_reason && (
                              <p className="mt-1 text-rose-700 font-medium">Rejection Reason: {handover.rejection_reason}</p>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="p-8 text-center text-xs text-navy-900/50">
                      Click "Generate Handover Now" above to synthesize an evidence-grounded handover brief for this patient.
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Tab 3: Multi-Hospital Referral Dispatch */}
            {activeTab === "referrals" && (
              <div className="space-y-5">
                {/* Broadcast Engine Panel */}
                <div className="card p-6 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h3 className="font-display text-base font-semibold text-navy-900">
                        Multi-Hospital Referral Engine
                      </h3>
                      <p className="text-xs text-navy-900/60">
                        Discover operational capacities, evaluate clinical capability matches, and broadcast requests.
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <select
                        className="input text-xs"
                        value={requestedResource}
                        onChange={(e) => setRequestedResource(e.target.value)}
                      >
                        <option value="ICU_BED">ICU Bed</option>
                        <option value="TRAUMA_BAY">Trauma Bay</option>
                        <option value="OT">Operating Theater</option>
                        <option value="CARDIAC_MONITOR">Cardiac Monitor</option>
                      </select>
                      <button
                        onClick={() => selected && loadCaseDetails(selected.id)}
                        className="btn-secondary text-xs"
                      >
                        Evaluate
                      </button>
                    </div>
                  </div>

                  {/* Discovered Eligible Hospitals Table */}
                  {eligibility && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between text-xs text-navy-900/60">
                        <span>Evaluated {eligibility.total_hospitals_evaluated} hospital facilities</span>
                        <span>{selectedHospitalIds.length} hospitals selected for dispatch</span>
                      </div>

                      <div className="divide-y divide-navy-900/10 rounded-lg border border-navy-900/10 overflow-hidden">
                        {eligibility.eligible_hospitals.map((h: EligibleHospitalItem) => {
                          const isSelected = selectedHospitalIds.includes(h.hospital_id);
                          return (
                            <div
                              key={h.hospital_id}
                              onClick={() => toggleHospitalSelection(h.hospital_id)}
                              className={`p-3.5 flex flex-wrap items-center justify-between gap-3 cursor-pointer text-xs transition ${
                                isSelected ? "bg-teal-50/60" : "hover:bg-navy-900/[0.02]"
                              }`}
                            >
                              <div className="flex items-center gap-3">
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={() => toggleHospitalSelection(h.hospital_id)}
                                  className="h-4 w-4 rounded border-navy-900/30 text-teal-600"
                                />
                                <div>
                                  <span className="font-bold text-navy-900">{h.hospital_name}</span>
                                  <p className="text-navy-900/50 text-[11px]">{h.city || h.address || "City facility"}</p>
                                </div>
                              </div>

                              <div className="flex items-center gap-4">
                                {/* Capabilities */}
                                <div className="text-right hidden sm:block">
                                  <span className="text-[10px] text-navy-900/50 block">Capabilities</span>
                                  <span className="font-medium text-navy-900">
                                    {h.verified_capabilities.slice(0, 2).join(", ") || "General Emergency"}
                                  </span>
                                </div>

                                {/* Usable Capacity */}
                                {h.resource_summary && (
                                  <div className="text-right">
                                    <span className="text-[10px] text-navy-900/50 block">Usable Capacity</span>
                                    <span className="font-bold text-teal-800">
                                      {h.resource_summary.usable_capacity} {h.resource_summary.resource_type.replace(/_/g, " ")}
                                    </span>
                                  </div>
                                )}

                                {/* Freshness Badge */}
                                {h.resource_summary && (
                                  <FreshnessBadge status={h.resource_summary.freshness_status} />
                                )}

                                {h.is_dispatched && (
                                  <span className="pill bg-blue-100 text-blue-800 text-[10px]">
                                    Already Dispatched
                                  </span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      {/* Broadcast Trigger Bar */}
                      <div className="flex flex-wrap items-center justify-between gap-3 pt-3">
                        <div className="flex items-center gap-3">
                          <input
                            className="input text-xs w-64"
                            placeholder="Coordinator notes (e.g. ETA 12 mins)"
                            value={referralNotes}
                            onChange={(e) => setReferralNotes(e.target.value)}
                          />
                          <select
                            className="input text-xs"
                            value={referralPriority}
                            onChange={(e) => setReferralPriority(Number(e.target.value))}
                          >
                            <option value={1}>Priority 1 (Critical)</option>
                            <option value={2}>Priority 2 (Urgent)</option>
                            <option value={3}>Priority 3 (Standard)</option>
                          </select>
                        </div>

                        <button
                          onClick={handleBroadcastReferrals}
                          disabled={broadcasting || !selectedHospitalIds.length}
                          className="btn-danger text-xs font-semibold px-4 py-2"
                        >
                          {broadcasting ? "Broadcasting…" : `🚀 Broadcast to ${selectedHospitalIds.length} Hospitals`}
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* Dispatched Referrals Status Table */}
                <div className="card p-6 space-y-4">
                  <h3 className="font-display text-base font-semibold text-navy-900">
                    Dispatched Referral Requests ({caseReferrals.length})
                  </h3>

                  <div className="space-y-3">
                    {caseReferrals.map((r) => (
                      <div key={r.id} className="rounded-lg border border-navy-900/10 p-4 space-y-2 text-xs">
                        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-navy-900/5 pb-2">
                          <div>
                            <span className="font-bold text-navy-900 text-sm">{r.hospital_name || `Hospital #${r.hospital_id}`}</span>
                            <span className="ml-2 font-mono text-[11px] text-navy-900/50">{r.request_reference}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <ReferralStatusBadge status={r.status} />
                            {r.is_active_acceptance && (
                              <span className="rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800 border border-emerald-300">
                                Confirmed Receiving Hospital
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center justify-between text-navy-900/60 text-[11px]">
                          <span>Requested: {r.requested_resource_type?.replace(/_/g, " ")}</span>
                          <span>Dispatched: {timeAgo(r.requested_at)}</span>
                        </div>

                        {r.clarification_notes && (
                          <div className="rounded bg-amber-50 p-2.5 text-amber-900 text-xs">
                            <strong>Clarification Thread:</strong>
                            <p className="mt-0.5 whitespace-pre-wrap">{r.clarification_notes}</p>
                          </div>
                        )}

                        {r.status === "CLARIFICATION_REQUIRED" && (
                          <div className="flex justify-end pt-1">
                            <button
                              onClick={() => setClarificationModal({ referralId: r.id, question: r.clarification_notes || "Clarification needed" })}
                              className="btn-secondary text-xs"
                            >
                              💬 Provide Clarification
                            </button>
                          </div>
                        )}
                      </div>
                    ))}

                    {!caseReferrals.length && (
                      <p className="text-xs text-navy-900/40 italic py-2">
                        No referrals dispatched for this case yet.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Tab 4: Health Vault & Checklist */}
            {activeTab === "summary" && (
              <div className="space-y-5">
                <SummaryCard s={selected.ai_summary} />
                {!!selected.checklist?.length && (
                  <ChecklistCard items={selected.checklist} onToggle={toggleChecklist} />
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="card p-12 text-center text-sm text-navy-900/50">
            Select an emergency case from the queue to review patient intelligence and manage referral coordination.
          </div>
        )}
      </div>

      {/* Clarification Response Modal */}
      {clarificationModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-900/50 p-4 backdrop-blur-sm">
          <div className="card w-full max-w-lg p-6 space-y-4">
            <h3 className="font-display text-base font-bold text-navy-900">
              Provide Referral Clarification
            </h3>
            <p className="text-xs text-navy-900/70 bg-amber-50 p-3 rounded border border-amber-200">
              Hospital Question: {clarificationModal.question}
            </p>
            <textarea
              className="input text-xs w-full"
              rows={3}
              placeholder="Enter clinical or operational answer for receiving team..."
              value={clarificationAnswer}
              onChange={(e) => setClarificationAnswer(e.target.value)}
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setClarificationModal(null)} className="btn-secondary text-xs">
                Cancel
              </button>
              <button onClick={handleRespondClarification} className="btn-primary text-xs">
                Send Clarification
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Handover Rejection Modal */}
      {rejectionModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-900/50 p-4 backdrop-blur-sm">
          <div className="card w-full max-w-md p-6 space-y-4">
            <h3 className="font-display text-base font-bold text-rose-900">
              Reject Clinical Handover Brief
            </h3>
            <p className="text-xs text-navy-900/60">
              Provide clinical justification for rejection (e.g. Inaccurate baseline data or updated trauma vitals required).
            </p>
            <textarea
              className="input text-xs w-full"
              rows={3}
              placeholder="Reason for rejection (required)..."
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              required
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setRejectionModalOpen(false)} className="btn-secondary text-xs">
                Cancel
              </button>
              <button
                onClick={handleRejectHandover}
                disabled={!rejectionReason.trim() || approvingHandover}
                className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-rose-700"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
