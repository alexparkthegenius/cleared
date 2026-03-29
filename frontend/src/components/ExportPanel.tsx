"use client";

import { useState } from "react";
import type { Finding } from "@/types";

interface ExportPanelProps {
  onExport: (config: {
    deliverable: string;
    deliverTo: string;
    formats: string[];
  }) => void;
  isExporting: boolean;
  findings?: Finding[];
}

const DELIVERABLE_SPECS = [
  "Broadcast ProRes 422HQ",
  "Web H.264",
  "Social H.264 vertical",
];

const EXPORT_OPTIONS = [
  "ProRes",
  "H.264",
  "Send to Iconik",
  "Send to NLE via OTIO",
];

export default function ExportPanel({ onExport, isExporting, findings = [] }: ExportPanelProps) {
  const [deliverable, setDeliverable] = useState(DELIVERABLE_SPECS[0]);
  const [formats, setFormats] = useState<string[]>(["ProRes"]);

  const toggleFormat = (f: string) => {
    setFormats((prev) =>
      prev.includes(f) ? prev.filter((x) => x !== f) : [...prev, f]
    );
  };

  const totalFindings = findings.length;
  const approved = findings.filter((f) => f.decision === "approved").length;
  const rejected = findings.filter((f) => f.decision === "rejected").length;
  const pending = findings.filter((f) => f.decision === "pending").length;

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Approvals */}
      <section>
        <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-3">
          Approvals
        </label>
        <div className="grid grid-cols-4 gap-3">
          <div className="p-3 rounded-lg border border-border bg-surface/50 text-center">
            <div className="text-lg font-bold text-foreground">{totalFindings}</div>
            <div className="text-[10px] text-muted uppercase font-semibold">Total</div>
          </div>
          <div className="p-3 rounded-lg border border-border bg-surface/50 text-center">
            <div className="text-lg font-bold text-emerald-400">{approved}</div>
            <div className="text-[10px] text-muted uppercase font-semibold">Approved</div>
          </div>
          <div className="p-3 rounded-lg border border-border bg-surface/50 text-center">
            <div className="text-lg font-bold text-red-400">{rejected}</div>
            <div className="text-[10px] text-muted uppercase font-semibold">Rejected</div>
          </div>
          <div className="p-3 rounded-lg border border-border bg-surface/50 text-center">
            <div className="text-lg font-bold text-amber-400">{pending}</div>
            <div className="text-[10px] text-muted uppercase font-semibold">Pending</div>
          </div>
        </div>
      </section>

      {/* Deliverable Spec */}
      <section>
        <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-2">
          Deliverable Specification
        </label>
        <select
          value={deliverable}
          onChange={(e) => setDeliverable(e.target.value)}
          className="w-full px-3 py-2.5 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
        >
          {DELIVERABLE_SPECS.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      </section>

      {/* Export Options */}
      <section>
        <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-3">
          Export Options
        </label>
        <div className="grid grid-cols-2 gap-2">
          {EXPORT_OPTIONS.map((f) => (
            <label
              key={f}
              className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg border cursor-pointer transition-colors ${
                formats.includes(f)
                  ? "border-emerald-500/40 bg-emerald-500/5"
                  : "border-border hover:border-border/80"
              }`}
            >
              <input
                type="checkbox"
                checked={formats.includes(f)}
                onChange={() => toggleFormat(f)}
                className="sr-only"
              />
              <div
                className={`w-4 h-4 rounded border-2 flex items-center justify-center transition-colors flex-shrink-0 ${
                  formats.includes(f)
                    ? "bg-emerald-500 border-emerald-500"
                    : "border-border"
                }`}
              >
                {formats.includes(f) && (
                  <svg
                    width="10"
                    height="10"
                    fill="none"
                    stroke="white"
                    strokeWidth="3"
                    viewBox="0 0 24 24"
                  >
                    <path d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </div>
              <span className="text-xs text-foreground">{f}</span>
            </label>
          ))}
        </div>
      </section>

      {/* Summary */}
      <div className="p-4 rounded-lg border border-border bg-surface/50">
        <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">
          Export Summary
        </h4>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between">
            <span className="text-muted">Deliverable:</span>
            <span className="text-foreground font-medium">{deliverable}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Formats:</span>
            <span className="text-foreground font-medium">
              {formats.length} selected
            </span>
          </div>
        </div>
      </div>

      {/* Go Button */}
      <button
        onClick={() => onExport({ deliverable, deliverTo: "Local Download", formats })}
        disabled={isExporting || formats.length === 0}
        className="w-full py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold transition-all active:scale-[0.98]"
      >
        {isExporting ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            Exporting...
          </span>
        ) : (
          "Go"
        )}
      </button>
    </div>
  );
}
