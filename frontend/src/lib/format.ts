export const STATUS_LABEL: Record<string, string> = {
  CREATED: "SOS received", PATIENT_IDENTIFIED: "Patient identified", SUMMARY_GENERATED: "Medical brief ready",
  DOCTOR_ASSIGNED: "Doctor assigned", ROOM_RESERVED: "Room reserved", PATIENT_ARRIVED: "Patient arrived",
  COMPLETED: "Case closed",
};
export const STATUS_ORDER = ["CREATED", "PATIENT_IDENTIFIED", "SUMMARY_GENERATED", "DOCTOR_ASSIGNED",
  "ROOM_RESERVED", "PATIENT_ARRIVED", "COMPLETED"];

export const TYPE_LABEL: Record<string, string> = {
  stroke: "Stroke", cardiac: "Cardiac", trauma: "Trauma", diabetic: "Diabetic emergency", accident: "Accident", other: "Other",
};

export function timeAgo(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

export function priorityLabel(p: number): { label: string; className: string } {
  if (p === 1) return { label: "P1 - Critical", className: "bg-coral-500/15 text-coral-500" };
  if (p === 2) return { label: "P2 - Urgent", className: "bg-amber-500/15 text-amber-500" };
  return { label: "P3 - Standard", className: "bg-teal-500/15 text-teal-700" };
}
