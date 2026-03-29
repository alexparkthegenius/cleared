# Cleared

**AI-powered video compliance checking for broadcast, streaming, and social platforms.**

---

## What It Does

- **Upload video, select platforms + jurisdictions, get instant compliance analysis.** Drop in any video file, pick your target platforms (YouTube, TikTok, broadcast, etc.) and regulatory jurisdictions, and Cleared scans the entire asset in seconds.
- **Pegasus (via AWS Bedrock) analyzes video content, audio, rights, and regulatory compliance.** TwelveLabs' Pegasus foundation model performs multimodal analysis across visual, audio, and textual dimensions against configurable rulesets.
- **Timecoded violations with severity, confidence, and one-click remediation via LTX-2.3.** Every finding is pinned to a timecode, color-coded by severity (Critical / Major / Minor), and can be fixed inline with AI-generated replacement video or audio.
- **Export cleared content as ProRes, H.264, OTIO, or deliver directly to platforms.** Once all violations are resolved, export in broadcast-grade formats or push directly to Iconik and other delivery targets.

---

## Architecture

```
Next.js Frontend (Vercel)  -->  FastAPI Backend (Railway)  -->  AWS Bedrock (Pegasus / Marengo)
                                       |                              |
                                       +---> LTX-2.3 (Remediation)   +---> S3 (Video Storage)
```

---

## Tech Stack

| Layer          | Technology                                         |
| -------------- | -------------------------------------------------- |
| Frontend       | Next.js 16, React 19, TypeScript, Tailwind CSS 4   |
| Backend        | FastAPI, Python 3.12, Pydantic                     |
| AI Models      | TwelveLabs Pegasus (via Bedrock), TwelveLabs Marengo, LTX-2.3 |
| Infrastructure | Vercel, Railway, AWS S3, AWS Bedrock                |
| Font           | JetBrains Mono                                     |

---

## Features

### Compliance Analysis
- **Content flags** -- alcohol, drugs, violence, nudity, minors, tobacco, dangerous stunts
- **Audio flags** -- profanity, unlicensed music, brand jingles, Wilhelm scream, hate speech, unauthorized celebrity voice
- **Rights & clearances** -- talent releases, artwork licenses, music sync rights, brand trademark usage
- **Platform suitability** -- per-platform policy checks for each target distribution channel
- **Regulatory review** -- jurisdiction-specific scanning against OFCOM, FCC, GDPR, ARPP, CRTC rules

### Violations Panel
- Timecoded findings linked to the video player (click to seek)
- Color-coded by severity: Critical (red), Major (amber), Minor (blue)
- Per-finding confidence scores and rule attribution
- Approve, reject, or escalate each finding individually

### Rights Tracker
- Auto-detected rights entries extracted from the compliance report
- Manual entry support for music, footage, images, talent, brands
- Expiry date tracking with territory scope
- Filterable by type, status, and clearance state

### LTX Remediation
- AI-powered video and audio replacement for flagged segments
- 6 regeneration types: blur, bleep, AI fix, and text-to-video generation
- Side-by-side preview of original vs. remediated content
- Approve-and-replace workflow before final export

### Export
- ProRes, H.264, OTIO timeline formats
- Direct delivery to Iconik or local download
- Only exports after all critical findings are resolved

### Ground Truth
- Auto-generate annotation data from analysis results
- Structured output for training and QA pipelines

---

## Supported Platforms

| Platform                | Notes                                      |
| ----------------------- | ------------------------------------------ |
| YouTube                 | Community guidelines, age restriction       |
| TikTok                  | No alcohol consumption, no graphic violence |
| Instagram               | Content policies, sponsored content rules   |
| Broadcast pre-watershed | Pre-9pm content restrictions                |
| Streaming (Netflix/HBO) | Rating-appropriate content checks           |
| Roblox                  | Child safety, no mature content             |
| The Sphere              | Immersive format compliance                 |

---

## Supported Jurisdictions

| Jurisdiction    | Regulatory Body | Key Rules                                                  |
| --------------- | --------------- | ---------------------------------------------------------- |
| OFCOM (UK)      | OFCOM           | Watershed violations, product placement, harmful content   |
| FCC (US)        | FCC             | Indecency, COPPA, sponsorship identification               |
| GDPR (EU)       | EU Commission   | Biometric data, facial recognition, children's data        |
| ARPP (France)   | ARPP            | Loi Evin (alcohol), food advertising to children           |
| CRTC (Canada)   | CRTC            | Canadian content rules, bilingual obligations              |
| Multi-region    | All of the above | Flags anything that would fail in any jurisdiction        |

---

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+
- AWS account with Bedrock access
- LTX API key

### Local Development

```bash
# Backend
cd api
pip install -r requirements.txt
cp .env.example .env  # fill in credentials
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

The frontend runs on `http://localhost:3000` and the API on `http://localhost:8000`.

---

## Environment Variables

| Variable                 | Required | Description                              |
| ------------------------ | -------- | ---------------------------------------- |
| `AWS_ACCESS_KEY_ID`      | Yes      | AWS IAM access key                       |
| `AWS_SECRET_ACCESS_KEY`  | Yes      | AWS IAM secret key                       |
| `AWS_SESSION_TOKEN`      | No       | Temporary session token (if using STS)   |
| `AWS_DEFAULT_REGION`     | Yes      | AWS region (e.g., `us-east-1`)           |
| `AWS_ACCOUNT_ID`         | Yes      | AWS account ID for Bedrock model access  |
| `CLEARED_S3_BUCKET`      | Yes      | S3 bucket name for video storage         |
| `LTX_API_KEY`            | Yes      | API key for LTX-2.3 remediation service  |
| `NEXT_PUBLIC_API_URL`    | Yes      | Backend URL exposed to the frontend      |

---

## API Endpoints

| Method | Path                       | Description                                   |
| ------ | -------------------------- | --------------------------------------------- |
| GET    | `/api/health`              | Health check and Bedrock connectivity status   |
| POST   | `/api/upload`              | Upload video file to S3                        |
| POST   | `/api/analyze`             | Run Pegasus compliance analysis on a video     |
| POST   | `/api/regen`               | Generate remediation options via LTX-2.3       |
| POST   | `/api/regen/text-to-video` | Text-to-video generation for segment replacement |
| GET    | `/api/rights`              | List all rights entries for the current session |
| POST   | `/api/rights`              | Add a manual rights entry                      |
| POST   | `/api/export`              | Export cleared video in specified format        |
| GET    | `/api/rulesets`            | List available compliance rulesets              |
| GET    | `/api/platforms`           | List supported platforms                       |
| GET    | `/api/jurisdictions`       | List supported jurisdictions                   |
| GET    | `/api/audio-flags`         | List audio flag categories                     |

---

## Compliance Checks

**Video**
- Art on screen, talent appearances, brand logos, competitor trademarks
- Nudity, violence, dangerous stunts without disclaimers

**Audio**
- Unlicensed music, sound effects requiring clearance
- Profanity, hate speech, brand jingles, Wilhelm scream, unauthorized celebrity voice

**Content**
- Alcohol branding, drug use, tobacco, violence, content involving minors, abuse

**Geographic**
- OFCOM watershed rules, FCC indecency standards, GDPR biometric data, ARPP alcohol advertising (Loi Evin), CRTC bilingual requirements

**Platform**
- Each platform's specific content policies checked independently
- Age restriction and rating requirements

**Rights**
- License duration and expiry tracking
- Talent release and clearance status
- Territory-scoped rights management

---

## Team

Built at Hackathon 2026.

---

## License

MIT
