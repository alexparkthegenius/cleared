"use client";

import type { Finding, Decision, Remediation } from "@/types";

interface FindingCardProps {
  finding: Finding;
  onSeek: (time: number) => void;
  onDecision: (id: string, decision: Decision) => void;
  onRemediation: (id: string, remediation: Remediation) => void;
  isActive: boolean;
}

function severityBadge(severity: string) {
  const base = "px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider";
  switch (severity) {
    case "CRITICAL":
      return `${base} bg-red-500/15 text-red-400`;
    case "MAJOR":
      return `${base} bg-orange-500/15 text-orange-400`;
    case "MINOR":
      return `${base} bg-blue-500/15 text-blue-400`;
    default:
      return `${base} bg-gray-500/15 text-gray-400`;
  }
}

function formatTimecode(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 10);
  return `${m}:${s.toString().padStart(2, "0")}.${ms}`;
}

function decisionBadge(decision: Decision) {
  switch (decision) {
    case "approved":
      return "bg-emerald-500/15 text-emerald-400";
    case "rejected":
      return "bg-red-500/15 text-red-400";
    case "escalated":
      return "bg-amber-500/15 text-amber-400";
    default:
      return "";
  }
}

export default function FindingCard({
  finding,
  onSeek,
  onDecision,
  onRemediation,
  isActive,
}: FindingCardProps) {
  return (
    <div
      className={`p-4 rounded-lg border transition-colors ${
        isActive
          ? "border-emerald-500/50 bg-emerald-500/5"
          : "border-border bg-surface hover:border-border/80"
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={severityBadge(finding.severity)}>{finding.severity}</span>
          <button
            onClick={() => onSeek(finding.timecode)}
            className="text-[11px] font-medium text-emerald-400 hover:text-emerald-300 tabular-nums bg-emerald-500/10 px-1.5 py-0.5 rounded transition-colors"
          >
            {formatTimecode(finding.timecode)}
          </button>
          {finding.decision !== "pending" && (
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${decisionBadge(
                finding.decision
              )}`}
            >
              {finding.decision}
            </span>
          )}
        </div>
        <span className="text-[10px] text-muted whitespace-nowrap tabular-nums">
          {Math.round(finding.confidence * 100)}% conf
        </span>
      </div>

      {/* Rule */}
      <p className="text-[11px] font-semibold text-foreground/80 mb-1">
        {finding.rule}
      </p>

      {/* Description */}
      <p className="text-xs text-muted leading-relaxed mb-3">{finding.text}</p>

      {/* Source */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[10px] text-muted">Source:</span>
        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
          {finding.source}
        </span>
      </div>

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-1.5">
        <button
          onClick={() => onDecision(finding.id, "approved")}
          className={`px-2.5 py-1 rounded text-[10px] font-semibold transition-colors ${
            finding.decision === "approved"
              ? "bg-emerald-500 text-white"
              : "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
          }`}
        >
          Approve
        </button>
        <button
          onClick={() => onDecision(finding.id, "rejected")}
          className={`px-2.5 py-1 rounded text-[10px] font-semibold transition-colors ${
            finding.decision === "rejected"
              ? "bg-red-500 text-white"
              : "bg-red-500/10 text-red-400 hover:bg-red-500/20"
          }`}
        >
          Reject
        </button>
        <button
          onClick={() => onDecision(finding.id, "escalated")}
          className={`px-2.5 py-1 rounded text-[10px] font-semibold transition-colors ${
            finding.decision === "escalated"
              ? "bg-amber-500 text-white"
              : "bg-amber-500/10 text-amber-400 hover:bg-amber-500/20"
          }`}
        >
          Escalate
        </button>
        <div className="w-px bg-border mx-0.5" />
        <button
          onClick={() => onRemediation(finding.id, "blur")}
          className={`px-2.5 py-1 rounded text-[10px] font-semibold transition-colors ${
            finding.remediation === "blur"
              ? "bg-blue-500 text-white"
              : "bg-blue-500/10 text-blue-400 hover:bg-blue-500/20"
          }`}
        >
          Blur
        </button>
        <button
          onClick={() => onRemediation(finding.id, "bleep")}
          className={`px-2.5 py-1 rounded text-[10px] font-semibold transition-colors ${
            finding.remediation === "bleep"
              ? "bg-blue-500 text-white"
              : "bg-blue-500/10 text-blue-400 hover:bg-blue-500/20"
          }`}
        >
          Bleep
        </button>
        <button
          onClick={() => onRemediation(finding.id, "ai_fix")}
          className={`px-2.5 py-1 rounded text-[10px] font-semibold transition-colors ${
            finding.remediation === "ai_fix"
              ? "bg-purple-500 text-white"
              : "bg-purple-500/10 text-purple-400 hover:bg-purple-500/20"
          }`}
        >
          AI Fix
        </button>
      </div>
    </div>
  );
}
