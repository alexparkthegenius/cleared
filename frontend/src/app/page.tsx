"use client";

import { useState, useCallback, useEffect } from "react";
import type {
  Finding,
  RightsEntry,
  TabId,
  Decision,
  Remediation,
  VideoSource,
  Platform,
  Jurisdiction,
} from "@/types";
import { MOCK_FINDINGS, MOCK_RIGHTS } from "@/lib/mockData";
import Sidebar from "@/components/Sidebar";
import VideoPlayer from "@/components/VideoPlayer";
import ViolationsPanel from "@/components/ViolationsPanel";
import TabBar from "@/components/TabBar";
import ComplianceFindings from "@/components/ComplianceFindings";
import RightsTracker from "@/components/RightsTracker";
import ExportPanel from "@/components/ExportPanel";
import GroundTruth from "@/components/GroundTruth";

export default function Home() {
  // Theme
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  // Sidebar
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Video state
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(120);

  // Analysis
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [riskScore, setRiskScore] = useState<number | null>(null);
  const [riskExplanation, setRiskExplanation] = useState("");

  // Rights
  const [rightsEntries, setRightsEntries] = useState<RightsEntry[]>([]);

  // Tabs
  const [activeTab, setActiveTab] = useState<TabId>("compliance");

  // Export
  const [isExporting, setIsExporting] = useState(false);

  // Ground truth
  const [groundTruth, setGroundTruth] = useState("");

  // Handlers
  const handleFileSelect = useCallback((file: File) => {
    const url = URL.createObjectURL(file);
    setVideoUrl(url);
  }, []);

  const handleSeek = useCallback((time: number) => {
    setCurrentTime(time);
  }, []);

  const handleRunCheck = useCallback(
    async (_config: {
      source: VideoSource;
      platforms: Platform[];
      jurisdictions: Jurisdiction[];
      customRules: string;
    }) => {
      setIsAnalyzing(true);
      setActiveTab("compliance");

      // Simulate API call with mock data
      await new Promise((resolve) => setTimeout(resolve, 2200));

      setFindings(MOCK_FINDINGS);
      setRightsEntries(MOCK_RIGHTS);
      setRiskScore(72);
      setRiskExplanation(
        "High risk due to 2 critical findings including unblurred minor and age-rating violation. " +
          "2 major issues with undisclosed product placement and potential copyright infringement. " +
          "Recommend immediate remediation before distribution."
      );
      setIsAnalyzing(false);
    },
    []
  );

  const handleDecision = useCallback(
    (id: string, decision: Decision) => {
      setFindings((prev) =>
        prev.map((f) => (f.id === id ? { ...f, decision } : f))
      );
    },
    []
  );

  const handleRemediation = useCallback(
    (id: string, remediation: Remediation) => {
      setFindings((prev) =>
        prev.map((f) => (f.id === id ? { ...f, remediation } : f))
      );
    },
    []
  );

  const handleAddRightsEntry = useCallback(
    (entry: Omit<RightsEntry, "id">) => {
      const newEntry: RightsEntry = {
        ...entry,
        id: `r${Date.now()}`,
      };
      setRightsEntries((prev) => [...prev, newEntry]);
    },
    []
  );

  const handleExport = useCallback(
    async (_config: { deliverable: string; deliverTo: string; formats: string[] }) => {
      setIsExporting(true);
      await new Promise((resolve) => setTimeout(resolve, 1500));
      setIsExporting(false);
      // In production, call exportManifest API
    },
    []
  );

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        onFileSelect={handleFileSelect}
        onRunCheck={handleRunCheck}
        isAnalyzing={isAnalyzing}
        theme={theme}
        onThemeToggle={() => setTheme(theme === "dark" ? "light" : "dark")}
      />

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Video + Violations Row */}
        <div className="flex-shrink-0 flex border-b border-border">
          {/* Video Player — sticky context */}
          <div className="flex-1 min-w-0 p-4 pb-2">
            <div className="sticky top-0 z-10">
              <VideoPlayer
                videoUrl={videoUrl}
                findings={findings}
                currentTime={currentTime}
                onTimeUpdate={setCurrentTime}
                onSeek={handleSeek}
                duration={duration}
                onDurationChange={setDuration}
              />
            </div>
          </div>

          {/* Violations Panel */}
          <div className="w-64 flex-shrink-0 border-l border-border bg-surface overflow-hidden flex flex-col">
            <ViolationsPanel
              findings={findings}
              currentTime={currentTime}
              onSeek={handleSeek}
            />
          </div>
        </div>

        {/* Tab Bar */}
        <TabBar
          activeTab={activeTab}
          onTabChange={setActiveTab}
          findingsCount={findings.length}
        />

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {activeTab === "compliance" && (
            <ComplianceFindings
              findings={findings}
              currentTime={currentTime}
              onSeek={handleSeek}
              onDecision={handleDecision}
              onRemediation={handleRemediation}
              riskScore={riskScore}
              riskExplanation={riskExplanation}
            />
          )}
          {activeTab === "rights" && (
            <RightsTracker
              entries={rightsEntries}
              onAddEntry={handleAddRightsEntry}
            />
          )}
          {activeTab === "export" && (
            <ExportPanel onExport={handleExport} isExporting={isExporting} />
          )}
          {activeTab === "ground-truth" && (
            <GroundTruth
              initialValue={groundTruth}
              onSave={setGroundTruth}
            />
          )}
        </div>
      </main>
    </div>
  );
}
