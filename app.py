import os
import json
import time
import logging
import traceback
import html as html_mod
import pandas as pd
from datetime import datetime, date
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from twelvelabs import TwelveLabs

# ── LOGGING SETUP ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("cleared")


class SessionLogHandler(logging.Handler):
    """Captures log records into a list for display in the UI."""
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append({
            "time": self.format(record).split(" ")[0] if self.format(record) else "",
            "level": record.levelname,
            "msg": record.getMessage(),
        })
        # keep last 200 entries
        if len(self.records) > 200:
            self.records = self.records[-200:]


_ui_handler = SessionLogHandler()
_ui_handler.setFormatter(logging.Formatter("%(asctime)s", datefmt="%H:%M:%S"))
logging.getLogger("cleared").addHandler(_ui_handler)
logging.getLogger("cleared.helpers").addHandler(_ui_handler)

from config import RULESETS, JURISDICTIONS, PLATFORMS, AUDIO_FLAGS, DEFAULT_INDEX_ID
from helpers import (
    parse_findings, severity_score, parse_timestamp_seconds, build_prompt,
    finding_text, finding_severity, finding_confidence,
    parse_rights_from_report,
    log_feedback, load_feedback_log, load_rights_log, save_rights_log,
    get_expiring_rights, load_ground_truth, save_ground_truth, compute_metrics,
)
from styles import get_app_css

load_dotenv()
_api_key = os.environ.get("TWELVELABS_API_KEY", "")
if not _api_key:
    log.error("TWELVELABS_API_KEY not set — API calls will fail")
else:
    log.info("API key loaded successfully")
client = TwelveLabs(api_key=_api_key) if _api_key else None

# ── API HELPERS (need client + st.cache) ─────────────────────
@st.cache_data(ttl=60)
def fetch_indexes():
    try:
        indexes = list(client.indexes.list())
        return [(idx.index_name or idx.id, idx.id) for idx in indexes]
    except Exception:
        return []

def get_or_create_index():
    """Get the first user-owned index, or create one."""
    try:
        log.info("Fetching indexes from TwelveLabs...")
        indexes = list(client.indexes.list())
        log.info(f"Found {len(indexes)} indexes: {[(idx.index_name, idx.id) for idx in indexes]}")
        for idx in indexes:
            name = idx.index_name or ""
            if "sample" not in name.lower():
                log.info(f"Using index: {name} ({idx.id})")
                return idx.id
        # no non-sample index found, create one
        log.info("No user index found, creating 'cleared-compliance'...")
        new_idx = client.indexes.create(
            index_name="cleared-compliance",
            models=[{"model_name": "marengo", "options": ["visual", "conversation", "text_in_video", "logo"]}],
        )
        log.info(f"Created index: {new_idx.id}")
        return new_idx.id
    except Exception as e:
        log.error(f"Index lookup failed: {e}\n{traceback.format_exc()}")
        try:
            new_idx = client.indexes.create(
                index_name="cleared-compliance",
                models=[{"model_name": "marengo", "options": ["visual", "conversation", "text_in_video", "logo"]}],
            )
            log.info(f"Fallback index created: {new_idx.id}")
            return new_idx.id
        except Exception as e2:
            log.error(f"Fallback index creation failed: {e2}\n{traceback.format_exc()}")
            return None

@st.cache_data(ttl=60)
def fetch_videos(index_id):
    try:
        videos = list(client.assets.list(index_id=index_id))
        return [
            (v.metadata.filename if hasattr(v, 'metadata') and v.metadata and v.metadata.filename else v.id, v.id)
            for v in videos
        ]
    except Exception:
        try:
            tasks = list(client.tasks.list(index_id=index_id))
            return [(t.video_id, t.video_id) for t in tasks if t.status == "ready"]
        except Exception:
            return []

@st.cache_data(ttl=3600)
def fetch_video_url(video_id, index_id):
    try:
        log.info(f"Fetching video URL: video={video_id}, index={index_id}")
        video = client.indexes.videos.retrieve(index_id, video_id)
        url = video.hls.video_url
        log.info(f"Video URL resolved: {url[:80]}...")
        return url
    except Exception as e:
        log.error(f"fetch_video_url failed: video={video_id}, index={index_id} — {e}")
        return None

# ── VIDEO PLAYER COMPONENT ───────────────────────────────────
def video_player(video_url: str, seek_to: float = 0, findings: list = None):
    markers_js = ""
    if findings:
        for i, f in enumerate(findings):
            ts = parse_timestamp_seconds(f)
            sev = finding_severity(f)
            color = "#dc2626" if sev == "CRITICAL" else "#ea580c" if sev == "MAJOR" else "#2563eb"
            ft = finding_text(f)
            conf = finding_confidence(f)
            safe_label = html_mod.escape(ft[:50]).replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"').replace("\n", " ")
            markers_js += f'addMarker({ts}, "{color}", "{safe_label} ({conf}%)");'

    findings_data = json.dumps([
        (parse_timestamp_seconds(f), html_mod.escape(finding_text(f)[:40]),
         finding_severity(f).lower(), finding_confidence(f))
        for f in (findings or [])
    ])

    components.html(f"""
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html, body {{
            background: #111;
            font-family: 'Inter', -apple-system, sans-serif;
            overflow: hidden;
            height: 100%;
        }}

        .outer-wrap {{
            display: flex;
            height: 100%;
            background: #111;
            border-radius: 10px;
            overflow: hidden;
        }}

        .video-side {{
            flex: 1;
            min-width: 0;
            display: flex;
            flex-direction: column;
            background: #000;
        }}

        video {{
            width: 100%;
            flex: 1;
            min-height: 0;
            background: #000;
            display: block;
        }}

        .timeline-wrap {{
            position: relative;
            height: 4px;
            background: #333;
            cursor: pointer;
            flex-shrink: 0;
        }}

        .timeline-progress {{
            position: absolute;
            top: 0; left: 0;
            height: 100%;
            background: #fff;
            pointer-events: none;
            transition: width 0.1s linear;
        }}

        .timeline-marker {{
            position: absolute;
            top: -4px;
            width: 3px;
            height: 12px;
            border-radius: 1px;
            cursor: pointer;
        }}

        .timeline-marker:hover {{ opacity: 0.7; }}

        .marker-tooltip {{
            display: none;
            position: absolute;
            bottom: 18px;
            left: 50%;
            transform: translateX(-50%);
            background: #fff;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            padding: 0.3rem 0.6rem;
            font-size: 0.62rem;
            color: #333;
            white-space: normal;
            width: 180px;
            z-index: 10;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }}

        .timeline-marker:hover .marker-tooltip {{ display: block; }}

        .controls-row {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.4rem 0.75rem;
            background: #111;
            border-top: 1px solid #222;
            flex-shrink: 0;
        }}

        .timecode {{
            font-size: 0.65rem;
            color: #888;
            letter-spacing: 0.05em;
            white-space: nowrap;
            font-weight: 500;
        }}

        .seekbar-panel {{
            width: 220px;
            flex-shrink: 0;
            display: flex;
            flex-direction: column;
            background: #0a0a0a;
            border-left: 1px solid #222;
            overflow: hidden;
        }}

        .panel-label {{
            font-size: 0.6rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: #666;
            padding: 0.6rem 0.75rem 0.5rem;
            border-bottom: 1px solid #222;
            flex-shrink: 0;
            font-weight: 600;
        }}

        .seekbar-wrap {{
            flex: 1;
            overflow-y: auto;
            padding: 0.4rem 0.5rem;
            display: flex;
            flex-direction: column;
            gap: 0.3rem;
        }}

        .seekbar-wrap::-webkit-scrollbar {{ width: 3px; }}
        .seekbar-wrap::-webkit-scrollbar-track {{ background: #0a0a0a; }}
        .seekbar-wrap::-webkit-scrollbar-thumb {{ background: #333; border-radius: 2px; }}

        .seek-badge {{
            background: transparent;
            border-radius: 6px;
            padding: 0.35rem 0.6rem;
            font-size: 0.6rem;
            cursor: pointer;
            letter-spacing: 0.02em;
            font-family: 'Inter', sans-serif;
            font-weight: 500;
            transition: all 0.12s;
            white-space: normal;
            text-align: left;
            line-height: 1.4;
            width: 100%;
        }}

        .seek-badge.critical {{
            border: 1px solid #dc2626; color: #fca5a5;
        }}
        .seek-badge.critical:hover {{ background: rgba(220,38,38,0.15); }}

        .seek-badge.major {{
            border: 1px solid #ea580c; color: #fdba74;
        }}
        .seek-badge.major:hover {{ background: rgba(234,88,12,0.15); }}

        .seek-badge.minor {{
            border: 1px solid #2563eb; color: #93c5fd;
        }}
        .seek-badge.minor:hover {{ background: rgba(37,99,235,0.15); }}

        .no-findings {{
            font-size: 0.62rem;
            color: #555;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            padding: 0.75rem 0.5rem;
            font-weight: 500;
        }}
    </style>

    <div class="outer-wrap">

        <!-- left: video -->
        <div class="video-side">
            <video id="clearedplayer" controls preload="metadata"></video>

            <div class="timeline-wrap" id="timeline" onclick="timelineClick(event)">
                <div class="timeline-progress" id="progress"></div>
            </div>

            <div class="controls-row">
                <span class="timecode" id="current-time">0:00</span>
                <span class="timecode">/</span>
                <span class="timecode" id="dur">--:--</span>
                {"<span class='timecode' style='color:#fff;margin-left:auto;background:#333;padding:2px 8px;border-radius:4px;'>⏱ " + str(int(seek_to)) + "s</span>" if seek_to > 0 else ""}
            </div>
        </div>

        <!-- right: violations -->
        <div class="seekbar-panel">
            <div class="panel-label">violations</div>
            <div class="seekbar-wrap" id="seekbar">
                <span class="no-findings" id="no-findings-msg">run check to see findings</span>
            </div>
        </div>

    </div>

    <script>
        const video = document.getElementById('clearedplayer');
        const progress = document.getElementById('progress');
        const timeline = document.getElementById('timeline');
        const seekbar = document.getElementById('seekbar');
        const videoSrc = "{video_url}";
        let duration = 0;

        function fmt(s) {{
            const m = Math.floor(s / 60);
            const sec = Math.floor(s % 60);
            return m + ':' + (sec < 10 ? '0' : '') + sec;
        }}

        function onReady() {{
            duration = video.duration;
            document.getElementById('dur').textContent = fmt(duration);
            {markers_js}
            video.currentTime = {seek_to};
            {"video.play();" if seek_to > 0 else ""}
        }}

        if (typeof Hls !== 'undefined' && Hls.isSupported() && videoSrc.includes('.m3u8')) {{
            const hls = new Hls();
            hls.loadSource(videoSrc);
            hls.attachMedia(video);
            hls.on(Hls.Events.MANIFEST_PARSED, onReady);
        }} else {{
            video.src = videoSrc;
            video.addEventListener('loadedmetadata', onReady);
        }}

        video.addEventListener('timeupdate', function() {{
            if (duration > 0) {{
                progress.style.width = (video.currentTime / duration * 100) + '%';
                document.getElementById('current-time').textContent = fmt(video.currentTime);
            }}
        }});

        function timelineClick(e) {{
            if (duration === 0) return;
            const rect = timeline.getBoundingClientRect();
            video.currentTime = ((e.clientX - rect.left) / rect.width) * duration;
            video.play();
        }}

        function addMarker(seconds, color, label) {{
            if (duration === 0) return;
            const pct = (seconds / duration) * 100;
            const marker = document.createElement('div');
            marker.className = 'timeline-marker';
            marker.style.left = pct + '%';
            marker.style.background = color;
            const tip = document.createElement('div');
            tip.className = 'marker-tooltip';
            tip.textContent = fmt(seconds) + ' — ' + label;
            marker.appendChild(tip);
            marker.onclick = function(e) {{
                e.stopPropagation();
                video.currentTime = seconds;
                video.play();
            }};
            timeline.appendChild(marker);
        }}

        const findings = {findings_data};
        if (findings.length > 0) {{
            const msg = document.getElementById('no-findings-msg');
            if (msg) msg.remove();
            findings.forEach(function(f) {{
                const btn = document.createElement('button');
                btn.className = 'seek-badge ' + f[2];
                const conf = f[3] || 70;
                btn.innerHTML = '<span style="opacity:0.6;font-size:0.5rem">' + conf + '%</span> ' + fmt(f[0]) + '  ' + f[1].substring(0, 35) + (f[1].length > 35 ? '…' : '');
                btn.onclick = function() {{
                    video.currentTime = f[0];
                    video.play();
                }};
                seekbar.appendChild(btn);
            }});
        }}
    </script>
    """, height=460)

# ── PAGE CONFIG ──────────────────────────────────────────────
st.set_page_config(page_title="Cleared", layout="wide", page_icon="C")

st.markdown(get_app_css(), unsafe_allow_html=True)

# ── SIDEBAR LABEL HELPER ─────────────────────────────────────
def _sidebar_label(text):
    st.markdown(
        f'<p style="margin-top:1rem;margin-bottom:0.25rem;font-size:0.62rem;font-weight:600;'
        f'color:var(--text-muted);letter-spacing:0.1em;text-transform:uppercase;'
        f'font-family:JetBrains Mono,monospace;">{text}</p>',
        unsafe_allow_html=True
    )

# ── SIDEBAR ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="padding:0.25rem 0 0.5rem 0;border-bottom:1px solid var(--border-light);margin-bottom:0.5rem;">'
        '<span style="font-family:JetBrains Mono,monospace;font-weight:700;color:var(--text-primary);font-size:1.1rem;'
        'letter-spacing:-0.02em;line-height:1;">Cleared</span>'
        '</div>',
        unsafe_allow_html=True
    )

    # ── 1. VIDEO ──
    _sidebar_label("1. Video")
    uploaded_file = st.file_uploader("Upload video", type=["mp4", "mov", "avi", "webm"], label_visibility="collapsed")

    if uploaded_file:
        upload_key = f"uploaded_{uploaded_file.name}_{uploaded_file.size}"
        if upload_key not in st.session_state:
            try:
                import tempfile
                log.info(f"Upload started: {uploaded_file.name} ({uploaded_file.size} bytes)")
                upload_index_id = get_or_create_index()
                if not upload_index_id:
                    raise Exception("Could not find or create an index. Check your API key.")
                log.info(f"Using index {upload_index_id} for upload")
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp:
                    tmp.write(uploaded_file.read())
                    tmp_path = tmp.name
                task = client.tasks.create(
                    index_id=upload_index_id,
                    video_file=open(tmp_path, "rb"),
                )
                log.info(f"Upload task created: video_id={task.video_id}, task_id={task.id}")
                os.unlink(tmp_path)
                st.session_state[upload_key] = {
                    "video_id": task.video_id,
                    "task_id": task.id,
                    "index_id": upload_index_id,
                    "label": uploaded_file.name,
                }
            except Exception as e:
                log.error(f"Upload failed: {e}\n{traceback.format_exc()}")
                st.error(f"Upload failed: {e}")

        upload_info = st.session_state.get(upload_key, {})
        selected_video_id = upload_info.get("video_id", "")
        selected_index_id = upload_info.get("index_id", DEFAULT_INDEX_ID)
        selected_task_id = upload_info.get("task_id", "")
        selected_video_label = upload_info.get("label", uploaded_file.name)
        st.caption(f"Source: {selected_video_label}")
    else:
        selected_video_id = ""
        selected_index_id = DEFAULT_INDEX_ID
        selected_task_id = ""
        selected_video_label = ""
        st.caption("No video selected")

    # ── 2. TARGET PLATFORMS ──
    _sidebar_label("2. Target Platforms")
    selected_platforms = st.multiselect("platforms", PLATFORMS, default=[], label_visibility="collapsed",
                                        placeholder="Where will this air?")

    # ── 3. JURISDICTIONS ──
    _sidebar_label("3. Jurisdictions")
    selected_jurisdictions = st.multiselect("jurisdictions", list(JURISDICTIONS.keys()), default=[], label_visibility="collapsed",
                                            placeholder="Which regions?")

    # ── AUTO-RULESET: derive from platform + jurisdiction selection ──
    auto_rulesets = set()
    for p in selected_platforms:
        if p in ("YouTube", "TikTok", "Instagram", "Roblox"):
            auto_rulesets.add("Platform Policies")
        elif p in ("Broadcast pre-watershed", "Streaming (Netflix/HBO)", "The Sphere"):
            auto_rulesets.add("Broadcast Standards")
    for j in selected_jurisdictions:
        if j != "None":
            auto_rulesets.add("Broadcast Standards")

    # show what rulesets will be applied
    if auto_rulesets:
        chips = " ".join(
            f'<span style="display:inline-block;padding:2px 8px;border:1px solid var(--border);border-radius:4px;'
            f'font-size:0.62rem;color:var(--text-tertiary);margin:2px 2px 2px 0;">{r}</span>'
            for r in sorted(auto_rulesets)
        )
        st.markdown(f'<p style="margin-top:0.5rem;font-size:0.6rem;color:var(--text-muted);letter-spacing:0.05em;">'
                    f'Auto-applied: {chips}</p>', unsafe_allow_html=True)

    # optional: add custom rules
    include_rights = True
    custom_rules = ""
    with st.expander("Custom rules", expanded=False):
        custom_rules = st.text_area("One rule per line", height=80, label_visibility="collapsed",
                                     placeholder="e.g.\nNo visible tattoos\nNo competitor products in frame")

    # combine all auto-applied rulesets for the prompt
    if not auto_rulesets:
        ruleset_name = "Broadcast Standards"
    elif len(auto_rulesets) == 1:
        ruleset_name = list(auto_rulesets)[0]
    else:
        ruleset_name = "Broadcast Standards"  # primary, others merged via custom_rules
        for rs in auto_rulesets:
            if rs != "Broadcast Standards":
                extra_rules = RULESETS.get(rs, {}).get("rules", [])
                if extra_rules:
                    custom_rules = (custom_rules or "") + "\n" + "\n".join(extra_rules)

    selected_audio = AUDIO_FLAGS

    # ── RUN BUTTON ──
    st.markdown('<div style="margin-top:0.75rem"></div>', unsafe_allow_html=True)
    run = st.button("Run Compliance Check", width='stretch')

# ── RUN ───────────────────────────────────────────────────────
if run:
    if not selected_video_id:
        st.error("Upload or select a video first.")
    elif not selected_platforms and not selected_jurisdictions:
        st.error("Select at least one platform or jurisdiction.")
    else:
        _run_status = st.empty()
        _run_progress = st.progress(0)
        try:
            # Step 1: wait for indexing if needed
            if selected_task_id:
                _run_status.caption("Waiting for video indexing...")
                log.info(f"Checking indexing status for task {selected_task_id}...")
                _max_wait = 300
                _waited = 0
                while _waited < _max_wait:
                    task_status = client.tasks.retrieve(selected_task_id)
                    status = getattr(task_status, 'status', 'unknown')
                    log.info(f"Task {selected_task_id} status: {status} ({_waited}s)")
                    _run_progress.progress(min(_waited / 60, 0.3))
                    if status == "ready":
                        log.info("Video indexing complete.")
                        break
                    elif status == "failed":
                        raise Exception(f"Video indexing failed (task {selected_task_id})")
                    time.sleep(5)
                    _waited += 5
                if _waited >= _max_wait:
                    raise Exception(f"Video indexing timed out after {_max_wait}s")

            # Step 2: run analysis
            _run_status.caption("Running compliance analysis...")
            _run_progress.progress(0.35)
            prompt = build_prompt(ruleset_name, custom_rules, selected_platforms, selected_jurisdictions, selected_audio, include_rights)
            log.info(f"Starting analysis: video={selected_video_id}, ruleset={ruleset_name}, platforms={selected_platforms}, jurisdictions={selected_jurisdictions}")
            log.info(f"Prompt length: {len(prompt)} chars")
            _t0 = time.time()
            response = client.analyze(video_id=selected_video_id, prompt=prompt)
            _elapsed = round(time.time() - _t0, 1)
            report_data = getattr(response, 'data', None) or str(response)
            log.info(f"Analysis complete in {_elapsed}s, response length: {len(report_data)} chars")
            _run_progress.progress(0.8)

            # Step 3: parse findings
            _run_status.caption("Parsing findings...")
            findings = parse_findings(report_data)
            log.info(f"Parsed {len(findings)} findings")
            for i, f in enumerate(findings):
                log.info(f"  Finding {i+1}: {finding_text(f)[:100]}")
            _run_progress.progress(0.9)

            # Step 4: fetch video URL
            _run_status.caption("Loading video player...")
            _video_url = fetch_video_url(selected_video_id, selected_index_id)
            _run_progress.progress(1.0)

            st.session_state.report = report_data
            st.session_state.findings = findings
            st.session_state.video_id = selected_video_id
            st.session_state.index_id = selected_index_id
            st.session_state.video_label = selected_video_label
            st.session_state.video_url = _video_url
            st.session_state.risk_score = severity_score(response.data)
            st.session_state.platforms = selected_platforms
            st.session_state.jurisdictions = selected_jurisdictions
            st.session_state.ruleset = ruleset_name
            st.session_state.run_time = datetime.now().isoformat()
            st.session_state.analysis_duration = _elapsed
            st.session_state.seek_to = 0
            log.info(f"Risk score: {st.session_state.risk_score}")
        except Exception as e:
            log.error(f"Analysis failed: {e}\n{traceback.format_exc()}")
            st.error(f"Analysis failed: {e}")
        finally:
            _run_status.empty()
            _run_progress.empty()

# ── THEATER PLAYER ────────────────────────────────────────────
# Only shows AFTER analysis has run — video source selection is decoupled
if "report" in st.session_state and st.session_state.get("video_url"):
    video_player(
        st.session_state.video_url,
        seek_to=st.session_state.get("seek_to", 0),
        findings=st.session_state.get("findings", []),
    )
elif "report" in st.session_state:
    st.markdown(
        '<div style="background:#111;border-radius:8px;height:420px;display:flex;align-items:center;'
        'justify-content:center;color:#555;font-family:\'JetBrains Mono\',monospace;font-size:0.78rem;'
        'letter-spacing:0.05em;">Video URL unavailable — analysis results below</div>',
        unsafe_allow_html=True
    )
else:
    # pre-analysis state: show instructions
    st.markdown(
        '<div style="background:#111;border-radius:8px;height:420px;display:flex;align-items:center;'
        'justify-content:center;color:#555;font-family:\'JetBrains Mono\',monospace;font-size:0.78rem;'
        'letter-spacing:0.05em;text-align:center;line-height:2;">'
        '1. Upload or select a video<br>'
        '2. Choose target platforms + jurisdictions<br>'
        '3. Click Run Compliance Check</div>',
        unsafe_allow_html=True
    )

# ── RESULTS ───────────────────────────────────────────────────
tab_findings, tab_rights, tab_export, tab_gt = st.tabs([
    "Compliance Findings", "Rights Tracker", "Export", "Ground Truth"
])

# ── TAB 1: COMPLIANCE FINDINGS ────────────────────────────
with tab_findings:
    if "report" not in st.session_state:
        st.markdown('<div style="text-align:center;padding:4rem 2rem;color:var(--text-muted);font-size:0.82rem;'
                    'font-family:JetBrains Mono,monospace;letter-spacing:0.02em;">'
                    'Select a video, configure platforms & jurisdictions, then click '
                    '<b style="color:var(--text-secondary)">Run Compliance Check</b></div>',
                    unsafe_allow_html=True)
    else:
        # risk banner
        score = st.session_state.risk_score
        if score >= 20:
            st.markdown(f'<div class="risk-critical">CRITICAL RISK &mdash; Score {score} &mdash; Immediate action required</div>', unsafe_allow_html=True)
        elif score >= 15:
            st.markdown(f'<div class="risk-high">HIGH RISK &mdash; Score {score}</div>', unsafe_allow_html=True)
        elif score >= 7:
            st.markdown(f'<div class="risk-medium">MEDIUM RISK &mdash; Score {score}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="risk-low">LOW RISK &mdash; Score {score}</div>', unsafe_allow_html=True)

        _dur = st.session_state.get('analysis_duration', '')
        _dur_str = f" &middot; {_dur}s" if _dur else ""
        st.markdown(f'<p style="font-size:0.72rem;color:var(--text-muted);margin-bottom:0.5rem;">'
                    f'{st.session_state.get("run_time","—")} &middot; {st.session_state.get("ruleset","—")} '
                    f'&middot; {st.session_state.get("video_label","")}{_dur_str}</p>',
                    unsafe_allow_html=True)

        findings = st.session_state.findings
        if not findings:
            st.info("No findings detected.")
        else:
            # init remediations dict
            if "remediations" not in st.session_state:
                st.session_state.remediations = {}

            for i, finding in enumerate(findings):
                ft = finding_text(finding)
                sev = finding_severity(finding)
                conf = finding_confidence(finding)
                ts_sec = parse_timestamp_seconds(finding)
                safe_ft = html_mod.escape(ft)

                card_class = "finding-card"
                if sev == "CRITICAL":
                    card_class += " finding-critical"
                elif sev == "MAJOR":
                    card_class += " finding-major"
                else:
                    card_class += " finding-minor"

                # confidence badge color
                conf_color = "#dc2626" if conf >= 85 else "#ea580c" if conf >= 70 else "#d97706" if conf >= 50 else "#6b7280"

                with st.container():
                    # finding card with confidence badge
                    st.markdown(f'<div class="{card_class}">'
                                f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:0.5rem;">'
                                f'<div style="flex:1">{safe_ft}</div>'
                                f'<div style="flex-shrink:0;background:{conf_color};color:#fff;padding:2px 8px;border-radius:4px;'
                                f'font-size:0.65rem;font-weight:700;font-family:JetBrains Mono,monospace;">{conf}%</div>'
                                f'</div></div>', unsafe_allow_html=True)

                    # action row: seek + approve/reject/escalate
                    col_seek, col_a, col_r, col_e = st.columns([2, 1, 1, 1])

                    if col_seek.button(f"Seek {ts_sec}s", key=f"seek_{i}"):
                        st.session_state.seek_to = ts_sec
                        st.rerun()

                    if col_a.button("Approve", key=f"a_{i}"):
                        log_feedback(finding, "approved", st.session_state.video_id, st.session_state.ruleset, st.session_state.platforms, st.session_state.jurisdictions)
                        st.session_state[f"decision_{i}"] = "approved"

                    if col_r.button("Reject", key=f"r_{i}"):
                        log_feedback(finding, "rejected", st.session_state.video_id, st.session_state.ruleset, st.session_state.platforms, st.session_state.jurisdictions)
                        st.session_state[f"decision_{i}"] = "rejected"

                    if col_e.button("Escalate", key=f"e_{i}"):
                        log_feedback(finding, "escalated", st.session_state.video_id, st.session_state.ruleset, st.session_state.platforms, st.session_state.jurisdictions)
                        st.session_state[f"decision_{i}"] = "escalated"

                    _decision = st.session_state.get(f"decision_{i}")
                    if _decision:
                        _colors = {"approved": "--risk-low-text", "rejected": "--risk-critical-text", "escalated": "--risk-medium-text"}
                        st.markdown(f'<p style="font-size:0.7rem;color:var({_colors.get(_decision, "--text-muted")});'
                                    f'font-weight:600;letter-spacing:0.05em;text-transform:uppercase;">{_decision}</p>',
                                    unsafe_allow_html=True)

                    # remediation row: blur / bleep / AI replace
                    st.markdown('<p style="font-size:0.62rem;color:var(--text-muted);letter-spacing:0.1em;'
                                'text-transform:uppercase;margin-top:0.5rem;margin-bottom:0.3rem;font-weight:600;">'
                                'Remediation</p>', unsafe_allow_html=True)

                    rem_col1, rem_col2, rem_col3 = st.columns(3)
                    current_rem = st.session_state.remediations.get(i, {}).get("type")

                    if rem_col1.button("Blur", key=f"blur_{i}", type="primary" if current_rem == "blur" else "secondary"):
                        st.session_state.remediations[i] = {"type": "blur", "timecode": ts_sec, "duration": 3}
                        st.rerun()

                    if rem_col2.button("Bleep", key=f"bleep_{i}", type="primary" if current_rem == "bleep" else "secondary"):
                        st.session_state.remediations[i] = {"type": "bleep", "timecode": ts_sec, "duration": 2}
                        st.rerun()

                    if rem_col3.button("AI Replace", key=f"ai_replace_{i}", type="primary" if current_rem == "ai_replace" else "secondary"):
                        st.session_state.remediations[i] = {"type": "ai_replace", "timecode": ts_sec, "duration": 3}

                    # show AI replacement options if selected
                    if current_rem == "ai_replace":
                        st.markdown('<div class="ltx-panel">', unsafe_allow_html=True)
                        st.markdown('<p style="color:#7c3aed;font-size:0.62rem;letter-spacing:0.1em;text-transform:uppercase;'
                                    'margin-bottom:0.5rem;font-weight:600;font-family:JetBrains Mono,monospace;">AI Replacement</p>',
                                    unsafe_allow_html=True)

                        v_lower = ft.lower()
                        if any(w in v_lower for w in ["alcohol", "drink", "beer", "wine", "bottle"]):
                            options = [
                                "Person holding sparkling water, same lighting and mood",
                                "Person with coffee cup, warm interior light",
                                "Hands on table, no beverage visible",
                                "Person gesturing, beverage removed from frame",
                            ]
                        elif any(w in v_lower for w in ["vap", "smok", "inhaler", "cigarette"]):
                            options = [
                                "Person exhaling, misty breath, no device present",
                                "Person pausing thoughtfully, hands at sides",
                                "Cutaway to environment, person not in frame",
                                "Person sipping water bottle instead",
                            ]
                        elif any(w in v_lower for w in ["logo", "brand", "trademark", "sign"]):
                            options = [
                                "Brand signage replaced with neutral text",
                                "Reframed angle avoiding branded element",
                                "Soft-focus background obscuring logo",
                                "Wide shot repositioning brand outside frame",
                            ]
                        elif any(w in v_lower for w in ["profan", "language", "speech", "slur", "curs"]):
                            options = [
                                "Audio bleep with matching waveform",
                                "Silence with ambient room tone fill",
                                "Redubbed clean dialogue replacement",
                                "Music swell covering flagged audio",
                            ]
                        else:
                            options = [
                                "Alternative shot without flagged element",
                                "Neutral establishing shot cutaway",
                                "Close-up on different subject in scene",
                                "Wide shot excluding violation from frame",
                            ]

                        _tcols = st.columns(2)
                        for j, opt in enumerate(options):
                            with _tcols[j % 2]:
                                if st.button(f"{opt[:50]}", key=f"ltx_{i}_{j}", use_container_width=True):
                                    st.session_state.remediations[i]["prompt"] = opt
                                    st.success(f"Queued: {opt}")

                        if st.session_state.remediations.get(i, {}).get("prompt"):
                            st.markdown(f'<p style="color:#166534;font-size:0.72rem;margin-top:0.5rem;font-weight:500">'
                                        f'Queued: {st.session_state.remediations[i]["prompt"]}</p>',
                                        unsafe_allow_html=True)

                        st.markdown('</div>', unsafe_allow_html=True)

                    # show applied remediation status
                    elif current_rem:
                        st.markdown(f'<p style="color:#059669;font-size:0.72rem;font-weight:600;margin-top:0.25rem;">'
                                    f'Applied: {current_rem.upper()} at {ts_sec}s</p>',
                                    unsafe_allow_html=True)

                    # reviewer note
                    note = st.text_input("Add note", key=f"note_{i}", label_visibility="collapsed", placeholder="Add reviewer note...")
                    if note:
                        st.session_state[f"annotation_{i}"] = note

                    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ── TAB 2: RIGHTS TRACKER ─────────────────────────────────
with tab_rights:
    # auto-detected rights from analysis
    auto_rights = []
    if "report" in st.session_state:
        auto_rights = parse_rights_from_report(st.session_state.report)

    rights_entries = load_rights_log()
    all_rights = auto_rights + rights_entries

    expiring = get_expiring_rights(all_rights, days_ahead=30)
    if expiring:
        for e in expiring:
            days = e.get("days_remaining", "?")
            color = "#dc2626" if isinstance(days, int) and days <= 7 else "#ea580c"
            st.markdown(f'<div class="rights-expiring" style="border-color:{color};color:{color}">'
                        f'<b>{e.get("asset","")}</b> — expires {e.get("expiry_date","?")} ({days} days) — {e.get("type","")}</div>',
                        unsafe_allow_html=True)

    st.markdown("### Rights & Clearances")

    # auto-detected section
    if auto_rights:
        st.markdown('<p style="font-size:0.62rem;color:var(--text-muted);letter-spacing:0.1em;text-transform:uppercase;'
                    'font-weight:600;margin-bottom:0.5rem;">Auto-detected from video</p>', unsafe_allow_html=True)
        for e in auto_rights:
            tag_color = "#7c3aed"
            st.markdown(f'<div class="finding-card" style="border-left:3px solid {tag_color};">'
                        f'<b>{html_mod.escape(e.get("asset",""))}</b> · '
                        f'<span style="color:{tag_color}">{e.get("type","")}</span> · '
                        f'{e.get("notes","")}</div>', unsafe_allow_html=True)
        st.markdown("---")

    st.caption("Track expiry dates for music, talent releases, artwork clearances, and licensed assets")

    with st.expander("+ add rights entry", expanded=False):
        r1, r2, r3, r4 = st.columns(4)
        r_asset = r1.text_input("asset name", placeholder="e.g. Track — Blue World")
        r_type = r2.selectbox("type", ["Music license", "Talent release", "Artwork clearance", "Brand license", "Archive footage", "Other"])
        r_expiry = r3.date_input("expiry date")
        r_notes = r4.text_input("notes", placeholder="licensor, territory...")
        if st.button("add to tracker"):
            entries = load_rights_log()
            entries.append({"asset": r_asset, "type": r_type, "expiry_date": r_expiry.isoformat(),
                            "notes": r_notes, "added_at": datetime.now().isoformat(),
                            "video_id": st.session_state.get("video_id", "")})
            save_rights_log(entries)
            st.success(f"added: {r_asset}")

    if rights_entries:
        st.markdown('<p style="font-size:0.62rem;color:var(--text-muted);letter-spacing:0.1em;text-transform:uppercase;'
                    'font-weight:600;margin-top:1rem;margin-bottom:0.5rem;">Manual entries</p>', unsafe_allow_html=True)
        for e in sorted(rights_entries, key=lambda x: x.get("expiry_date", "")):
            try:
                days = (date.fromisoformat(e["expiry_date"]) - date.today()).days
                if days <= 0:
                    css, indicator = "rights-expiring", f"EXPIRED {abs(days)} days ago"
                    color = "#dc2626"
                elif days <= 7:
                    css, indicator = "rights-expiring", f"Expires in {days} days"
                    color = "#ea580c"
                elif days <= 30:
                    css, indicator = "rights-expiring", f"{days} days remaining"
                    color = "#d97706"
                else:
                    css, indicator = "rights-ok", f"{days} days remaining"
                    color = "#888"
            except Exception:
                css, indicator, color = "rights-ok", "date unknown", "#888"
            st.markdown(f'<div class="{css}" style="border-color:{color};color:{color}">'
                        f'<b>{e.get("asset","")}</b> · {e.get("type","")} · {e.get("expiry_date","")} · {indicator}'
                        f'{("  ·  " + e.get("notes","")) if e.get("notes") else ""}</div>',
                        unsafe_allow_html=True)
    elif not auto_rights:
        st.caption("No rights entries yet. Run a compliance check to auto-detect, or add manually.")

# ── TAB 3: EXPORT ─────────────────────────────────────────
with tab_export:
    if "report" not in st.session_state:
        st.caption("Run a compliance check to enable export.")
    else:
        st.markdown("### Final Review & Export")
        st.caption("Review all findings and applied remediations before committing to export.")

        findings = st.session_state.findings
        remediations = st.session_state.get("remediations", {})
        score = st.session_state.risk_score

        # summary cards
        total_findings = len(findings)
        total_remediated = len(remediations)
        total_approved = sum(1 for i in range(total_findings) if st.session_state.get(f"decision_{i}") == "approved")
        total_rejected = sum(1 for i in range(total_findings) if st.session_state.get(f"decision_{i}") == "rejected")

        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f'<div class="metric-card"><div class="metric-number">{total_findings}</div><div class="metric-label">findings</div></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="metric-card"><div class="metric-number" style="color:#059669">{total_remediated}</div><div class="metric-label">remediated</div></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="metric-card"><div class="metric-number" style="color:#16a34a">{total_approved}</div><div class="metric-label">approved</div></div>', unsafe_allow_html=True)
        m4.markdown(f'<div class="metric-card"><div class="metric-number" style="color:#dc2626">{total_rejected}</div><div class="metric-label">rejected</div></div>', unsafe_allow_html=True)

        st.markdown("---")

        # findings summary with remediation status
        for i, finding in enumerate(findings):
            ft = finding_text(finding)
            sev = finding_severity(finding)
            decision = st.session_state.get(f"decision_{i}", "pending")
            rem = remediations.get(i, {})
            rem_type = rem.get("type", "none")

            sev_color = "#dc2626" if sev == "CRITICAL" else "#ea580c" if sev == "MAJOR" else "#2563eb"
            dec_color = "#059669" if decision == "approved" else "#dc2626" if decision == "rejected" else "#d97706" if decision == "escalated" else "#6b7280"

            st.markdown(f'<div style="display:flex;align-items:center;gap:0.75rem;padding:0.5rem 0;border-bottom:1px solid var(--border-light);font-size:0.78rem;">'
                        f'<span style="color:{sev_color};font-weight:700;font-size:0.6rem;letter-spacing:0.05em;min-width:55px;">{sev}</span>'
                        f'<span style="flex:1;color:var(--text-secondary)">{html_mod.escape(ft[:80])}</span>'
                        f'<span style="color:{dec_color};font-weight:600;font-size:0.65rem;text-transform:uppercase;min-width:60px;">{decision}</span>'
                        f'<span style="color:#7c3aed;font-size:0.65rem;min-width:70px;">{rem_type if rem_type != "none" else "—"}</span>'
                        f'</div>', unsafe_allow_html=True)

        st.markdown("---")

        # deliverable spec
        st.markdown("### Deliverable Spec")
        deliverable = st.selectbox("Output format", [
            "Broadcast ProRes 422HQ (1920x1080)",
            "Web H.264 (1920x1080, AAC audio)",
            "Social H.264 (1080x1920 vertical, AAC audio)",
        ], label_visibility="collapsed")

        st.markdown("---")

        # commit & export
        col_commit, col_manifest, col_otio, col_audit = st.columns(4)

        with col_commit:
            if st.button("Commit & Export", type="primary", use_container_width=True):
                export_manifest = {
                    "report_id": f"cleared_{int(time.time())}",
                    "generated_at": datetime.now().isoformat(),
                    "video_id": st.session_state.video_id,
                    "video_label": st.session_state.get("video_label", ""),
                    "ruleset": st.session_state.get("ruleset"),
                    "platforms": st.session_state.get("platforms"),
                    "jurisdictions": st.session_state.get("jurisdictions"),
                    "risk_score": score,
                    "deliverable_spec": deliverable,
                    "findings": [
                        {
                            "text": finding_text(f),
                            "severity": finding_severity(f),
                            "confidence": finding_confidence(f),
                            "decision": st.session_state.get(f"decision_{i}", "pending"),
                            "remediation": remediations.get(i, {}),
                            "annotation": st.session_state.get(f"annotation_{i}", ""),
                        }
                        for i, f in enumerate(findings)
                    ],
                }
                st.session_state.export_manifest = export_manifest
                st.success("Export committed. Download your deliverables below.")

        if st.session_state.get("export_manifest"):
            manifest = st.session_state.export_manifest
            with col_manifest:
                st.download_button("Manifest JSON", json.dumps(manifest, indent=2),
                                   "cleared_export.json", "application/json", use_container_width=True)
            with col_otio:
                otio_markers = []
                for i, finding in enumerate(findings):
                    ts = parse_timestamp_seconds(finding)
                    sev = finding_severity(finding)
                    ft = finding_text(finding)
                    otio_markers.append({
                        "OTIO_SCHEMA": "Marker.1",
                        "metadata": {"cleared_compliance": {"finding": ft, "severity": sev}},
                        "name": f"COMPLIANCE: {sev}",
                        "color": "RED" if sev == "CRITICAL" else "PINK" if sev == "MAJOR" else "YELLOW",
                        "marked_range": {
                            "OTIO_SCHEMA": "TimeRange.1",
                            "start_time": {"OTIO_SCHEMA": "RationalTime.1", "rate": 24, "value": ts * 24},
                            "duration": {"OTIO_SCHEMA": "RationalTime.1", "rate": 24, "value": 48}
                        },
                        "comment": ft
                    })
                otio_export = {"OTIO_SCHEMA": "Timeline.1", "metadata": {"cleared_version": "1.0"},
                               "name": f"Cleared — {st.session_state.video_id[:12]}", "markers": otio_markers}
                st.download_button("OTIO Markers", json.dumps(otio_export, indent=2),
                                   "cleared_markers.otio", "application/json", use_container_width=True)
            with col_audit:
                logs = load_feedback_log()
                if logs:
                    st.download_button("Audit Trail", pd.DataFrame(logs).to_csv(index=False),
                                       "cleared_audit_trail.csv", "text/csv", use_container_width=True)

        st.caption("OTIO markers import into Premiere Pro, Avid, and DaVinci Resolve via OpenTimelineIO")

# ── TAB 4: GROUND TRUTH ──────────────────────────────────
with tab_gt:
    st.markdown("### Ground Truth & Accuracy")
    st.caption("Compare system findings against human-verified ground truth")

    gt_data = load_ground_truth()
    video_key = st.session_state.get("video_id", "unknown")
    current_ruleset = st.session_state.get("ruleset", "Broadcast Standards")

    gt_key = f"{video_key}__{current_ruleset}"
    existing_gt = gt_data.get(gt_key, {}).get("violations", [])

    # pre-populate with system findings if no ground truth exists yet
    if not existing_gt and "findings" in st.session_state:
        pre_populated = "\n".join(finding_text(f) for f in st.session_state.findings)
    else:
        pre_populated = "\n".join(existing_gt)

    st.markdown("#### Human-Verified Violations")
    st.caption("Pre-populated with system findings. Edit to match what a human reviewer would flag — add missed items, remove false positives.")

    gt_input = st.text_area(
        f"Ground truth for: {current_ruleset}",
        value=pre_populated,
        height=200,
        placeholder="e.g.\n[00:37] Man drinking from bottle — alcohol consumption\n[00:49] Woman using inhaler-like device — possible drug reference"
    )

    col_save, col_clear = st.columns([2, 1])
    if col_save.button("Save Ground Truth"):
        if gt_key not in gt_data:
            gt_data[gt_key] = {}
        gt_data[gt_key]["violations"] = [l.strip() for l in gt_input.split("\n") if l.strip()]
        gt_data[gt_key]["video_id"] = video_key
        gt_data[gt_key]["ruleset"] = current_ruleset
        gt_data[gt_key]["saved_at"] = datetime.now().isoformat()
        save_ground_truth(gt_data)
        st.success(f"Saved {len(gt_data[gt_key]['violations'])} ground truth violations")

    if col_clear.button("Clear"):
        if gt_key in gt_data:
            del gt_data[gt_key]
            save_ground_truth(gt_data)
            st.rerun()

    st.markdown("---")

    # computed metrics
    system_findings = st.session_state.get("findings", [])
    gt_violations = gt_data.get(gt_key, {}).get("violations", [])

    if not system_findings:
        st.info("Run a compliance check first to generate system findings.")
    elif not gt_violations:
        st.info("Save ground truth violations above to compute metrics.")
    else:
        metrics = compute_metrics(gt_violations, system_findings)

        st.markdown("#### Accuracy Metrics")
        m1, m2, m3, m4, m5, m6 = st.columns(6)

        def _metric_card(col, value, label, color):
            col.markdown(f'<div class="metric-card"><div class="metric-number" style="color:{color}">{value}</div>'
                         f'<div class="metric-label">{label}</div></div>', unsafe_allow_html=True)

        _metric_card(m1, metrics["tp"], "true positives", "#059669")
        _metric_card(m2, metrics["fp"], "false positives", "#dc2626")
        _metric_card(m3, metrics["fn"], "false negatives", "#d97706")
        _metric_card(m4, f"{metrics['precision']:.0%}", "precision", "#7c3aed")
        _metric_card(m5, f"{metrics['recall']:.0%}", "recall", "#2563eb")
        _metric_card(m6, f"{metrics['f1']:.0%}", "f1 score", "#be185d")

        st.markdown("---")
        st.markdown("#### Manual Review Baseline")
        col_manual, col_auto = st.columns(2)
        manual_time = col_manual.number_input("Manual review time (minutes)", min_value=1, value=45)
        auto_time = col_auto.number_input("System analysis time (seconds)", min_value=1,
                                           value=int(st.session_state.get("analysis_duration", 25)))
        speedup = round((manual_time * 60) / auto_time, 1)
        st.markdown(f'<div style="background:var(--bg-secondary);border:1px solid var(--border-light);border-radius:8px;'
                    f'padding:1rem;margin-top:0.5rem;">'
                    f'<p style="color:var(--text-secondary);font-size:0.85rem;">'
                    f'Manual: <b style="color:#ea580c">{manual_time} min</b> · '
                    f'System: <b style="color:#059669">{auto_time}s</b> · '
                    f'Speedup: <b style="color:#be185d">{speedup}x</b></p>'
                    f'<p style="color:var(--text-muted);font-size:0.75rem;margin-top:0.25rem;">'
                    f'At $150/hr: ${round(manual_time/60*150, 2)} saved per video</p></div>',
                    unsafe_allow_html=True)

# ── DEBUG PANEL ──────────────────────────────────────────────
with st.expander("System Log", expanded=False):
    logs_list = _ui_handler.records
    if not logs_list:
        st.caption("No log entries yet. Run a compliance check to see activity.")
    else:
        errors = [r for r in logs_list if r["level"] in ("ERROR", "WARNING")]
        if errors:
            st.markdown(f'<p style="color:var(--risk-critical-accent);font-size:0.72rem;font-weight:600;">'
                        f'{len(errors)} error(s) / warning(s)</p>', unsafe_allow_html=True)
        for r in reversed(logs_list[-50:]):
            color = "#dc2626" if r["level"] == "ERROR" else "#d97706" if r["level"] == "WARNING" else "var(--text-muted)"
            st.markdown(
                f'<p style="font-family:JetBrains Mono,monospace;font-size:0.68rem;color:{color};'
                f'line-height:1.5;margin:0;padding:1px 0;">'
                f'<span style="color:var(--text-muted)">{r["time"]}</span> '
                f'<span style="font-weight:600">[{r["level"]}]</span> {html_mod.escape(r["msg"][:200])}</p>',
                unsafe_allow_html=True
            )