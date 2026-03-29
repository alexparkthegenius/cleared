"use client";

import type { Finding } from "@/types";

interface ViolationsPanelProps {
  findings: Finding[];
  currentTime: number;
  onSeek: (time: number) => void;
}

function formatTimecode(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function severityDot(severity: string) {
  switch (severity) {
    case "CRITICAL":
      return "bg-red-500";
    case "MAJOR":
      return "bg-orange-500";
    case "MINOR":
      return "bg-blue-500";
    default:
      return "bg-gray-500";
  }
}

export default function ViolationsPanel({
  findings,
  currentTime,
  onSeek,
}: ViolationsPanelProps) {
  if (findings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted py-12">
        <svg
          className="w-10 h-10 mb-3 opacity-30"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <p className="text-xs">No findings yet</p>
      </div>
    );
  }

  const sorted = [...findings].sort((a, b) => a.timecode - b.timecode);

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-border flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">
          Timeline
        </h3>
        <span className="text-[10px] text-muted tabular-nums">
          {findings.length} issue{findings.length !== 1 ? "s" : ""}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {sorted.map((f) => {
          const isNear =
            Math.abs(f.timecode - currentTime) < 3;
          return (
            <button
              key={f.id}
              onClick={() => onSeek(f.timecode)}
              className={`w-full text-left px-3 py-2.5 border-b border-border/50 hover:bg-foreground/5 transition-colors flex items-start gap-2.5 ${
                isNear ? "bg-foreground/5" : ""
              }`}
            >
              <div className="flex flex-col items-center gap-1 pt-0.5">
                <div className={`w-2 h-2 rounded-full ${severityDot(f.severity)}`} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[10px] font-medium text-emerald-400 tabular-nums">
                    {formatTimecode(f.timecode)}
                  </span>
                  <span className="text-[9px] font-bold uppercase tracking-wider text-muted">
                    {f.severity}
                  </span>
                </div>
                <p className="text-[11px] text-foreground/80 leading-snug line-clamp-2">
                  {f.rule}
                </p>
                {f.decision !== "pending" && (
                  <span
                    className={`inline-block mt-1 text-[9px] font-bold uppercase px-1.5 py-0.5 rounded ${
                      f.decision === "approved"
                        ? "bg-emerald-500/15 text-emerald-400"
                        : f.decision === "rejected"
                        ? "bg-red-500/15 text-red-400"
                        : "bg-amber-500/15 text-amber-400"
                    }`}
                  >
                    {f.decision}
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
