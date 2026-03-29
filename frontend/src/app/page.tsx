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
import { uploadVideo, analyzeVideo } from "@/lib/api";
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

  // Video file + S3 state
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [s3Uri, setS3Uri] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Handlers
  const handleFileSelect = useCallback(async (file: File) => {
    const url = URL.createObjectURL(file);
    setVideoUrl(url);
    setVideoFile(file);
    setUploadError(null);

    // Upload to S3 in background
    try {
      const result = await uploadVideo(file);
      setS3Uri(result.s3_uri);
      console.log("Uploaded to S3:", result.s3_uri);
    } catch (err) {
      console.error("Upload failed:", err);
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    }
  }, []);

  const handleSeek = useCallback((time: number) => {
    setCurrentTime(time);
  }, []);

  const handleRunCheck = useCallback(
    async (config: {
      source: VideoSource;
      platforms: Platform[];
      jurisdictions: Jurisdiction[];
      customRules: string;
    }) => {
      setIsAnalyzing(true);
      setActiveTab("compliance");

      // If no S3 URI yet, fall back to mock data
      if (!s3Uri) {
        console.warn("No S3 URI — using mock data");
        await new Promise((resolve) => setTimeout(resolve, 2200));
        setFindings(MOCK_FINDINGS);
        setRightsEntries(MOCK_RIGHTS);
        setRiskScore(72);
        setRiskExplanation("Mock analysis — upload a video for real results.");
        setIsAnalyzing(false);
        return;
      }

      try {
        const result = await analyzeVideo({
          s3_uri: s3Uri,
          platforms: config.platforms,
          jurisdictions: config.jurisdictions,
          custom_rules: config.customRules || undefined,
          ruleset: "Broadcast Standards",
          include_rights: true,
        });

        // Map API findings to frontend Finding type
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const mappedFindings: Finding[] = ((result as any).findings || []).map((f: any, i: number) => ({
          id: `f${i}`,
          timecode: typeof f.timecode === "number" ? f.timecode : (f.timestamp_seconds as number) || 0,
          text: (f.text as string) || (f.description as string) || "",
          severity: ((f.severity as string) || "MINOR").toLowerCase() as Finding["severity"],
          confidence: (f.confidence as number) || 50,
          rule: (f.rule as string) || "",
          source: (f.source as string) || "compliance",
          decision: "pending" as Decision,
          remediation: "none" as Remediation,
        }));

        setFindings(mappedFindings);
        setRiskScore(result.risk_score || 0);
        setRiskExplanation(result.risk_explanation || "");

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const rawResult = result as any;
        if (rawResult.rights_entries && rawResult.rights_entries.length > 0) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const mappedRights: RightsEntry[] = rawResult.rights_entries.map((r: any, i: number) => ({
            id: `r${i}`,
            asset: (r.asset as string) || "",
            type: (r.type as string) || "other",
            status: "pending" as RightsEntry["status"],
            expiry_date: (r.expiry_date as string) || "",
            territory: (r.territory as string) || "",
            notes: (r.notes as string) || "",
            source: "auto-detected",
            library: "",
          }));
          setRightsEntries(mappedRights);
        }
      } catch (err) {
        console.error("Analysis failed:", err);
        // Fall back to mock on error
        setFindings(MOCK_FINDINGS);
        setRightsEntries(MOCK_RIGHTS);
        setRiskScore(72);
        setRiskExplanation("Analysis failed — showing mock data. Error: " + (err instanceof Error ? err.message : String(err)));
      }

      setIsAnalyzing(false);
    },
    [s3Uri]
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
