export type Severity = "CRITICAL" | "MAJOR" | "MINOR";

export type Decision = "pending" | "approved" | "rejected" | "escalated";

export type Remediation = "none" | "blur" | "bleep" | "ai_fix";

export type VideoSource = "upload" | "twelvelabs" | "iconik";

export interface Finding {
  id: string;
  text: string;
  severity: Severity;
  confidence: number;
  timecode: number; // seconds
  rule: string;
  source: string;
  decision: Decision;
  remediation: Remediation;
}

export interface RightsEntry {
  id: string;
  asset: string;
  type: "music" | "footage" | "image" | "talent" | "brand" | "other";
  status: "cleared" | "pending" | "expired" | "denied";
  expiry_date: string;
  territory: string;
  notes: string;
  source: string;
  library: string;
}

export interface AnalysisResult {
  findings: Finding[];
  risk_score: number;
  risk_explanation: string;
  report: string;
  duration: number;
  rights_entries?: any[];
}

export type Platform =
  | "YouTube"
  | "TikTok"
  | "Instagram"
  | "Broadcast pre-watershed"
  | "Streaming Netflix/HBO"
  | "Roblox"
  | "The Sphere";

export type Jurisdiction =
  | "OFCOM UK"
  | "FCC US"
  | "GDPR EU"
  | "ARPP France"
  | "CRTC Canada"
  | "Multi-region";

export type TabId =
  | "compliance"
  | "rights"
  | "approve"
  | "ground-truth";

export interface ExportConfig {
  deliverable: string;
  deliverTo: string;
  formats: string[];
}
