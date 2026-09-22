import { useCallback, useEffect, useState } from "react";
import { api, CaseDetail, TimelineEntry } from "../lib/api";
import { useEmergencyEvents } from "../lib/ws";
import { TYPE_LABEL, timeAgo } from "../lib/format";
import StatusStepper from "../components/StatusStepper";
import EtaCard from "../components/EtaCard";

export default function FamilyPortal() {
  const [active, setActive] = useState<CaseDetail | null | undefined>(undefined);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);

  const refresh = useCallback(() => {
    api.get<CaseDetail | null>("/emergency/active").then(setActive).catch(() => setActive(null));
  }, []);
  useEffect(refresh, [refresh]);
  useEmergencyEvents(() => refresh());

  useEffect(() => {
    if (!active) return;
    api.get<TimelineEntry[]>(`/emergency/${active.id}/timeline`).then(setTimeline).catch(() => {});
  }, [active?.id, active?.updated_at]);

  if (active === undefined) return null;

  if (!active) {
    return (
      <div className="mx-auto max-w-2xl px-5 py-16 text-center">
        <p className="text-3xl" aria-hidden>🫀</p>
        <h1 className="mt-3 font-display text-xl font-semibold text-navy-900">No active emergency</h1>
        <p className="mt-2 text-sm text-navy-900/60">You'll see live tracking here the moment your linked patient triggers an SOS.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5 px-5 py-8">
      <div className="card p-5">
        <h1 className="font-display text-lg font-semibold text-navy-900">{active.patient.full_name} · {TYPE_LABEL[active.emergency_type]}</h1>
        <div className="mt-3"><StatusStepper status={active.status} /></div>
      </div>
      <EtaCard c={active} />
      {active.hospital && (
        <div className="card p-5">
          <h3 className="font-display text-base font-semibold text-navy-900">Hospital</h3>
          <p className="mt-2 text-sm text-navy-900/80">{active.hospital.name} — {active.hospital.address}</p>
          {active.doctor && <p className="text-sm text-navy-900/60">Attending: Dr. {active.doctor.name}</p>}
        </div>
      )}
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
        <p className="mt-3 text-xs text-navy-900/40">Clinical details (symptoms, AI brief) are visible to hospital staff only, not the family portal.</p>
      </div>
    </div>
  );
}
