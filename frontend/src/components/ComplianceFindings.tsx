"use client";

import type { Finding, Decision, Remediation } from "@/types";
import FindingCard from "./FindingCard";

interface ComplianceFindingsProps {
  findings: Finding[];
  currentTime: number;
  onSeek: (time: number) => void;
  onDecision: (id: string, decision: Decision) => void;
  onRemediation: (id: string, remediation: Remediation) => void;
  riskScore: number | null;
  riskExplanation: string;
}

function riskColor(score: number): string {
  if (score >= 70) return "text-red-400";
  if (score >= 40) return "text-amber-400";
  return "text-emerald-400";
}

function riskBg(score: number): string {
  if (score >= 70) return "bg-red-500/10";
  if (score >= 40) return "bg-amber-500/10";
  return "bg-emerald-500/10";
}

export default function ComplianceFindings({
  findings,
  currentTime,
  onSeek,
  onDecision,
  onRemediation,
  riskScore,
  riskExplanation,
}: ComplianceFindingsProps) {
  const critical = findings.filter((f) => f.severity === "CRITICAL").length;
  const major = findings.filter((f) => f.severity === "MAJOR").length;
  const minor = findings.filter((f) => f.severity === "MINOR").length;

  return (
    <div className="space-y-4">
      {/* Risk Score Summary */}
      {riskScore !== null && (
        <div className={`p-4 rounded-lg border border-border ${riskBg(riskScore)}`}>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-foreground">Risk Assessment</h3>
            <span className={`text-2xl font-bold tabular-nums ${riskColor(riskScore)}`}>
              {riskScore}
              <span className="text-xs text-muted font-normal">/100</span>
            </span>
          </div>
          <p className="text-xs text-muted leading-relaxed">{riskExplanation}</p>
          <div className="flex flex-wrap gap-6 mt-3">
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-red-500 flex-shrink-0" />
              <span className="text-xs text-muted whitespace-nowrap">
                {critical} Critical
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-orange-500 flex-shrink-0" />
              <span className="text-xs text-muted whitespace-nowrap">
                {major} Major
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-blue-500 flex-shrink-0" />
              <span className="text-xs text-muted whitespace-nowrap">
                {minor} Minor
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Finding Cards */}
      {findings.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted">
          <svg
            className="w-12 h-12 mb-3 opacity-20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
            />
          </svg>
          <p className="text-sm">Run a compliance check to see findings</p>
        </div>
      ) : (
        <div className="space-y-3">
          {findings.map((f) => (
            <FindingCard
              key={f.id}
              finding={f}
              onSeek={onSeek}
              onDecision={onDecision}
              onRemediation={onRemediation}
              isActive={Math.abs(f.timecode - currentTime) < 3}
            />
          ))}
        </div>
      )}
    </div>
  );
}
