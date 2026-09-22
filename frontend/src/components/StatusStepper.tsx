import { STATUS_LABEL, STATUS_ORDER } from "../lib/format";

export default function StatusStepper({ status }: { status: string }) {
  const idx = STATUS_ORDER.indexOf(status);
  return (
    <ol className="flex flex-wrap gap-2">
      {STATUS_ORDER.map((s, i) => {
        const done = i < idx, active = i === idx;
        return (
          <li key={s}
            className={`pill border ${active ? "border-teal-600 bg-teal-600 text-white" :
              done ? "border-teal-600/30 bg-teal-50 text-teal-700" : "border-navy-900/10 bg-white text-navy-900/40"}`}>
            {STATUS_LABEL[s]}
          </li>
        );
      })}
    </ol>
  );
}
