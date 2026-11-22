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
  postEmergencyApi,
  EmergencyOutcome,
  DischargeSummary,
  MedicationReconciliationItem,
  FollowUpPlanItem,
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

type DetailTab = "intake" | "handover" | "referrals" | "summary" | "continuity";

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

  // Post-Emergency Continuity State (Prompt 10)
  const [outcome, setOutcome] = useState<EmergencyOutcome | null>(null);
  const [outcomeDisposition, setOutcomeDisposition] = useState<string>("DISCHARGED");
  const [outcomeNotes, setOutcomeNotes] = useState<string>("");
  const [outcomeDept, setOutcomeDept] = useState<string>("");
  const [outcomeFacility, setOutcomeFacility] = useState<string>("");
  const [outcomeAmendmentReason, setOutcomeAmendmentReason] = useState<string>("");
  const [recordingOutcome, setRecordingOutcome] = useState(false);

  const [dischargeSummary, setDischargeSummary] = useState<DischargeSummary | null>(null);
  const [approvingDischarge, setApprovingDischarge] = useState(false);
  const [dischargeApprovalNotes, setDischargeApprovalNotes] = useState("");
  const [dischargeRejectionModal, setDischargeRejectionModal] = useState(false);
  const [dischargeRejectionReason, setDischargeRejectionReason] = useState("");
  const [generatingDraft, setGeneratingDraft] = useState(false);

  const [medRecs, setMedRecs] = useState<MedicationReconciliationItem[]>([]);
  const [newMedName, setNewMedName] = useState("");
  const [newMedDosage, setNewMedDosage] = useState("");
  const [newMedFreq, setNewMedFreq] = useState("Daily");
  const [newMedAction, setNewMedAction] = useState("CONTINUE");
  const [newMedIndication, setNewMedIndication] = useState("");
  const [addingMedRec, setAddingMedRec] = useState(false);

  const [followUps, setFollowUps] = useState<FollowUpPlanItem[]>([]);
  const [newFuSpecialty, setNewFuSpecialty] = useState("Cardiology");
  const [newFuProvider, setNewFuProvider] = useState("");
  const [newFuTimeframe, setNewFuTimeframe] = useState("Within 7 days");
  const [newFuDate, setNewFuDate] = useState("");
  const [newFuInstructions, setNewFuInstructions] = useState("");
  const [addingFu, setAddingFu] = useState(false);

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
    postEmergencyApi.getOutcome(caseId).then((o) => {
      setOutcome(o);
      if (o) {
        setOutcomeDisposition(o.disposition);
        setOutcomeNotes(o.disposition_notes);
        setOutcomeDept(o.admitted_department || "");
        setOutcomeFacility(o.transferred_to_facility || "");
      }
    }).catch(() => setOutcome(null));
    postEmergencyApi.getDischargeSummary(caseId).then(setDischargeSummary).catch(() => setDischargeSummary(null));
    postEmergencyApi.listMedicationReconciliations(caseId).then(setMedRecs).catch(() => setMedRecs([]));
    postEmergencyApi.listFollowUpPlans(caseId).then(setFollowUps).catch(() => setFollowUps([]));
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

  // --- Post-Emergency Handlers (Prompt 10) ---
  async function handleRecordOrAmendOutcome() {
    if (!selected || !outcomeNotes.trim()) return;
    setRecordingOutcome(true);
    setErrorMessage(null);
    try {
      if (outcome) {
        const updated = await postEmergencyApi.amendOutcome(selected.id, {
          disposition: outcomeDisposition,
          disposition_notes: outcomeNotes.trim(),
          amendment_reason: outcomeAmendmentReason.trim() || "Clinical outcome updated by attending physician",
          admitted_department: outcomeDept.trim() || undefined,
          transferred_to_facility: outcomeFacility.trim() || undefined,
        });
        setOutcome(updated);
      } else {
        const created = await postEmergencyApi.recordOutcome(selected.id, {
          disposition: outcomeDisposition,
          disposition_notes: outcomeNotes.trim(),
          admitted_department: outcomeDept.trim() || undefined,
          transferred_to_facility: outcomeFacility.trim() || undefined,
        });
        setOutcome(created);
      }
      refreshCases();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to record emergency outcome");
    } finally {
      setRecordingOutcome(false);
    }
  }

  async function handleApproveDischarge() {
    if (!selected || !dischargeSummary) return;
    setApprovingDischarge(true);
    setErrorMessage(null);
    try {
      const res = await postEmergencyApi.approveDischargeSummary(selected.id, dischargeSummary.id, dischargeApprovalNotes.trim() || undefined);
      setDischargeSummary(res);
      refreshCases();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to approve discharge summary");
    } finally {
      setApprovingDischarge(false);
    }
  }

  async function handleRejectDischarge() {
    if (!selected || !dischargeSummary || !dischargeRejectionReason.trim()) return;
    setApprovingDischarge(true);
    setErrorMessage(null);
    try {
      const res = await postEmergencyApi.rejectDischargeSummary(selected.id, dischargeSummary.id, dischargeRejectionReason.trim());
      setDischargeSummary(res);
      setDischargeRejectionModal(false);
      setDischargeRejectionReason("");
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to reject discharge summary");
    } finally {
      setApprovingDischarge(false);
    }
  }

  async function handleGenerateDischargeDraft() {
    if (!selected) return;
    setGeneratingDraft(true);
    setErrorMessage(null);
    try {
      const draft = await postEmergencyApi.generateDischargeSummary(selected.id);
      setDischargeSummary(draft);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to generate discharge summary draft");
    } finally {
      setGeneratingDraft(false);
    }
  }

  async function handleVerifyMedRec(itemId: number, approved: boolean) {
    if (!selected) return;
    try {
      const updated = await postEmergencyApi.verifyMedicationReconciliation(selected.id, itemId, approved);
      setMedRecs((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to verify medication reconciliation item");
    }
  }

  async function handleAddMedRec(e: React.FormEvent) {
    e.preventDefault();
    if (!selected || !newMedName.trim() || !newMedDosage.trim()) return;
    setAddingMedRec(true);
    try {
      const created = await postEmergencyApi.createMedicationReconciliation(selected.id, {
        medication_name: newMedName.trim(),
        dosage: newMedDosage.trim(),
        frequency: newMedFreq.trim(),
        action: newMedAction,
        clinical_indication: newMedIndication.trim() || undefined,
        source: "Attending Physician Verification",
      });
      setMedRecs((prev) => [...prev, created]);
      setNewMedName("");
      setNewMedDosage("");
      setNewMedIndication("");
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to add medication entry");
    } finally {
      setAddingMedRec(false);
    }
  }

  async function handleAddFollowUp(e: React.FormEvent) {
    e.preventDefault();
    if (!selected || !newFuInstructions.trim()) return;
    setAddingFu(true);
    try {
      const created = await postEmergencyApi.createFollowUpPlan(selected.id, {
        specialty: newFuSpecialty,
        provider_name: newFuProvider.trim() || undefined,
        timeframe: newFuTimeframe,
        scheduled_date: newFuDate || undefined,
        instructions: newFuInstructions.trim(),
      });
      setFollowUps((prev) => [...prev, created]);
      setNewFuInstructions("");
      setNewFuDate("");
      setNewFuProvider("");
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to create follow up plan");
    } finally {
      setAddingFu(false);
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
                { id: "continuity", label: `Post-Emergency & Continuity ${outcome ? `(${outcome.disposition})` : ""}` },
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

            {/* Tab 5: Post-Emergency Continuity & Outcome (Prompt 10) */}
            {activeTab === "continuity" && (
              <div className="space-y-6">
                {/* 1. Emergency Outcome & Disposition */}
                <div className="card p-6 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-navy-900/10 pb-3">
                    <div>
                      <h3 className="font-display text-base font-bold text-navy-900">
                        Emergency Episode Outcome & Disposition
                      </h3>
                      <p className="text-xs text-navy-900/60">
                        Distinguish clinical release, inpatient admission, or specialized facility transfer.
                      </p>
                    </div>
                    {outcome && (
                      <span className={`pill ${
                        outcome.disposition === "DISCHARGED"
                          ? "bg-teal-100 text-teal-900"
                          : outcome.disposition === "ADMITTED"
                          ? "bg-indigo-100 text-indigo-900"
                          : "bg-amber-100 text-amber-900"
                      } text-xs font-bold`}>
                        {outcome.disposition} (v{outcome.version} · {outcome.verification_status})
                      </span>
                    )}
                  </div>

                  {outcome ? (
                    <div className="rounded-lg bg-navy-900/[0.02] p-4 border border-navy-900/10 space-y-2 text-xs">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                          <span className="font-bold text-navy-900/60 uppercase text-[10px]">Active Disposition</span>
                          <p className="text-sm font-semibold text-navy-900">{outcome.disposition}</p>
                          {outcome.admitted_department && (
                            <p className="text-navy-900/70">Admitted Department: <span className="font-semibold">{outcome.admitted_department}</span></p>
                          )}
                          {outcome.transferred_to_facility && (
                            <p className="text-navy-900/70">Transferred Facility: <span className="font-semibold">{outcome.transferred_to_facility}</span></p>
                          )}
                        </div>
                        <div>
                          <span className="font-bold text-navy-900/60 uppercase text-[10px]">Provenance & Timestamps</span>
                          <p className="text-navy-900/70">Recorded by: {outcome.recorded_by_name || `User #${outcome.recorded_by_user_id}`}</p>
                          <p className="text-navy-900/50">Recorded at: {new Date(outcome.outcome_at).toLocaleString()}</p>
                          {outcome.amendment_reason && (
                            <p className="text-amber-800 font-medium mt-1">Amendment Note: {outcome.amendment_reason}</p>
                          )}
                        </div>
                      </div>
                      <div className="pt-2 border-t border-navy-900/5">
                        <span className="font-bold text-navy-900/60 uppercase text-[10px]">Clinical Disposition Notes</span>
                        <p className="text-navy-900 mt-0.5 whitespace-pre-wrap">{outcome.disposition_notes}</p>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-navy-900/50 italic">
                      No final outcome has been recorded for this case yet. Emergency status is currently active.
                    </p>
                  )}

                  {/* Outcome Record / Amendment Form */}
                  <div className="rounded-lg bg-navy-900/[0.01] p-4 border border-dashed border-navy-900/20 space-y-3">
                    <h4 className="text-xs font-bold text-navy-900 uppercase">
                      {outcome ? "Amend Documented Outcome" : "Record Episode Outcome"}
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="text-[11px] font-semibold text-navy-900/70">Disposition Type</label>
                        <select
                          className="input text-xs w-full mt-1"
                          value={outcomeDisposition}
                          onChange={(e) => setOutcomeDisposition(e.target.value)}
                        >
                          <option value="DISCHARGED">DISCHARGED (Outpatient release)</option>
                          <option value="ADMITTED">ADMITTED (Inpatient admission)</option>
                          <option value="TRANSFERRED">TRANSFERRED (Specialized facility)</option>
                          <option value="OTHER">OTHER (Clinical documentation)</option>
                        </select>
                      </div>

                      {outcomeDisposition === "ADMITTED" && (
                        <div>
                          <label className="text-[11px] font-semibold text-navy-900/70">Admitting Department</label>
                          <input
                            type="text"
                            placeholder="e.g. Cardiology Ward 3B, CCU"
                            className="input text-xs w-full mt-1"
                            value={outcomeDept}
                            onChange={(e) => setOutcomeDept(e.target.value)}
                          />
                        </div>
                      )}

                      {outcomeDisposition === "TRANSFERRED" && (
                        <div>
                          <label className="text-[11px] font-semibold text-navy-900/70">Receiving Facility Name</label>
                          <input
                            type="text"
                            placeholder="e.g. Regional Heart & Lung Institute"
                            className="input text-xs w-full mt-1"
                            value={outcomeFacility}
                            onChange={(e) => setOutcomeFacility(e.target.value)}
                          />
                        </div>
                      )}
                    </div>

                    <div>
                      <label className="text-[11px] font-semibold text-navy-900/70">Clinical Disposition Notes</label>
                      <textarea
                        rows={2}
                        placeholder="Detail clinical condition, stability at handover/discharge, and immediate post-emergency instructions..."
                        className="input text-xs w-full mt-1"
                        value={outcomeNotes}
                        onChange={(e) => setOutcomeNotes(e.target.value)}
                      />
                    </div>

                    {outcome && (
                      <div>
                        <label className="text-[11px] font-semibold text-navy-900/70">Reason for Amendment (Auditable)</label>
                        <input
                          type="text"
                          placeholder="e.g. Condition reassessed after post-cath lab observation"
                          className="input text-xs w-full mt-1"
                          value={outcomeAmendmentReason}
                          onChange={(e) => setOutcomeAmendmentReason(e.target.value)}
                        />
                      </div>
                    )}

                    <div className="flex justify-end pt-2">
                      <button
                        onClick={handleRecordOrAmendOutcome}
                        disabled={recordingOutcome || !outcomeNotes.trim()}
                        className="btn-primary text-xs"
                      >
                        {recordingOutcome ? "Saving..." : outcome ? "Save Outcome Amendment" : "Record Emergency Outcome"}
                      </button>
                    </div>
                  </div>
                </div>

                {/* 2. Evidence-Grounded Discharge Summary & Physician Approval Gate */}
                <div className="card p-6 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-navy-900/10 pb-3">
                    <div>
                      <h3 className="font-display text-base font-bold text-navy-900">
                        Discharge Synthesis & Physician Approval Gate
                      </h3>
                      <p className="text-xs text-navy-900/60">
                        Evidence-grounded continuity document. AI never diagnoses; requires explicit clinician approval.
                      </p>
                    </div>
                    {dischargeSummary && (
                      <span className={`pill ${
                        dischargeSummary.status === "APPROVED"
                          ? "bg-teal-100 text-teal-900"
                          : dischargeSummary.status === "REJECTED"
                          ? "bg-rose-100 text-rose-900"
                          : "bg-amber-100 text-amber-900"
                      } text-xs font-bold`}>
                        {dischargeSummary.status} (v{dischargeSummary.version})
                      </span>
                    )}
                  </div>

                  {dischargeSummary ? (
                    <div className="space-y-4 text-xs">
                      {/* Non-Diagnostic Disclaimer Alert */}
                      <div className="rounded-lg bg-teal-50 border border-teal-200 p-3 text-teal-900 space-y-1">
                        <span className="font-bold uppercase text-[10px] tracking-wider text-teal-800">
                          Evidence-Grounded Clinical Governance
                        </span>
                        <p className="text-[11px] leading-relaxed">{dischargeSummary.non_diagnostic_disclaimer}</p>
                      </div>

                      {/* Warnings if missing data */}
                      {dischargeSummary.missing_data_warnings && dischargeSummary.missing_data_warnings.length > 0 && (
                        <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-amber-900 text-xs">
                          <span className="font-bold">Missing Data Warnings:</span>
                          <ul className="list-disc pl-4 mt-1 space-y-0.5">
                            {dischargeSummary.missing_data_warnings.map((w, idx) => (
                              <li key={idx}>{w}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <span className="font-bold text-navy-900/60 uppercase text-[10px]">Primary Diagnosis</span>
                          <p className="font-semibold text-navy-900 text-sm">{dischargeSummary.primary_diagnosis}</p>

                          <span className="font-bold text-navy-900/60 uppercase text-[10px] block pt-2">Clinical Course</span>
                          <p className="text-navy-900/80 leading-relaxed whitespace-pre-wrap">{dischargeSummary.clinical_course || "Standard clinical protocol observed."}</p>
                        </div>

                        <div className="space-y-2">
                          <span className="font-bold text-navy-900/60 uppercase text-[10px]">Discharge Condition</span>
                          <p className="font-medium text-navy-900">{dischargeSummary.discharge_condition}</p>

                          {dischargeSummary.precautions && dischargeSummary.precautions.length > 0 && (
                            <div>
                              <span className="font-bold text-navy-900/60 uppercase text-[10px] block pt-2">Precautions & Red Flags</span>
                              <div className="flex flex-wrap gap-1 mt-1">
                                {dischargeSummary.precautions.map((p, idx) => (
                                  <span key={idx} className="rounded bg-rose-50 px-2 py-0.5 text-[11px] font-medium text-rose-800 border border-rose-200">
                                    ⚠️ {p}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {dischargeSummary.follow_up_instructions && (
                            <div>
                              <span className="font-bold text-navy-900/60 uppercase text-[10px] block pt-2">Follow-up Instructions</span>
                              <p className="text-navy-900/80">{dischargeSummary.follow_up_instructions}</p>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Evidence Citations */}
                      {dischargeSummary.evidence_citations && dischargeSummary.evidence_citations.length > 0 && (
                        <div className="pt-2 border-t border-navy-900/10">
                          <span className="font-bold text-navy-900/60 uppercase text-[10px]">Evidence Citations</span>
                          <div className="mt-1 space-y-1">
                            {dischargeSummary.evidence_citations.map((c, idx) => (
                              <p key={idx} className="text-[11px] text-navy-900/70 bg-navy-900/[0.02] p-1.5 rounded">
                                <span className="font-semibold text-teal-800">[{c.source}]</span> {c.text}
                              </p>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Physician Approval / Rejection Gate */}
                      {dischargeSummary.status !== "APPROVED" ? (
                        <div className="mt-4 pt-4 border-t border-navy-900/10 rounded-lg bg-teal-900/[0.02] p-4 space-y-3">
                          <h4 className="text-xs font-bold text-navy-900 uppercase">
                            Attending Physician Verification Gate
                          </h4>
                          <p className="text-xs text-navy-900/60">
                            By approving, you attest that you have reviewed this summary, confirmed all clinical facts, and verified the treatment plan.
                          </p>
                          <input
                            type="text"
                            placeholder="Optional approval remarks / clinical addenda..."
                            className="input text-xs w-full"
                            value={dischargeApprovalNotes}
                            onChange={(e) => setDischargeApprovalNotes(e.target.value)}
                          />
                          <div className="flex justify-end gap-2">
                            <button
                              onClick={() => setDischargeRejectionModal(true)}
                              className="rounded-lg bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-100 border border-rose-200"
                            >
                              Reject & Request Revision
                            </button>
                            <button
                              onClick={handleApproveDischarge}
                              disabled={approvingDischarge}
                              className="btn-primary text-xs"
                            >
                              {approvingDischarge ? "Approving..." : "Approve & Sign Discharge Summary"}
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="mt-3 rounded-lg bg-teal-50 border border-teal-200 p-3 text-teal-900 text-xs flex items-center justify-between">
                          <div>
                            <span className="font-bold">✓ Clinically Approved & Signed</span>
                            <p className="text-[11px] text-teal-800 mt-0.5">
                              Approved by {dischargeSummary.approved_by_name || `Doctor #${dischargeSummary.approved_by_doctor_id}`} on {new Date(dischargeSummary.approved_at || "").toLocaleString()}. Integrated into patient Health Timeline.
                            </p>
                          </div>
                          <button
                            onClick={handleGenerateDischargeDraft}
                            disabled={generatingDraft}
                            className="btn-secondary text-xs"
                          >
                            Generate New Version
                          </button>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-center py-6 space-y-3">
                      <p className="text-xs text-navy-900/50 italic">
                        No discharge summary has been synthesized for this case yet.
                      </p>
                      <button
                        onClick={handleGenerateDischargeDraft}
                        disabled={generatingDraft}
                        className="btn-primary text-xs"
                      >
                        {generatingDraft ? "Synthesizing Evidence..." : "Synthesize Discharge Summary Draft"}
                      </button>
                    </div>
                  )}
                </div>

                {/* 3. Medication Reconciliation Table */}
                <div className="card p-6 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-navy-900/10 pb-3">
                    <div>
                      <h3 className="font-display text-base font-bold text-navy-900">
                        Medication Reconciliation & Longitudinal Promotion
                      </h3>
                      <p className="text-xs text-navy-900/60">
                        Explicit CONTINUE, START, STOP, or CHANGE actions. Approved entries update longitudinal patient records.
                      </p>
                    </div>
                    <span className="text-xs font-semibold text-navy-900/60">
                      {medRecs.length} Reconciled Items
                    </span>
                  </div>

                  {medRecs.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-navy-900/10 text-[10px] uppercase font-bold text-navy-900/60">
                            <th className="py-2">Medication</th>
                            <th className="py-2">Dosage & Freq</th>
                            <th className="py-2">Action</th>
                            <th className="py-2">Indication</th>
                            <th className="py-2">Status</th>
                            <th className="py-2 text-right">Verification</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-navy-900/5">
                          {medRecs.map((m) => (
                            <tr key={m.id} className="hover:bg-navy-900/[0.01]">
                              <td className="py-2.5 font-semibold text-navy-900">{m.medication_name}</td>
                              <td className="py-2.5 text-navy-900/70">{m.dosage} ({m.frequency})</td>
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
                                <span className={`text-[10px] font-semibold ${
                                  m.status === "VERIFIED" ? "text-teal-700" : "text-amber-700"
                                }`}>
                                  {m.status}
                                </span>
                              </td>
                              <td className="py-2.5 text-right space-x-1">
                                {m.status === "PROPOSED" ? (
                                  <>
                                    <button
                                      onClick={() => handleVerifyMedRec(m.id, true)}
                                      className="rounded bg-teal-600 px-2 py-0.5 text-[10px] font-semibold text-white hover:bg-teal-700"
                                    >
                                      Verify
                                    </button>
                                    <button
                                      onClick={() => handleVerifyMedRec(m.id, false)}
                                      className="rounded bg-rose-100 px-2 py-0.5 text-[10px] font-semibold text-rose-700 hover:bg-rose-200"
                                    >
                                      Reject
                                    </button>
                                  </>
                                ) : (
                                  <span className="text-[10px] text-teal-800 font-medium">
                                    ✓ Promoted
                                  </span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="text-xs text-navy-900/50 italic py-2">
                      No medication reconciliation entries documented yet.
                    </p>
                  )}

                  {/* Add Medication Reconciliation Form */}
                  <form onSubmit={handleAddMedRec} className="rounded-lg bg-navy-900/[0.01] p-3 border border-dashed border-navy-900/20 space-y-3">
                    <span className="text-xs font-bold uppercase text-navy-900">Add Reconciled Medication</span>
                    <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
                      <input
                        type="text"
                        placeholder="Medication (e.g. Aspirin)"
                        className="input text-xs"
                        value={newMedName}
                        onChange={(e) => setNewMedName(e.target.value)}
                        required
                      />
                      <input
                        type="text"
                        placeholder="Dosage (e.g. 75mg Oral)"
                        className="input text-xs"
                        value={newMedDosage}
                        onChange={(e) => setNewMedDosage(e.target.value)}
                        required
                      />
                      <select
                        className="input text-xs"
                        value={newMedAction}
                        onChange={(e) => setNewMedAction(e.target.value)}
                      >
                        <option value="CONTINUE">CONTINUE (Home med)</option>
                        <option value="START">START (New discharge med)</option>
                        <option value="STOP">STOP (Discontinued)</option>
                        <option value="CHANGE">CHANGE (Dosage modified)</option>
                      </select>
                      <input
                        type="text"
                        placeholder="Indication / Reason"
                        className="input text-xs"
                        value={newMedIndication}
                        onChange={(e) => setNewMedIndication(e.target.value)}
                      />
                    </div>
                    <div className="flex justify-end">
                      <button
                        type="submit"
                        disabled={addingMedRec || !newMedName.trim() || !newMedDosage.trim()}
                        className="btn-secondary text-xs"
                      >
                        {addingMedRec ? "Adding..." : "+ Propose Medication Action"}
                      </button>
                    </div>
                  </form>
                </div>

                {/* 4. Longitudinal Follow-Up Plans */}
                <div className="card p-6 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-navy-900/10 pb-3">
                    <div>
                      <h3 className="font-display text-base font-bold text-navy-900">
                        Longitudinal Follow-Up Care Plans
                      </h3>
                      <p className="text-xs text-navy-900/60">
                        Structured post-emergency continuity appointments and clinical instructions.
                      </p>
                    </div>
                    <span className="text-xs font-semibold text-navy-900/60">
                      {followUps.length} Follow-Up Tasks
                    </span>
                  </div>

                  {followUps.length > 0 ? (
                    <div className="space-y-2">
                      {followUps.map((f) => (
                        <div key={f.id} className="rounded-lg bg-navy-900/[0.02] p-3 border border-navy-900/10 flex flex-wrap items-center justify-between gap-2 text-xs">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-navy-900">{f.specialty}</span>
                              <span className="pill bg-indigo-50 text-indigo-800 text-[10px]">{f.timeframe}</span>
                              <span className={`pill text-[10px] ${
                                f.status === "COMPLETED" ? "bg-teal-100 text-teal-900" : "bg-amber-100 text-amber-900"
                              }`}>
                                {f.status}
                              </span>
                            </div>
                            <p className="text-navy-900/70 mt-1">{f.instructions}</p>
                            {f.provider_name && <p className="text-navy-900/50 text-[11px]">Provider: {f.provider_name}</p>}
                            {f.scheduled_date && <p className="text-navy-900/50 text-[11px]">Target Date: {f.scheduled_date}</p>}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-navy-900/50 italic py-2">
                      No follow-up plans scheduled yet.
                    </p>
                  )}

                  {/* Add Follow-Up Form */}
                  <form onSubmit={handleAddFollowUp} className="rounded-lg bg-navy-900/[0.01] p-3 border border-dashed border-navy-900/20 space-y-3">
                    <span className="text-xs font-bold uppercase text-navy-900">Document Follow-Up Requirement</span>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                      <input
                        type="text"
                        placeholder="Specialty (e.g. Cardiology, Neurology)"
                        className="input text-xs"
                        value={newFuSpecialty}
                        onChange={(e) => setNewFuSpecialty(e.target.value)}
                        required
                      />
                      <input
                        type="text"
                        placeholder="Timeframe (e.g. Within 7 days, 2 weeks)"
                        className="input text-xs"
                        value={newFuTimeframe}
                        onChange={(e) => setNewFuTimeframe(e.target.value)}
                        required
                      />
                      <input
                        type="text"
                        placeholder="Target Provider / Clinic (Optional)"
                        className="input text-xs"
                        value={newFuProvider}
                        onChange={(e) => setNewFuProvider(e.target.value)}
                      />
                    </div>
                    <textarea
                      rows={2}
                      placeholder="Specific follow-up instructions, required repeat labs, and warning signs..."
                      className="input text-xs w-full"
                      value={newFuInstructions}
                      onChange={(e) => setNewFuInstructions(e.target.value)}
                      required
                    />
                    <div className="flex justify-end">
                      <button
                        type="submit"
                        disabled={addingFu || !newFuInstructions.trim()}
                        className="btn-secondary text-xs"
                      >
                        {addingFu ? "Saving..." : "+ Add Follow-Up Plan"}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="card p-12 text-center text-sm text-navy-900/50">
            Select an emergency case from the queue to review patient intelligence and manage referral coordination.
          </div>
        )}
      </div>

      {/* Discharge Summary Rejection Modal */}
      {dischargeRejectionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-900/50 p-4 backdrop-blur-sm">
          <div className="card w-full max-w-md p-6 space-y-4">
            <h3 className="font-display text-base font-bold text-rose-900">
              Reject Discharge Summary Draft
            </h3>
            <p className="text-xs text-navy-900/60">
              Provide clinical justification for rejecting this discharge draft (e.g. Missing post-procedure vitals or inaccurate follow-up instructions).
            </p>
            <textarea
              className="input text-xs w-full"
              rows={3}
              placeholder="Reason for rejection (required)..."
              value={dischargeRejectionReason}
              onChange={(e) => setDischargeRejectionReason(e.target.value)}
              required
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setDischargeRejectionModal(false)} className="btn-secondary text-xs">
                Cancel
              </button>
              <button
                onClick={handleRejectDischarge}
                disabled={!dischargeRejectionReason.trim() || approvingDischarge}
                className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-rose-700"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}

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
