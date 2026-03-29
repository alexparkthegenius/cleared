"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import type { Finding } from "@/types";

interface VideoPlayerProps {
  videoUrl: string | null;
  findings: Finding[];
  currentTime: number;
  onTimeUpdate: (time: number) => void;
  onSeek: (time: number) => void;
  duration: number;
  onDurationChange: (d: number) => void;
}

function severityColor(severity: string): string {
  switch (severity) {
    case "CRITICAL":
      return "#dc2626";
    case "MAJOR":
      return "#ea580c";
    case "MINOR":
      return "#2563eb";
    default:
      return "#6b7280";
  }
}

export default function VideoPlayer({
  videoUrl,
  findings,
  currentTime,
  onTimeUpdate,
  onSeek,
  duration,
  onDurationChange,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const scrubberRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const handleTime = () => onTimeUpdate(video.currentTime);
    const handleDuration = () => onDurationChange(video.duration || 120);
    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    video.addEventListener("timeupdate", handleTime);
    video.addEventListener("loadedmetadata", handleDuration);
    video.addEventListener("play", handlePlay);
    video.addEventListener("pause", handlePause);
    return () => {
      video.removeEventListener("timeupdate", handleTime);
      video.removeEventListener("loadedmetadata", handleDuration);
      video.removeEventListener("play", handlePlay);
      video.removeEventListener("pause", handlePause);
    };
  }, [onTimeUpdate, onDurationChange]);

  const seekTo = useCallback(
    (time: number) => {
      const video = videoRef.current;
      if (video) {
        video.currentTime = time;
        onSeek(time);
      }
    },
    [onSeek]
  );

  const handleScrubberClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = scrubberRef.current?.getBoundingClientRect();
    if (!rect || !duration) return;
    const fraction = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    seekTo(fraction * duration);
  };

  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) video.play();
    else video.pause();
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  const progressPct = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="bg-surface rounded-xl border border-border overflow-hidden">
      {/* Video */}
      <div className="relative bg-black aspect-video">
        {videoUrl ? (
          <video
            ref={videoRef}
            src={videoUrl}
            className="w-full h-full object-contain"
            playsInline
          />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-muted">
            <svg
              className="w-16 h-16 mb-3 opacity-30"
              fill="none"
              stroke="currentColor"
              strokeWidth="1"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z"
              />
            </svg>
            <p className="text-sm">Upload a video to begin</p>
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="px-4 py-3 space-y-2">
        {/* Scrubber with violation markers */}
        <div
          ref={scrubberRef}
          onClick={handleScrubberClick}
          className="relative h-2 bg-background rounded-full cursor-pointer group"
        >
          {/* Progress */}
          <div
            className="absolute inset-y-0 left-0 bg-emerald-500 rounded-full transition-[width] duration-100"
            style={{ width: `${progressPct}%` }}
          />
          {/* Violation markers */}
          {duration > 0 &&
            findings.map((f) => (
              <div
                key={f.id}
                className="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full ring-1 ring-black/30 cursor-pointer hover:scale-150 transition-transform z-10"
                style={{
                  left: `${(f.timecode / duration) * 100}%`,
                  backgroundColor: severityColor(f.severity),
                  transform: "translate(-50%, -50%)",
                }}
                title={`${formatTime(f.timecode)} — ${f.severity}: ${f.rule}`}
                onClick={(e) => {
                  e.stopPropagation();
                  seekTo(f.timecode);
                }}
              />
            ))}
          {/* Playhead */}
          <div
            className="absolute top-1/2 w-3.5 h-3.5 bg-white rounded-full shadow-md -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity z-20"
            style={{
              left: `${progressPct}%`,
              transform: "translate(-50%, -50%)",
            }}
          />
        </div>

        {/* Play button + time */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={togglePlay}
              className="w-8 h-8 rounded-full bg-foreground/10 hover:bg-foreground/20 flex items-center justify-center transition-colors"
            >
              {isPlaying ? (
                <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                </svg>
              ) : (
                <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z" />
                </svg>
              )}
            </button>
            <span className="text-xs text-muted tabular-nums">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>
          <div className="flex items-center gap-1">
            {findings.length > 0 && (
              <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-critical/15 text-critical">
                {findings.length} finding{findings.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
