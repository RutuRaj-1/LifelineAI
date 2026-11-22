import { useCallback, useEffect, useState } from "react";
import {
  api,
  CaseDetail,
  DoctorSummary,
  HospitalCapability,
  HospitalDepartment,
  HospitalProfile,
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

type TabKey = "queue" | "profile" | "departments" | "capabilities";

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

  const loadRegistry = useCallback(() => {
    setLoadingRegistry(true);
    Promise.all([
      api.get<HospitalProfile>("/hospital/profile"),
      api.get<HospitalDepartment[]>("/hospital/departments"),
      api.get<HospitalCapability[]>("/hospital/capabilities"),
    ])
      .then(([prof, depts, caps]) => {
        setProfile(prof);
        setDepartments(depts);
        setCapabilities(caps);
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
  }, [refreshQueue]);

  useEffect(() => {
    if (activeTab !== "queue") {
      loadRegistry();
    }
  }, [activeTab, loadRegistry]);

  useEmergencyEvents(() => refreshQueue());
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

  return (
    <div className="mx-auto max-w-6xl px-5 py-8">
      {/* Top Banner / Navigation */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-navy-900/10 pb-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-navy-900">
            {profile?.name || "Hospital Command Center"}
          </h1>
          <p className="text-xs text-navy-900/60">
            {profile ? `${profile.city} · Type: ${profile.hospital_type} · Status: ${profile.status}` : "Emergency Readiness & Hospital Intelligence"}
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
                  <span className="font-medium">Reported symptoms:</span> {selected.symptoms || "—"}
                </p>

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

      {/* --- TAB 2: HOSPITAL PROFILE --- */}
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

      {/* --- TAB 3: DEPARTMENTS WORKSPACE --- */}
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

          {/* Department List */}
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

      {/* --- TAB 4: CAPABILITIES WORKSPACE --- */}
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
