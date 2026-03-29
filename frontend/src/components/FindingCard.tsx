"use client";

import { useState } from "react";
import type { Finding, Decision, Remediation, RegenOption } from "@/types";
import { regenClip } from "@/lib/api";

interface FindingCardProps {
  finding: Finding;
  onSeek: (time: number) => void;
  onDecision: (id: string, decision: Decision) => void;
  onRemediation: (id: string, remediation: Remediation) => void;
  isActive: boolean;
  s3Uri?: string | null;
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

type RegenType = "Video" | "Audio" | "Captions" | "Titles" | "Lower Thirds" | "Select";

const REGEN_PILLS: RegenType[] = ["Video", "Audio", "Captions", "Titles", "Lower Thirds", "Select"];

const REGEN_GRADIENTS = [
  "from-purple-600 to-indigo-700",
  "from-teal-600 to-cyan-700",
];

function regenTypeToMode(type: RegenType): string {
  switch (type) {
    case "Video":
      return "replace_video";
    case "Audio":
      return "replace_audio";
    case "Captions":
    case "Titles":
    case "Lower Thirds":
      return "replace_video";
    case "Select":
      return "replace_audio_and_video";
  }
}

function regenTypeToPromptPrefix(type: RegenType): string {
  switch (type) {
    case "Captions":
      return "Generate compliant captions overlay: ";
    case "Titles":
      return "Generate compliant title card: ";
    case "Lower Thirds":
      return "Generate compliant lower third graphic: ";
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
  s3Uri,
}: FindingCardProps) {
  const [showRemediation, setShowRemediation] = useState(false);
  const [regenType, setRegenType] = useState<RegenType | null>(null);
  const [regenLoading, setRegenLoading] = useState(false);
  const [regenOptions, setRegenOptions] = useState<RegenOption[]>([]);
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [selectDropdownOpen, setSelectDropdownOpen] = useState(false);

  const handleRegenPill = async (type: RegenType) => {
    if (type === "Select") {
      setRegenType(type);
      setSelectDropdownOpen(true);
      return;
    }
    await runRegen(type);
  };

  const runRegen = async (type: RegenType, overrideMode?: string) => {
    setRegenType(type);
    setSelectDropdownOpen(false);
    setRegenLoading(true);
    setRegenOptions([]);
    setSelectedOption(null);

    const mode = overrideMode || regenTypeToMode(type);
    const prefix = regenTypeToPromptPrefix(type);
    const prompt = `${prefix}${finding.text}`;

    try {
      const result = await regenClip({
        video_uri: s3Uri || "",
        start_time: finding.timecode,
        duration: 3,
        prompt,
        mode,
        finding_id: finding.id,
      });
      setRegenOptions(result.options);
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      console.error("Regen failed:", errMsg);
      // Show error state with placeholder options
      setRegenOptions([
        { id: `${finding.id}_err`, video_url: "", prompt: `Generation failed: ${errMsg}`, duration: 3 },
      ]);
    } finally {
      setRegenLoading(false);
    }
  };

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

          {/* Regen type pills */}
          <div className="flex flex-wrap gap-1.5 mb-3">
            {REGEN_PILLS.map((pill) => (
              <button
                key={pill}
                onClick={() => handleRegenPill(pill)}
                disabled={regenLoading}
                className={`px-3 py-1 rounded-full text-[10px] font-semibold transition-colors ${
                  regenType === pill
                    ? "bg-purple-500 text-white"
                    : "bg-purple-500/10 text-purple-400 hover:bg-purple-500/20"
                } ${regenLoading ? "opacity-50 cursor-not-allowed" : ""}`}
              >
                {pill}
              </button>
            ))}
          </div>

          {/* Select dropdown */}
          {regenType === "Select" && selectDropdownOpen && (
            <div className="mb-3 p-2 rounded-lg border border-purple-500/20 bg-surface">
              <p className="text-[10px] font-semibold text-foreground/60 mb-1.5">SELECT MODE:</p>
              {["replace_video", "replace_audio", "replace_audio_and_video"].map((mode) => (
                <button
                  key={mode}
                  onClick={() => runRegen("Select", mode)}
                  className="block w-full text-left px-2 py-1 text-[10px] text-purple-400 hover:bg-purple-500/10 rounded"
                >
                  {mode.replace(/_/g, " ")}
                </button>
              ))}
            </div>
          )}

          {/* Loading state */}
          {regenLoading && (
            <div className="flex items-center gap-2 py-6 justify-center">
              <div className="w-4 h-4 border-2 border-purple-400 border-t-transparent rounded-full animate-spin" />
              <span className="text-[11px] text-purple-400 font-medium">Generating...</span>
            </div>
          )}

          {/* Regen options grid */}
          {!regenLoading && regenOptions.length > 0 && (
            <>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-foreground/60 mb-3">
                GENERATED OPTIONS:
              </p>
              <div className="grid grid-cols-2 gap-3 mb-3">
                {regenOptions.map((opt, i) => (
                  <div key={opt.id} className="flex flex-col gap-1.5">
                    {/* Video preview or gradient placeholder */}
                    <div
                      className={`relative aspect-video rounded-md overflow-hidden ${
                        opt.video_url
                          ? "bg-black"
                          : `bg-gradient-to-br ${REGEN_GRADIENTS[i % REGEN_GRADIENTS.length]}`
                      } flex items-center justify-center`}
                    >
                      {opt.video_url ? (
                        <video
                          src={opt.video_url}
                          className="w-full h-full object-cover"
                          muted
                          playsInline
                          onMouseEnter={(e) => (e.target as HTMLVideoElement).play()}
                          onMouseLeave={(e) => {
                            const v = e.target as HTMLVideoElement;
                            v.pause();
                            v.currentTime = 0;
                          }}
                        />
                      ) : (
                        <svg
                          className="w-8 h-8 text-white/70"
                          fill="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path d="M8 5v14l11-7z" />
                        </svg>
                      )}
                      <span className="absolute top-1 left-1 bg-black/60 text-white text-[9px] px-1.5 py-0.5 rounded font-bold">
                        Option {i + 1}
                      </span>
                    </div>
                    {/* Prompt */}
                    <p className="text-[10px] text-muted leading-snug truncate">
                      {opt.prompt}
                    </p>
                    {/* Actions */}
                    <div className="flex gap-1.5">
                      <button
                        onClick={() => {
                          if (opt.video_url) window.open(opt.video_url, "_blank");
                        }}
                        className="flex-1 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider bg-blue-600 hover:bg-blue-500 text-white transition-colors"
                      >
                        Preview
                      </button>
                      <button
                        onClick={() => setSelectedOption(opt.id)}
                        className={`flex-1 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider transition-colors ${
                          selectedOption === opt.id
                            ? "bg-emerald-500 text-white"
                            : "bg-emerald-600 hover:bg-emerald-500 text-white"
                        }`}
                      >
                        {selectedOption === opt.id ? "Approved" : "Approve"}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Initial state — no type selected yet */}
          {!regenLoading && regenOptions.length === 0 && !regenType && (
            <p className="text-[10px] text-center text-muted py-4">
              Select a remediation type above to generate replacement clips
            </p>
          )}

          {/* Upload custom link */}
          <p className="text-[10px] text-center text-purple-400 hover:text-purple-300 cursor-pointer underline underline-offset-2">
            Or upload custom replacement
          </p>
        </div>
      )}
    </div>
  );
}
