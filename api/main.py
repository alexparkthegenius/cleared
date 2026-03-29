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
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# ── Request logging (non-middleware approach to avoid CORS interference) ───
from starlette.requests import Request
import traceback


# ── Global exception handler ──────────────────────────────────
from fastapi.responses import JSONResponse


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"Unhandled exception on {request.method} {request.url.path}: "
              f"{type(exc).__name__}: {exc}")
    log.debug(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}: {str(exc)}"},
    )


# ── Startup logging ──────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    log.info("=" * 60)
    log.info("Cleared API starting up")
    log.info(f"Bedrock available: {is_bedrock_available()}")
    log.info(f"AWS region: {os.environ.get('AWS_DEFAULT_REGION', 'not set')}")
    log.info(f"S3 bucket: {os.environ.get('CLEARED_S3_BUCKET', 'not set')}")
    log.info(f"AWS account: {os.environ.get('AWS_ACCOUNT_ID', 'not set')}")
    log.info("=" * 60)


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
    log.info(f"Upload request received: filename={file.filename}, content_type={file.content_type}")

    if not is_bedrock_available():
        log.error("Upload rejected: AWS credentials not configured")
        raise HTTPException(
            status_code=503,
            detail="AWS credentials not configured. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.",
        )

    try:
        file_bytes = await file.read()
    except Exception:
        log.exception("Failed to read uploaded file")
        raise HTTPException(status_code=400, detail="Failed to read uploaded file.")

    if not file_bytes:
        log.warning("Upload rejected: empty file")
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    filename = file.filename or f"video_{uuid.uuid4().hex[:8]}.mp4"
    video_id = f"{uuid.uuid4().hex[:12]}_{filename}"

    log.info(f"Uploading to S3: filename={filename}, size={len(file_bytes)} bytes, video_id={video_id}")
    try:
        s3_uri = upload_to_s3(file_bytes, video_id)
    except Exception:
        log.exception(f"S3 upload failed: filename={filename}, video_id={video_id}")
        raise HTTPException(status_code=500, detail="Failed to upload video to S3. Check AWS credentials.")

    if not s3_uri:
        log.error(f"S3 upload returned None: filename={filename}, video_id={video_id}")
        raise HTTPException(status_code=500, detail="Failed to upload video to S3.")

    log.info(f"S3 upload successful: s3_uri={s3_uri}")

    try:
        presigned_url = get_s3_presigned_url(s3_uri)
    except Exception:
        log.exception(f"Failed to generate presigned URL for s3_uri={s3_uri}")
        presigned_url = None

    return UploadResponse(
        s3_uri=s3_uri,
        video_id=video_id,
        presigned_url=presigned_url,
    )


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_video(req: AnalyzeRequest):
    """Run Pegasus compliance analysis on a video."""
    log.info(f"Analyze request: s3_uri={req.s3_uri[:60]}..., ruleset={req.ruleset}, "
             f"platforms={req.platforms}, jurisdictions={req.jurisdictions}")

    if not is_bedrock_available():
        log.error("Analysis rejected: AWS credentials not configured")
        raise HTTPException(
            status_code=503,
            detail="AWS credentials not configured. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.",
        )

    # Validate ruleset
    if req.ruleset not in RULESETS:
        log.error(f"Unknown ruleset requested: {req.ruleset}")
        raise HTTPException(
            status_code=400,
            detail=f"Unknown ruleset: {req.ruleset}. Available: {list(RULESETS.keys())}",
        )

    # Validate platforms
    for p in req.platforms:
        if p not in PLATFORMS and p != "Custom":
            log.warning(f"Non-standard platform requested: {p}")

    # Build prompt
    try:
        prompt = build_prompt(
            ruleset_name=req.ruleset,
            custom_rules=req.custom_rules,
            platforms=req.platforms,
            jurisdictions=req.jurisdictions,
            audio_flags=req.audio_flags,
            include_rights=req.include_rights,
        )
        log.info(f"Prompt built: {len(prompt)} chars")
    except Exception:
        log.exception("Failed to build analysis prompt")
        raise HTTPException(status_code=500, detail="Failed to build analysis prompt.")

    t0 = time.time()

    # Run Pegasus
    try:
        log.info(f"Invoking Pegasus: s3_uri={req.s3_uri[:60]}...")
        report_data = run_pegasus_analysis(
            video_s3_uri=req.s3_uri,
            prompt=prompt,
        )
    except Exception:
        elapsed = round(time.time() - t0, 1)
        log.exception(f"Pegasus invocation failed after {elapsed}s: s3_uri={req.s3_uri[:60]}")
        raise HTTPException(
            status_code=500,
            detail="Pegasus analysis failed. Check AWS credentials, S3 permissions, and video format.",
        )

    if not report_data:
        elapsed = round(time.time() - t0, 1)
        log.error(f"Pegasus returned empty response after {elapsed}s: s3_uri={req.s3_uri[:60]}")
        raise HTTPException(
            status_code=500,
            detail="Pegasus analysis returned no results. Check AWS credentials and video input.",
        )

    elapsed = round(time.time() - t0, 1)
    log.info(f"Pegasus complete: {elapsed}s, response_length={len(report_data)} chars")
    log.info(f"Report preview: {report_data[:200]}...")

    # Parse findings
    try:
        compliance_findings = parse_findings(report_data)
        rights_entries_auto, rights_findings = parse_rights_from_report(report_data)
        all_findings = compliance_findings + rights_findings
        log.info(f"Parsed findings: {len(compliance_findings)} compliance + "
                 f"{len(rights_findings)} rights = {len(all_findings)} total, "
                 f"{len(rights_entries_auto)} auto-detected rights entries")
    except Exception:
        log.exception(f"Failed to parse Pegasus response: report_length={len(report_data)}")
        raise HTTPException(status_code=500, detail="Failed to parse analysis results.")

    # Compute risk score
    try:
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
    except Exception:
        log.exception("Failed to compute risk score")
        risk_score_val = 0
        risk_explanation = "scoring error"

    # Build response
    findings_out = []
    for i, f in enumerate(all_findings):
        try:
            findings_out.append(FindingOut(
                text=finding_text(f),
                severity=finding_severity(f),
                confidence=finding_confidence(f),
                source=f.get("source", "compliance"),
                rule=f.get("rule", "Content flag"),
                timestamp_seconds=parse_timestamp_seconds(f),
                asset_type=f.get("asset_type"),
            ))
        except Exception:
            log.exception(f"Failed to serialize finding {i}: {f}")

    log.info(f"Analysis complete: {len(findings_out)} findings, risk={risk_score_val}/100, "
             f"duration={elapsed}s, video={req.s3_uri[:40]}")

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


# ══════════════════════════════════════════════════════════════
# LTX Video Regeneration
# ══════════════════════════════════════════════════════════════

import httpx

LTX_API_KEY = os.environ.get("LTX_API_KEY", "")

REGEN_MODES = {"replace_video", "replace_audio", "replace_audio_and_video"}


class RegenOption(BaseModel):
    id: str
    video_url: str
    prompt: str
    duration: float


class RegenRequest(BaseModel):
    video_uri: str
    start_time: float
    duration: float = Field(default=3.0, ge=2.0)
    prompt: str
    mode: str = "replace_audio_and_video"
    finding_id: str


class RegenResponse(BaseModel):
    finding_id: str
    options: list[RegenOption]


class TextToVideoRequest(BaseModel):
    prompt: str
    duration: float = Field(default=3.0, ge=2.0)
    finding_id: str


async def _call_ltx_retake(
    video_uri: str,
    prompt: str,
    start_time: float,
    duration: float,
    mode: str,
) -> bytes:
    """Call LTX retake API and return raw MP4 bytes."""
    url = "https://api.ltx.video/v1/retake"
    payload = {
        "video_uri": video_uri,
        "prompt": prompt,
        "start_time": start_time,
        "duration": duration,
        "mode": mode,
        "model": "ltx-2-3-pro",
    }
    headers = {
        "Authorization": f"Bearer {LTX_API_KEY}",
        "Content-Type": "application/json",
    }
    log.info(f"LTX retake request: prompt={prompt[:80]}..., start={start_time}, dur={duration}, mode={mode}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
    if resp.status_code != 200:
        log.error(f"LTX retake failed: status={resp.status_code}, body={resp.text[:300]}")
        raise HTTPException(status_code=502, detail=f"LTX API error: {resp.status_code}")
    log.info(f"LTX retake success: received {len(resp.content)} bytes")
    return resp.content


async def _call_ltx_text_to_video(prompt: str, duration: float) -> bytes:
    """Call LTX text-to-video API and return raw MP4 bytes."""
    url = "https://api.ltx.video/v1/text-to-video"
    payload = {
        "prompt": prompt,
        "duration": duration,
        "model": "ltx-2-3-pro",
    }
    headers = {
        "Authorization": f"Bearer {LTX_API_KEY}",
        "Content-Type": "application/json",
    }
    log.info(f"LTX text-to-video request: prompt={prompt[:80]}..., dur={duration}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
    if resp.status_code != 200:
        log.error(f"LTX text-to-video failed: status={resp.status_code}, body={resp.text[:300]}")
        raise HTTPException(status_code=502, detail=f"LTX API error: {resp.status_code}")
    log.info(f"LTX text-to-video success: received {len(resp.content)} bytes")
    return resp.content


def _upload_regen_clip(mp4_bytes: bytes, finding_id: str) -> str:
    """Upload regenerated MP4 to S3 and return a presigned URL."""
    filename = f"regen/{finding_id}_{uuid.uuid4().hex[:8]}.mp4"
    s3_uri = upload_to_s3(mp4_bytes, filename)
    if not s3_uri:
        raise HTTPException(status_code=500, detail="Failed to upload regen clip to S3")
    presigned = get_s3_presigned_url(s3_uri)
    if not presigned:
        raise HTTPException(status_code=500, detail="Failed to generate presigned URL for regen clip")
    log.info(f"Regen clip uploaded: s3_uri={s3_uri}")
    return presigned


@app.post("/api/regen", response_model=RegenResponse)
async def regen_clip(req: RegenRequest):
    """Generate replacement video clips using LTX-2.3."""
    if not LTX_API_KEY:
        log.error("LTX_API_KEY not set")
        raise HTTPException(status_code=503, detail="LTX_API_KEY not configured")
    if req.mode not in REGEN_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}. Must be one of {REGEN_MODES}")

    log.info(f"Regen request: finding={req.finding_id}, mode={req.mode}, start={req.start_time}, dur={req.duration}")

    # Convert S3 URI to presigned HTTPS URL for LTX
    video_url = req.video_uri
    if video_url.startswith("s3://"):
        log.info(f"Converting S3 URI to presigned URL: {video_url[:60]}")
        presigned = get_s3_presigned_url(video_url)
        if not presigned:
            log.error(f"Failed to generate presigned URL for regen: {video_url[:60]}")
            raise HTTPException(status_code=500, detail="Failed to generate presigned URL for source video")
        video_url = presigned
        log.info(f"Presigned URL generated: {video_url[:80]}...")

    options: list[RegenOption] = []

    # Option 1 — original prompt
    try:
        mp4_1 = await _call_ltx_retake(video_url, req.prompt, req.start_time, req.duration, req.mode)
        url_1 = _upload_regen_clip(mp4_1, req.finding_id)
        options.append(RegenOption(
            id=f"{req.finding_id}_opt1",
            video_url=url_1,
            prompt=req.prompt,
            duration=req.duration,
        ))
    except HTTPException:
        raise
    except Exception:
        log.exception("LTX retake option 1 failed")
        raise HTTPException(status_code=502, detail="LTX generation failed for option 1")

    # Option 2 — alternative angle
    try:
        alt_prompt = f"{req.prompt}, alternative angle"
        mp4_2 = await _call_ltx_retake(video_url, alt_prompt, req.start_time, req.duration, req.mode)
        url_2 = _upload_regen_clip(mp4_2, req.finding_id)
        options.append(RegenOption(
            id=f"{req.finding_id}_opt2",
            video_url=url_2,
            prompt=alt_prompt,
            duration=req.duration,
        ))
    except Exception:
        log.exception("LTX retake option 2 failed (non-fatal)")
        # Still return option 1 if option 2 fails

    log.info(f"Regen complete: finding={req.finding_id}, options={len(options)}")
    return RegenResponse(finding_id=req.finding_id, options=options)


@app.post("/api/regen/text-to-video", response_model=RegenResponse)
async def regen_text_to_video(req: TextToVideoRequest):
    """Generate video from text only using LTX-2.3."""
    if not LTX_API_KEY:
        log.error("LTX_API_KEY not set")
        raise HTTPException(status_code=503, detail="LTX_API_KEY not configured")

    log.info(f"Text-to-video request: finding={req.finding_id}, dur={req.duration}")

    options: list[RegenOption] = []

    # Option 1
    try:
        mp4_1 = await _call_ltx_text_to_video(req.prompt, req.duration)
        url_1 = _upload_regen_clip(mp4_1, req.finding_id)
        options.append(RegenOption(
            id=f"{req.finding_id}_opt1",
            video_url=url_1,
            prompt=req.prompt,
            duration=req.duration,
        ))
    except HTTPException:
        raise
    except Exception:
        log.exception("LTX text-to-video option 1 failed")
        raise HTTPException(status_code=502, detail="LTX text-to-video generation failed for option 1")

    # Option 2
    try:
        alt_prompt = f"{req.prompt}, alternative angle"
        mp4_2 = await _call_ltx_text_to_video(alt_prompt, req.duration)
        url_2 = _upload_regen_clip(mp4_2, req.finding_id)
        options.append(RegenOption(
            id=f"{req.finding_id}_opt2",
            video_url=url_2,
            prompt=alt_prompt,
            duration=req.duration,
        ))
    except Exception:
        log.exception("LTX text-to-video option 2 failed (non-fatal)")

    log.info(f"Text-to-video complete: finding={req.finding_id}, options={len(options)}")
    return RegenResponse(finding_id=req.finding_id, options=options)
