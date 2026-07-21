# NVision — PRD & Build Log

## Original problem statement
> I want to build an AI vision platform for realtime updates. Connect CCTV cameras, add API keys or use platform-hosted models, start with free credits then charge. Use cases from public safety to B2B — thermal cameras, precision manufacturing quality inspection, detect unsafe workers without safety gear via prompt. Not only detect but send data / notifications via webhook / Telegram / Slack / phone call / Teams. Memory layer: AI stores text summaries so users can ask about incidents at specific times without replaying clips.

User expanded the vision into a detailed PRD (see chat), codename **NVision**, positioning: **"Vapi of vision"** — developer-friendly, self-serve, BYO keys, India-first (WhatsApp-first, Razorpay, DLT-aware SMS), memory-as-product.

## Architecture (v0.1 MVP)
- **Frontend**: React 19 + React Router + Tailwind + Shadcn UI + Recharts + Lucide + Sonner (toasts). Fonts: Cabinet Grotesk / IBM Plex Sans / JetBrains Mono. Dark terminal aesthetic (`#050505` / `#ccff00`).
- **Backend**: FastAPI + Motor (MongoDB) + JWT auth + bcrypt + httpx.
- **AI**: Gemini 3 Flash (`gemini-3-flash-preview`) via emergentintegrations for image analysis, Claude Sonnet 4.6 for memory Q&A.
- **Data**: MongoDB collections — users, cameras, detections, events, channels, alert_deliveries, credit_tx, api_keys.

## Implemented (v0.1) — 21 Jul 2026
- JWT email/password auth + 500-credit signup bonus + credit ledger.
- Cameras: CRUD, snapshot URL / RTSP field, demo snapshot quick-picks.
- Detections: prompt + up-to-6 sample images + 10-template library (Trespasser, PPE Helmet, PPE Vest, Smoke/Fire, Vehicle, Zone intrusion, Crowd, Door open, Quality defect, Camera tamper) + sensitivity slider + schedule.
- `/api/analyze` — deducts VLM credits, calls Gemini 3 Flash vision with prompt + reference samples, returns match/confidence/caption/objects, stores event, fans out to enabled channels.
- Events feed with match/no-match filters, thumbs-up/down feedback loop, acknowledge button.
- Memory search — keyword + LLM synthesis over event captions, cited answer via Claude Sonnet.
- Alert channels: Slack (LIVE), Webhook (LIVE, HMAC-signed), WhatsApp / SMS / Voice / Email / Teams (SIMULATED — MOCKED delivery log).
- Delivery log page with status per dispatch.
- Credits/Billing: rate card, 7-day burn, projection, top-up packs (starter/growth/scale) — MOCKED (Stripe/Razorpay checkout is Phase 2, top-up adds credits instantly).
- API keys: create/rotate/revoke, one-time-view secret, SHA-256 hash storage.
- Analytics: totals, precision from feedback, 7-day events line chart, busiest cameras bar chart.
- Settings: BYO OpenAI/Anthropic/Gemini/Twilio/Plivo/Exotel keys (encrypted-at-rest masked).
- Landing page + login/signup.

## User personas
1. **Citizen / small shop** — free tier, WhatsApp alerts, hobby prompts.
2. **SMB (warehouse, retail)** — Business tier, custom prompts, Slack + webhook, API.
3. **Factory / cold storage** — Industrial tier, PPE/smoke packs, escalation chains.
4. **Developer / integrator** — API-first, BYO keys, credit-based.

## Backlog / next phases

### P0 — near-term polish
- Real Stripe + Razorpay checkout for top-ups.
- Emergent Google OAuth login (currently JWT only).
- Zones polygon editor per camera.
- Escalation chains (ordered channel steps + acknowledgment windows).
- Backtest button on detection builder.

### P1 — v0.2 / v1.0
- Real WhatsApp / Twilio / Plivo / Exotel dispatch (currently simulated).
- Voice call TTS reading alert + DTMF ack.
- Slack OAuth app + interactive buttons (Ack / False alarm).
- Semantic memory search (embeddings) — currently keyword-only.
- Real RTSP ingestion via edge worker (ffmpeg → snapshot → analyze).
- Motion gate stage + object-detector stage before VLM.
- Camera health / offline detection.

### P2 — Industrial
- Audit log, SLA tooling, multi-site reports.
- Thermal camera pilot program.
- Edge agent (on-prem gateway).
- Privacy-mask polygon editor.

## Success metrics (from user PRD)
- Activation < 10 min median · retention 70% D30 · precision > 90% · free→paid 8–12% · break-even at 110 paying cameras.

## Known limitations / MOCKED
- WhatsApp / SMS / Voice / Email / Teams dispatch = **SIMULATED** (logged in delivery log, marked `simulated`).
- Stripe / Razorpay top-up = **SIMULATED** (credits granted instantly).
- RTSP live streaming = **not implemented** (analysis only via snapshot URL / image upload / API).
