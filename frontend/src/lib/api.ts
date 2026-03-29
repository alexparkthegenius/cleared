import type { AnalysisResult, RightsEntry } from "@/types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function uploadVideo(
  file: File
): Promise<{ s3_uri: string; video_id: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE_URL}/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error("Upload failed");
  return res.json();
}

export async function analyzeVideo(params: {
  video_id: string;
  platforms: string[];
  jurisdictions: string[];
  custom_rules?: string;
}): Promise<AnalysisResult> {
  const res = await fetch(`${BASE_URL}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error("Analysis failed");
  return res.json();
}

export async function getRights(): Promise<RightsEntry[]> {
  const res = await fetch(`${BASE_URL}/rights`);
  if (!res.ok) throw new Error("Failed to fetch rights");
  return res.json();
}

export async function saveRights(entry: Omit<RightsEntry, "id">): Promise<void> {
  const res = await fetch(`${BASE_URL}/rights`, {
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
  const res = await fetch(`${BASE_URL}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error("Export failed");
  return res.blob();
}
