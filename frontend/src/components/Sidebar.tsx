"use client";

import { useState, useEffect } from "react";
import type { VideoSource, Platform, Jurisdiction } from "@/types";
import {
  getTwelveLabsIndexes,
  getTwelveLabsVideos,
  getTwelveLabsVideoUrl,
} from "@/lib/api";

const PLATFORMS: Platform[] = [
  "YouTube",
  "TikTok",
  "Instagram",
  "Broadcast pre-watershed",
  "Streaming Netflix/HBO",
  "Roblox",
  "The Sphere",
];

const JURISDICTIONS: Jurisdiction[] = [
  "OFCOM UK",
  "FCC US",
  "GDPR EU",
  "ARPP France",
  "CRTC Canada",
  "Multi-region",
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  onFileSelect: (file: File) => void;
  onTwelveLabsVideoSelect: (hlsUrl: string, indexId: string, videoId: string) => void;
  onRunCheck: (config: {
    source: VideoSource;
    platforms: Platform[];
    jurisdictions: Jurisdiction[];
    customRules: string;
  }) => void;
  isAnalyzing: boolean;
  theme: "dark" | "light";
  onThemeToggle: () => void;
}

export default function Sidebar({
  collapsed,
  onToggle,
  onFileSelect,
  onTwelveLabsVideoSelect,
  onRunCheck,
  isAnalyzing,
  theme,
  onThemeToggle,
}: SidebarProps) {
  const [source, setSource] = useState<VideoSource>("upload");
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [jurisdictions, setJurisdictions] = useState<Jurisdiction[]>([]);
  const [customRules, setCustomRules] = useState("");
  const [showCustomRules, setShowCustomRules] = useState(false);
  const [quickRule, setQuickRule] = useState("");
  const [dragOver, setDragOver] = useState(false);

  // TwelveLabs picker state
  const [tlIndexes, setTlIndexes] = useState<{ id: string; name: string; video_count: number }[]>([]);
  const [tlVideos, setTlVideos] = useState<{ id: string; name: string; duration: number }[]>([]);
  const [tlSelectedIndex, setTlSelectedIndex] = useState("");
  const [tlSelectedVideo, setTlSelectedVideo] = useState("");
  const [tlLoadingIndexes, setTlLoadingIndexes] = useState(false);
  const [tlLoadingVideos, setTlLoadingVideos] = useState(false);
  const [tlLoadingUrl, setTlLoadingUrl] = useState(false);
  const [tlError, setTlError] = useState<string | null>(null);

  // Fetch indexes when TwelveLabs source is selected
  useEffect(() => {
    if (source !== "twelvelabs") return;
    if (tlIndexes.length > 0) return; // already loaded
    setTlLoadingIndexes(true);
    setTlError(null);
    getTwelveLabsIndexes()
      .then((data) => setTlIndexes(data))
      .catch((err) => setTlError(err.message))
      .finally(() => setTlLoadingIndexes(false));
  }, [source, tlIndexes.length]);

  // Fetch videos when an index is selected
  useEffect(() => {
    if (!tlSelectedIndex) { setTlVideos([]); return; }
    setTlLoadingVideos(true);
    setTlError(null);
    setTlSelectedVideo("");
    getTwelveLabsVideos(tlSelectedIndex)
      .then((data) => setTlVideos(data))
      .catch((err) => setTlError(err.message))
      .finally(() => setTlLoadingVideos(false));
  }, [tlSelectedIndex]);

  // Fetch video URL when a video is selected
  useEffect(() => {
    if (!tlSelectedIndex || !tlSelectedVideo) return;
    setTlLoadingUrl(true);
    setTlError(null);
    getTwelveLabsVideoUrl(tlSelectedIndex, tlSelectedVideo)
      .then((data) => {
        if (data.hls_url) {
          onTwelveLabsVideoSelect(data.hls_url, tlSelectedIndex, tlSelectedVideo);
        } else {
          setTlError("No playback URL available for this video");
        }
      })
      .catch((err) => setTlError(err.message))
      .finally(() => setTlLoadingUrl(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tlSelectedIndex, tlSelectedVideo]);

  const togglePlatform = (p: Platform) => {
    setPlatforms((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]
    );
  };

  const toggleJurisdiction = (j: Jurisdiction) => {
    setJurisdictions((prev) =>
      prev.includes(j) ? prev.filter((x) => x !== j) : [...prev, j]
    );
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) onFileSelect(file);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFileSelect(file);
  };

  if (collapsed) {
    return (
      <aside className="w-12 flex-shrink-0 bg-surface border-r border-border flex flex-col items-center py-4 gap-4">
        <button
          onClick={onToggle}
          className="w-8 h-8 rounded-md bg-border/50 hover:bg-border flex items-center justify-center text-foreground/60 hover:text-foreground transition-colors"
          title="Expand sidebar"
        >
          <svg
            width="16"
            height="16"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            viewBox="0 0 24 24"
          >
            <path d="M9 18l6-6-6-6" />
          </svg>
        </button>
        <div
          className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center text-emerald-400 text-xs font-bold"
          title="Cleared"
        >
          C
        </div>
      </aside>
    );
  }

  return (
    <aside className="w-80 flex-shrink-0 bg-surface border-r border-border flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-5 pt-5 pb-4 flex items-center justify-between border-b border-border">
        <h1 className="text-[2.4rem] font-bold leading-none tracking-tight text-foreground">
          Cleared
        </h1>
        <div className="flex items-center gap-2">
          <button
            onClick={onThemeToggle}
            className="w-8 h-8 rounded-md hover:bg-border/50 flex items-center justify-center text-muted hover:text-foreground transition-colors"
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? (
              <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            ) : (
              <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
                <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
              </svg>
            )}
          </button>
          <button
            onClick={onToggle}
            className="w-8 h-8 rounded-md hover:bg-border/50 flex items-center justify-center text-muted hover:text-foreground transition-colors"
            title="Collapse sidebar"
          >
            <svg
              width="16"
              height="16"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              viewBox="0 0 24 24"
            >
              <path d="M15 18l-6-6 6-6" />
            </svg>
          </button>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
        {/* Video Source */}
        <section>
          <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-2">
            Video Source
          </label>
          <div className="flex gap-1 bg-background rounded-lg p-1">
            {(["upload", "twelvelabs", "iconik"] as VideoSource[]).map((s) => (
              <button
                key={s}
                onClick={() => setSource(s)}
                className={`flex-1 px-2 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  source === s
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "text-muted hover:text-foreground"
                }`}
              >
                {s === "twelvelabs" ? "TwelveLabs" : s === "iconik" ? "Iconik" : "Upload"}
              </button>
            ))}
          </div>
        </section>

        {/* File Upload Dropzone */}
        {source === "upload" && (
          <section>
            <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-2">
              Upload Video
            </label>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer ${
                dragOver
                  ? "border-emerald-500 bg-emerald-500/10"
                  : "border-border hover:border-muted"
              }`}
            >
              <input
                type="file"
                accept="video/*"
                onChange={handleFileInput}
                className="hidden"
                id="file-upload"
              />
              <label htmlFor="file-upload" className="cursor-pointer">
                <svg
                  className="w-8 h-8 mx-auto mb-2 text-muted"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
                  />
                </svg>
                <p className="text-xs text-muted">
                  Drop video or{" "}
                  <span className="text-emerald-400 underline">browse</span>
                </p>
              </label>
            </div>
            {/* Recent uploads */}
            <div className="mt-3">
              <label className="block text-[10px] font-semibold uppercase tracking-wider text-muted mb-1.5">
                Recent uploads
              </label>
              <div className="flex gap-2">
                {[1, 2, 3, 4].map((i) => (
                  <div
                    key={i}
                    className="w-14 h-10 rounded bg-background border border-border flex items-center justify-center text-muted/40"
                  >
                    <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M8 5v14l11-7z" />
                    </svg>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* TwelveLabs picker */}
        {source === "twelvelabs" && (
          <section className="space-y-3">
            {/* Index dropdown */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-2">
                Select Index
              </label>
              {tlLoadingIndexes ? (
                <div className="flex items-center gap-2 text-xs text-muted py-2">
                  <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Loading indexes...
                </div>
              ) : (
                <select
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50 focus:border-emerald-500/50"
                  value={tlSelectedIndex}
                  onChange={(e) => setTlSelectedIndex(e.target.value)}
                >
                  <option value="">Select an index...</option>
                  {tlIndexes.map((idx) => (
                    <option key={idx.id} value={idx.id}>
                      {idx.name} ({idx.video_count} videos)
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Video dropdown */}
            {tlSelectedIndex && (
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-2">
                  Select Video
                </label>
                {tlLoadingVideos ? (
                  <div className="flex items-center gap-2 text-xs text-muted py-2">
                    <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Loading videos...
                  </div>
                ) : (
                  <select
                    className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50 focus:border-emerald-500/50"
                    value={tlSelectedVideo}
                    onChange={(e) => setTlSelectedVideo(e.target.value)}
                  >
                    <option value="">Select a video...</option>
                    {tlVideos.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name} ({Math.round(v.duration)}s)
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}

            {/* Loading URL indicator */}
            {tlLoadingUrl && (
              <div className="flex items-center gap-2 text-xs text-emerald-400 py-1">
                <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Loading video...
              </div>
            )}

            {/* Error */}
            {tlError && (
              <p className="text-[11px] text-red-400">{tlError}</p>
            )}
          </section>
        )}

        {/* Iconik dropdown */}
        {source === "iconik" && (
          <section>
            <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-2">
              Select Asset or Collection
            </label>
            <select
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50 focus:border-emerald-500/50"
              defaultValue=""
            >
              <option value="" disabled>Select an asset or collection...</option>
              <option value="col-001">Collection: Spring Campaign</option>
              <option value="col-002">Collection: Archive 2025</option>
              <option value="ast-001">Asset: Hero Film Final</option>
              <option value="ast-002">Asset: BTS Reel</option>
            </select>
          </section>
        )}

        {/* Target Platforms */}
        <section>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted">
              Target Platforms
            </label>
            <button
              onClick={() =>
                setPlatforms(
                  platforms.length === PLATFORMS.length ? [] : [...PLATFORMS]
                )
              }
              className="text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 transition-colors"
            >
              {platforms.length === PLATFORMS.length ? "Clear" : "All"}
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {PLATFORMS.map((p) => (
              <button
                key={p}
                onClick={() => togglePlatform(p)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                  platforms.includes(p)
                    ? "bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/30"
                    : "bg-background text-muted hover:text-foreground hover:bg-border/50"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </section>

        {/* Jurisdictions */}
        <section>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted">
              Jurisdictions
            </label>
            <button
              onClick={() =>
                setJurisdictions(
                  jurisdictions.length === JURISDICTIONS.length
                    ? []
                    : [...JURISDICTIONS]
                )
              }
              className="text-[10px] font-semibold px-2 py-0.5 rounded bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 transition-colors"
            >
              {jurisdictions.length === JURISDICTIONS.length ? "Clear" : "All"}
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {JURISDICTIONS.map((j) => (
              <button
                key={j}
                onClick={() => toggleJurisdiction(j)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                  jurisdictions.includes(j)
                    ? "bg-blue-500/20 text-blue-400 ring-1 ring-blue-500/30"
                    : "bg-background text-muted hover:text-foreground hover:bg-border/50"
                }`}
              >
                {j}
              </button>
            ))}
          </div>
        </section>

        {/* Custom Rules */}
        <section>
          <button
            onClick={() => setShowCustomRules(!showCustomRules)}
            className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted hover:text-foreground transition-colors w-full"
          >
            <svg
              width="12"
              height="12"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              viewBox="0 0 24 24"
              className={`transition-transform ${showCustomRules ? "rotate-90" : ""}`}
            >
              <path d="M9 18l6-6-6-6" />
            </svg>
            Custom Rules
          </button>
          {showCustomRules && (
            <div className="mt-2 space-y-2">
              <div className="flex gap-1.5">
                <input
                  type="text"
                  value={quickRule}
                  onChange={(e) => setQuickRule(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && quickRule.trim()) {
                      setCustomRules((prev) => (prev ? prev + "\n" : "") + quickRule.trim());
                      setQuickRule("");
                    }
                  }}
                  placeholder="Describe a rule in plain language..."
                  className="flex-1 px-3 py-1.5 bg-background border border-border rounded-lg text-xs text-foreground placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-emerald-500/50 focus:border-emerald-500/50"
                />
                <button
                  onClick={() => {
                    if (quickRule.trim()) {
                      setCustomRules((prev) => (prev ? prev + "\n" : "") + quickRule.trim());
                      setQuickRule("");
                    }
                  }}
                  className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-colors"
                >
                  Add
                </button>
              </div>
              <textarea
                value={customRules}
                onChange={(e) => setCustomRules(e.target.value)}
                placeholder={"e.g.\nNo visible tattoos\nNo competitor products in frame\nAll talent must have signed releases\nNo unlicensed music"}
                rows={4}
                className="w-full px-3 py-2 bg-background border border-border rounded-lg text-xs text-foreground placeholder:text-muted resize-none focus:outline-none focus:ring-1 focus:ring-emerald-500/50 focus:border-emerald-500/50"
              />
            </div>
          )}
        </section>
      </div>

      {/* Run Button */}
      <div className="px-5 py-4 border-t border-border">
        <button
          onClick={() =>
            onRunCheck({ source, platforms, jurisdictions, customRules })
          }
          disabled={isAnalyzing || platforms.length === 0 || jurisdictions.length === 0}
          className="w-full py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold transition-all active:scale-[0.98]"
        >
          {isAnalyzing ? (
            <span className="flex items-center justify-center gap-2">
              <svg
                className="animate-spin w-4 h-4"
                fill="none"
                viewBox="0 0 24 24"
              >
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
              Analyzing...
            </span>
          ) : (
            "Run Compliance Check"
          )}
        </button>
        {(platforms.length === 0 || jurisdictions.length === 0) && !isAnalyzing && (
          <p className="text-[10px] text-amber-400 mt-2 text-center">
            Select at least one platform and jurisdiction
          </p>
        )}
      </div>
    </aside>
  );
}
