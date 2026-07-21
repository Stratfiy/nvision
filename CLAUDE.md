# NVision — Engineering Rules
- Architecture: FastAPI backend (backend/server.py) + React frontend + NEW ingestion worker (worker/).
- Cost model is sacred: NEVER send frames to the VLM continuously. Motion gate first; VLM only on qualifying events; per-detection cooldown enforced.
- Decode RTSP substream / downscaled frames only (max 640px wide, 2–5 fps for motion detection). Never full-res continuous decode.
- All third-party keys (BYO Twilio/Plivo/Exotel/OpenAI/Gemini) encrypted at rest with Fernet; master key from env NVISION_MASTER_KEY. Never log secrets or RTSP credentials.
- No dependency on emergentintegrations — direct provider APIs only.
- Every change must keep `docker compose up` working end-to-end.
- Work in small increments; after each task, show me how to verify it.

## Implementation notes (keep updated)
- VLM: Google Gemini via `google-genai` (`GEMINI_API_KEY`, model `gemini-flash-latest`). Memory Q&A: Anthropic `anthropic` SDK (`ANTHROPIC_API_KEY`, optional — degrades to a summary stub if unset).
- Internal endpoints (`/api/internal/*`) are worker-only, authed with `X-Worker-Token` == env `WORKER_TOKEN`.
- Cooldown: `detections.cooldown_seconds` (default 120), enforced backend-side in the ingest path via `last_fired_at`.
- Worker env knobs: `BACKEND_URL`, `WORKER_TOKEN`, `MOTION_MIN_AREA_PCT` (default 0.5), `MOTION_SUSTAINED_FRAMES` (default 2), `SAMPLE_FPS` (2–5), `MAX_FRAME_WIDTH` (640), `POLL_INTERVAL_SECONDS`.
- Camera status: worker emits `camera.online`/`camera.offline` heartbeats to `POST /api/internal/cameras/{id}/status` after 3 failed reconnect attempts (offline) / on recovery (online).
