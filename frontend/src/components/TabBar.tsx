"use client";

import type { TabId } from "@/types";

interface TabBarProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  findingsCount: number;
}

const TABS: { id: TabId; label: string }[] = [
  { id: "compliance", label: "Compliance Findings" },
  { id: "rights", label: "Rights Tracker" },
  { id: "approve", label: "Approve & Send" },
  { id: "ground-truth", label: "Ground Truth" },
];

export default function TabBar({
  activeTab,
  onTabChange,
  findingsCount,
}: TabBarProps) {
  return (
    <div className="flex border-b border-border bg-surface/50">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={`relative px-5 py-3 text-xs font-semibold transition-colors ${
            activeTab === tab.id
              ? "text-foreground"
              : "text-muted hover:text-foreground/70"
          }`}
        >
          <span className="flex items-center gap-2">
            {tab.label}
            {tab.id === "compliance" && findingsCount > 0 && (
              <span className="min-w-[18px] h-[18px] flex items-center justify-center text-[10px] font-bold rounded-full bg-critical/15 text-critical px-1">
                {findingsCount}
              </span>
            )}
          </span>
          {activeTab === tab.id && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-500" />
          )}
        </button>
      ))}
    </div>
  );
}
