"""
Helper functions for parsing, scoring, and prompt building.
Extracted from the Streamlit app — all logic preserved exactly.
"""

import re
import logging
from datetime import datetime, date, timedelta

from config import RULESETS, JURISDICTIONS

_helpers_log = logging.getLogger("cleared.helpers")


# ── Internal helpers ──────────────────────────────────────────


def _normalize_severity(text: str) -> str:
    t = text.upper()
    if "CRITICAL" in t:
        return "CRITICAL"
    if "MAJOR" in t:
        return "MAJOR"
    return "MINOR"


def _estimate_confidence(severity: str, description: str = "") -> int:
    """Estimate confidence when not provided by the model.
    Conservative defaults — only boost when language is definitive.
    """
    base = {"CRITICAL": 72, "MAJOR": 62, "MINOR": 50}.get(severity, 55)
    desc_lower = (description or "").lower()
    # only boost for very definitive language
    if any(w in desc_lower for w in ["clearly", "confirmed", "detected", "identified"]):
        base = min(base + 10, 90)
    # penalize uncertain language
    if any(w in desc_lower for w in ["possible", "may", "might", "appears", "potential", "unclear", "ambiguous"]):
        base = max(base - 15, 30)
    # penalize "clearance needed" / "review" which are speculative
    if any(w in desc_lower for w in ["clearance needed", "review recommended", "needs review", "maybe"]):
        base = max(base - 10, 35)
    return base


# ── Public API ────────────────────────────────────────────────


def parse_findings(report: str) -> list[dict]:
    """Extract timestamped findings from a compliance report.
    Returns list of dicts: {text, timestamp, severity, confidence}

    Robust parser handles multiple output formats from Pegasus:
    - Timestamp: [HH:MM] ...
    - [HH:MM] ...
    - **[HH:MM]** ...
    - 1. [HH:MM] ...
    - - [HH:MM] ...
    - Any line containing [MM:SS] or [HH:MM:SS] timestamps
    """
    _helpers_log.info(f"Parsing findings from report ({len(report)} chars, {report.count(chr(10))} lines)")
    _helpers_log.info(f"Report preview: {report[:500]}")
    findings = []
    lines = report.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Pattern 1: Timestamp: [HH:MM] structured format
        if line.lower().startswith("timestamp:") and "[" in line:
            ts_match = re.search(r'\[[\d:]+(?:-[\d:]+)?\]', line)
            ts_str = ts_match.group(0) if ts_match else ""

            category = ""
            for back in range(i - 1, max(i - 5, -1), -1):
                prev = lines[back].strip()
                if prev and not prev.lower().startswith("timestamp"):
                    category = prev
                    break

            description = ""
            severity = ""
            confidence = 0
            for fwd in range(i + 1, min(i + 10, len(lines))):
                fwd_line = lines[fwd].strip()
                if fwd_line.lower().startswith("description:"):
                    description = fwd_line[len("description:"):].strip()
                elif fwd_line.lower().startswith("severity:"):
                    severity = fwd_line[len("severity:"):].strip()
                elif fwd_line.lower().startswith("confidence:"):
                    conf_match = re.search(r'(\d+)', fwd_line)
                    if conf_match:
                        confidence = min(int(conf_match.group(1)), 100)

            parts = [p for p in [ts_str, category, description, severity] if p]
            text = " — ".join(parts)
            if not confidence:
                confidence = _estimate_confidence(severity, description)
            findings.append({
                "text": text,
                "severity": _normalize_severity(severity or text),
                "confidence": confidence,
                "source": "compliance",
                "rule": category or "Content flag",
            })
            i += 1
            continue

        # Pattern 2: Line contains a timestamp [MM:SS] or [HH:MM:SS] anywhere
        # Strips leading bullets, numbers, asterisks, markdown bold
        ts_match = re.search(r'\[(\d{1,2}:\d{2}(?::\d{2})?(?:\s*-\s*\d{1,2}:\d{2}(?::\d{2})?)?)\]', line)
        if ts_match and len(line) > 8:
            # clean markdown formatting
            clean = re.sub(r'^\s*[-*\u2022]\s*', '', line)       # bullets
            clean = re.sub(r'^\s*\d+[\.\)]\s*', '', clean)  # numbered lists
            clean = re.sub(r'\*\*', '', clean)               # bold
            clean = clean.strip()

            sev = _normalize_severity(clean)
            conf_match = re.search(r'[Cc]onfidence[:\s]+(\d+)', clean)
            confidence = min(int(conf_match.group(1)), 100) if conf_match else _estimate_confidence(sev, clean)

            # extract rule/category from context
            rule = "Content flag"
            clean_lower = clean.lower()
            if any(w in clean_lower for w in ["music", "audio", "sound", "song"]):
                rule = "Audio content"
            elif any(w in clean_lower for w in ["logo", "brand", "trademark"]):
                rule = "Brand/trademark"
            elif any(w in clean_lower for w in ["talent", "face", "person", "actor"]):
                rule = "Talent clearance"
            elif any(w in clean_lower for w in ["alcohol", "drink", "beer", "wine"]):
                rule = "Substance portrayal"
            elif any(w in clean_lower for w in ["profan", "language", "speech", "slur"]):
                rule = "Language/speech"
            elif any(w in clean_lower for w in ["violen", "blood", "weapon", "gun"]):
                rule = "Violence"
            elif any(w in clean_lower for w in ["art", "painting", "sculpture", "design"]):
                rule = "Artwork clearance"

            findings.append({
                "text": clean,
                "severity": sev,
                "confidence": confidence,
                "source": "compliance",
                "rule": rule,
            })
            i += 1
            continue

        i += 1

    _helpers_log.info(f"Parsed {len(findings)} findings")
    return findings


def parse_rights_from_report(report: str) -> tuple[list[dict], list[dict]]:
    """Extract rights/clearance items from the compliance report.
    Returns TWO things:
    1. rights_entries — for the Rights Tracker (asset/type/expiry format)
    2. rights_findings — in the same finding dict format as parse_findings
    """
    rights_entries = []
    rights_findings = []
    in_rights_section = False
    lines = report.split("\n")
    today = date.today()

    for line in lines:
        stripped = line.strip()
        if "RIGHTS" in stripped.upper() and "CLEARANCE" in stripped.upper():
            in_rights_section = True
            continue
        if in_rights_section and stripped.startswith("SECTION"):
            break
        if in_rights_section and stripped.startswith("["):
            ts_match = re.search(r'\[[\d:]+(?:-[\d:]+)?\]', stripped)
            ts_str = ts_match.group(0) if ts_match else ""
            rest = re.sub(r'\[[\d:]+(?:-[\d:]+)?\]\s*', '', stripped)

            # determine type
            asset_type = "Other"
            rest_lower = rest.lower()
            if any(w in rest_lower for w in ["music", "track", "song", "audio", "jingle"]):
                asset_type = "Music license"
            elif any(w in rest_lower for w in ["logo", "brand", "trademark", "product"]):
                asset_type = "Brand license"
            elif any(w in rest_lower for w in ["talent", "face", "person", "actor", "performer"]):
                asset_type = "Talent release"
            elif any(w in rest_lower for w in ["artwork", "painting", "sculpture", "art"]):
                asset_type = "Artwork clearance"
            elif any(w in rest_lower for w in ["footage", "archive", "news", "clip"]):
                asset_type = "Archive footage"

            needs_clearance = "YES" in rest.upper() or "MAYBE" in rest.upper()
            severity = "MAJOR" if needs_clearance else "MINOR"

            # rights entry (for Rights Tracker)
            rights_entries.append({
                "asset": rest[:80],
                "type": asset_type,
                "expiry_date": (today + timedelta(days=30)).isoformat(),
                "notes": f"Auto-detected. {'Clearance needed.' if needs_clearance else 'Review recommended.'}",
                "added_at": datetime.now().isoformat(),
                "auto_detected": True,
            })

            # unified finding (same format as compliance findings)
            rights_findings.append({
                "text": f"{ts_str} {rest}".strip(),
                "severity": severity,
                "confidence": 75 if needs_clearance else 60,
                "source": "rights",
                "asset_type": asset_type,
                "rule": f"{asset_type} — {'clearance required' if needs_clearance else 'review recommended'}",
            })

    _helpers_log.info(f"Extracted {len(rights_entries)} rights entries, {len(rights_findings)} rights findings")
    return rights_entries, rights_findings


def severity_score(report: str) -> int:
    """Compute a weighted severity score from a report, capped at 100."""
    score = 0
    score += report.count("CRITICAL") * 10
    score += report.count("MAJOR") * 7
    score += report.count("MINOR") * 3
    return min(score, 100)


def parse_timestamp_seconds(finding) -> int:
    """Extract timestamp in seconds from a finding string or dict."""
    text = finding["text"] if isinstance(finding, dict) else finding
    try:
        match = re.search(r'\[(\d+):(\d+)', text)
        if match:
            return int(match.group(1)) * 60 + int(match.group(2))
    except Exception:
        _helpers_log.error(
            f"parse_timestamp_seconds: failed to parse timestamp from text={text[:80]!r}",
            exc_info=True,
        )
    return 0


def finding_text(finding) -> str:
    """Get display text from a finding (dict or string)."""
    if isinstance(finding, dict):
        return finding.get("text", str(finding))
    return finding


def finding_severity(finding) -> str:
    """Get severity from a finding (dict or string)."""
    if isinstance(finding, dict):
        return finding.get("severity", "MINOR")
    return _normalize_severity(finding)


def finding_confidence(finding) -> int:
    """Get confidence from a finding (dict or string)."""
    if isinstance(finding, dict):
        return finding.get("confidence", 70)
    return 70


def build_prompt(
    ruleset_name: str,
    custom_rules: str,
    platforms: list[str],
    jurisdictions: list[str],
    audio_flags: list[str],
    include_rights: bool = True,
) -> str:
    """Build the compliance analysis prompt for TwelveLabs Pegasus."""
    rules_list = list(RULESETS[ruleset_name]["rules"]) if ruleset_name != "Custom" else []
    if custom_rules:
        for r in custom_rules.split("\n"):
            if r.strip():
                rules_list.append(r.strip())

    rules_text = "\n".join(f"- {r}" for r in rules_list)
    platforms_text = ", ".join(platforms)

    jurisdiction_blocks = []
    for j in jurisdictions:
        if j != "None" and JURISDICTIONS.get(j):
            jurisdiction_blocks.append(f"{j}: {JURISDICTIONS[j]}")
    jurisdiction_text = "\n".join(jurisdiction_blocks) if jurisdiction_blocks else "No specific jurisdiction selected."

    audio_text = "\n".join(f"- {a}" for a in audio_flags) if audio_flags else "- General audio compliance check"

    rights_section = """
SECTION 3 - RIGHTS & CLEARANCES
Watch the ENTIRE video timeline carefully. For each of the following asset types, report the EXACT moment (MM:SS) when it FIRST becomes visible or audible. You must scrub through the full video — do not just report the opening frames.
- On-screen artworks, paintings, sculptures, installations
- Brand logos, trademarks, product packaging
- Identifiable talent (faces visible, recognizable)
- Background music, sound effects, jingles
- Architectural works, set designs
- News footage, archival material

TIMESTAMP RULES:
- The [MM:SS] MUST be the real video playback time where the asset first appears
- A 2-minute video will have assets appearing throughout — NOT all at [00:00]
- If an asset appears at 45 seconds in, write [00:45], not [00:00]
- If you cannot determine the exact timestamp, estimate based on the video position

Format: [MM:SS] asset type — description — Clearance needed: YES/MAYBE/NO
""" if include_rights else ""

    return f"""You are a senior compliance reviewer. You MUST ONLY flag violations that match the specific rules listed below. Do NOT invent, infer, or speculate about violations not covered by these rules. If you are not confident a violation exists, do NOT report it. Only report what you can directly observe in the video.

IMPORTANT CONSTRAINTS:
- Only flag items that clearly violate a rule listed below
- Confidence must reflect how certain you are: use 30-50 for uncertain, 50-70 for likely, 70-90 for clear, 90+ only for unambiguous
- If a category has no violations, write: NOT DETECTED
- Do NOT flag normal, compliant content
- Do NOT flag things that "could potentially" be an issue — only flag what IS an issue
- ALL timestamps MUST be the ACTUAL video playback time (MM:SS) where the item appears. Do NOT use sequential numbering like 00:00, 00:01, 00:02. Use real timecodes from the video timeline.

TARGET PLATFORMS: {platforms_text}

RULES TO CHECK ({ruleset_name}):
{rules_text}

AUDIO RULES TO CHECK:
{audio_text}

FORMAT — use this exact structure for every finding:

SECTION 1 - CONTENT FLAGS
For each violation of the rules above:
[MM:SS] Description of exactly what is visible/audible — Rule violated — Severity: CRITICAL/MAJOR/MINOR — Confidence: N

SECTION 2 - AUDIO FLAGS
For each audio violation:
[MM:SS] Description of audio content — Rule violated — Severity: CRITICAL/MAJOR/MINOR — Confidence: N

{rights_section}

SECTION 4 - PLATFORM SUITABILITY
For each platform in [{platforms_text}]:
[platform]: APPROVED / FLAGGED / REJECTED — reason [timestamps if relevant]

SECTION 5 - REGULATORY REVIEW
{jurisdiction_text}
For each jurisdiction: COMPLIANT / FLAG — specific rule — evidence

SECTION 6 - OVERALL
APPROVED FOR DISTRIBUTION / NEEDS REVIEW / REJECTED
Risk: CRITICAL / HIGH / MEDIUM / LOW
One paragraph summary for client."""
