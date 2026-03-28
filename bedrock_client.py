"""Bedrock wrapper for TwelveLabs Pegasus and Marengo model inference."""

import os
import json
import base64
import logging
import requests

log = logging.getLogger("cleared.bedrock")

# Bedrock model IDs
PEGASUS_MODEL_ID = "us.twelvelabs.pegasus-1-2-v1:0"
MARENGO_MODEL_ID = "us.twelvelabs.marengo-embed-2-7-v1:0"

_bedrock_client = None


def init_bedrock():
    """Initialize boto3 Bedrock runtime client. Returns None if AWS creds not configured."""
    global _bedrock_client
    if _bedrock_client:
        return _bedrock_client

    aws_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    aws_region = os.environ.get("AWS_DEFAULT_REGION", "us-west-2")

    if not aws_key or not aws_secret:
        log.warning("AWS credentials not set — Bedrock calls will fall back to TwelveLabs SDK")
        return None

    try:
        import boto3
        _bedrock_client = boto3.client(
            service_name="bedrock-runtime",
            region_name=aws_region,
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
        )
        log.info(f"Bedrock client initialized (region={aws_region})")
        return _bedrock_client
    except Exception as e:
        log.error(f"Failed to initialize Bedrock client: {e}")
        return None


def _download_video_bytes(video_url, max_mb=100):
    """Download video from URL and return bytes. Handles HLS by fetching the master URL."""
    try:
        # For HLS streams, we need the actual video segments — try direct download first
        if ".m3u8" in video_url:
            log.info("HLS URL detected — attempting direct segment download")
            # Get the manifest
            resp = requests.get(video_url, timeout=30)
            if resp.status_code != 200:
                log.error(f"Failed to fetch HLS manifest: {resp.status_code}")
                return None
            # Find the highest quality stream URL
            lines = resp.text.strip().split("\n")
            segment_urls = [l for l in lines if l.startswith("http") or l.endswith(".ts") or l.endswith(".mp4")]
            if not segment_urls:
                # Try to find a rendition URL
                for line in lines:
                    if line.strip() and not line.startswith("#"):
                        if line.startswith("http"):
                            segment_urls.append(line.strip())
                        else:
                            # relative URL
                            base = video_url.rsplit("/", 1)[0]
                            segment_urls.append(f"{base}/{line.strip()}")

            if not segment_urls:
                log.warning("Could not extract video segments from HLS manifest")
                return None

            # Download and concatenate segments
            video_bytes = b""
            for seg_url in segment_urls:
                seg_resp = requests.get(seg_url, timeout=60)
                if seg_resp.status_code == 200:
                    video_bytes += seg_resp.content
                if len(video_bytes) > max_mb * 1024 * 1024:
                    log.warning(f"Video exceeds {max_mb}MB limit, truncating")
                    break

            if video_bytes:
                log.info(f"Downloaded {len(video_bytes)} bytes from HLS stream")
                return video_bytes
            return None
        else:
            # Direct video URL
            resp = requests.get(video_url, timeout=120, stream=True)
            if resp.status_code != 200:
                log.error(f"Failed to download video: {resp.status_code}")
                return None
            video_bytes = resp.content
            log.info(f"Downloaded {len(video_bytes)} bytes from direct URL")
            return video_bytes
    except Exception as e:
        log.error(f"Video download failed: {e}")
        return None


def analyze_video_pegasus(video_url, prompt):
    """Run Pegasus analysis on a video via Bedrock.

    Args:
        video_url: HLS or direct URL to the video
        prompt: The compliance analysis prompt

    Returns:
        Report text string, or None if Bedrock is unavailable/fails
    """
    bedrock = init_bedrock()
    if not bedrock:
        return None

    try:
        log.info(f"Pegasus via Bedrock: downloading video from {video_url[:60]}...")
        video_bytes = _download_video_bytes(video_url)
        if not video_bytes:
            log.error("Could not download video for Bedrock analysis")
            return None

        video_b64 = base64.b64encode(video_bytes).decode("utf-8")
        log.info(f"Video encoded: {len(video_b64)} chars base64 ({len(video_bytes)} bytes raw)")

        request_body = {
            "prompt": prompt,
            "video": {
                "mediaSource": {
                    "base64String": video_b64
                }
            }
        }

        log.info(f"Invoking Bedrock Pegasus ({PEGASUS_MODEL_ID})...")
        response = bedrock.invoke_model(
            modelId=PEGASUS_MODEL_ID,
            body=json.dumps(request_body),
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read())
        log.info(f"Bedrock Pegasus response received: {len(str(response_body))} chars")

        # Extract text from response — format may vary
        if isinstance(response_body, dict):
            # Try common response fields
            for key in ["text", "output", "completion", "content", "result"]:
                if key in response_body:
                    result = response_body[key]
                    if isinstance(result, str):
                        return result
                    if isinstance(result, list) and result:
                        return str(result[0].get("text", result[0])) if isinstance(result[0], dict) else str(result[0])
            # If none of those keys, return the whole thing as string
            return json.dumps(response_body, indent=2)
        return str(response_body)

    except Exception as e:
        log.error(f"Bedrock Pegasus analysis failed: {e}")
        return None


def is_bedrock_available():
    """Check if Bedrock credentials are configured."""
    return bool(os.environ.get("AWS_ACCESS_KEY_ID")) and bool(os.environ.get("AWS_SECRET_ACCESS_KEY"))
