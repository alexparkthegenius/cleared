"use client";

import { useState, useCallback, useEffect, useRef } from "react";
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
  const [seekTarget, setSeekTarget] = useState<number | null>(null);

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

  // Analysis config (stored for report export)
  const [lastPlatforms, setLastPlatforms] = useState<Platform[]>([]);
  const [lastJurisdictions, setLastJurisdictions] = useState<Jurisdiction[]>([]);

  // Video file + S3 state
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [s3Uri, setS3Uri] = useState<string | null>(null);
  const s3UriRef = useRef<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const uploadDoneRef = useRef(false);

  // Handlers
  const handleFileSelect = useCallback(async (file: File) => {
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    const url = URL.createObjectURL(file);
    setVideoUrl(url);
    setVideoFile(file);
    setUploadError(null);

    // Reset S3 state BEFORE starting new upload
    setS3Uri(null);
    s3UriRef.current = null;
    uploadDoneRef.current = false;
    setIsUploading(true);

    // Clear previous analysis state
    setFindings([]);
    setRiskScore(null);
    setRiskExplanation("");
    setRightsEntries([]);
    setCurrentTime(0);
    setSeekTarget(null);

    // Upload to S3
    try {
      const result = await uploadVideo(file);
      setS3Uri(result.s3_uri);
      s3UriRef.current = result.s3_uri;
      console.log("Uploaded to S3:", result.s3_uri);
    } catch (err) {
      console.error("Upload failed:", err);
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
      uploadDoneRef.current = true;
    }
  }, [videoUrl]);

  const handleTwelveLabsVideoSelect = useCallback(
    (hlsUrl: string, indexId: string, videoId: string) => {
      // Set the HLS URL as the video source for the player
      setVideoUrl(hlsUrl);
      // Use a twelvelabs:// pseudo-URI so the rest of the app has a reference
      const pseudoUri = `twelvelabs://${indexId}/${videoId}`;
      setS3Uri(pseudoUri);
      s3UriRef.current = pseudoUri;
      uploadDoneRef.current = true;
      setIsUploading(false);
      setUploadError(null);
      // Clear previous analysis
      setFindings([]);
      setRiskScore(null);
      setRiskExplanation("");
      setRightsEntries([]);
      setCurrentTime(0);
      setSeekTarget(null);
      console.log("TwelveLabs video selected:", hlsUrl, pseudoUri);
    },
    []
  );

  const handleSeek = useCallback((time: number) => {
    setCurrentTime(time);
    // Force re-seek even if same timecode by briefly nulling then setting
    setSeekTarget(null);
    requestAnimationFrame(() => setSeekTarget(time));
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
      setLastPlatforms(config.platforms);
      setLastJurisdictions(config.jurisdictions);

      // Wait for upload if still in progress
      if (isUploading) {
        console.log("Waiting for upload to complete...");
        await new Promise<void>((resolve) => {
          const check = setInterval(() => {
            if (s3UriRef.current || uploadDoneRef.current) {
              clearInterval(check);
              resolve();
            }
          }, 200);
          // Timeout after 60s
          setTimeout(() => { clearInterval(check); resolve(); }, 60000);
        });
      }

      const currentS3Uri = s3UriRef.current;

      // If no S3 URI yet, fall back to mock data
      if (!currentS3Uri) {
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
          s3_uri: currentS3Uri,
          platforms: config.platforms,
          jurisdictions: config.jurisdictions,
          custom_rules: config.customRules || undefined,
          ruleset: "Broadcast Standards",
          include_rights: true,
        });

        // Debug: log raw API response
        console.log("Raw API response:", JSON.stringify(result, null, 2));

        // Map API findings to frontend Finding type
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const mappedFindings: Finding[] = ((result as any).findings || []).map((f: any, i: number) => {
          const tc = Number(f.timecode ?? f.timestamp_seconds ?? 0);
          if (i < 5) console.log(`Finding ${i} timecode mapping: timecode=${f.timecode}, timestamp_seconds=${f.timestamp_seconds}, resolved=${tc}`);
          return {
          id: `f${i}`,
          timecode: isNaN(tc) ? 0 : tc,
          text: ((f.text as string) || (f.description as string) || "").replace(/\s*—\s*Severity:\s*\w+\s*—\s*Confidence:\s*\d+/gi, ""),
          severity: ((f.severity as string) || "MINOR").toUpperCase() as Finding["severity"],
          confidence: (f.confidence as number) || 50,
          rule: (f.rule as string) || "",
          source: (f.source as string) || "compliance",
          decision: "pending" as Decision,
          remediation: "none" as Remediation,
        }});

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
    [isUploading]
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
    async (config: { deliverable: string; deliverTo: string; formats: string[] }) => {
      setIsExporting(true);
      try {
        const manifest = {
          report_id: `cleared_${Date.now()}`,
          generated_at: new Date().toISOString(),
          video_id: s3Uri || videoUrl || "",
          video_label: videoUrl ? "Uploaded video" : "",
          ruleset: "Broadcast Standards",
          platforms: [],
          jurisdictions: [],
          risk_score: riskScore,
          deliverable_spec: config.deliverable,
          deliver_to: config.deliverTo,
          exchange_formats: config.formats,
          findings: findings.map((f) => ({
            text: f.text,
            severity: f.severity,
            confidence: f.confidence,
            timecode: f.timecode,
            rule: f.rule,
            decision: f.decision || "pending",
            remediation: f.remediation || "none",
          })),
        };
        const blob = new Blob([JSON.stringify(manifest, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `cleared_export_${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
        console.log("Export manifest downloaded:", manifest.report_id);
      } catch (err) {
        console.error("Export failed:", err);
      } finally {
        setIsExporting(false);
      }
    },
    [findings, s3Uri, videoUrl, riskScore]
  );

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        onFileSelect={handleFileSelect}
        onTwelveLabsVideoSelect={handleTwelveLabsVideoSelect}
        onRunCheck={handleRunCheck}
        isAnalyzing={isAnalyzing}
        theme={theme}
        onThemeToggle={() => setTheme(theme === "dark" ? "light" : "dark")}
      />

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top: Video + Violations */}
        <div className="flex border-b border-border" style={{ height: '50vh', minHeight: '250px' }}>
          {/* Video Player */}
          <div className="flex-1 min-w-0 p-3 pb-1">
            <VideoPlayer
              videoUrl={videoUrl}
              findings={findings}
              currentTime={currentTime}
              onTimeUpdate={setCurrentTime}
              onSeek={handleSeek}
              duration={duration}
              onDurationChange={setDuration}
              seekTarget={seekTarget}
            />
          </div>

          {/* Violations Panel */}
          <div className="w-72 flex-shrink-0 border-l border-border bg-surface overflow-y-auto">
            <ViolationsPanel
              findings={findings}
              currentTime={currentTime}
              onSeek={handleSeek}
            />
          </div>
        </div>

        {/* Bottom: Tabs + Content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Tab Bar */}
          <TabBar
            activeTab={activeTab}
            onTabChange={setActiveTab}
            findingsCount={findings.length}
          />

          {/* Tab Content — scrollable */}
          <div className="flex-1 overflow-y-auto p-4 pb-20">
          {activeTab === "compliance" && (
            <ComplianceFindings
              findings={findings}
              currentTime={currentTime}
              onSeek={handleSeek}
              onDecision={handleDecision}
              onRemediation={handleRemediation}
              riskScore={riskScore}
              riskExplanation={riskExplanation}
              s3Uri={s3Uri}
            />
          )}
          {activeTab === "rights" && (
            <RightsTracker
              entries={rightsEntries}
              onAddEntry={handleAddRightsEntry}
              onSeek={handleSeek}
            />
          )}
          {activeTab === "approve" && (
            <ExportPanel
              onExport={handleExport}
              isExporting={isExporting}
              findings={findings}
              rightsEntries={rightsEntries}
              riskScore={riskScore}
              riskExplanation={riskExplanation}
              videoLabel={videoFile?.name || videoUrl || ""}
              platforms={lastPlatforms}
              jurisdictions={lastJurisdictions}
              ruleset="Broadcast Standards"
            />
          )}
          {activeTab === "ground-truth" && (
            <GroundTruth
              initialValue={groundTruth}
              onSave={setGroundTruth}
              findings={findings}
            />
          )}
          </div>
        </div>
      </main>
    </div>
  );
}
