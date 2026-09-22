import { CaseDetail } from "../lib/api";

export default function EtaCard({ c }: { c: CaseDetail }) {
  const pct = c.initial_eta_minutes ? Math.min(100, Math.round((1 - (c.eta_minutes ?? 0) / c.initial_eta_minutes) * 100)) : 0;
  return (
    <div className="card p-5">
      <div className="flex items-baseline justify-between">
        <h3 className="font-display text-base font-semibold text-navy-900">Live ETA</h3>
        {c.hospital && <span className="text-sm text-navy-900/60">to {c.hospital.name}</span>}
      </div>
      {c.status === "PATIENT_ARRIVED" || c.status === "COMPLETED" ? (
        <p className="mt-3 text-2xl font-semibold text-teal-700">Arrived</p>
      ) : c.eta_minutes != null ? (
        <>
          <p className="mt-3 text-4xl font-semibold text-navy-900">{c.eta_minutes} <span className="text-lg font-normal text-navy-900/50">min</span></p>
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-navy-900/10">
            <div className="h-full rounded-full bg-teal-600 transition-all" style={{ width: `${pct}%` }} />
          </div>
        </>
      ) : (
        <p className="mt-3 text-sm text-navy-900/60">Routing to nearest capable hospital…</p>
      )}
    </div>
  );
}
