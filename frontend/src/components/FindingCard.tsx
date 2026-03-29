"use client";

import { useState } from "react";
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

const REMEDIATION_OPTIONS = [
  {
    gradient: "from-purple-600 to-indigo-700",
    description: "Alternative shot without flagged element...",
  },
  {
    gradient: "from-teal-600 to-cyan-700",
    description: "Cutaway to neutral establishing shot...",
  },
  {
    gradient: "from-blue-600 to-sky-700",
    description: "AI-generated replacement with compliant content...",
  },
  {
    gradient: "from-green-600 to-emerald-700",
    description: "Audio-only replacement maintaining visual...",
  },
];

export default function FindingCard({
  finding,
  onSeek,
  onDecision,
  onRemediation,
  isActive,
}: FindingCardProps) {
  const [showRemediation, setShowRemediation] = useState(false);

  return (
    <div
      onClick={() => onSeek(finding.timecode)}
      className={`p-4 rounded-lg border transition-colors cursor-pointer ${
        isActive
          ? "border-emerald-500/50 bg-emerald-500/5"
          : "border-border bg-surface hover:border-emerald-500/30 hover:brightness-105"
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={severityBadge(finding.severity)}>{finding.severity}</span>
          <span
            className="text-[11px] font-medium text-emerald-400 tabular-nums bg-emerald-500/10 px-1.5 py-0.5 rounded"
          >
            {formatTimecode(finding.timecode)}
          </span>
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
          {Math.round(finding.confidence)}% conf
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
          onClick={(e) => { e.stopPropagation(); onDecision(finding.id, "approved"); }}
          className={`px-2.5 py-1 rounded text-[10px] font-semibold transition-colors ${
            finding.decision === "approved"
              ? "bg-emerald-500 text-white"
              : "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
          }`}
        >
          Approve
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onDecision(finding.id, "rejected"); }}
          className={`px-2.5 py-1 rounded text-[10px] font-semibold transition-colors ${
            finding.decision === "rejected"
              ? "bg-red-500 text-white"
              : "bg-red-500/10 text-red-400 hover:bg-red-500/20"
          }`}
        >
          Reject
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onDecision(finding.id, "escalated"); }}
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
          onClick={(e) => { e.stopPropagation(); onRemediation(finding.id, "blur"); }}
          className={`px-2.5 py-1 rounded text-[10px] font-semibold transition-colors ${
            finding.remediation === "blur"
              ? "bg-blue-500 text-white"
              : "bg-blue-500/10 text-blue-400 hover:bg-blue-500/20"
          }`}
        >
          Blur
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onRemediation(finding.id, "bleep"); }}
          className={`px-2.5 py-1 rounded text-[10px] font-semibold transition-colors ${
            finding.remediation === "bleep"
              ? "bg-blue-500 text-white"
              : "bg-blue-500/10 text-blue-400 hover:bg-blue-500/20"
          }`}
        >
          Bleep
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            setShowRemediation((prev) => !prev);
            onRemediation(finding.id, "ai_fix");
          }}
          className={`px-2.5 py-1 rounded text-[10px] font-semibold transition-colors ${
            finding.remediation === "ai_fix"
              ? "bg-purple-500 text-white"
              : "bg-purple-500/10 text-purple-400 hover:bg-purple-500/20"
          }`}
        >
          AI Fix
        </button>
      </div>

      {/* LTX Remediation Panel */}
      {showRemediation && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="mt-4 p-4 rounded-lg border border-purple-500/30 bg-purple-500/5"
        >
          {/* Header */}
          <h4 className="text-xs font-bold text-purple-400 tracking-wider mb-2">
            &#10022; LTX REMEDIATION
          </h4>

          {/* Finding text truncated */}
          <p className="text-[11px] text-muted truncate mb-3">
            {finding.text}
          </p>

          {/* Prompt */}
          <p className="text-[10px] font-semibold uppercase tracking-wider text-foreground/60 mb-3">
            SELECT REPLACEMENT CLIP TO GENERATE:
          </p>

          {/* 2x2 grid */}
          <div className="grid grid-cols-2 gap-3 mb-3">
            {REMEDIATION_OPTIONS.map((opt, i) => (
              <div key={i} className="flex flex-col gap-1.5">
                {/* Gradient placeholder with play icon */}
                <div
                  className={`relative aspect-video rounded-md bg-gradient-to-br ${opt.gradient} flex items-center justify-center`}
                >
                  <svg
                    className="w-8 h-8 text-white/70"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path d="M8 5v14l11-7z" />
                  </svg>
                </div>
                {/* Description */}
                <p className="text-[10px] text-muted leading-snug">
                  {opt.description}
                </p>
                {/* Generate button */}
                <button className="w-full py-1.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-600 hover:bg-emerald-500 text-white transition-colors">
                  GENERATE
                </button>
              </div>
            ))}
          </div>

          {/* Upload custom link */}
          <p className="text-[10px] text-center text-purple-400 hover:text-purple-300 cursor-pointer underline underline-offset-2">
            Or upload custom replacement
          </p>
        </div>
      )}
    </div>
  );
}
