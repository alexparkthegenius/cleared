"use client";

import { forwardRef } from "react";
import type { Finding, RightsEntry } from "@/types";

interface ComplianceReportPrintProps {
  findings: Finding[];
  rightsEntries: RightsEntry[];
  riskScore: number | null;
  riskExplanation: string;
  videoLabel: string;
  platforms: string[];
  jurisdictions: string[];
  ruleset: string;
  analysisDuration?: number;
}

function formatTimecode(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function riskLevel(score: number): string {
  if (score >= 70) return "HIGH";
  if (score >= 40) return "MEDIUM";
  return "LOW";
}

const ComplianceReportPrint = forwardRef<HTMLDivElement, ComplianceReportPrintProps>(
  function ComplianceReportPrint(
    {
      findings,
      rightsEntries,
      riskScore,
      riskExplanation,
      videoLabel,
      platforms,
      jurisdictions,
      ruleset,
      analysisDuration,
    },
    ref
  ) {
    const score = riskScore ?? 0;
    const critical = findings.filter((f) => f.severity === "CRITICAL").length;
    const major = findings.filter((f) => f.severity === "MAJOR").length;
    const minor = findings.filter((f) => f.severity === "MINOR").length;
    const dateStr = new Date().toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });

    return (
      <div ref={ref} className="compliance-report-print">
        <style>{`
          @media print {
            body * { visibility: hidden !important; }
            .compliance-report-print, .compliance-report-print * { visibility: visible !important; }
            .compliance-report-print {
              position: absolute !important;
              left: 0; top: 0;
              width: 100% !important;
              background: white !important;
              color: #111 !important;
              font-size: 11px !important;
              line-height: 1.5 !important;
            }
          }
          @media screen {
            .compliance-report-print {
              position: fixed;
              left: -9999px;
              top: 0;
              width: 210mm;
              background: white;
              color: #111;
              font-size: 11px;
              line-height: 1.5;
              padding: 20mm 15mm;
              font-family: Arial, Helvetica, sans-serif;
            }
          }
          .compliance-report-print h1 { font-size: 20px; margin: 0 0 12px; color: #111; }
          .compliance-report-print h2 { font-size: 14px; margin: 20px 0 8px; color: #111; border-bottom: 1px solid #ccc; padding-bottom: 4px; }
          .compliance-report-print table { width: 100%; border-collapse: collapse; font-size: 10px; margin: 8px 0; }
          .compliance-report-print th, .compliance-report-print td { border: 1px solid #ddd; padding: 4px 6px; text-align: left; }
          .compliance-report-print th { background: #f5f5f5; font-weight: 600; }
          .compliance-report-print .meta-grid { display: grid; grid-template-columns: auto 1fr; gap: 2px 12px; margin-bottom: 12px; font-size: 11px; }
          .compliance-report-print .meta-grid dt { font-weight: 600; }
          .compliance-report-print .meta-grid dd { margin: 0; }
          .compliance-report-print hr { border: none; border-top: 1px solid #ccc; margin: 16px 0; }
          .compliance-report-print .footer { margin-top: 24px; font-size: 9px; color: #888; font-style: italic; }
        `}</style>

        <h1>Cleared Compliance Report</h1>

        <dl className="meta-grid">
          <dt>Video:</dt>
          <dd>{videoLabel || "Untitled"}</dd>
          <dt>Date:</dt>
          <dd>{dateStr}</dd>
          <dt>Risk Score:</dt>
          <dd>
            {score}/100 &mdash; {riskLevel(score)}
          </dd>
          <dt>Platforms:</dt>
          <dd>{platforms.length > 0 ? platforms.join(", ") : "None selected"}</dd>
          <dt>Jurisdictions:</dt>
          <dd>{jurisdictions.length > 0 ? jurisdictions.join(", ") : "None selected"}</dd>
          <dt>Ruleset:</dt>
          <dd>{ruleset}</dd>
          {analysisDuration != null && (
            <>
              <dt>Analysis Duration:</dt>
              <dd>{analysisDuration}s</dd>
            </>
          )}
        </dl>

        <hr />

        <h2>Risk Assessment</h2>
        <p>
          <strong>
            {score}/100 &mdash; {critical} critical, {major} major, {minor} minor
          </strong>
        </p>
        {riskExplanation && <p>{riskExplanation}</p>}

        <hr />

        <h2>Findings</h2>
        {findings.length === 0 ? (
          <p>No findings.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Timecode</th>
                <th>Severity</th>
                <th>Confidence</th>
                <th>Rule</th>
                <th>Description</th>
                <th>Decision</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((f, i) => (
                <tr key={f.id}>
                  <td>{i + 1}</td>
                  <td>{formatTimecode(f.timecode)}</td>
                  <td>{f.severity}</td>
                  <td>{f.confidence}%</td>
                  <td>{f.rule}</td>
                  <td>{f.text}</td>
                  <td>{f.decision}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <hr />

        <h2>Rights &amp; Clearances</h2>
        {rightsEntries.length === 0 ? (
          <p>No rights entries.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Asset</th>
                <th>Type</th>
                <th>Status</th>
                <th>Expiry</th>
              </tr>
            </thead>
            <tbody>
              {rightsEntries.map((r) => (
                <tr key={r.id}>
                  <td>{r.asset}</td>
                  <td>{r.type}</td>
                  <td>{r.status}</td>
                  <td>{r.expiry_date || "N/A"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <hr />

        <h2>Overall Assessment</h2>
        <p>{riskExplanation || "No assessment available."}</p>

        <hr />

        <div className="footer">
          Generated by Cleared Compliance &mdash; {dateStr}
        </div>
      </div>
    );
  }
);

export default ComplianceReportPrint;
