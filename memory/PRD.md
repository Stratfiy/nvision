# NVision — PRD & Build Log

## Original problem statement
Build an AI vision platform that turns any RTSP/IP camera into an intelligent agent — plain-English detection prompts, real-time alerts on WhatsApp/Slack/webhook/call, and a searchable text memory of every event.

User expanded into "Vapi of vision" — developer-friendly, self-serve, BYO keys, India-first (Razorpay + DLT-aware SMS + WhatsApp-first), memory-as-product.

## Architecture
- **Frontend**: React 19 + Tailwind + Shadcn UI + Recharts + Lucide + Sonner. Fonts: Cabinet Grotesk / IBM Plex Sans / JetBrains Mono. Dark terminal aesthetic (#050505 / #ccff00).
- **Backend**: FastAPI + Motor (MongoDB) + JWT + bcrypt + httpx + razorpay + twilio.
- **AI**: Gemini 3 Flash (vision, zone-aware prompts) · Claude Sonnet 4.6 (memory Q&A).
- **Payments**: Razorpay Checkout (INR, test mode) + signature verify + webhook.
- **Alerts**: Slack (live) · Webhook (live, HMAC) · Twilio/Plivo/Exotel/Vonage/MessageBird (BYO — real dispatch) · Email/Teams (simulated).

## Implemented (v0.2) — 21 Jul 2026

### v0.1 (baseline)
- JWT auth + 500-credit signup bonus + credit ledger.
- Cameras (CRUD, snapshot URL, demo picks).
- Detections (prompt + sample images + 10 templates + sensitivity + schedule).
- Vision `/api/analyze` via Gemini 3 Flash.
- Events feed + feedback loop + acknowledge.
- Memory search (keyword + Claude synthesis).
- Alert channels + delivery log.
- API keys.
- Analytics.
- Landing/login/signup.

### v0.2 additions
- **Razorpay Checkout**: `/api/credits/topup` creates order, opens Razorpay modal on frontend, `/api/credits/verify` HMAC-checks signature and grants credits, `/api/credits/razorpay/webhook` for reliability. INR packs: Starter ₹499 / Growth ₹1999 / Scale ₹7999.
- **Zone Editor**: Camera has `zones: [{name, points: [[x,y],...]}]` (normalized 0-1). Frontend canvas polygon draw over camera snapshot. Detection prompt is zone-aware — model only reports match if target is inside a zone.
- **BYO Telephony**: Real dispatch via user-configured Twilio (WhatsApp+SMS+Voice), Plivo (SMS+WhatsApp), Exotel (SMS+Voice, India), Vonage (SMS), MessageBird (SMS). Settings page has multi-field entry per provider. Alerts modal has provider selector for WhatsApp/SMS/Voice channel kinds. Delivery log records all attempts.

## Backlog
### P0
- WhatsApp Business Cloud API (direct Meta, no Twilio) for Indian merchants.
- Escalation chains (ordered channel steps with ack windows + DTMF).
- Real RTSP → snapshot ingestion worker (ffmpeg).
- Slack interactive buttons (Ack / False alarm) via Slack OAuth app.
- Motion-gate + object-detect stage before VLM (cost control).

### P1
- Semantic memory search (embeddings) — currently keyword-only.
- GST-compliant Razorpay invoices + auto-email.
- Camera health / offline detection + auto-reconnect.
- Edge agent (on-prem gateway) for low-bandwidth sites.

### P2
- Thermal camera pilot.
- Audit log + SLA tooling.
- Privacy-mask polygon editor (opposite of zones).

## Known limitations / MOCKED
- Email / Teams dispatch = simulated (Resend/SendGrid + Teams webhook = Phase 2).
- Razorpay ends at signature verify — GST invoices, Razorpay Payment Links, subscriptions = future.
- No RTSP live streaming yet — analysis via snapshot URL or image upload only.

## Success metrics (from PRD)
Activation <10min · retention 70% D30 · precision >90% · free→paid 8–12% · break-even 110 paying cameras.

## Test credentials
`nvision.tester@example.com` / `Testpass123!` (500 free credits)
