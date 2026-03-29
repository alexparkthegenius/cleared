"use client";

import { useState } from "react";
import type { RightsEntry } from "@/types";

interface RightsTrackerProps {
  entries: RightsEntry[];
  onAddEntry: (entry: Omit<RightsEntry, "id">) => void;
  onSeek?: (time: number) => void;
}

const TYPES = ["music", "footage", "image", "talent", "brand", "other"] as const;
const STATUSES = ["cleared", "pending", "expired", "denied"] as const;

function statusBadge(status: string) {
  switch (status) {
    case "cleared":
      return "bg-emerald-500/15 text-emerald-400";
    case "pending":
      return "bg-amber-500/15 text-amber-400";
    case "expired":
      return "bg-red-500/15 text-red-400";
    case "denied":
      return "bg-red-500/15 text-red-400";
    default:
      return "bg-gray-500/15 text-gray-400";
  }
}

function typeBadge(type: string) {
  const colors = [
    "bg-emerald-500/15 text-emerald-400",
    "bg-blue-500/15 text-blue-400",
    "bg-purple-500/15 text-purple-400",
    "bg-pink-500/15 text-pink-400",
    "bg-amber-500/15 text-amber-400",
    "bg-cyan-500/15 text-cyan-400",
  ];
  const idx = TYPES.indexOf(type as (typeof TYPES)[number]);
  return colors[idx >= 0 ? idx : 5];
}

function parseTimecodeFromAsset(asset: string): number | null {
  const match = asset.match(/\[(\d{1,2}):(\d{2})\]/);
  if (match) {
    return parseInt(match[1], 10) * 60 + parseInt(match[2], 10);
  }
  const secMatch = asset.match(/\[(\d+)\]/);
  if (secMatch) {
    return parseInt(secMatch[1], 10);
  }
  return null;
}

export default function RightsTracker({
  entries,
  onAddEntry,
  onSeek,
}: RightsTrackerProps) {
  const [filterType, setFilterType] = useState<string>("all");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [filterLibrary, setFilterLibrary] = useState<string>("all");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    asset: "",
    type: "music" as RightsEntry["type"],
    status: "pending" as RightsEntry["status"],
    expiry_date: "",
    territory: "",
    notes: "",
    source: "",
    library: "",
  });

  const libraries = Array.from(new Set(entries.map((e) => e.library).filter(Boolean)));

  const filtered = entries.filter((e) => {
    if (filterType !== "all" && e.type !== filterType) return false;
    if (filterStatus !== "all" && e.status !== filterStatus) return false;
    if (filterLibrary !== "all" && e.library !== filterLibrary) return false;
    return true;
  });

  const handleSubmit = () => {
    if (!form.asset) return;
    onAddEntry(form);
    setForm({
      asset: "",
      type: "music",
      status: "pending",
      expiry_date: "",
      territory: "",
      notes: "",
      source: "",
      library: "",
    });
    setShowForm(false);
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-muted">
            Type
          </label>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="bg-background border border-border rounded px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
          >
            <option value="all">All</option>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-muted">
            Status
          </label>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="bg-background border border-border rounded px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
          >
            <option value="all">All</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-muted">
            Library
          </label>
          <select
            value={filterLibrary}
            onChange={(e) => setFilterLibrary(e.target.value)}
            className="bg-background border border-border rounded px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
          >
            <option value="all">All</option>
            {libraries.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <div className="flex-1" />
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-colors"
        >
          {showForm ? "Cancel" : "+ Add Entry"}
        </button>
      </div>

      {/* Add Entry Form */}
      {showForm && (
        <div className="p-4 rounded-lg border border-border bg-surface space-y-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted">
            New Rights Entry
          </h4>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] text-muted mb-1">Asset Name *</label>
              <input
                value={form.asset}
                onChange={(e) => setForm({ ...form, asset: e.target.value })}
                className="w-full px-2.5 py-1.5 bg-background border border-border rounded text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
                placeholder="e.g., Background Music Track"
              />
            </div>
            <div>
              <label className="block text-[10px] text-muted mb-1">Type</label>
              <select
                value={form.type}
                onChange={(e) =>
                  setForm({ ...form, type: e.target.value as RightsEntry["type"] })
                }
                className="w-full px-2.5 py-1.5 bg-background border border-border rounded text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
              >
                {TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[10px] text-muted mb-1">Status</label>
              <select
                value={form.status}
                onChange={(e) =>
                  setForm({ ...form, status: e.target.value as RightsEntry["status"] })
                }
                className="w-full px-2.5 py-1.5 bg-background border border-border rounded text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[10px] text-muted mb-1">Expiry Date</label>
              <input
                type="date"
                value={form.expiry_date}
                onChange={(e) => setForm({ ...form, expiry_date: e.target.value })}
                className="w-full px-2.5 py-1.5 bg-background border border-border rounded text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
              />
            </div>
            <div>
              <label className="block text-[10px] text-muted mb-1">Territory</label>
              <input
                value={form.territory}
                onChange={(e) => setForm({ ...form, territory: e.target.value })}
                className="w-full px-2.5 py-1.5 bg-background border border-border rounded text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
                placeholder="e.g., Worldwide"
              />
            </div>
            <div>
              <label className="block text-[10px] text-muted mb-1">Source</label>
              <input
                value={form.source}
                onChange={(e) => setForm({ ...form, source: e.target.value })}
                className="w-full px-2.5 py-1.5 bg-background border border-border rounded text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
                placeholder="e.g., Shutterstock"
              />
            </div>
            <div>
              <label className="block text-[10px] text-muted mb-1">Library</label>
              <input
                value={form.library}
                onChange={(e) => setForm({ ...form, library: e.target.value })}
                className="w-full px-2.5 py-1.5 bg-background border border-border rounded text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
                placeholder="e.g., Stock Footage"
              />
            </div>
            <div>
              <label className="block text-[10px] text-muted mb-1">Notes</label>
              <input
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                className="w-full px-2.5 py-1.5 bg-background border border-border rounded text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
                placeholder="Additional notes..."
              />
            </div>
          </div>
          <button
            onClick={handleSubmit}
            disabled={!form.asset}
            className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold transition-colors"
          >
            Save Entry
          </button>
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-background/50">
              <th className="text-left px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
                Asset
              </th>
              <th className="text-left px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
                Type
              </th>
              <th className="text-left px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
                Status
              </th>
              <th className="text-left px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
                Territory
              </th>
              <th className="text-left px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
                Expiry
              </th>
              <th className="text-left px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
                Notes
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-8 text-center text-muted">
                  No rights entries found
                </td>
              </tr>
            ) : (
              filtered.map((entry) => {
                const tc = parseTimecodeFromAsset(entry.asset);
                return (
                <tr
                  key={entry.id}
                  onClick={() => { if (tc != null && onSeek) onSeek(tc); }}
                  className={`border-t border-border/50 hover:bg-foreground/[0.02] transition-colors ${tc != null && onSeek ? "cursor-pointer" : ""}`}
                >
                  <td className="px-3 py-2.5 font-medium text-foreground">
                    {entry.asset}
                  </td>
                  <td className="px-3 py-2.5">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${typeBadge(
                        entry.type
                      )}`}
                    >
                      {entry.type}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${statusBadge(
                        entry.status
                      )}`}
                    >
                      {entry.status}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-muted">{entry.territory}</td>
                  <td className="px-3 py-2.5 text-muted tabular-nums">
                    {entry.expiry_date || "N/A"}
                  </td>
                  <td className="px-3 py-2.5 text-muted max-w-[200px] truncate">
                    {entry.notes}
                  </td>
                </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
