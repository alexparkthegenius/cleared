# Cleared — Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              USER BROWSER                                       │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                     NEXT.JS FRONTEND (Vercel)                             │  │
│  │                                                                           │  │
│  │  ┌─────────────┐  ┌──────────────────────┐  ┌────────────────────────┐   │  │
│  │  │   SIDEBAR    │  │    VIDEO PLAYER       │  │   VIOLATIONS PANEL    │   │  │
│  │  │             │  │                        │  │                       │   │  │
│  │  │ • Upload    │  │  HTML5 <video>         │  │  Timecoded findings   │   │  │
│  │  │ • TwelveLabs│  │  Scrubber markers      │  │  Color-coded severity │   │  │
│  │  │ • Iconik    │  │  seekTo() on click     │  │  Click → seekTo()    │   │  │
│  │  │             │  │                        │  │                       │   │  │
│  │  │ Platforms   │  └──────────────────────┘  └────────────────────────┘   │  │
│  │  │ Jurisdict.  │                                                          │  │
│  │  │ Custom Rules│  ┌──────────────────────────────────────────────────┐   │  │
│  │  │             │  │                    TABS                          │   │  │
│  │  │ [Run Check] │  │                                                  │   │  │
│  │  └─────────────┘  │  Compliance   Rights    Approve    Ground        │   │  │
│  │                    │  Findings    Tracker   & Send     Truth          │   │  │
│  │                    │                                                  │   │  │
│  │                    │  ┌────────────────────────────────────────────┐  │   │  │
│  │                    │  │  FINDING CARD                              │  │   │  │
│  │                    │  │  [MAJOR] 0:49  Brand/trademark     70%     │  │   │  │
│  │                    │  │  Description of violation...               │  │   │  │
│  │                    │  │  [Approve] [Reject] [Escalate]            │  │   │  │
│  │                    │  │  [Blur] [Bleep] [AI Fix]                  │  │   │  │
│  │                    │  │                                            │  │   │  │
│  │                    │  │  ┌─ LTX REMEDIATION ────────────────────┐ │  │   │  │
│  │                    │  │  │ [Video][Audio][Captions][Titles]     │ │  │   │  │
│  │                    │  │  │ ┌─────────┐  ┌─────────┐            │ │  │   │  │
│  │                    │  │  │ │Option 1 │  │Option 2 │            │ │  │   │  │
│  │                    │  │  │ │  ▶ MP4  │  │  ▶ MP4  │            │ │  │   │  │
│  │                    │  │  │ │[PREVIEW] │  │[PREVIEW] │            │ │  │   │  │
│  │                    │  │  │ │[APPROVE] │  │[APPROVE] │            │ │  │   │  │
│  │                    │  │  │ └─────────┘  └─────────┘            │ │  │   │  │
│  │                    │  │  └──────────────────────────────────────┘ │  │   │  │
│  │                    │  └────────────────────────────────────────────┘  │   │  │
│  │                    └──────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┬────────────────────────┘
                                                         │
                                                    HTTPS API
                                                         │
┌────────────────────────────────────────────────────────┴────────────────────────┐
│                        FASTAPI BACKEND (Railway)                                │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                           API ENDPOINTS                                  │   │
│  │                                                                          │   │
│  │  POST /api/upload ─────── Upload video → S3                              │   │
│  │  POST /api/analyze ────── Build prompt → Pegasus → Parse findings        │   │
│  │  POST /api/regen ─────── LTX retake → S3 → Presigned URLs               │   │
│  │  POST /api/regen/t2v ─── LTX text-to-video → S3                         │   │
│  │  GET  /api/health ─────── Status + Bedrock availability                  │   │
│  │  GET  /api/rights ─────── Rights tracker entries                         │   │
│  │  POST /api/rights ─────── Add rights entry                               │   │
│  │  POST /api/export ─────── Generate export manifest                       │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  config.py    │  │  helpers.py   │  │  bedrock.py   │  │  main.py         │   │
│  │              │  │              │  │              │  │                  │   │
│  │ RULESETS     │  │ parse_findings│  │ run_pegasus  │  │ CORS, logging,  │   │
│  │ PLATFORMS    │  │ build_prompt │  │ search_maren.│  │ middleware,     │   │
│  │ JURISDICTIONS│  │ severity_score│  │ upload_to_s3 │  │ error handling  │   │
│  │ AUDIO_FLAGS  │  │ parse_rights │  │ presigned_url│  │                  │   │
│  └──────────────┘  └──────────────┘  └──────┬───────┘  └──────────────────┘   │
│                                              │                                  │
└──────────────────────────────────────────────┼──────────────────────────────────┘
                                               │
                          ┌────────────────────┼────────────────────┐
                          │                    │                    │
                          ▼                    ▼                    ▼
              ┌───────────────────┐ ┌──────────────────┐ ┌──────────────────┐
              │   AWS BEDROCK     │ │     AWS S3        │ │   LTX-2.3 API    │
              │                   │ │                    │ │                  │
              │ ┌───────────────┐ │ │ cleared-compliance │ │ POST /v1/retake  │
              │ │   PEGASUS     │ │ │ -videos/           │ │ POST /v1/t2v     │
              │ │               │ │ │                    │ │                  │
              │ │ Video analysis│ │ │ uploads/           │ │ Input:           │
              │ │ 6-section     │ │ │   *.mp4            │ │  video_uri       │
              │ │ compliance    │ │ │                    │ │  prompt           │
              │ │ report        │ │ │ regen/             │ │  start_time      │
              │ │               │ │ │   *_opt1.mp4       │ │  duration         │
              │ └───────────────┘ │ │   *_opt2.mp4       │ │  mode             │
              │                   │ │                    │ │                  │
              │ ┌───────────────┐ │ └──────────────────┘ │ Output:          │
              │ │   MARENGO     │ │                       │  MP4 binary      │
              │ │               │ │                       │  (uploaded → S3) │
              │ │ Semantic      │ │                       │                  │
              │ │ video search  │ │                       └──────────────────┘
              │ │ & retrieval   │ │
              │ └───────────────┘ │
              └───────────────────┘


═══════════════════════════════════════════════════════════════════════════════════

                              DATA FLOW

═══════════════════════════════════════════════════════════════════════════════════


  1. UPLOAD
  ─────────
  User drops video
       │
       ▼
  Frontend ──POST /api/upload──▶ Backend ──put_object──▶ S3
       │                              │
       │◀─── { s3_uri } ─────────────┘
       │
  Video plays locally (blob URL)


  2. ANALYZE
  ──────────
  User selects platforms + jurisdictions → clicks "Run Compliance Check"
       │
       ▼
  Frontend ──POST /api/analyze──▶ Backend
                                     │
                                     ├── build_prompt(ruleset, platforms, jurisdictions, audio_flags)
                                     │
                                     ├── invoke_model(Pegasus) ──▶ AWS Bedrock
                                     │        │
                                     │        │◀── 6-section compliance report (text)
                                     │
                                     ├── parse_findings(report) → compliance findings[]
                                     ├── parse_rights_from_report(report) → rights entries[]
                                     ├── severity_score(report) → risk score /100
                                     │
                                     │◀── { findings, rights_entries, risk_score, report }
       │
       ▼
  Findings populate:
    • Violations panel (right of player)
    • Compliance Findings tab (cards with actions)
    • Scrubber markers on video timeline
    • Rights Tracker tab (auto-detected entries)


  3. REMEDIATE (LTX)
  ──────────────────
  User clicks "AI Fix" → picks type (Video/Audio/Captions/...)
       │
       ▼
  Frontend ──POST /api/regen──▶ Backend
                                    │
                                    ├── get_s3_presigned_url(s3_uri) → https URL
                                    │
                                    ├── POST api.ltx.video/v1/retake ──▶ LTX-2.3
                                    │        │
                                    │        │◀── MP4 bytes (replacement clip)
                                    │
                                    ├── upload_to_s3(mp4, regen/{id}.mp4) ──▶ S3
                                    ├── get_s3_presigned_url → preview URL
                                    │
                                    │   (repeat for option 2 with "alternative angle")
                                    │
                                    │◀── { options: [{ video_url, prompt }, ...] }
       │
       ▼
  User previews options → clicks "Approve" on preferred clip
  Approved clips queued for final export


  4. EXPORT
  ─────────
  User reviews all approved changes in "Approve & Send" tab
       │
       ├── Selects deliverable spec (ProRes / H.264)
       ├── Selects export format (OTIO / Iconik / direct)
       ├── Clicks "Go"
       │
       ▼
  Export manifest generated with all findings, decisions, remediations
  Final output rendered with approved replacements composited


═══════════════════════════════════════════════════════════════════════════════════

                           PEGASUS PROMPT STRUCTURE

═══════════════════════════════════════════════════════════════════════════════════

  ┌─────────────────────────────────────────────────────────┐
  │  SECTION 1 — CONTENT FLAGS                              │
  │  Scan for: alcohol, drugs, violence, nudity, minors,    │
  │  hate speech, tobacco, weapons, self-harm, gambling...   │
  │  Format: [MM:SS] Description — Rule — Severity          │
  ├─────────────────────────────────────────────────────────┤
  │  SECTION 2 — AUDIO FLAGS                                │
  │  Scan for: profanity, unlicensed music, SFX,            │
  │  Wilhelm scream, brand jingles, singing...               │
  ├─────────────────────────────────────────────────────────┤
  │  SECTION 3 — RIGHTS & CLEARANCES                        │
  │  Scan for: brand logos, talent faces, artworks,          │
  │  archive footage, on-screen text...                      │
  ├─────────────────────────────────────────────────────────┤
  │  SECTION 4 — PLATFORM SUITABILITY                       │
  │  Check each selected platform's content policies         │
  │  YouTube / TikTok / Instagram / Broadcast / Roblox...    │
  ├─────────────────────────────────────────────────────────┤
  │  SECTION 5 — REGULATORY REVIEW                          │
  │  Check jurisdiction-specific rules                       │
  │  OFCOM / FCC / GDPR / ARPP / CRTC                       │
  ├─────────────────────────────────────────────────────────┤
  │  SECTION 6 — OVERALL ASSESSMENT                         │
  │  APPROVED / NEEDS REVIEW / REJECTED                      │
  │  Risk level + summary                                    │
  └─────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════════

                           FINDING STATE MODEL

═══════════════════════════════════════════════════════════════════════════════════

  Finding {
    id:              "f0"
    timecode:        49                    // seconds
    text:            "Woman smoking..."
    severity:        "MAJOR"               // CRITICAL | MAJOR | MINOR
    confidence:      70                    // 0-100
    rule:            "Content flag"
    source:          "compliance"          // compliance | rights
    decision:        "pending"             // pending | approved | rejected | escalated
    remediation:     "none"                // none | blur | bleep | ai_fix
    regen_options?: [                      // populated after LTX call
      { id, video_url, prompt, duration }
    ]
    selected_regen?: "f0_opt1"             // user's chosen replacement
  }
```
