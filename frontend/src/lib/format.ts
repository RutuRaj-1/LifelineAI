export const STATUS_LABEL: Record<string, string> = {
  CREATED: "SOS Received",
  INITIATED: "Incident Initiated",
  INTAKE_IN_PROGRESS: "Intake Active",
  COORDINATION_ACTIVE: "Coordination Active",
  REFERRAL_IN_PROGRESS: "Referral Broadcasting",
  ACCEPTED: "Hospital Accepted",
  IN_TRANSIT: "In Transit",
  ARRIVED: "Patient Arrived",
  HANDOVER_COMPLETED: "Handover Complete",
  COMPLETED: "Case Closed",
  CLOSED: "Case Closed",
  // Legacy backward-compatibility mappings
  PATIENT_IDENTIFIED: "Patient Identified",
  SUMMARY_GENERATED: "Medical Brief Ready",
  DOCTOR_ASSIGNED: "Doctor Assigned",
  ROOM_RESERVED: "Bed Reserved",
  PATIENT_ARRIVED: "Patient Arrived",
};

export const STATUS_ORDER = [
  "CREATED",
  "INITIATED",
  "INTAKE_IN_PROGRESS",
  "COORDINATION_ACTIVE",
  "REFERRAL_IN_PROGRESS",
  "ACCEPTED",
  "IN_TRANSIT",
  "ARRIVED",
  "HANDOVER_COMPLETED",
  "COMPLETED",
];

export const CANONICAL_STATUS_MILESTONES = [
  { key: "INITIATED", label: "SOS Intake", match: ["CREATED", "INITIATED", "INTAKE_IN_PROGRESS"] },
  { key: "COORDINATION_ACTIVE", label: "Coordination", match: ["COORDINATION_ACTIVE", "PATIENT_IDENTIFIED", "SUMMARY_GENERATED", "DOCTOR_ASSIGNED"] },
  { key: "REFERRAL_IN_PROGRESS", label: "Referral Dispatch", match: ["REFERRAL_IN_PROGRESS"] },
  { key: "ACCEPTED", label: "Hospital Accepted", match: ["ACCEPTED", "ROOM_RESERVED"] },
  { key: "IN_TRANSIT", label: "In Transit", match: ["IN_TRANSIT"] },
  { key: "ARRIVED", label: "Arrived", match: ["ARRIVED", "PATIENT_ARRIVED"] },
  { key: "HANDOVER_COMPLETED", label: "Handover", match: ["HANDOVER_COMPLETED"] },
  { key: "COMPLETED", label: "Completed", match: ["COMPLETED", "CLOSED"] },
];

export const REFERRAL_STATUS_LABEL: Record<string, string> = {
  DRAFT: "Draft",
  SENT: "Dispatched",
  REVIEWING: "Under Review",
  CLARIFICATION_REQUIRED: "Clarification Needed",
  ACCEPTED: "Accepted",
  DECLINED: "Declined",
  EXPIRED: "Expired",
  CANCELLED: "Cancelled",
};

export const HANDOVER_STATUS_LABEL: Record<string, string> = {
  PENDING_REVIEW: "Pending Review",
  APPROVED: "Doctor Approved",
  SUPERSEDED: "Superseded",
  REJECTED: "Rejected",
};

export const TYPE_LABEL: Record<string, string> = {
  stroke: "Stroke",
  cardiac: "Cardiac",
  trauma: "Trauma",
  diabetic: "Diabetic Emergency",
  accident: "Accident",
  other: "Other Emergency",
};

export function timeAgo(iso?: string | null): string {
  if (!iso) return "just now";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

export function priorityLabel(p: number): { label: string; className: string } {
  if (p === 1) return { label: "P1 - Critical", className: "bg-coral-500/15 text-coral-600 border border-coral-200" };
  if (p === 2) return { label: "P2 - Urgent", className: "bg-amber-500/15 text-amber-700 border border-amber-200" };
  return { label: "P3 - Standard", className: "bg-teal-500/15 text-teal-700 border border-teal-200" };
}
