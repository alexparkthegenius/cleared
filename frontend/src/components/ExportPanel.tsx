"use client";

import { useState } from "react";

interface ExportPanelProps {
  onExport: (config: {
    deliverable: string;
    deliverTo: string;
    formats: string[];
  }) => void;
  isExporting: boolean;
}

const DELIVERABLES = [
  "Final Master",
  "Compliance Report",
  "Clearance Certificate",
  "Pre-TX QC Report",
  "Platform-specific Edit",
  "Rights Summary",
];

const DELIVER_TO = [
  "Local Download",
  "S3 Bucket",
  "Iconik",
  "Frame.io",
  "Google Drive",
  "Email",
  "Slack Channel",
];

const EXCHANGE_FORMATS = [
  "EBU-TT (Subtitles)",
  "TTML (Timed Text)",
  "BXF (Broadcast Exchange)",
  "IMF (Interoperable Master)",
  "MXF (Material Exchange)",
  "JSON Manifest",
  "PDF Report",
  "CSV",
];

export default function ExportPanel({ onExport, isExporting }: ExportPanelProps) {
  const [deliverable, setDeliverable] = useState(DELIVERABLES[0]);
  const [deliverTo, setDeliverTo] = useState(DELIVER_TO[0]);
  const [formats, setFormats] = useState<string[]>(["JSON Manifest", "PDF Report"]);

  const toggleFormat = (f: string) => {
    setFormats((prev) =>
      prev.includes(f) ? prev.filter((x) => x !== f) : [...prev, f]
    );
  };

  return (
    <div className="space-y-6 max-w-2xl">
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
          {DELIVERABLES.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      </section>

      {/* Deliver To */}
      <section>
        <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-2">
          Deliver To
        </label>
        <select
          value={deliverTo}
          onChange={(e) => setDeliverTo(e.target.value)}
          className="w-full px-3 py-2.5 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
        >
          {DELIVER_TO.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      </section>

      {/* Exchange Formats */}
      <section>
        <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-3">
          Exchange Formats
        </label>
        <div className="grid grid-cols-2 gap-2">
          {EXCHANGE_FORMATS.map((f) => (
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
            <span className="text-muted">Destination:</span>
            <span className="text-foreground font-medium">{deliverTo}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Formats:</span>
            <span className="text-foreground font-medium">
              {formats.length} selected
            </span>
          </div>
        </div>
      </div>

      {/* Commit & Export */}
      <button
        onClick={() => onExport({ deliverable, deliverTo, formats })}
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
          "Commit & Export"
        )}
      </button>
    </div>
  );
}
