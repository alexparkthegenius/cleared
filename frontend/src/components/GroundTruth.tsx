"use client";

import { useState } from "react";
import type { Finding } from "@/types";

interface GroundTruthProps {
  initialValue: string;
  onSave: (text: string) => void;
  findings: Finding[];
}

function formatTimecode(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function GroundTruth({ initialValue, onSave, findings }: GroundTruthProps) {
  const [text, setText] = useState(initialValue);
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    onSave(text);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleAutoGenerate = () => {
    const generated = findings
      .map(
        (f) =>
          `${formatTimecode(f.timecode)} — ${f.text} (${f.severity})`
      )
      .join("\n");
    setText(generated);
  };

  return (
    <div className="space-y-4 max-w-3xl">
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-xs font-semibold uppercase tracking-wider text-muted">
            Manual Annotation / Ground Truth
          </label>
          {saved && (
            <span className="text-[10px] font-semibold text-emerald-400 animate-pulse">
              Saved
            </span>
          )}
        </div>
      </div>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={16}
        placeholder={`Enter ground truth annotations...\n\nExample format:\n0:12 — Minor's face visible (CRITICAL)\n0:34 — Coca-Cola logo placement (MAJOR)\n0:45 — Unlicensed music detected (MAJOR)\n1:07 — Mild expletive (MINOR)`}
        className="w-full px-4 py-3 bg-background border border-border rounded-lg text-sm text-foreground placeholder:text-muted/50 resize-y focus:outline-none focus:ring-1 focus:ring-emerald-500/50 focus:border-emerald-500/50 leading-relaxed"
      />

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          className="px-5 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-colors active:scale-[0.98]"
        >
          Save Annotations
        </button>
        <button
          onClick={handleAutoGenerate}
          disabled={findings.length === 0}
          className="px-5 py-2.5 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-semibold transition-colors active:scale-[0.98]"
        >
          Auto-generate from analysis
        </button>
        <button
          onClick={() => setText("")}
          className="px-5 py-2.5 rounded-lg bg-background border border-border hover:bg-foreground/5 text-foreground text-xs font-semibold transition-colors"
        >
          Clear
        </button>
      </div>
    </div>
  );
}
