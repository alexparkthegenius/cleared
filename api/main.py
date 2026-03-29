"""
FastAPI backend for the Cleared video compliance checking app.

Run with:
    uvicorn api.main:app --reload --port 8000
"""

import os
import re
import time
import uuid
import logging
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import httpx

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
    finding_summary,
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
    platforms_flagged: list[str] = []
    jurisdictions_flagged: list[str] = []
    summary: str = ""


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

    # Handle TwelveLabs pseudo-URI — download video and re-upload to S3
    analysis_s3_uri = req.s3_uri
    if req.s3_uri.startswith("twelvelabs://"):
        try:
            parts = req.s3_uri.replace("twelvelabs://", "").split("/")
            tl_index_id, tl_video_id = parts[0], parts[1]
            log.info(f"TwelveLabs source detected: index={tl_index_id}, video={tl_video_id}")
            # Fetch HLS/video URL from TwelveLabs
            import httpx as _httpx
            tl_resp = _httpx.get(
                f"https://api.twelvelabs.io/v1.3/indexes/{tl_index_id}/videos/{tl_video_id}",
                headers={"x-api-key": TWELVELABS_API_KEY},
                timeout=15.0,
            )
            tl_data = tl_resp.json()
            tl_video_url = tl_data.get("hls", {}).get("video_url")
            if not tl_video_url:
                raise ValueError("No video URL returned from TwelveLabs")
            log.info(f"TwelveLabs video URL: {tl_video_url[:80]}...")
            # Download video bytes
            dl_resp = _httpx.get(tl_video_url, timeout=120.0, follow_redirects=True)
            dl_resp.raise_for_status()
            video_bytes = dl_resp.content
            log.info(f"Downloaded TwelveLabs video: {len(video_bytes)} bytes")
            # Upload to S3
            s3_filename = f"twelvelabs_{tl_video_id}.mp4"
            analysis_s3_uri = upload_to_s3(video_bytes, s3_filename)
            log.info(f"Re-uploaded TwelveLabs video to S3: {analysis_s3_uri}")
        except Exception:
            log.exception("Failed to fetch/re-upload TwelveLabs video for Pegasus")
            raise HTTPException(status_code=500, detail="Failed to fetch video from TwelveLabs for analysis.")

    # ── Try TwelveLabs SDK direct analysis first (better timecodes) ──
    report_data = None
    analysis_method = "unknown"

    if TWELVELABS_API_KEY:
        try:
            import asyncio
            log.info("Attempting TwelveLabs direct analysis (better temporal accuracy)...")

            tl_auth_headers = {"x-api-key": TWELVELABS_API_KEY}
            tl_json_headers = {"x-api-key": TWELVELABS_API_KEY, "Content-Type": "application/json"}

            tl_video_id = None
            tl_index_id = None

            # If source is TwelveLabs, use the video ID directly
            if req.s3_uri.startswith("twelvelabs://"):
                parts = req.s3_uri.replace("twelvelabs://", "").split("/", 2)
                if len(parts) >= 2:
                    tl_index_id, tl_video_id = parts[0], parts[1]
                    log.info(f"Using existing TwelveLabs video: index={tl_index_id}, video={tl_video_id}")
                else:
                    log.error(f"Invalid twelvelabs:// URI format: {req.s3_uri}")
            else:
                # For S3 uploads: get presigned URL, find/create index, upload, wait
                presigned_url = get_s3_presigned_url(analysis_s3_uri)
                if not presigned_url:
                    log.warning("Could not generate presigned URL for TwelveLabs upload")
                else:
                    # Find existing index
                    async with httpx.AsyncClient(timeout=15.0) as tl_client:
                        idx_resp = await tl_client.get(
                            "https://api.twelvelabs.io/v1.3/indexes",
                            headers=tl_auth_headers,
                        )
                    indexes = idx_resp.json().get("data", [])
                    if indexes:
                        tl_index_id = indexes[0]["_id"]
                        log.info(f"Using existing TwelveLabs index: {tl_index_id}")
                    else:
                        # Create index
                        async with httpx.AsyncClient(timeout=15.0) as tl_client:
                            create_resp = await tl_client.post(
                                "https://api.twelvelabs.io/v1.3/indexes",
                                headers=tl_json_headers,
                                json={"index_name": "cleared-compliance",
                                      "models": [{"model_name": "marengo2.7", "options": ["visual", "audio"]}]},
                            )
                        if create_resp.status_code == 200 or create_resp.status_code == 201:
                            tl_index_id = create_resp.json().get("_id")
                            log.info(f"Created TwelveLabs index: {tl_index_id}")
                        else:
                            log.error(f"Failed to create TwelveLabs index: {create_resp.status_code} {create_resp.text[:200]}")

                    if tl_index_id:
                        # Upload video via URL
                        async with httpx.AsyncClient(timeout=30.0) as tl_client:
                            upload_resp = await tl_client.post(
                                "https://api.twelvelabs.io/v1.3/tasks",
                                headers=tl_json_headers,
                                json={"index_id": tl_index_id, "url": presigned_url},
                            )
                        if upload_resp.status_code not in (200, 201):
                            log.error(f"TwelveLabs upload failed: {upload_resp.status_code} {upload_resp.text[:200]}")
                        else:
                            task_data = upload_resp.json()
                            task_id = task_data.get("_id")
                            tl_video_id = task_data.get("video_id")
                            log.info(f"TwelveLabs upload task: {task_id}, video: {tl_video_id}")

                            # Wait for indexing (up to 120s)
                            if task_id:
                                for attempt in range(60):
                                    async with httpx.AsyncClient(timeout=10.0) as tl_client:
                                        status_resp = await tl_client.get(
                                            f"https://api.twelvelabs.io/v1.3/tasks/{task_id}",
                                            headers=tl_auth_headers,
                                        )
                                    status = status_resp.json().get("status")
                                    if status == "ready":
                                        log.info(f"TwelveLabs indexing complete (attempt {attempt+1})")
                                        break
                                    elif status == "failed":
                                        log.error(f"TwelveLabs indexing failed: {status_resp.json()}")
                                        tl_video_id = None
                                        break
                                    await asyncio.sleep(2)
                                else:
                                    log.error("TwelveLabs indexing timed out after 120s")
                                    tl_video_id = None

            # Run analysis via TwelveLabs
            if tl_video_id and tl_index_id:
                log.info(f"Running TwelveLabs analyze: index={tl_index_id}, video={tl_video_id}")
                async with httpx.AsyncClient(timeout=300.0) as tl_client:
                    analyze_resp = await tl_client.post(
                        "https://api.twelvelabs.io/v1.3/analyze",
                        headers=tl_json_headers,
                        json={
                            "video_id": tl_video_id,
                            "prompt": prompt,
                            "stream": False,
                        },
                    )
                if analyze_resp.status_code == 200:
                    tl_result = analyze_resp.json()
                    # Extract text from response — TwelveLabs returns {data: "text..."} or {text: "..."}
                    report_data = tl_result.get("data", "")
                    if not isinstance(report_data, str):
                        report_data = tl_result.get("text", "")
                    if not report_data:
                        # Try extracting from nested structure
                        report_data = json.dumps(tl_result, indent=2) if tl_result else ""
                        log.warning(f"TwelveLabs response had unexpected structure, serialized: {report_data[:200]}")
                    analysis_method = "twelvelabs-direct"
                    log.info(f"TwelveLabs direct analysis success: {len(report_data)} chars")
                else:
                    log.warning(f"TwelveLabs analyze failed ({analyze_resp.status_code}): {analyze_resp.text[:300]}")
            else:
                log.info("TwelveLabs video not available, will fall back to Bedrock")
        except Exception:
            log.exception("TwelveLabs direct analysis failed, falling back to Bedrock")

    # ── Fall back to Bedrock Pegasus if TwelveLabs didn't work ──
    if not report_data:
        try:
            log.info(f"Invoking Bedrock Pegasus: s3_uri={analysis_s3_uri[:60]}...")
            report_data = run_pegasus_analysis(
                video_s3_uri=analysis_s3_uri,
                prompt=prompt,
            )
            analysis_method = "bedrock-pegasus"
        except Exception:
            elapsed = round(time.time() - t0, 1)
            log.exception(f"Pegasus invocation failed after {elapsed}s: s3_uri={req.s3_uri[:60]}")
            raise HTTPException(
                status_code=500,
                detail="Analysis failed via both TwelveLabs and Bedrock. Check credentials.",
            )

    if not report_data:
        elapsed = round(time.time() - t0, 1)
        log.error(f"All analysis methods returned empty after {elapsed}s")
        raise HTTPException(
            status_code=500,
            detail="Analysis returned no results from any provider.",
        )

    elapsed = round(time.time() - t0, 1)
    log.info(f"Analysis complete ({analysis_method}): {elapsed}s, response_length={len(report_data)} chars")
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

    # ── Deduplicate findings ────────────────────────────────────
    # Platform findings look like "YouTube: FLAGGED — tobacco use [00:49]"
    # Jurisdiction findings look like "OFCOM: FLAG — tobacco use [00:49]"
    # We merge these into the parent content finding as tags.
    try:
        _PLATFORM_NAMES = {p for p in PLATFORMS if p != "Custom"}
        _JURISDICTION_NAMES = {j for j in JURISDICTIONS if j != "None"}
        # Also match short jurisdiction prefixes (e.g. "OFCOM", "FCC", "GDPR")
        _JURISDICTION_SHORTS = {j.split(" (")[0] for j in _JURISDICTION_NAMES if " (" in j}

        _PLATFORM_RE = re.compile(
            r'^(' + '|'.join(re.escape(p) for p in sorted(_PLATFORM_NAMES, key=len, reverse=True)) + r')\s*:\s*(FLAGGED|APPROVED|REJECTED)',
            re.IGNORECASE,
        )
        _JURISDICTION_RE = re.compile(
            r'^(' + '|'.join(re.escape(j) for j in sorted(_JURISDICTION_NAMES | _JURISDICTION_SHORTS, key=len, reverse=True)) + r')\s*:\s*(FLAG|COMPLIANT)',
            re.IGNORECASE,
        )

        content_findings = []
        platform_findings = []
        jurisdiction_findings = []

        for f in all_findings:
            txt = f.get("text", "")
            if _PLATFORM_RE.match(txt):
                platform_findings.append(f)
            elif _JURISDICTION_RE.match(txt):
                jurisdiction_findings.append(f)
            else:
                content_findings.append(f)

        # For each platform/jurisdiction finding, try to attach it to a content finding
        # by matching timestamp or shared violation keywords
        for cf in content_findings:
            cf.setdefault("_platforms_flagged", [])
            cf.setdefault("_jurisdictions_flagged", [])
            cf_ts = parse_timestamp_seconds(cf)
            cf_text_lower = cf.get("text", "").lower()

            for pf in platform_findings:
                pf_ts = parse_timestamp_seconds(pf)
                pf_text = pf.get("text", "")
                m = _PLATFORM_RE.match(pf_text)
                if not m:
                    continue
                platform_name = m.group(1)
                status = m.group(2).upper()
                # Match by timestamp or by shared keywords
                remainder = pf_text[m.end():].lower()
                keywords_overlap = any(
                    w in cf_text_lower
                    for w in remainder.split()
                    if len(w) > 3 and w not in ("the", "and", "for", "with", "from", "that", "this")
                )
                if (cf_ts > 0 and pf_ts > 0 and abs(cf_ts - pf_ts) <= 5) or keywords_overlap:
                    label = f"{platform_name}: {status}"
                    if label not in cf["_platforms_flagged"]:
                        cf["_platforms_flagged"].append(label)

            for jf in jurisdiction_findings:
                jf_ts = parse_timestamp_seconds(jf)
                jf_text = jf.get("text", "")
                m = _JURISDICTION_RE.match(jf_text)
                if not m:
                    continue
                jurisdiction_name = m.group(1)
                status = m.group(2).upper()
                # Try to find full name
                full_name = jurisdiction_name
                for jn in _JURISDICTION_NAMES:
                    if jn.startswith(jurisdiction_name):
                        full_name = jn
                        break
                remainder = jf_text[m.end():].lower()
                keywords_overlap = any(
                    w in cf_text_lower
                    for w in remainder.split()
                    if len(w) > 3 and w not in ("the", "and", "for", "with", "from", "that", "this")
                )
                if (cf_ts > 0 and jf_ts > 0 and abs(cf_ts - jf_ts) <= 5) or keywords_overlap:
                    label = f"{full_name}: {status}"
                    if label not in cf["_jurisdictions_flagged"]:
                        cf["_jurisdictions_flagged"].append(label)

        # If any platform/jurisdiction findings couldn't be matched, keep them as standalone
        matched_platforms = set()
        matched_jurisdictions = set()
        for cf in content_findings:
            for lbl in cf.get("_platforms_flagged", []):
                matched_platforms.add(lbl)
            for lbl in cf.get("_jurisdictions_flagged", []):
                matched_jurisdictions.add(lbl)

        # Unmatched platform/jurisdiction findings become standalone content findings
        for pf in platform_findings:
            m = _PLATFORM_RE.match(pf.get("text", ""))
            if m:
                label = f"{m.group(1)}: {m.group(2).upper()}"
                if label not in matched_platforms:
                    content_findings.append(pf)

        for jf in jurisdiction_findings:
            m = _JURISDICTION_RE.match(jf.get("text", ""))
            if m:
                full_name = m.group(1)
                for jn in _JURISDICTION_NAMES:
                    if jn.startswith(full_name):
                        full_name = jn
                        break
                label = f"{full_name}: {m.group(2).upper()}"
                if label not in matched_jurisdictions:
                    content_findings.append(jf)

        all_findings = content_findings
        log.info(f"Deduplication: {len(compliance_findings) + len(rights_findings)} -> {len(all_findings)} findings "
                 f"({len(platform_findings)} platform, {len(jurisdiction_findings)} jurisdiction merged)")
    except Exception:
        log.exception("Finding deduplication failed, using raw findings")

    # ── Timestamp note: TwelveLabs direct has better timecodes than Bedrock ──
    if analysis_method == "bedrock-pegasus":
        rights_with_ts = [f for f in all_findings if f.get("source") == "rights"]
        rights_timestamps = [parse_timestamp_seconds(f) for f in rights_with_ts]
        rights_zero_count = sum(1 for t in rights_timestamps if t <= 1)
        if len(rights_with_ts) > 1 and rights_zero_count >= len(rights_with_ts) * 0.5:
            log.warning(f"Bedrock rights timestamps clustered at 0 ({rights_zero_count}/{len(rights_with_ts)}). "
                       "TwelveLabs direct was used as primary — this is a fallback path.")

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
                platforms_flagged=f.get("_platforms_flagged", []),
                jurisdictions_flagged=f.get("_jurisdictions_flagged", []),
                summary=finding_summary(f),
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
# TwelveLabs Index / Video Picker
# ══════════════════════════════════════════════════════════════


@app.get("/api/twelvelabs/indexes")
async def list_twelvelabs_indexes():
    """List all TwelveLabs indexes."""
    if not TWELVELABS_API_KEY:
        log.error("TWELVELABS_API_KEY not set")
        raise HTTPException(status_code=503, detail="TWELVELABS_API_KEY not configured")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.twelvelabs.io/v1.3/indexes",
                headers={"x-api-key": TWELVELABS_API_KEY},
            )
        if resp.status_code != 200:
            log.error(f"TwelveLabs indexes error: {resp.status_code} {resp.text[:300]}")
            raise HTTPException(status_code=502, detail=f"TwelveLabs API error ({resp.status_code})")
        data = resp.json().get("data", [])
        log.info(f"TwelveLabs indexes: {len(data)} found")
        return [
            {"id": idx["_id"], "name": idx.get("index_name", idx["_id"]), "video_count": idx.get("video_count", 0)}
            for idx in data
        ]
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to fetch TwelveLabs indexes")
        raise HTTPException(status_code=500, detail="Failed to fetch TwelveLabs indexes")


@app.get("/api/twelvelabs/indexes/{index_id}/videos")
async def list_twelvelabs_videos(index_id: str):
    """List videos in a TwelveLabs index."""
    if not TWELVELABS_API_KEY:
        raise HTTPException(status_code=503, detail="TWELVELABS_API_KEY not configured")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"https://api.twelvelabs.io/v1.3/indexes/{index_id}/videos",
                headers={"x-api-key": TWELVELABS_API_KEY},
            )
        if resp.status_code != 200:
            log.error(f"TwelveLabs videos error: {resp.status_code} {resp.text[:300]}")
            raise HTTPException(status_code=502, detail=f"TwelveLabs API error ({resp.status_code})")
        data = resp.json().get("data", [])
        log.info(f"TwelveLabs videos for index {index_id}: {len(data)} found")
        return [
            {
                "id": v["_id"],
                "name": v.get("metadata", {}).get("filename", v.get("system_metadata", {}).get("filename", v["_id"])),
                "duration": v.get("metadata", {}).get("duration", v.get("system_metadata", {}).get("duration", 0)),
                "thumbnail_url": v.get("hls", {}).get("thumbnail_urls", [None])[0] if v.get("hls") else None,
                "hls_url": v.get("hls", {}).get("video_url"),
            }
            for v in data
        ]
    except HTTPException:
        raise
    except Exception:
        log.exception(f"Failed to fetch TwelveLabs videos for index {index_id}")
        raise HTTPException(status_code=500, detail="Failed to fetch TwelveLabs videos")


@app.get("/api/twelvelabs/videos/{index_id}/{video_id}/url")
async def get_twelvelabs_video_url(index_id: str, video_id: str):
    """Get playback URL for a specific TwelveLabs video."""
    if not TWELVELABS_API_KEY:
        raise HTTPException(status_code=503, detail="TWELVELABS_API_KEY not configured")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"https://api.twelvelabs.io/v1.3/indexes/{index_id}/videos/{video_id}",
                headers={"x-api-key": TWELVELABS_API_KEY},
            )
        if resp.status_code != 200:
            log.error(f"TwelveLabs video URL error: {resp.status_code} {resp.text[:300]}")
            raise HTTPException(status_code=502, detail=f"TwelveLabs API error ({resp.status_code})")
        data = resp.json()
        hls = data.get("hls", {})
        log.info(f"TwelveLabs video URL fetched: index={index_id}, video={video_id}")
        return {
            "hls_url": hls.get("video_url"),
            "thumbnail_url": (hls.get("thumbnail_urls", [None]) or [None])[0],
        }
    except HTTPException:
        raise
    except Exception:
        log.exception(f"Failed to fetch TwelveLabs video URL: {index_id}/{video_id}")
        raise HTTPException(status_code=500, detail="Failed to fetch TwelveLabs video URL")


# ══════════════════════════════════════════════════════════════
# LTX Video Regeneration
# ══════════════════════════════════════════════════════════════

LTX_API_KEY = os.environ.get("LTX_API_KEY", "")
TWELVELABS_API_KEY = os.environ.get("TWELVELABS_API_KEY", "")

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
        error_body = resp.text[:500]
        log.error(f"LTX retake failed: status={resp.status_code}, body={error_body}")
        raise HTTPException(status_code=502, detail=f"LTX retake error ({resp.status_code}): {error_body}")
    content_type = resp.headers.get("content-type", "")
    log.info(f"LTX retake success: {len(resp.content)} bytes, content-type={content_type}")
    return resp.content


async def _call_ltx_text_to_video(prompt: str, duration: float) -> bytes:
    """Call LTX text-to-video API and return raw MP4 bytes."""
    url = "https://api.ltx.video/v1/text-to-video"
    payload = {
        "prompt": prompt,
        "duration": duration,
        "model": "ltx-2-3-pro",
        "resolution": "1920x1080",
    }
    headers = {
        "Authorization": f"Bearer {LTX_API_KEY}",
        "Content-Type": "application/json",
    }
    log.info(f"LTX text-to-video request: prompt={prompt[:80]}..., dur={duration}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
    if resp.status_code != 200:
        error_body = resp.text[:500]
        log.error(f"LTX text-to-video failed: status={resp.status_code}, body={error_body}")
        raise HTTPException(status_code=502, detail=f"LTX t2v error ({resp.status_code}): {error_body}")
    content_type = resp.headers.get("content-type", "")
    log.info(f"LTX text-to-video success: {len(resp.content)} bytes, content-type={content_type}")
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

    # Clamp duration to LTX max (20 seconds)
    gen_duration = min(req.duration, 8.0)  # Keep short for fast generation
    if gen_duration < 2.0:
        gen_duration = 3.0

    # Build a descriptive replacement prompt
    replacement_prompt = (
        f"Generate a clean replacement clip: {req.prompt}. "
        f"Professional broadcast quality, natural lighting, smooth camera movement. "
        f"No violations, brand-safe content."
    )

    options: list[RegenOption] = []

    # Use text-to-video (no input video limit) — generates from prompt alone
    # This avoids the LTX retake frame count / duration limit
    log.info(f"Using text-to-video for regen (avoids retake frame limit): dur={gen_duration}")

    # Option 1 — original prompt
    try:
        mp4_1 = await _call_ltx_text_to_video(replacement_prompt, gen_duration)
        url_1 = _upload_regen_clip(mp4_1, req.finding_id)
        options.append(RegenOption(
            id=f"{req.finding_id}_opt1",
            video_url=url_1,
            prompt=replacement_prompt,
            duration=gen_duration,
        ))
    except HTTPException:
        raise
    except Exception:
        log.exception("LTX text-to-video option 1 failed")
        raise HTTPException(status_code=502, detail="LTX generation failed for option 1")

    # Option 2 — alternative angle
    try:
        alt_prompt = f"{replacement_prompt} Alternative camera angle, wide establishing shot."
        mp4_2 = await _call_ltx_text_to_video(alt_prompt, gen_duration)
        url_2 = _upload_regen_clip(mp4_2, req.finding_id)
        options.append(RegenOption(
            id=f"{req.finding_id}_opt2",
            video_url=url_2,
            prompt=alt_prompt,
            duration=gen_duration,
        ))
    except Exception:
        log.exception("LTX text-to-video option 2 failed (non-fatal)")
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
