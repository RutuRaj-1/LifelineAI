import React from "react";
import { STATUS_LABEL, REFERRAL_STATUS_LABEL, HANDOVER_STATUS_LABEL } from "../lib/format";
import { useWsConnectionStatus } from "../lib/ws";

export function EmergencyStatusBadge({ status }: { status: string }) {
  const label = STATUS_LABEL[status] || status.replace(/_/g, " ");

  let style = "bg-navy-100 text-navy-800 border-navy-200";
  if (status === "CREATED" || status === "INITIATED") {
    style = "bg-red-50 text-red-700 border-red-200";
  } else if (status === "INTAKE_IN_PROGRESS" || status === "COORDINATION_ACTIVE") {
    style = "bg-amber-50 text-amber-800 border-amber-200";
  } else if (status === "REFERRAL_IN_PROGRESS") {
    style = "bg-sky-50 text-sky-800 border-sky-200";
  } else if (status === "ACCEPTED" || status === "ROOM_RESERVED") {
    style = "bg-emerald-50 text-emerald-800 border-emerald-200";
  } else if (status === "IN_TRANSIT") {
    style = "bg-indigo-50 text-indigo-800 border-indigo-200";
  } else if (status === "ARRIVED" || status === "PATIENT_ARRIVED") {
    style = "bg-purple-50 text-purple-800 border-purple-200";
  } else if (status === "HANDOVER_COMPLETED") {
    style = "bg-teal-50 text-teal-800 border-teal-200";
  } else if (status === "COMPLETED" || status === "CLOSED") {
    style = "bg-gray-100 text-gray-700 border-gray-200";
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${style}`}>
      {label}
    </span>
  );
}

export function ReferralStatusBadge({ status }: { status: string }) {
  const label = REFERRAL_STATUS_LABEL[status] || status;

  let style = "bg-gray-100 text-gray-700 border-gray-200";
  if (status === "SENT") {
    style = "bg-sky-50 text-sky-800 border-sky-200";
  } else if (status === "REVIEWING") {
    style = "bg-blue-50 text-blue-800 border-blue-200";
  } else if (status === "CLARIFICATION_REQUIRED") {
    style = "bg-amber-50 text-amber-800 border-amber-200";
  } else if (status === "ACCEPTED") {
    style = "bg-emerald-50 text-emerald-800 border-emerald-300 font-bold";
  } else if (status === "DECLINED") {
    style = "bg-rose-50 text-rose-800 border-rose-200";
  } else if (status === "CANCELLED" || status === "EXPIRED") {
    style = "bg-gray-100 text-gray-600 border-gray-200";
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${style}`}>
      {label}
    </span>
  );
}

export function HandoverStatusBadge({ status }: { status: string }) {
  const label = HANDOVER_STATUS_LABEL[status] || status.replace(/_/g, " ");

  let style = "bg-gray-100 text-gray-700 border-gray-200";
  if (status === "PENDING_REVIEW") {
    style = "bg-amber-50 text-amber-800 border-amber-200";
  } else if (status === "APPROVED") {
    style = "bg-teal-50 text-teal-800 border-teal-300 font-bold";
  } else if (status === "REJECTED") {
    style = "bg-rose-50 text-rose-800 border-rose-200";
  } else if (status === "SUPERSEDED") {
    style = "bg-gray-100 text-gray-500 border-gray-200";
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${style}`}>
      {label}
    </span>
  );
}

export function FreshnessBadge({ status }: { status: string }) {
  if (status === "FRESH") {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-teal-50 px-2 py-0.5 text-[10px] font-bold text-teal-800 border border-teal-200">
        <span className="h-1.5 w-1.5 rounded-full bg-teal-600" /> FRESH
      </span>
    );
  }
  if (status === "STALE") {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-800 border border-amber-200">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-600" /> STALE
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-600 border border-gray-200">
      {status || "UNKNOWN"}
    </span>
  );
}

export function ProvenanceBadge({ source, status }: { source?: string; status?: string }) {
  let statusStyle = "bg-gray-100 text-gray-700 border-gray-200";
  if (status === "VERIFIED") statusStyle = "bg-teal-50 text-teal-700 border-teal-200";
  else if (status === "REVIEWED") statusStyle = "bg-blue-50 text-blue-700 border-blue-200";
  else if (status === "UNVERIFIED") statusStyle = "bg-amber-50 text-amber-700 border-amber-200";
  else if (status === "REJECTED") statusStyle = "bg-rose-50 text-rose-700 border-rose-200";

  return (
    <div className="inline-flex items-center gap-1.5 text-[10px]">
      {source && (
        <span className="text-navy-900/60 font-medium">
          Source: {source.replace(/_/g, " ")}
        </span>
      )}
      {status && (
        <span className={`px-1.5 py-0.5 rounded border font-semibold ${statusStyle}`}>
          {status}
        </span>
      )}
    </div>
  );
}

export function ConnectionStatusBadge() {
  const status = useWsConnectionStatus();

  if (status === "CONNECTED") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-400 border border-emerald-500/20" title="Real-time WebSocket connected">
        <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
        <span className="hidden sm:inline">LIVE</span>
      </span>
    );
  }
  if (status === "RECONNECTING") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-300 border border-amber-500/20" title="Reconnecting WebSocket...">
        <span className="h-2 w-2 rounded-full bg-amber-400 animate-spin" />
        <span className="hidden sm:inline">SYNCING</span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-500/10 px-2 py-0.5 text-[11px] font-medium text-rose-300 border border-rose-500/20" title="WebSocket disconnected">
      <span className="h-2 w-2 rounded-full bg-rose-400" />
      <span className="hidden sm:inline">OFFLINE</span>
    </span>
  );
}
