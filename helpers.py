"""Helper functions for parsing, scoring, logging, and metrics."""

import re
import json
import logging
from datetime import datetime, date, timedelta

log = logging.getLogger("cleared.helpers")


def parse_findings(report):
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
    log.info(f"Parsing findings from report ({len(report)} chars, {report.count(chr(10))} lines)")
    log.info(f"Report preview: {report[:500]}")
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
            clean = re.sub(r'^\s*[-*•]\s*', '', line)       # bullets
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

    log.info(f"Parsed {len(findings)} findings")
    return findings


def _normalize_severity(text):
    t = text.upper()
    if "CRITICAL" in t:
        return "CRITICAL"
    if "MAJOR" in t:
        return "MAJOR"
    return "MINOR"


def _estimate_confidence(severity, description=""):
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


def parse_rights_from_report(report):
    """Extract rights/clearance items from the compliance report.
    Returns TWO things:
    1. rights_entries — for the Rights Tracker tab (asset/type/expiry format)
    2. rights_findings — in the same finding dict format as parse_findings (text/severity/confidence/source)
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

            # rights entry (for Rights Tracker tab)
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

    log.info(f"Extracted {len(rights_entries)} rights entries, {len(rights_findings)} rights findings")
    return rights_entries, rights_findings


def severity_score(report):
    """Compute a weighted severity score from a report, capped at 100."""
    score = 0
    score += report.count("CRITICAL") * 10
    score += report.count("MAJOR") * 7
    score += report.count("MINOR") * 3
    return min(score, 100)


def parse_timestamp_seconds(finding):
    """Extract timestamp in seconds from a finding string or dict."""
    text = finding["text"] if isinstance(finding, dict) else finding
    try:
        match = re.search(r'\[(\d+):(\d+)', text)
        if match:
            return int(match.group(1)) * 60 + int(match.group(2))
    except Exception:
        log.error(f"parse_timestamp_seconds: failed to parse timestamp from text={text[:80]!r}", exc_info=True)
    return 0


def finding_text(finding):
    """Get display text from a finding (dict or string)."""
    if isinstance(finding, dict):
        return finding.get("text", str(finding))
    return finding


def finding_severity(finding):
    """Get severity from a finding (dict or string)."""
    if isinstance(finding, dict):
        return finding.get("severity", "MINOR")
    return _normalize_severity(finding)


def finding_confidence(finding):
    """Get confidence from a finding (dict or string)."""
    if isinstance(finding, dict):
        return finding.get("confidence", 70)
    return 70


def log_feedback(finding, decision, video_id, ruleset, platforms, jurisdictions):
    """Append a reviewer decision to the feedback log."""
    f_text = finding_text(finding)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "video_id": video_id,
        "finding": f_text,
        "decision": decision,
        "ruleset": ruleset,
        "platforms": platforms,
        "jurisdictions": jurisdictions,
    }
    log.info(f"Feedback logged: {decision} — {f_text[:60]}")
    try:
        with open("feedback_log.json", "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        log.exception(f"log_feedback: failed to write feedback entry for video_id={video_id}, decision={decision}")


def load_feedback_log():
    try:
        with open("feedback_log.json", "r") as f:
            entries = []
            for line_num, l in enumerate(f.readlines(), 1):
                try:
                    entries.append(json.loads(l))
                except json.JSONDecodeError:
                    log.warning(f"load_feedback_log: skipping malformed JSON at line {line_num}: {l[:80]!r}")
                    continue
            return entries
    except FileNotFoundError:
        return []
    except Exception:
        log.exception("load_feedback_log: unexpected error reading feedback_log.json")
        return []


def load_rights_log():
    try:
        with open("rights_log.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except Exception:
        log.exception("load_rights_log: failed to parse rights_log.json")
        return []


def save_rights_log(entries):
    with open("rights_log.json", "w") as f:
        json.dump(entries, f, indent=2, default=str)


def get_expiring_rights(entries, days_ahead=30):
    today = date.today()
    expiring = []
    for e in entries:
        try:
            exp = date.fromisoformat(e["expiry_date"])
            delta = (exp - today).days
            if delta <= days_ahead:
                e["days_remaining"] = delta
                expiring.append(e)
        except Exception:
            log.warning(f"get_expiring_rights: failed to parse expiry_date for asset={e.get('asset', 'unknown')!r}, "
                        f"expiry_date={e.get('expiry_date')!r}", exc_info=True)
    return expiring


def load_ground_truth():
    try:
        with open("ground_truth.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception:
        log.exception("load_ground_truth: failed to parse ground_truth.json")
        return {}


def save_ground_truth(data):
    with open("ground_truth.json", "w") as f:
        json.dump(data, f, indent=2)


def compute_metrics(ground_truth_violations, system_findings):
    """Compare ground truth list against system findings list."""
    # normalize findings to strings
    sf_texts = [finding_text(f) for f in system_findings]

    tp = 0
    fp = 0
    fn = 0
    matched = set()

    for gt in ground_truth_violations:
        gt_lower = gt.lower()
        found = False
        for i, sf in enumerate(sf_texts):
            if i not in matched:
                gt_words = set(gt_lower.split())
                sf_words = set(sf.lower().split())
                overlap = gt_words & sf_words
                if len(overlap) >= 2:
                    tp += 1
                    matched.add(i)
                    found = True
                    break
        if not found:
            fn += 1

    fp = len(sf_texts) - len(matched)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0

    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
    }


def build_prompt(ruleset_name, custom_rules, platforms, jurisdictions, audio_flags, include_rights):
    """Build the compliance analysis prompt for TwelveLabs Pegasus."""
    from app_config import RULESETS, JURISDICTIONS

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
Identify ALL of the following requiring clearance:
- On-screen artworks, paintings, sculptures, installations
- Brand logos, trademarks, product packaging
- Identifiable talent (faces visible, recognizable)
- Background music, sound effects, jingles
- Architectural works, set designs
- News footage, archival material
Format: [timestamp] [asset type] [description] [clearance needed: YES/MAYBE/NO]
""" if include_rights else ""

    return f"""You are a senior compliance reviewer. You MUST ONLY flag violations that match the specific rules listed below. Do NOT invent, infer, or speculate about violations not covered by these rules. If you are not confident a violation exists, do NOT report it. Only report what you can directly observe in the video.

IMPORTANT CONSTRAINTS:
- Only flag items that clearly violate a rule listed below
- Confidence must reflect how certain you are: use 30-50 for uncertain, 50-70 for likely, 70-90 for clear, 90+ only for unambiguous
- If a category has no violations, write: NOT DETECTED
- Do NOT flag normal, compliant content
- Do NOT flag things that "could potentially" be an issue — only flag what IS an issue

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
