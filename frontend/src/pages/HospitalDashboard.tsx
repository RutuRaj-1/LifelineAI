import { useCallback, useEffect, useState } from "react";
import {
  api,
  CaseDetail,
  DoctorSummary,
  HospitalCapability,
  HospitalDepartment,
  HospitalProfile,
  OperationalResource,
  ResourceHistoryResponse,
  ResourceStatusHistory,
} from "../lib/api";
import { useEmergencyEvents } from "../lib/ws";
import { TYPE_LABEL, priorityLabel, timeAgo } from "../lib/format";
import StatusStepper from "../components/StatusStepper";

interface Resource {
  resource_type: string;
  total: number;
  available: number;
}
interface Scenario {
  key: string;
  title: string;
  emergency_type: string;
}

type TabKey = "queue" | "resources" | "profile" | "departments" | "capabilities";

export default function HospitalDashboard() {
  const [activeTab, setActiveTab] = useState<TabKey>("queue");

  // Queue state
  const [queue, setQueue] = useState<CaseDetail[]>([]);
  const [resources, setResources] = useState<Resource[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selected, setSelected] = useState<CaseDetail | null>(null);
  const [doctors, setDoctors] = useState<DoctorSummary[]>([]);

  // Registry state
  const [profile, setProfile] = useState<HospitalProfile | null>(null);
  const [departments, setDepartments] = useState<HospitalDepartment[]>([]);
  const [capabilities, setCapabilities] = useState<HospitalCapability[]>([]);
  const [loadingRegistry, setLoadingRegistry] = useState(false);
  const [registryMessage, setRegistryMessage] = useState<string | null>(null);

  // Operational Resource Intelligence (Prompt 06)
  const [operationalResources, setOperationalResources] = useState<OperationalResource[]>([]);
  const [resourceFilter, setResourceFilter] = useState<string>("ALL");
  const [attestModalResource, setAttestModalResource] = useState<OperationalResource | null>(null);
  const [attestForm, setAttestForm] = useState({
    staffed_capacity: 0,
    occupied_count: 0,
    maintenance_count: 0,
    operational_status: "FUNCTIONAL",
    status_source: "STAFF_ATTESTED",
    remarks: "",
  });
  const [historyModalResource, setHistoryModalResource] = useState<OperationalResource | null>(null);
  const [historyData, setHistoryData] = useState<ResourceStatusHistory[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Department creation form state
  const [deptForm, setDeptForm] = useState({
    department_name: "",
    department_code: "",
    description: "",
    contact_information: "",
  });
  const [showDeptModal, setShowDeptModal] = useState(false);

  // Capability creation form state
  const [capForm, setCapForm] = useState({
    capability_code: "",
    capability_name: "",
    capability_category: "DIAGNOSTIC",
    department_id: "",
    description: "",
    availability_mode: "24_7" as const,
  });
  const [showCapModal, setShowCapModal] = useState(false);

  // Profile edit state
  const [editingProfile, setEditingProfile] = useState(false);
  const [profileForm, setProfileForm] = useState({
    name: "",
    phone: "",
    contact_email: "",
    hospital_type: "GENERAL",
    address: "",
  });

  const refreshQueue = useCallback(() => {
    api.get<CaseDetail[]>("/hospital/queue").then((rows) => {
      setQueue(rows);
      setSelected((cur) => (cur ? rows.find((r) => r.id === cur.id) || cur : rows[0] || null));
    }).catch(() => {});
    api.get<Resource[]>("/hospital/resources").then(setResources).catch(() => {});
  }, []);

  const loadOperationalResources = useCallback(() => {
    api.get<OperationalResource[]>("/hospital/resources")
      .then((rows) => {
        setOperationalResources(rows);
      })
      .catch(() => {});
  }, []);

  const loadRegistry = useCallback(() => {
    setLoadingRegistry(true);
    Promise.all([
      api.get<HospitalProfile>("/hospital/profile"),
      api.get<HospitalDepartment[]>("/hospital/departments"),
      api.get<HospitalCapability[]>("/hospital/capabilities"),
      api.get<OperationalResource[]>("/hospital/resources"),
    ])
      .then(([prof, depts, caps, resList]) => {
        setProfile(prof);
        setDepartments(depts);
        setCapabilities(caps);
        setOperationalResources(resList);
        setProfileForm({
          name: prof.name || "",
          phone: prof.phone || "",
          contact_email: prof.contact_email || "",
          hospital_type: prof.hospital_type || "GENERAL",
          address: prof.address || "",
        });
      })
      .catch((err) => {
        setRegistryMessage(`Unable to load registry: ${err.message}`);
      })
      .finally(() => setLoadingRegistry(false));
  }, []);

  useEffect(() => {
    refreshQueue();
    loadOperationalResources();
  }, [refreshQueue, loadOperationalResources]);

  useEffect(() => {
    if (activeTab === "resources") {
      loadOperationalResources();
    } else if (activeTab !== "queue") {
      loadRegistry();
    }
  }, [activeTab, loadRegistry, loadOperationalResources]);

  useEmergencyEvents(() => {
    refreshQueue();
    loadOperationalResources();
  });

  useEffect(() => {
    api.get<Scenario[]>("/demo/scenarios").then(setScenarios).catch(() => {});
  }, []);
  useEffect(() => {
    api.get<DoctorSummary[]>("/doctors").then(setDoctors).catch(() => {});
  }, [selected?.id]);

  async function assign(doctorId: number) {
    if (!selected) return;
    await api.post("/doctor/assign", { case_id: selected.id, doctor_id: doctorId });
    refreshQueue();
  }

  async function fireScenario(key: string) {
    try {
      await api.post(`/demo/scenarios/${key}/trigger`);
      refreshQueue();
    } catch {
      // scenario patient may already have active case
    }
  }

  async function handleSaveProfile(e: React.FormEvent) {
    e.preventDefault();
    try {
      const updated = await api.patch<HospitalProfile>("/hospital/profile", profileForm);
      setProfile(updated);
      setEditingProfile(false);
      setRegistryMessage("Hospital profile successfully updated.");
      setTimeout(() => setRegistryMessage(null), 3500);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to update profile");
    }
  }

  async function handleSubmitProfileForReview() {
    if (!confirm("Submit this hospital profile for administrative verification?")) return;
    try {
      await api.post("/hospital/profile/submit");
      loadRegistry();
      setRegistryMessage("Profile submitted for state health administrative review.");
      setTimeout(() => setRegistryMessage(null), 4000);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to submit profile");
    }
  }

  async function handleCreateDepartment(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.post("/hospital/departments", deptForm);
      setShowDeptModal(false);
      setDeptForm({ department_name: "", department_code: "", description: "", contact_information: "" });
      loadRegistry();
      setRegistryMessage("Department added successfully.");
      setTimeout(() => setRegistryMessage(null), 3500);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to create department");
    }
  }

  async function handleDeactivateDepartment(id: number) {
    if (!confirm("Deactivate this department? Existing resources will remain linked for historical audit.")) return;
    try {
      await api.delete(`/hospital/departments/${id}`);
      loadRegistry();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to deactivate department");
    }
  }

  async function handleCreateCapability(e: React.FormEvent) {
    e.preventDefault();
    try {
      const payload = {
        ...capForm,
        department_id: capForm.department_id ? parseInt(capForm.department_id, 10) : undefined,
      };
      await api.post("/hospital/capabilities", payload);
      setShowCapModal(false);
      setCapForm({
        capability_code: "",
        capability_name: "",
        capability_category: "DIAGNOSTIC",
        department_id: "",
        description: "",
        availability_mode: "24_7",
      });
      loadRegistry();
      setRegistryMessage("Clinical capability registered in UNVERIFIED state.");
      setTimeout(() => setRegistryMessage(null), 3500);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to register capability");
    }
  }

  async function handleSubmitCapabilityForReview(id: number) {
    try {
      await api.post(`/hospital/capabilities/${id}/submit-review`);
      loadRegistry();
      setRegistryMessage("Capability submitted for administrative review.");
      setTimeout(() => setRegistryMessage(null), 3500);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to submit capability");
    }
  }

  function openAttestModal(r: OperationalResource) {
    setAttestModalResource(r);
    setAttestForm({
      staffed_capacity: r.staffed_capacity,
      occupied_count: r.occupied_count,
      maintenance_count: r.maintenance_count,
      operational_status: r.operational_status,
      status_source: "STAFF_ATTESTED",
      remarks: "",
    });
  }

  async function handleAttestSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!attestModalResource) return;
    try {
      await api.post(`/hospital/resources/${attestModalResource.id}/attest`, attestForm);
      setAttestModalResource(null);
      loadOperationalResources();
      refreshQueue();
      setRegistryMessage(`Operational attestation recorded for ${attestModalResource.resource_type}.`);
      setTimeout(() => setRegistryMessage(null), 4000);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to submit attestation");
    }
  }

  async function openHistoryModal(r: OperationalResource) {
    setHistoryModalResource(r);
    setLoadingHistory(true);
    try {
      const resp = await api.get<ResourceHistoryResponse>(`/hospital/resources/${r.id}/history`);
      setHistoryData(resp.items);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to fetch history");
    } finally {
      setLoadingHistory(false);
    }
  }

  const filteredResources = operationalResources.filter((r) => {
    if (resourceFilter === "FUNCTIONAL") return r.operational_status === "FUNCTIONAL";
    if (resourceFilter === "FRESH") return r.freshness_status === "FRESH";
    if (resourceFilter === "STALE") return r.freshness_status === "STALE" || r.freshness_status === "UNKNOWN";
    return true;
  });

  return (
    <div className="mx-auto max-w-6xl px-5 py-8">
      {/* Top Banner / Navigation */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-navy-900/10 pb-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-navy-900">
            {profile?.name || "Hospital Command Center"}
          </h1>
          <p className="text-xs text-navy-900/60">
            {profile ? `${profile.city} · Type: ${profile.hospital_type} · Registry: ${profile.status}` : "Emergency Readiness & Hospital Intelligence"}
          </p>
        </div>

        {/* Tab Controls */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setActiveTab("queue")}
            className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
              activeTab === "queue"
                ? "bg-teal-700 text-white shadow-sm"
                : "bg-navy-900/5 text-navy-900/70 hover:bg-navy-900/10"
            }`}
          >
            🚨 Emergency Queue ({queue.length})
          </button>
          <button
            onClick={() => setActiveTab("resources")}
            className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
              activeTab === "resources"
                ? "bg-teal-700 text-white shadow-sm"
                : "bg-navy-900/5 text-navy-900/70 hover:bg-navy-900/10"
            }`}
          >
            🩺 Operational Resources ({operationalResources.length || resources.length})
          </button>
          <button
            onClick={() => setActiveTab("profile")}
            className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
              activeTab === "profile"
                ? "bg-teal-700 text-white shadow-sm"
                : "bg-navy-900/5 text-navy-900/70 hover:bg-navy-900/10"
            }`}
          >
            🏥 Hospital Profile
          </button>
          <button
            onClick={() => setActiveTab("departments")}
            className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
              activeTab === "departments"
                ? "bg-teal-700 text-white shadow-sm"
                : "bg-navy-900/5 text-navy-900/70 hover:bg-navy-900/10"
            }`}
          >
            🏢 Departments ({departments.length})
          </button>
          <button
            onClick={() => setActiveTab("capabilities")}
            className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
              activeTab === "capabilities"
                ? "bg-teal-700 text-white shadow-sm"
                : "bg-navy-900/5 text-navy-900/70 hover:bg-navy-900/10"
            }`}
          >
            ⚡ Capabilities ({capabilities.length})
          </button>
        </div>
      </div>

      {registryMessage && (
        <div className="mb-4 rounded-lg bg-teal-50 p-3 text-xs font-medium text-teal-800 border border-teal-200">
          ℹ️ {registryMessage}
        </div>
      )}

      {/* --- TAB 1: EMERGENCY QUEUE --- */}
      {activeTab === "queue" && (
        <>
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-display text-lg font-semibold text-navy-900">Active Incoming Patients</h2>
            <div className="flex flex-wrap gap-2">
              {scenarios.map((s) => (
                <button
                  key={s.key}
                  onClick={() => fireScenario(s.key)}
                  className="btn-secondary text-xs"
                >
                  ▶ Demo: {TYPE_LABEL[s.emergency_type]}
                </button>
              ))}
            </div>
          </div>

          <div className="mb-6 grid grid-cols-3 gap-3 sm:grid-cols-6">
            {resources.map((r) => (
              <div key={r.resource_type} className="card p-3 text-center">
                <p className="text-lg font-semibold text-navy-900">
                  {r.available}
                  <span className="text-xs text-navy-900/40">/{r.total}</span>
                </p>
                <p className="text-xs text-navy-900/50">{r.resource_type.replace("_", " ")}</p>
              </div>
            ))}
          </div>

          <div className="grid gap-5 lg:grid-cols-[380px_1fr]">
            <div className="space-y-3">
              {queue.map((c) => {
                const prio = priorityLabel(c.priority);
                return (
                  <button
                    key={c.id}
                    onClick={() => setSelected(c)}
                    className={`card block w-full p-4 text-left transition ${
                      selected?.id === c.id ? "ring-2 ring-teal-600 bg-teal-50/20" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-navy-900">{c.patient.full_name}</span>
                      <span className={`pill ${prio.className}`}>{prio.label}</span>
                    </div>
                    <p className="mt-1 text-sm text-navy-900/60">
                      {TYPE_LABEL[c.emergency_type]} · ETA {c.eta_minutes ?? "—"} min
                    </p>
                    <p className="mt-1 text-xs text-navy-900/40">{timeAgo(c.created_at)}</p>
                  </button>
                );
              })}
              {!queue.length && (
                <p className="card p-4 text-sm text-navy-900/50">
                  No active emergencies. Trigger a demo scenario above.
                </p>
              )}
            </div>

            {selected && (
              <div className="card space-y-4 p-6">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h2 className="font-display text-lg font-semibold text-navy-900">
                      {selected.patient.full_name}
                    </h2>
                    <p className="text-sm text-navy-900/60">
                      {selected.patient.age ? `${selected.patient.age}y` : ""} {selected.patient.gender} · {selected.patient.blood_group}
                    </p>
                  </div>
                  <span className={`pill ${priorityLabel(selected.priority).className}`}>
                    {priorityLabel(selected.priority).label}
                  </span>
                </div>
                <StatusStepper status={selected.status} />
                <p className="text-sm text-navy-900/80">
                  <span className="font-medium">Reported symptoms:</span> {selected.symptoms || "—"}</p>

                {selected.checklist && selected.checklist.length > 0 && (
                  <div>
                    <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-navy-900/50">Checklist</p>
                    <ul className="space-y-1">
                      {selected.checklist.map((it, i) => (
                        <li key={i} className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={it.done}
                            onChange={async (e) => {
                              await api.post(`/emergency/${selected.id}/checklist`, { index: i, done: e.target.checked });
                              refreshQueue();
                            }}
                            className="h-4 w-4 rounded border-navy-900/30 text-teal-600"
                          />
                          <span className={it.done ? "text-navy-900/40 line-through" : "text-navy-900"}>{it.item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {!selected.doctor && (
                  <div>
                    <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-navy-900/50">Assign a doctor</p>
                    <div className="flex flex-wrap gap-2">
                      {doctors.filter((d) => d.is_available).map((d) => (
                        <button key={d.id} onClick={() => assign(d.id)} className="btn-secondary text-xs">
                          {d.name} · {d.specialty}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {selected.status !== "COMPLETED" && (
                  <button
                    className="btn-secondary"
                    onClick={async () => {
                      await api.post(`/emergency/${selected.id}/complete`);
                      refreshQueue();
                    }}
                  >
                    Mark case complete
                  </button>
                )}
              </div>
            )}
          </div>
        </>
      )}

      {/* --- TAB 2: OPERATIONAL RESOURCES (Prompt 06) --- */}
      {activeTab === "resources" && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="font-display text-xl font-bold text-navy-900">Live Resource Availability & Readiness</h2>
              <p className="text-xs text-navy-900/60">
                Staffed capacity, active emergency holds, maintenance deductions, and freshness audit trails.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-navy-900/60 font-medium">Filter:</span>
              <select
                value={resourceFilter}
                onChange={(e) => setResourceFilter(e.target.value)}
                className="rounded border border-navy-900/20 p-1.5 text-xs bg-white text-navy-900"
              >
                <option value="ALL">All Resources ({operationalResources.length})</option>
                <option value="FUNCTIONAL">Functional Only</option>
                <option value="FRESH">Fresh Attestation Only</option>
                <option value="STALE">Stale / Unverified Only</option>
              </select>
              <button onClick={loadOperationalResources} className="btn-secondary text-xs">
                🔄 Refresh
              </button>
            </div>
          </div>

          <div className="rounded-lg bg-teal-50 p-3.5 text-xs text-teal-900 border border-teal-200">
            <strong>Clinical Safety Principle:</strong> A vacant bed is not automatically usable.
            Usable capacity is calculated strictly as: <span className="font-mono font-semibold">Usable = Staffed - Occupied - Maintenance - Active Holds</span>.
            Resources with expired freshness windows require staff re-attestation before accepting emergency referrals.
          </div>

          {/* Operational Resources Cards Grid */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredResources.map((r) => {
              const isFresh = r.freshness_status === "FRESH";
              const isSuspended = r.freshness_status === "SUSPENDED" || r.operational_status === "MAINTENANCE";
              return (
                <div key={r.id} className="card p-5 space-y-4 border border-navy-900/10">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="font-display text-base font-bold text-navy-900">
                        {r.resource_type.replace(/_/g, " ")}
                      </h3>
                      <p className="text-[11px] text-navy-900/60">
                        Dept: {r.department_name || "General Facility"}
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <span
                        className={`pill text-[10px] font-semibold ${
                          isFresh
                            ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                            : isSuspended
                            ? "bg-red-100 text-red-800 border border-red-300"
                            : "bg-amber-100 text-amber-800 border border-amber-300"
                        }`}
                      >
                        {r.freshness_status}
                      </span>
                      <span className="text-[10px] text-navy-900/50">
                        Status: {r.operational_status}
                      </span>
                    </div>
                  </div>

                  {/* Capacity Dashboard Stats */}
                  <div className="rounded-lg bg-slate-50 p-3 border border-slate-200 grid grid-cols-2 gap-2 text-center">
                    <div className="border-r border-slate-200 pr-2">
                      <p className="text-2xl font-bold text-teal-700">{r.usable_capacity}</p>
                      <p className="text-[10px] uppercase font-semibold text-navy-900/60">Usable Now</p>
                    </div>
                    <div className="pl-2">
                      <p className="text-lg font-semibold text-navy-900">{r.staffed_capacity}<span className="text-xs text-navy-900/40">/{r.physical_capacity}</span></p>
                      <p className="text-[10px] uppercase font-semibold text-navy-900/60">Staffed / Total</p>
                    </div>
                  </div>

                  {/* Deductions Breakdown */}
                  <div className="space-y-1 text-xs text-navy-900/70 border-t border-navy-900/10 pt-2">
                    <div className="flex justify-between">
                      <span>Occupied Beds / Units:</span>
                      <span className="font-medium">{r.occupied_count}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Under Maintenance:</span>
                      <span className="font-medium text-amber-700">{r.maintenance_count}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Active Referral Holds:</span>
                      <span className="font-medium text-teal-700">{r.active_reserved_holds}</span>
                    </div>
                    <div className="flex justify-between text-[11px] text-navy-900/50 pt-1">
                      <span>Last Attested:</span>
                      <span>{r.last_verified_at ? timeAgo(r.last_verified_at) : "Never"} ({r.status_source})</span>
                    </div>
                  </div>

                  {/* Action Controls */}
                  <div className="flex gap-2 pt-2 border-t border-navy-900/10">
                    <button
                      onClick={() => openAttestModal(r)}
                      className="btn-primary text-xs flex-1 text-center"
                    >
                      ✍️ Attest Status
                    </button>
                    <button
                      onClick={() => openHistoryModal(r)}
                      className="btn-secondary text-xs flex-1 text-center"
                    >
                      📜 Audit History
                    </button>
                  </div>
                </div>
              );
            })}
            {!filteredResources.length && (
              <p className="card p-6 text-sm text-navy-900/50 sm:col-span-3 text-center">
                No resources match the selected filter.
              </p>
            )}
          </div>

          {/* Attestation Modal */}
          {attestModalResource && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-900/40 backdrop-blur-sm p-4">
              <div className="card w-full max-w-lg p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-navy-900/10 pb-3">
                  <div>
                    <h3 className="font-display text-lg font-bold text-navy-900">
                      Attest Operational Capacity
                    </h3>
                    <p className="text-xs text-navy-900/60">
                      Resource: {attestModalResource.resource_type} (Physical: {attestModalResource.physical_capacity})
                    </p>
                  </div>
                  <button
                    onClick={() => setAttestModalResource(null)}
                    className="text-navy-900/50 hover:text-navy-900 text-sm font-bold"
                  >
                    ✕
                  </button>
                </div>

                <form onSubmit={handleAttestSubmit} className="space-y-4">
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="text-xs font-semibold text-navy-900">Staffed Capacity</label>
                      <input
                        type="number"
                        min="0"
                        max={attestModalResource.physical_capacity}
                        value={attestForm.staffed_capacity}
                        onChange={(e) => setAttestForm({ ...attestForm, staffed_capacity: parseInt(e.target.value, 10) || 0 })}
                        className="mt-1 w-full rounded border border-navy-900/20 p-2 text-sm text-center"
                        required
                      />
                      <p className="text-[10px] text-navy-900/40 mt-0.5">Max: {attestModalResource.physical_capacity}</p>
                    </div>

                    <div>
                      <label className="text-xs font-semibold text-navy-900">Occupied Units</label>
                      <input
                        type="number"
                        min="0"
                        value={attestForm.occupied_count}
                        onChange={(e) => setAttestForm({ ...attestForm, occupied_count: parseInt(e.target.value, 10) || 0 })}
                        className="mt-1 w-full rounded border border-navy-900/20 p-2 text-sm text-center"
                        required
                      />
                    </div>

                    <div>
                      <label className="text-xs font-semibold text-navy-900">Under Maintenance</label>
                      <input
                        type="number"
                        min="0"
                        value={attestForm.maintenance_count}
                        onChange={(e) => setAttestForm({ ...attestForm, maintenance_count: parseInt(e.target.value, 10) || 0 })}
                        className="mt-1 w-full rounded border border-navy-900/20 p-2 text-sm text-center"
                        required
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-navy-900">Operational Status</label>
                    <select
                      value={attestForm.operational_status}
                      onChange={(e) => setAttestForm({ ...attestForm, operational_status: e.target.value })}
                      className="mt-1 w-full rounded border border-navy-900/20 p-2 text-sm bg-white"
                    >
                      <option value="FUNCTIONAL">Functional (Fully Operational)</option>
                      <option value="LIMITED">Limited (Staffed with Constraints)</option>
                      <option value="MAINTENANCE">Maintenance (Offline for Servicing)</option>
                      <option value="NON_OPERATIONAL">Non-Operational (Emergency Divert)</option>
                      <option value="UNSTAFFED">Unstaffed (No Clinical Personnel)</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-navy-900">Attestation Rationale / Remarks</label>
                    <textarea
                      placeholder="e.g. Shift turnover completed, 2 beds sanitized and ready for triage..."
                      value={attestForm.remarks}
                      onChange={(e) => setAttestForm({ ...attestForm, remarks: e.target.value })}
                      className="mt-1 w-full rounded border border-navy-900/20 p-2 text-xs"
                      rows={2}
                    />
                  </div>

                  {/* Live Formula Preview */}
                  <div className="rounded bg-teal-50/60 p-2.5 text-xs text-teal-900 border border-teal-200">
                    <span className="font-semibold">Calculated Usable Capacity: </span>
                    <span className="font-mono font-bold text-sm">
                      {attestForm.operational_status === "FUNCTIONAL" || attestForm.operational_status === "LIMITED"
                        ? Math.max(0, attestForm.staffed_capacity - attestForm.occupied_count - attestForm.maintenance_count - attestModalResource.active_reserved_holds)
                        : 0}
                    </span>
                    <span className="text-[11px] text-navy-900/60 block mt-0.5">
                      Formula: {attestForm.staffed_capacity} (staffed) - {attestForm.occupied_count} (occupied) - {attestForm.maintenance_count} (maint) - {attestModalResource.active_reserved_holds} (holds)
                    </span>
                  </div>

                  <div className="flex justify-end gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setAttestModalResource(null)}
                      className="btn-secondary text-xs"
                    >
                      Cancel
                    </button>
                    <button type="submit" className="btn-primary text-xs">
                      Submit Official Attestation
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Audit History Modal */}
          {historyModalResource && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-900/40 backdrop-blur-sm p-4">
              <div className="card w-full max-w-2xl p-6 space-y-4 max-h-[85vh] flex flex-col">
                <div className="flex items-center justify-between border-b border-navy-900/10 pb-3">
                  <div>
                    <h3 className="font-display text-lg font-bold text-navy-900">
                      Audit Trail: {historyModalResource.resource_type}
                    </h3>
                    <p className="text-xs text-navy-900/60">
                      Immutable append-only log of historical capacity attestations.
                    </p>
                  </div>
                  <button
                    onClick={() => setHistoryModalResource(null)}
                    className="text-navy-900/50 hover:text-navy-900 text-sm font-bold"
                  >
                    ✕
                  </button>
                </div>

                <div className="overflow-y-auto space-y-2 flex-1 pr-1">
                  {loadingHistory && <p className="text-xs text-navy-900/50 p-4 text-center">Loading audit history...</p>}
                  {!loadingHistory && !historyData.length && (
                    <p className="text-xs text-navy-900/50 p-6 text-center">No previous attestation history found.</p>
                  )}
                  {historyData.map((h) => (
                    <div key={h.id} className="p-3 bg-slate-50 rounded border border-slate-200 text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-navy-900">
                          {h.previous_status || "INIT"} ➔ {h.new_status}
                        </span>
                        <span className="text-[11px] text-navy-900/40">
                          {h.created_at ? new Date(h.created_at).toLocaleString() : "—"}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-navy-900/70">
                        <span>Capacity: <span className="font-mono">{h.previous_available_count ?? "—"} ➔ {h.new_available_count}</span></span>
                        <span>Source: <span className="pill text-[9px]">{h.verification_source}</span></span>
                        {h.verified_by_user_id && <span>Staff ID: #{h.verified_by_user_id}</span>}
                      </div>
                      {h.remarks && <p className="text-[11px] text-navy-900/60 italic">"{h.remarks}"</p>}
                    </div>
                  ))}
                </div>

                <div className="border-t border-navy-900/10 pt-3 flex justify-end">
                  <button
                    onClick={() => setHistoryModalResource(null)}
                    className="btn-secondary text-xs"
                  >
                    Close History
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* --- TAB 3: HOSPITAL PROFILE --- */}
      {activeTab === "profile" && (
        <div className="card space-y-6 p-6">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-navy-900/10 pb-4">
            <div>
              <h2 className="font-display text-xl font-bold text-navy-900">Hospital Institutional Registry</h2>
              <p className="text-xs text-navy-900/60">
                Official establishment details registered in state referral network.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`pill ${
                  profile?.status === "VERIFIED"
                    ? "bg-green-100 text-green-800"
                    : profile?.status === "UNDER_REVIEW"
                    ? "bg-amber-100 text-amber-800"
                    : "bg-slate-100 text-slate-700"
                }`}
              >
                Verification: {profile?.status || "UNKNOWN"}
              </span>
              {profile?.status !== "VERIFIED" && profile?.status !== "UNDER_REVIEW" && (
                <button onClick={handleSubmitProfileForReview} className="btn-primary text-xs">
                  Submit for Verification
                </button>
              )}
            </div>
          </div>

          {editingProfile ? (
            <form onSubmit={handleSaveProfile} className="grid max-w-xl gap-4">
              <div>
                <label className="text-xs font-semibold text-navy-900">Hospital Name</label>
                <input
                  type="text"
                  value={profileForm.name}
                  onChange={(e) => setProfileForm({ ...profileForm, name: e.target.value })}
                  className="mt-1 w-full rounded border border-navy-900/20 p-2 text-sm"
                  required
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-navy-900">Hospital Type</label>
                <select
                  value={profileForm.hospital_type}
                  onChange={(e) => setProfileForm({ ...profileForm, hospital_type: e.target.value })}
                  className="mt-1 w-full rounded border border-navy-900/20 p-2 text-sm"
                >
                  <option value="GENERAL">General Hospital</option>
                  <option value="TERTIARY_CARE">Tertiary Care Center</option>
                  <option value="TRAUMA_CENTER">Level 1 Trauma Center</option>
                  <option value="SPECIALTY">Specialty Hospital</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-semibold text-navy-900">Contact Email</label>
                <input
                  type="email"
                  value={profileForm.contact_email}
                  onChange={(e) => setProfileForm({ ...profileForm, contact_email: e.target.value })}
                  className="mt-1 w-full rounded border border-navy-900/20 p-2 text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-navy-900">Emergency Phone</label>
                <input
                  type="text"
                  value={profileForm.phone}
                  onChange={(e) => setProfileForm({ ...profileForm, phone: e.target.value })}
                  className="mt-1 w-full rounded border border-navy-900/20 p-2 text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-navy-900">Full Address</label>
                <input
                  type="text"
                  value={profileForm.address}
                  onChange={(e) => setProfileForm({ ...profileForm, address: e.target.value })}
                  className="mt-1 w-full rounded border border-navy-900/20 p-2 text-sm"
                />
              </div>
              <div className="flex gap-2">
                <button type="submit" className="btn-primary text-xs">Save Changes</button>
                <button type="button" onClick={() => setEditingProfile(false)} className="btn-secondary text-xs">Cancel</button>
              </div>
            </form>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2 text-sm">
                <p><span className="font-semibold text-navy-900">Hospital ID:</span> {profile?.id}</p>
                <p><span className="font-semibold text-navy-900">Name:</span> {profile?.name}</p>
                <p><span className="font-semibold text-navy-900">Type:</span> {profile?.hospital_type}</p>
                <p><span className="font-semibold text-navy-900">Contact Email:</span> {profile?.contact_email || "—"}</p>
                <p><span className="font-semibold text-navy-900">Emergency Contact:</span> {profile?.phone || "—"}</p>
              </div>
              <div className="space-y-2 text-sm">
                <p><span className="font-semibold text-navy-900">City / Region:</span> {profile?.city}</p>
                <p><span className="font-semibold text-navy-900">Address:</span> {profile?.address}</p>
                <p><span className="font-semibold text-navy-900">Coordinates:</span> {profile?.lat}, {profile?.lng}</p>
                <p><span className="font-semibold text-navy-900">Active Departments:</span> {profile?.department_count}</p>
                <p><span className="font-semibold text-navy-900">Registered Capabilities:</span> {profile?.capability_count}</p>
              </div>
              <div className="sm:col-span-2 pt-2">
                <button onClick={() => setEditingProfile(true)} className="btn-secondary text-xs">
                  ✏️ Edit Profile Information
                </button>
              </div>
            </div>
          )}

          {profile?.verification_notes && (
            <div className="rounded-lg bg-slate-50 p-3 text-xs text-navy-900/70 border border-slate-200">
              <span className="font-semibold">Reviewer Audit Notes:</span> {profile.verification_notes}
            </div>
          )}
        </div>
      )}

      {/* --- TAB 4: DEPARTMENTS WORKSPACE --- */}
      {activeTab === "departments" && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="font-display text-xl font-bold text-navy-900">Department Hierarchy</h2>
              <p className="text-xs text-navy-900/60">
                Institutional clinical departments and organizational divisions.
              </p>
            </div>
            <button onClick={() => setShowDeptModal(true)} className="btn-primary text-xs">
              + Add Department
            </button>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {departments.map((d) => (
              <div key={d.id} className="card p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-navy-900">{d.department_name}</span>
                  <span
                    className={`pill text-[10px] ${
                      d.operational_status === "ACTIVE"
                        ? "bg-green-100 text-green-800"
                        : "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {d.operational_status}
                  </span>
                </div>
                <p className="font-mono text-xs text-teal-700 bg-teal-50 inline-block px-1.5 py-0.5 rounded">
                  CODE: {d.department_code}
                </p>
                <p className="text-xs text-navy-900/70">{d.description || "No description provided."}</p>
                {d.contact_information && (
                  <p className="text-xs text-navy-900/50">📞 {d.contact_information}</p>
                )}
                {d.operational_status === "ACTIVE" && (
                  <div className="pt-2">
                    <button
                      onClick={() => handleDeactivateDepartment(d.id)}
                      className="text-[11px] font-medium text-red-600 hover:underline"
                    >
                      Deactivate
                    </button>
                  </div>
                )}
              </div>
            ))}
            {!departments.length && (
              <p className="card p-6 text-sm text-navy-900/50 sm:col-span-3 text-center">
                No departments registered yet. Use the button above to create one.
              </p>
            )}
          </div>

          {/* Add Department Modal */}
          {showDeptModal && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-900/40 backdrop-blur-sm p-4">
              <div className="card w-full max-w-md p-6 space-y-4">
                <h3 className="font-display text-lg font-bold text-navy-900">Add Clinical Department</h3>
                <form onSubmit={handleCreateDepartment} className="space-y-3">
                  <div>
                    <label className="text-xs font-semibold text-navy-900">Department Name</label>
                    <input
                      type="text"
                      placeholder="e.g. Cardiology & Cath Lab"
                      value={deptForm.department_name}
                      onChange={(e) => setDeptForm({ ...deptForm, department_name: e.target.value })}
                      className="mt-1 w-full rounded border border-navy-900/20 p-2 text-xs"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-navy-900">Department Code (Unique)</label>
                    <input
                      type="text"
                      placeholder="e.g. CARDIO"
                      value={deptForm.department_code}
                      onChange={(e) => setDeptForm({ ...deptForm, department_code: e.target.value })}
                      className="mt-1 w-full rounded border border-navy-900/20 p-2 text-xs uppercase"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-navy-900">Description</label>
                    <textarea
                      placeholder="Scope of clinical care..."
                      value={deptForm.description}
                      onChange={(e) => setDeptForm({ ...deptForm, description: e.target.value })}
                      className="mt-1 w-full rounded border border-navy-900/20 p-2 text-xs"
                      rows={2}
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-navy-900">Internal Extension / Phone</label>
                    <input
                      type="text"
                      placeholder="e.g. Ext 4210"
                      value={deptForm.contact_information}
                      onChange={(e) => setDeptForm({ ...deptForm, contact_information: e.target.value })}
                      className="mt-1 w-full rounded border border-navy-900/20 p-2 text-xs"
                    />
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <button type="button" onClick={() => setShowDeptModal(false)} className="btn-secondary text-xs">
                      Cancel
                    </button>
                    <button type="submit" className="btn-primary text-xs">
                      Save Department
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      )}

      {/* --- TAB 5: CAPABILITIES WORKSPACE --- */}
      {activeTab === "capabilities" && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="font-display text-xl font-bold text-navy-900">Registered Clinical Capabilities</h2>
              <p className="text-xs text-navy-900/60">
                Institutional clinical service readiness claims and administrative verification statuses.
              </p>
            </div>
            <button onClick={() => setShowCapModal(true)} className="btn-primary text-xs">
              + Register Capability
            </button>
          </div>

          <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900 border border-amber-200">
            ⚠️ <strong>Clinical Notice:</strong> A registered capability demonstrates verified clinical capacity
            to deliver a specialized pathway. It does <em>not</em> represent real-time staffed bed or operative availability.
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {capabilities.map((c) => (
              <div key={c.id} className="card p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-navy-900">{c.capability_name}</span>
                  <span
                    className={`pill text-[10px] ${
                      c.verification_status === "VERIFIED"
                        ? "bg-green-100 text-green-800"
                        : c.verification_status === "PENDING_REVIEW"
                        ? "bg-amber-100 text-amber-800"
                        : "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {c.verification_status}
                  </span>
                </div>

                <div className="flex flex-wrap gap-1 text-[11px]">
                  <span className="rounded bg-navy-900/5 px-1.5 py-0.5 text-navy-900/70">
                    Category: {c.capability_category}
                  </span>
                  <span className="rounded bg-teal-50 px-1.5 py-0.5 text-teal-700">
                    Mode: {c.availability_mode}
                  </span>
                </div>

                <p className="text-xs text-navy-900/70">{c.description || "No description provided."}</p>

                {c.department_name && (
                  <p className="text-[11px] text-navy-900/50">🏢 Dept: {c.department_name}</p>
                )}

                {c.verification_status === "UNVERIFIED" && (
                  <div className="pt-2 border-t border-navy-900/10">
                    <button
                      onClick={() => handleSubmitCapabilityForReview(c.id)}
                      className="btn-secondary text-[11px] w-full"
                    >
                      Submit for Verification
                    </button>
                  </div>
                )}
              </div>
            ))}
            {!capabilities.length && (
              <p className="card p-6 text-sm text-navy-900/50 sm:col-span-3 text-center">
                No clinical capabilities registered yet. Register institutional capabilities using the button above.
              </p>
            )}
          </div>

          {/* Add Capability Modal */}
          {showCapModal && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-900/40 backdrop-blur-sm p-4">
              <div className="card w-full max-w-md p-6 space-y-4">
                <h3 className="font-display text-lg font-bold text-navy-900">Register Clinical Capability</h3>
                <form onSubmit={handleCreateCapability} className="space-y-3">
                  <div>
                    <label className="text-xs font-semibold text-navy-900">Capability Code</label>
                    <input
                      type="text"
                      placeholder="e.g. CATH_LAB_PRIMARY_PCI"
                      value={capForm.capability_code}
                      onChange={(e) => setCapForm({ ...capForm, capability_code: e.target.value })}
                      className="mt-1 w-full rounded border border-navy-900/20 p-2 text-xs uppercase"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-navy-900">Capability Name</label>
                    <input
                      type="text"
                      placeholder="e.g. Primary Percutaneous Coronary Intervention"
                      value={capForm.capability_name}
                      onChange={(e) => setCapForm({ ...capForm, capability_name: e.target.value })}
                      className="mt-1 w-full rounded border border-navy-900/20 p-2 text-xs"
                      required
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-xs font-semibold text-navy-900">Category</label>
                      <select
                        value={capForm.capability_category}
                        onChange={(e) => setCapForm({ ...capForm, capability_category: e.target.value })}
                        className="mt-1 w-full rounded border border-navy-900/20 p-2 text-xs"
                      >
                        <option value="DIAGNOSTIC">Diagnostic</option>
                        <option value="SURGICAL">Surgical</option>
                        <option value="CRITICAL_CARE">Critical Care</option>
                        <option value="STABILIZATION">Stabilization</option>
                        <option value="CARDIOLOGY">Cardiology</option>
                        <option value="NEUROLOGY">Neurology</option>
                        <option value="TRAUMA_CARE">Trauma Care</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-semibold text-navy-900">Availability Mode</label>
                      <select
                        value={capForm.availability_mode}
                        onChange={(e) => setCapForm({ ...capForm, availability_mode: e.target.value as any })}
                        className="mt-1 w-full rounded border border-navy-900/20 p-2 text-xs"
                      >
                        <option value="24_7">24/7 Available</option>
                        <option value="ON_CALL">On-Call Specialist</option>
                        <option value="BUSINESS_HOURS">Business Hours Only</option>
                        <option value="CONDITIONAL">Conditional</option>
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-navy-900">Associated Department (Optional)</label>
                    <select
                      value={capForm.department_id}
                      onChange={(e) => setCapForm({ ...capForm, department_id: e.target.value })}
                      className="mt-1 w-full rounded border border-navy-900/20 p-2 text-xs"
                    >
                      <option value="">None (Hospital Wide)</option>
                      {departments.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.department_name} ({d.department_code})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-navy-900">Clinical Scope / Description</label>
                    <textarea
                      placeholder="Protocol, diagnostic equipment, or specialist coverage..."
                      value={capForm.description}
                      onChange={(e) => setCapForm({ ...capForm, description: e.target.value })}
                      className="mt-1 w-full rounded border border-navy-900/20 p-2 text-xs"
                      rows={2}
                    />
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <button type="button" onClick={() => setShowCapModal(false)} className="btn-secondary text-xs">
                      Cancel
                    </button>
                    <button type="submit" className="btn-primary text-xs">
                      Register Capability
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
