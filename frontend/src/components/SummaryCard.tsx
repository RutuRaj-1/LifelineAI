import { AiSummary, BriefItem } from "../lib/api";

const SECTIONS: { key: keyof AiSummary; label: string }[] = [
  { key: "major_diseases", label: "Major diseases / conditions" },
  { key: "current_medicines", label: "Current medicines" },
  { key: "allergies", label: "Allergies" },
  { key: "previous_surgeries", label: "Previous surgeries" },
  { key: "critical_risks", label: "Critical risk flags" },
];

function Items({ items }: { items: BriefItem[] }) {
  if (!items.length) return <p className="text-sm text-navy-900/40">Nothing found in uploaded records.</p>;
  return (
    <ul className="space-y-2">
      {items.map((it, i) => (
        <li key={i} className="text-sm">
          <span className="text-navy-900">{it.text}</span>
          <span className="ml-2 text-xs text-navy-900/40">
            [{it.evidence.map((e) => e.title).join(", ")}]
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function SummaryCard({ s }: { s: AiSummary | null | undefined }) {
  if (!s) return (
    <div className="card p-5">
      <h3 className="font-display text-base font-semibold text-navy-900">AI emergency brief</h3>
      <p className="mt-3 text-sm text-navy-900/60">Generating from uploaded records…</p>
    </div>
  );
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-base font-semibold text-navy-900">AI emergency brief</h3>
        <span className="pill bg-navy-900/5 text-navy-900/50">{s.generated_by}</span>
      </div>
      {s.insufficient_records && (
        <p className="mt-2 rounded-md bg-amber-500/10 px-3 py-2 text-xs text-amber-700">
          Limited or no uploaded records were found for this patient. Brief reflects reported symptoms only.
        </p>
      )}
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        {SECTIONS.map(({ key, label }) => (
          <div key={key}>
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-navy-900/50">{label}</p>
            <Items items={s[key] as BriefItem[]} />
          </div>
        ))}
      </div>
      <p className="mt-4 border-t border-navy-900/10 pt-3 text-xs italic text-navy-900/50">{s.disclaimer}</p>
    </div>
  );
}
