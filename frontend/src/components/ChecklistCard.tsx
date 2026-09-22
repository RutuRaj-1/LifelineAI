import { ChecklistItem } from "../lib/api";

export default function ChecklistCard({ items, onToggle }: { items: ChecklistItem[]; onToggle?: (i: number, done: boolean) => void }) {
  return (
    <div className="card p-5">
      <h3 className="font-display text-base font-semibold text-navy-900">Preparation checklist</h3>
      <ul className="mt-3 space-y-2">
        {items.map((it, i) => (
          <li key={i} className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={it.done} disabled={!onToggle}
              onChange={(e) => onToggle?.(i, e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-navy-900/30 text-teal-600 focus:ring-teal-500" />
            <span className={it.done ? "text-navy-900/40 line-through" : "text-navy-900"}>{it.item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
