import { useCallback, useEffect, useState } from "react";
import { api, CaseDetail } from "../lib/api";
import { useEmergencyEvents } from "../lib/ws";
import { TYPE_LABEL, priorityLabel } from "../lib/format";
import StatusStepper from "../components/StatusStepper";
import SummaryCard from "../components/SummaryCard";
import ChecklistCard from "../components/ChecklistCard";

export default function DoctorDashboard() {
  const [cases, setCases] = useState<CaseDetail[]>([]);
  const [selected, setSelected] = useState<CaseDetail | null>(null);

  const refresh = useCallback(() => {
    api.get<CaseDetail[]>("/doctor/cases").then((rows) => {
      setCases(rows);
      setSelected((cur) => (cur ? rows.find((r) => r.id === cur.id) || null : rows.find((r) => r.status !== "COMPLETED") || rows[0] || null));
    });
  }, []);
  useEffect(refresh, [refresh]);
  useEmergencyEvents(() => refresh());

  async function toggle(i: number, done: boolean) {
    if (!selected) return;
    await api.post(`/emergency/${selected.id}/checklist`, { index: i, done });
    refresh();
  }

  return (
    <div className="mx-auto max-w-6xl px-5 py-8">
      <h1 className="mb-6 font-display text-xl font-semibold text-navy-900">Assigned cases</h1>
      <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
        <div className="space-y-3">
          {cases.map((c) => {
            const prio = priorityLabel(c.priority);
            return (
              <button key={c.id} onClick={() => setSelected(c)}
                className={`card block w-full p-4 text-left ${selected?.id === c.id ? "ring-2 ring-teal-600" : ""}`}>
                <div className="flex items-center justify-between">
                  <span className="font-medium text-navy-900">{c.patient.full_name}</span>
                  <span className={`pill ${prio.className}`}>{prio.label}</span>
                </div>
                <p className="mt-1 text-sm text-navy-900/60">{TYPE_LABEL[c.emergency_type]} · {c.status.replace(/_/g, " ").toLowerCase()}</p>
              </button>
            );
          })}
          {!cases.length && <p className="card p-4 text-sm text-navy-900/50">No cases assigned yet.</p>}
        </div>
        {selected && (
          <div className="space-y-5">
            <div className="card p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-display text-lg font-semibold text-navy-900">{selected.patient.full_name}</h2>
                <span className="text-sm text-navy-900/60">{selected.patient.age}y · {selected.patient.gender} · {selected.patient.blood_group}</span>
              </div>
              <div className="mt-3"><StatusStepper status={selected.status} /></div>
              <p className="mt-3 text-sm text-navy-900/80"><span className="font-medium">Reported symptoms:</span> {selected.symptoms}</p>
              {selected.patient.emergency_contacts?.[0] && (
                <p className="mt-1 text-sm text-navy-900/60">Contact: {selected.patient.emergency_contacts[0].name} · {selected.patient.emergency_contacts[0].phone}</p>
              )}
            </div>
            <SummaryCard s={selected.ai_summary} />
            {!!selected.checklist?.length && <ChecklistCard items={selected.checklist} onToggle={toggle} />}
          </div>
        )}
      </div>
    </div>
  );
}
