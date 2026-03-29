"""
Bedrock wrapper for TwelveLabs Pegasus (analysis) and Marengo (search/retrieval).
All model inference goes through this module. No TwelveLabs SDK for model calls.
Video input is S3 URI or local file path.

Extracted from the Streamlit app — all logic preserved exactly.
"""

import os
import json
import base64
import logging

_bedrock_log = logging.getLogger("cleared.bedrock")

# Bedrock model IDs
PEGASUS_MODEL_ID = "us.twelvelabs.pegasus-1-2-v1:0"
MARENGO_MODEL_ID = "us.twelvelabs.marengo-embed-2-7-v1:0"

_bedrock_client = None
_s3_client = None

S3_BUCKET = os.environ.get("CLEARED_S3_BUCKET", "cleared-compliance-videos")
S3_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-west-2")


def _get_bedrock():
    """Lazy-init Bedrock runtime client."""
    global _bedrock_client
    if _bedrock_client:
        return _bedrock_client
    try:
        import boto3
        _bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=S3_REGION,
        )
        _bedrock_log.info(f"Bedrock client initialized (region={S3_REGION})")
        return _bedrock_client
    except Exception:
        _bedrock_log.exception(f"Bedrock init failed (region={S3_REGION})")
        return None


def _get_s3():
    """Lazy-init S3 client."""
    global _s3_client
    if _s3_client:
        return _s3_client
    try:
        import boto3
        _s3_client = boto3.client("s3", region_name=S3_REGION)
        _bedrock_log.info("S3 client initialized")
        return _s3_client
    except Exception:
        _bedrock_log.exception(f"S3 client init failed (region={S3_REGION})")
        return None


def is_bedrock_available() -> bool:
    """Check if AWS credentials are configured."""
    return bool(os.environ.get("AWS_ACCESS_KEY_ID")) and bool(os.environ.get("AWS_SECRET_ACCESS_KEY"))


def upload_to_s3(file_bytes: bytes, filename: str) -> str | None:
    """Upload video bytes to S3. Returns s3:// URI."""
    s3 = _get_s3()
    if not s3:
        _bedrock_log.error("S3 client not available")
        return None
    try:
        key = f"uploads/{filename}"
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=file_bytes)
        uri = f"s3://{S3_BUCKET}/{key}"
        _bedrock_log.info(f"Uploaded to S3: {uri}")
        return uri
    except Exception:
        _bedrock_log.exception(f"S3 upload failed for filename={filename}, bucket={S3_BUCKET}")
        return None


def get_s3_presigned_url(s3_uri: str, expires_in: int = 3600) -> str | None:
    """Generate a presigned URL for video playback from S3 URI."""
    s3 = _get_s3()
    if not s3:
        _bedrock_log.error("get_s3_presigned_url: S3 client not available")
        return None
    if not s3_uri:
        _bedrock_log.error("get_s3_presigned_url: no s3_uri provided")
        return None
    try:
        # parse s3://bucket/key
        parts = s3_uri.replace("s3://", "").split("/", 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ""
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        _bedrock_log.info(f"Presigned URL generated for {s3_uri[:50]}...")
        return url
    except Exception:
        _bedrock_log.exception(f"Presigned URL generation failed for s3_uri={s3_uri}")
        return None


def _extract_text(response_body):
    """Extract text content from a Bedrock model response.
    Pegasus returns: {"message": "...", "finishReason": "stop"}
    """
    if isinstance(response_body, str):
        return response_body
    if isinstance(response_body, dict):
        # Pegasus format: "message" key
        for key in ["message", "text", "output", "completion", "content", "result"]:
            if key in response_body:
                val = response_body[key]
                if isinstance(val, str):
                    return val
                if isinstance(val, list) and val:
                    if isinstance(val[0], dict):
                        return val[0].get("text", json.dumps(val[0]))
                    return str(val[0])
        _bedrock_log.warning(f"_extract_text: no known text key in response, keys={list(response_body.keys())}")
        return json.dumps(response_body, indent=2)
    return str(response_body)


# ── PEGASUS: Video Analysis ──────────────────────────────────


def run_pegasus_analysis(
    video_s3_uri: str | None = None,
    video_bytes: bytes | None = None,
    prompt: str = "",
) -> str | None:
    """Run Pegasus analysis via Bedrock.

    Accepts either:
    - video_s3_uri: s3://bucket/key reference
    - video_bytes: raw bytes (will be base64 encoded)

    Returns: report text string, or None on failure.
    """
    bedrock = _get_bedrock()
    if not bedrock:
        _bedrock_log.error("run_pegasus_analysis: Bedrock client not available, cannot run analysis")
        return None

    try:
        # build mediaSource — top-level, not nested under "video"
        if video_s3_uri:
            s3_location = {"uri": video_s3_uri}
            account_id = os.environ.get("AWS_ACCOUNT_ID", "")
            if account_id:
                s3_location["bucketOwner"] = account_id
            else:
                _bedrock_log.warning("AWS_ACCOUNT_ID not set — omitting bucketOwner from Pegasus request")
            media_source = {"s3Location": s3_location}
            _bedrock_log.info(f"Pegasus input: S3 URI {video_s3_uri[:60]}")
        elif video_bytes:
            video_b64 = base64.b64encode(video_bytes).decode("utf-8")
            media_source = {"base64String": video_b64}
            _bedrock_log.info(f"Pegasus input: base64 ({len(video_bytes)} bytes)")
        else:
            _bedrock_log.error("No video input provided")
            return None

        request_body = {
            "inputPrompt": prompt,
            "mediaSource": media_source,
            "temperature": 0,
        }

        _bedrock_log.info(f"Invoking Bedrock Pegasus ({PEGASUS_MODEL_ID})...")
        response = bedrock.invoke_model(
            modelId=PEGASUS_MODEL_ID,
            body=json.dumps(request_body),
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read())
        _bedrock_log.info(f"Pegasus response: {len(str(response_body))} chars")

        # extract text from response
        return _extract_text(response_body)

    except Exception:
        _bedrock_log.exception(
            f"Pegasus analysis failed (model={PEGASUS_MODEL_ID}, "
            f"s3_uri={video_s3_uri}, has_bytes={video_bytes is not None})"
        )
        return None


# ── MARENGO: Semantic Search / Retrieval ─────────────────────


def search_with_marengo(
    video_s3_uri: str | None = None,
    video_bytes: bytes | None = None,
    query: str = "",
    embedding_options: list[str] | None = None,
) -> dict | None:
    """Run Marengo semantic search/embedding via Bedrock.

    Use for:
    - Finding specific scenes/moments in video
    - Semantic retrieval of relevant segments
    - Video similarity/classification

    Returns: embedding results or search matches, or None on failure.
    """
    bedrock = _get_bedrock()
    if not bedrock:
        _bedrock_log.error("search_with_marengo: Bedrock client not available")
        return None

    try:
        if embedding_options is None:
            embedding_options = ["visual-text", "audio"]

        if video_s3_uri:
            s3_loc = {"uri": video_s3_uri}
            acct = os.environ.get("AWS_ACCOUNT_ID", "")
            if acct:
                s3_loc["bucketOwner"] = acct
            video_input = {"s3Location": s3_loc}
            input_type = "video"
        elif video_bytes:
            video_b64 = base64.b64encode(video_bytes).decode("utf-8")
            video_input = {"base64String": video_b64}
            input_type = "video"
        elif query:
            # text-only query for text embeddings
            input_type = "text"
            video_input = None
        else:
            _bedrock_log.error("No input provided for Marengo")
            return None

        if input_type == "text":
            request_body = {
                "inputType": "text",
                "text": query,
                "embeddingOption": embedding_options,
            }
        else:
            request_body = {
                "inputType": "video",
                "mediaSource": video_input,
                "embeddingOption": embedding_options,
            }

        _bedrock_log.info(f"Invoking Bedrock Marengo ({MARENGO_MODEL_ID}), type={input_type}...")
        response = bedrock.invoke_model(
            modelId=MARENGO_MODEL_ID,
            body=json.dumps(request_body),
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read())
        _bedrock_log.info(f"Marengo response: {len(str(response_body))} chars")
        return response_body

    except Exception:
        _bedrock_log.exception(
            f"Marengo search failed (model={MARENGO_MODEL_ID}, "
            f"s3_uri={video_s3_uri}, has_bytes={video_bytes is not None}, "
            f"query_len={len(query) if query else 0})"
        )
        return None
