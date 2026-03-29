import type { AnalysisResult, RightsEntry } from "@/types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function uploadVideo(
  file: File
): Promise<{ s3_uri: string; video_id: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE_URL}/api/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Upload failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function analyzeVideo(params: {
  s3_uri: string;
  platforms: string[];
  jurisdictions: string[];
  custom_rules?: string;
  ruleset?: string;
  audio_flags?: string[];
  include_rights?: boolean;
}): Promise<AnalysisResult> {
  const res = await fetch(`${BASE_URL}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Analysis failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function getRights(): Promise<RightsEntry[]> {
  const res = await fetch(`${BASE_URL}/api/rights`);
  if (!res.ok) throw new Error("Failed to fetch rights");
  return res.json();
}

export async function saveRights(entry: Omit<RightsEntry, "id">): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/rights`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(entry),
  });
  if (!res.ok) throw new Error("Failed to save rights entry");
}

export async function exportManifest(params: {
  deliverable: string;
  deliver_to: string;
  formats: string[];
}): Promise<Blob> {
  const res = await fetch(`${BASE_URL}/api/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error("Export failed");
  return res.blob();
}

export async function healthCheck(): Promise<{ status: string; bedrock_available: boolean }> {
  const res = await fetch(`${BASE_URL}/api/health`);
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export async function regenClip(params: {
  video_uri: string;
  start_time: number;
  duration: number;
  prompt: string;
  mode: string;
  finding_id: string;
}): Promise<{
  finding_id: string;
  options: { id: string; video_url: string; prompt: string; duration: number }[];
}> {
  const res = await fetch(`${BASE_URL}/api/regen`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Regen failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function regenTextToVideo(params: {
  prompt: string;
  duration: number;
  finding_id: string;
}): Promise<{
  finding_id: string;
  options: { id: string; video_url: string; prompt: string; duration: number }[];
}> {
  const res = await fetch(`${BASE_URL}/api/regen/text-to-video`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Text-to-video regen failed (${res.status}): ${text}`);
  }
  return res.json();
}
