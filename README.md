# NVision — AI Vision Platform

Real-time camera monitoring: RTSP ingestion → motion gate → VLM analysis (Gemini) → alerts.

```
RTSP camera ──> worker (OpenCV: downscale ≤640px, 2-5fps, MOG2 motion gate)
                    │ qualifying frame (JPEG)
                    ▼
                backend /api/internal/ingest ── cooldown check ──> Gemini VLM
                    │                                                 │ match
                    ▼                                                 ▼
                Mongo (events, credits)                    alert channels (Slack/webhook/SMS/…)
```

**Cost model:** the VLM is never called continuously. The worker only forwards frames after sustained motion, and the backend enforces a per-detection cooldown (default 120s) after each fire.

## Deploy on a server (EC2) in 3 commands

On a fresh Ubuntu instance with Docker installed (`sudo apt-get install -y docker.io docker-compose-v2 git`):

```bash
git clone https://github.com/Stratfiy/nvision.git && cd nvision
git checkout claude/nvision-rtsp-realtime-ld6qtc
bash scripts/setup-env.sh              # generates secrets + detects public IP (Elastic IP if attached)
docker compose up -d --build
```

`scripts/setup-env.sh` writes `.env` for you — it generates `NVISION_MASTER_KEY` and `WORKER_TOKEN`, auto-detects the instance's public IP for `REACT_APP_BACKEND_URL`, and **leaves `GEMINI_API_KEY` blank on purpose**. Pass an IP explicitly if you don't want auto-detection: `bash scripts/setup-env.sh <YOUR_ELASTIC_IP>`.

Then:
1. Open the security group for inbound **TCP 3000 and 8000**.
2. Browse to `http://<PUBLIC_IP>:3000`, sign up.
3. Add your Gemini key in the UI: **Settings → BYO Provider Keys → Google Gemini** (encrypted at rest; no key ever touches the shell or git).

Secrets never go in git — `.env` is generated on the box and `.gitignore`d.

## Run locally in 5 minutes

1. **Configure env**
   ```bash
   cp .env.example .env
   ```
   Fill in `.env`:
   - `GEMINI_API_KEY` — from https://aistudio.google.com/apikey
   - `NVISION_MASTER_KEY` — generate with:
     ```bash
     python backend/scripts/generate_master_key.py
     ```
     (needs `pip install cryptography`; a docker one-liner alternative is in `.env.example`)

2. **Start everything**
   ```bash
   docker compose up --build
   ```
   Services: Mongo, backend (http://localhost:8000), ingestion worker, frontend (http://localhost:3000).

3. **Open http://localhost:3000** → sign up (free credits are granted automatically).

4. **Add a camera** with a live RTSP URL. No camera handy? Use the **built-in test stream** (see below) — no external service or credentials needed.

### Built-in test stream (no external dependencies)

Public test streams expire and come and go. To exercise the full pipeline reliably, the compose file ships an optional RTSP test-stream service (MediaMTX + ffmpeg) that generates a moving pattern inside the Docker network. Start the stack with the `test` profile:

```bash
docker compose --profile test up -d --build
```

Then add a camera with this RTSP URL (reachable from the worker over the Docker network):

```
rtsp://teststream:8554/people
```

Within ~seconds the camera goes ONLINE, Live View shows the moving pattern, and — with a detection created and a Gemini key set — events flow. The pattern is synthetic (not people), so use a detection prompt like *"Is a colorful moving pattern visible?"* to see a match, or point the camera at a real stream for person detection.

5. **Create a detection** from the "Trespasser/Person" template on that camera (set cooldown, e.g. 60s), and add an alert channel (Slack incoming webhook, or a generic webhook pointed at https://webhook.site for testing).

6. **Watch it fire** (within ~60s of a person walking through the frame):
   - `docker compose logs -f worker` → `connected` → `motion` → `ingest` lines
   - `docker compose logs -f backend` → `ingest` → `vlm eval` → `cooldown skip` lines
   - Events page shows the event with caption + confidence; your webhook/Slack receives the alert with a snapshot; Billing shows credits deducted.

7. **Offline detection:** edit the camera's RTSP URL to a bad host — within ~2 minutes the camera shows `OFFLINE` and an offline alert is dispatched.

### Verifying cost controls

```bash
# VLM calls should be rare compared to frames processed:
docker compose logs backend | grep -c "vlm eval"
docker compose logs backend | grep "cooldown skip"
docker compose logs worker | grep -c "ingest"
```

### Security notes

- BYO provider keys (Twilio/Plivo/Exotel/…) are encrypted at rest with Fernet (`NVISION_MASTER_KEY`); they are decrypted only at alert dispatch time. Inspect Mongo to confirm: `docker compose exec mongo mongosh nvision --eval 'db.users.findOne({},{byo_keys:1})'` — values are ciphertext.
- RTSP URLs with embedded credentials are masked (`rtsp://user:•••@host/...`) in all API responses and logs. Only the internal worker endpoint receives raw URLs, authenticated by `WORKER_TOKEN`.

## Services

| Service  | Path        | Notes |
|----------|-------------|-------|
| backend  | `backend/`  | FastAPI + Mongo. VLM via Google Gemini (`google-genai`), memory Q&A via Anthropic. |
| worker   | `worker/`   | RTSP ingestion + motion gate (OpenCV/FFmpeg, TCP transport). Polls `/api/internal/cameras/active`. |
| frontend | `frontend/` | React (CRA + craco), talks to the backend at `REACT_APP_BACKEND_URL`. |

## Engineering rules

See [CLAUDE.md](CLAUDE.md).
