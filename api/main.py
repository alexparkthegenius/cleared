"""
FastAPI backend for the Cleared video compliance checking app.

Run with:
    uvicorn api.main:app --reload --port 8000
"""

import os
import time
import uuid
import logging
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

from config import RULESETS, JURISDICTIONS, PLATFORMS, AUDIO_FLAGS
from bedrock import (
    is_bedrock_available,
    upload_to_s3,
    get_s3_presigned_url,
    run_pegasus_analysis,
    search_with_marengo,
)
from helpers import (
    parse_findings,
    parse_rights_from_report,
    severity_score,
    build_prompt,
    finding_text,
    finding_severity,
    finding_confidence,
    parse_timestamp_seconds,
)

# ── Logging ───────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("cleared.api")

# ── App ───────────────────────────────────────────────────────

app = FastAPI(
    title="Cleared Compliance API",
    description="Video compliance checking powered by TwelveLabs Pegasus via AWS Bedrock",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory rights store (stateless per-process) ────────────
_rights_store: list[dict] = []


# ══════════════════════════════════════════════════════════════
# Pydantic Models
# ══════════════════════════════════════════════════════════════


class UploadResponse(BaseModel):
    s3_uri: str
    video_id: str
    presigned_url: str | None = None


class AnalyzeRequest(BaseModel):
    s3_uri: str
    platforms: list[str] = Field(default_factory=lambda: ["YouTube"])
    jurisdictions: list[str] = Field(default_factory=lambda: ["None"])
    ruleset: str = "Broadcast Standards"
    custom_rules: str = ""
    audio_flags: list[str] = Field(default_factory=list)
    include_rights: bool = True


class FindingOut(BaseModel):
    text: str
    severity: str
    confidence: int
    source: str
    rule: str
    timestamp_seconds: int = 0
    asset_type: str | None = None


class AnalyzeResponse(BaseModel):
    findings: list[FindingOut]
    rights_entries: list[dict]
    risk_score: int
    risk_explanation: str
    report: str
    analysis_duration: float
    video_id: str


class RightsEntry(BaseModel):
    asset: str
    type: str = "Other"
    expiry_date: str = ""
    notes: str = ""


class RightsEntryOut(BaseModel):
    id: str
    asset: str
    type: str
    expiry_date: str
    notes: str
    added_at: str
    auto_detected: bool = False


class ExportRequest(BaseModel):
    video_id: str = ""
    video_label: str = ""
    ruleset: str = ""
    platforms: list[str] = Field(default_factory=list)
    jurisdictions: list[str] = Field(default_factory=list)
    risk_score: int = 0
    deliverable_spec: str = "Web H.264 (1920x1080, AAC audio)"
    deliver_to: str = "Local download"
    findings: list[dict] = Field(default_factory=list)


class ExportResponse(BaseModel):
    manifest: dict


class HealthResponse(BaseModel):
    status: str
    bedrock_available: bool
    timestamp: str


# ══════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        bedrock_available=is_bedrock_available(),
        timestamp=datetime.now().isoformat(),
    )


@app.post("/api/upload", response_model=UploadResponse)
async def upload_video(file: UploadFile = File(...)):
    """Upload a video file to S3 and return the S3 URI."""
    if not is_bedrock_available():
        raise HTTPException(
            status_code=503,
            detail="AWS credentials not configured. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    filename = file.filename or f"video_{uuid.uuid4().hex[:8]}.mp4"
    video_id = f"{uuid.uuid4().hex[:12]}_{filename}"

    log.info(f"Uploading video: {filename} ({len(file_bytes)} bytes)")
    s3_uri = upload_to_s3(file_bytes, video_id)
    if not s3_uri:
        raise HTTPException(status_code=500, detail="Failed to upload video to S3.")

    presigned_url = get_s3_presigned_url(s3_uri)

    return UploadResponse(
        s3_uri=s3_uri,
        video_id=video_id,
        presigned_url=presigned_url,
    )


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_video(req: AnalyzeRequest):
    """Run Pegasus compliance analysis on a video.

    Accepts an S3 URI (from /api/upload) along with analysis parameters.
    Returns parsed findings, risk score, and the raw report.
    """
    if not is_bedrock_available():
        raise HTTPException(
            status_code=503,
            detail="AWS credentials not configured. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.",
        )

    # Validate ruleset
    if req.ruleset not in RULESETS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown ruleset: {req.ruleset}. Available: {list(RULESETS.keys())}",
        )

    # Validate platforms
    for p in req.platforms:
        if p not in PLATFORMS and p != "Custom":
            log.warning(f"Non-standard platform requested: {p}")

    # Build prompt (identical logic to Streamlit app)
    prompt = build_prompt(
        ruleset_name=req.ruleset,
        custom_rules=req.custom_rules,
        platforms=req.platforms,
        jurisdictions=req.jurisdictions,
        audio_flags=req.audio_flags,
        include_rights=req.include_rights,
    )

    log.info(f"Starting Pegasus analysis: s3={req.s3_uri}, ruleset={req.ruleset}")
    log.info(f"Prompt length: {len(prompt)} chars")
    t0 = time.time()

    # Run Pegasus
    report_data = run_pegasus_analysis(
        video_s3_uri=req.s3_uri,
        prompt=prompt,
    )
    if not report_data:
        raise HTTPException(
            status_code=500,
            detail="Pegasus analysis returned no results. Check AWS credentials and video input.",
        )

    elapsed = round(time.time() - t0, 1)
    log.info(f"Pegasus complete in {elapsed}s, response: {len(report_data)} chars")

    # Parse findings (compliance + rights -> unified list)
    compliance_findings = parse_findings(report_data)
    rights_entries_auto, rights_findings = parse_rights_from_report(report_data)
    all_findings = compliance_findings + rights_findings
    log.info(
        f"Parsed {len(compliance_findings)} compliance + "
        f"{len(rights_findings)} rights = {len(all_findings)} total findings"
    )

    # Compute risk score with breakdown (identical to Streamlit app)
    risk_score_val = severity_score(report_data)
    n_critical = report_data.upper().count("CRITICAL")
    n_major = report_data.upper().count("MAJOR")
    n_minor = report_data.upper().count("MINOR")
    risk_parts = []
    if n_critical:
        risk_parts.append(f"{n_critical} critical")
    if n_major:
        risk_parts.append(f"{n_major} major")
    if n_minor:
        risk_parts.append(f"{n_minor} minor")
    risk_explanation = ", ".join(risk_parts) if risk_parts else "no flags detected"

    log.info(f"Risk score: {risk_score_val}/100 — {risk_explanation}")

    # Build response findings
    findings_out = []
    for f in all_findings:
        findings_out.append(FindingOut(
            text=finding_text(f),
            severity=finding_severity(f),
            confidence=finding_confidence(f),
            source=f.get("source", "compliance"),
            rule=f.get("rule", "Content flag"),
            timestamp_seconds=parse_timestamp_seconds(f),
            asset_type=f.get("asset_type"),
        ))

    return AnalyzeResponse(
        findings=findings_out,
        rights_entries=rights_entries_auto,
        risk_score=risk_score_val,
        risk_explanation=risk_explanation,
        report=report_data,
        analysis_duration=elapsed,
        video_id=req.s3_uri,
    )


@app.post("/api/rights", response_model=RightsEntryOut)
async def create_rights_entry(entry: RightsEntry):
    """Create a new rights tracker entry."""
    record = {
        "id": uuid.uuid4().hex[:12],
        "asset": entry.asset,
        "type": entry.type,
        "expiry_date": entry.expiry_date,
        "notes": entry.notes,
        "added_at": datetime.now().isoformat(),
        "auto_detected": False,
    }
    _rights_store.append(record)
    log.info(f"Rights entry created: {record['id']} — {entry.asset[:50]}")
    return RightsEntryOut(**record)


@app.get("/api/rights", response_model=list[RightsEntryOut])
async def get_rights_entries():
    """Get all rights tracker entries."""
    return [RightsEntryOut(**r) for r in _rights_store]


@app.post("/api/export", response_model=ExportResponse)
async def create_export(req: ExportRequest):
    """Generate an export manifest JSON.

    Mirrors the Streamlit app's Commit & Export logic.
    """
    manifest = {
        "report_id": f"cleared_{int(time.time())}",
        "generated_at": datetime.now().isoformat(),
        "video_id": req.video_id,
        "video_label": req.video_label,
        "ruleset": req.ruleset,
        "platforms": req.platforms,
        "jurisdictions": req.jurisdictions,
        "risk_score": req.risk_score,
        "deliverable_spec": req.deliverable_spec,
        "deliver_to": req.deliver_to,
        "findings": [
            {
                "text": f.get("text", ""),
                "severity": f.get("severity", "MINOR"),
                "confidence": f.get("confidence", 70),
                "decision": f.get("decision", "pending"),
                "remediation": f.get("remediation", {}),
                "annotation": f.get("annotation", ""),
            }
            for f in req.findings
        ],
    }
    log.info(f"Export manifest generated: {manifest['report_id']}")
    return ExportResponse(manifest=manifest)


# ── Reference data endpoints ─────────────────────────────────


@app.get("/api/rulesets")
async def get_rulesets():
    """Return available rulesets and their rules."""
    return RULESETS


@app.get("/api/platforms")
async def get_platforms():
    """Return available platforms."""
    return PLATFORMS


@app.get("/api/jurisdictions")
async def get_jurisdictions():
    """Return available jurisdictions."""
    return JURISDICTIONS


@app.get("/api/audio-flags")
async def get_audio_flags():
    """Return available audio flag options."""
    return AUDIO_FLAGS
