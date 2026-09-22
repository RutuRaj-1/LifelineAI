import { useCallback, useEffect, useState } from "react";
import { api, CaseDetail, DoctorSummary } from "../lib/api";
import { useEmergencyEvents } from "../lib/ws";
import { TYPE_LABEL, priorityLabel, timeAgo } from "../lib/format";
import StatusStepper from "../components/StatusStepper";

interface Resource { resource_type: string; total: number; available: number; }
interface Scenario { key: string; title: string; emergency_type: string; }

export default function HospitalDashboard() {
  const [queue, setQueue] = useState<CaseDetail[]>([]);
  const [resources, setResources] = useState<Resource[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selected, setSelected] = useState<CaseDetail | null>(null);
  const [doctors, setDoctors] = useState<DoctorSummary[]>([]);

  const refresh = useCallback(() => {
    api.get<CaseDetail[]>("/hospital/queue").then((rows) => {
      setQueue(rows);
      setSelected((cur) => (cur ? rows.find((r) => r.id === cur.id) || cur : rows[0] || null));
    });
    api.get<Resource[]>("/hospital/resources").then(setResources);
  }, []);
  useEffect(refresh, [refresh]);
  useEmergencyEvents(() => refresh());
  useEffect(() => { api.get<Scenario[]>("/demo/scenarios").then(setScenarios).catch(() => {}); }, []);
  useEffect(() => { api.get<DoctorSummary[]>("/doctors").then(setDoctors).catch(() => {}); }, [selected?.id]);

  async function assign(doctorId: number) {
    if (!selected) return;
    await api.post("/doctor/assign", { case_id: selected.id, doctor_id: doctorId });
    refresh();
  }

  async function fireScenario(key: string) {
    try { await api.post(`/demo/scenarios/${key}/trigger`); refresh(); }
    catch { /* scenario patient may already have an active case - fine for a demo */ }
  }

  return (
    <div className="mx-auto max-w-6xl px-5 py-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-xl font-semibold text-navy-900">Emergency queue</h1>
        <div className="flex flex-wrap gap-2">
          {scenarios.map((s) => (
            <button key={s.key} onClick={() => fireScenario(s.key)} className="btn-secondary text-xs">
              ▶ Demo: {TYPE_LABEL[s.emergency_type]}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-6 grid grid-cols-3 gap-3 sm:grid-cols-6">
        {resources.map((r) => (
          <div key={r.resource_type} className="card p-3 text-center">
            <p className="text-lg font-semibold text-navy-900">{r.available}<span className="text-xs text-navy-900/40">/{r.total}</span></p>
            <p className="text-xs text-navy-900/50">{r.resource_type.replace("_", " ")}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-5 lg:grid-cols-[380px_1fr]">
        <div className="space-y-3">
          {queue.map((c) => {
            const prio = priorityLabel(c.priority);
            return (
              <button key={c.id} onClick={() => setSelected(c)}
                className={`card block w-full p-4 text-left ${selected?.id === c.id ? "ring-2 ring-teal-600" : ""}`}>
                <div className="flex items-center justify-between">
                  <span className="font-medium text-navy-900">{c.patient.full_name}</span>
                  <span className={`pill ${prio.className}`}>{prio.label}</span>
                </div>
                <p className="mt-1 text-sm text-navy-900/60">{TYPE_LABEL[c.emergency_type]} · ETA {c.eta_minutes ?? "—"} min</p>
                <p className="mt-1 text-xs text-navy-900/40">{timeAgo(c.created_at)}</p>
              </button>
            );
          })}
          {!queue.length && <p className="card p-4 text-sm text-navy-900/50">No active emergencies. Trigger a demo scenario above.</p>}
        </div>

        {selected && (
          <div className="card space-y-4 p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="font-display text-lg font-semibold text-navy-900">{selected.patient.full_name}</h2>
                <p className="text-sm text-navy-900/60">{selected.patient.age ? `${selected.patient.age}y` : ""} {selected.patient.gender} · {selected.patient.blood_group}</p>
              </div>
              <span className={`pill ${priorityLabel(selected.priority).className}`}>{priorityLabel(selected.priority).label}</span>
            </div>
            <StatusStepper status={selected.status} />
            <p className="text-sm text-navy-900/80"><span className="font-medium">Reported symptoms:</span> {selected.symptoms || "—"}</p>

            {selected.checklist && selected.checklist.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-navy-900/50">Checklist</p>
                <ul className="space-y-1">
                  {selected.checklist.map((it, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm">
                      <input type="checkbox" checked={it.done} onChange={async (e) => {
                        await api.post(`/emergency/${selected.id}/checklist`, { index: i, done: e.target.checked });
                        refresh();
                      }} className="h-4 w-4 rounded border-navy-900/30 text-teal-600" />
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
              <button className="btn-secondary" onClick={async () => { await api.post(`/emergency/${selected.id}/complete`); refresh(); }}>
                Mark case complete
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
