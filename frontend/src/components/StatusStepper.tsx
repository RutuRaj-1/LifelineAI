import { CANONICAL_STATUS_MILESTONES, STATUS_LABEL } from "../lib/format";

export default function StatusStepper({ status }: { status: string }) {
  // Find index of current milestone
  let currentIdx = CANONICAL_STATUS_MILESTONES.findIndex((m) => m.match.includes(status));
  if (currentIdx === -1) {
    currentIdx = 0;
  }

  return (
    <div className="w-full">
      <ol className="flex flex-wrap items-center gap-2">
        {CANONICAL_STATUS_MILESTONES.map((m, idx) => {
          const isDone = idx < currentIdx;
          const isCurrent = idx === currentIdx;

          let pillStyle = "border-navy-900/10 bg-white text-navy-900/40";
          if (isCurrent) {
            pillStyle = "border-teal-600 bg-teal-600 text-white font-bold shadow-sm";
          } else if (isDone) {
            pillStyle = "border-teal-600/30 bg-teal-50 text-teal-800 font-medium";
          }

          return (
            <li
              key={m.key}
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors ${pillStyle}`}
            >
              {isDone ? (
                <span className="text-[10px]">✓</span>
              ) : isCurrent ? (
                <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse" />
              ) : (
                <span className="text-[10px] text-navy-900/30">{idx + 1}</span>
              )}
              <span>{m.label}</span>
            </li>
          );
        })}
      </ol>
      <div className="mt-2 text-[11px] text-navy-900/60 font-medium">
        Current Lifecycle State: <span className="font-semibold text-teal-900">{STATUS_LABEL[status] || status}</span>
      </div>
    </div>
  );
}
