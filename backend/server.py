"""NVision — AI Vision Platform Backend (MVP v0.1)."""
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header, UploadFile, File, Form, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
import base64
import json
import re
import hmac
import hashlib
import asyncio
import bcrypt
import jwt as pyjwt
import httpx
import razorpay
from twilio.rest import Client as TwilioClient
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']
JWT_SECRET = os.environ.get('JWT_SECRET', 'devsecret')
JWT_ALGO = os.environ.get('JWT_ALGORITHM', 'HS256')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-flash-latest')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
ANTHROPIC_MODEL = os.environ.get('ANTHROPIC_MODEL', 'claude-opus-4-8')
NVISION_MASTER_KEY = os.environ.get('NVISION_MASTER_KEY', '')
WORKER_TOKEN = os.environ.get('WORKER_TOKEN', '')
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', '')

rzp = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)) if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET else None

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="NVision API", version="0.1.0")
api = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("nvision")


# ========================= SECRETS (Fernet) =========================
from cryptography.fernet import Fernet, InvalidToken

_fernet = None
if NVISION_MASTER_KEY:
    try:
        _fernet = Fernet(NVISION_MASTER_KEY.encode())
    except Exception:
        logger.error("NVISION_MASTER_KEY is not a valid Fernet key — run backend/scripts/generate_master_key.py")

def encrypt_secret(value: str) -> str:
    if not _fernet:
        raise HTTPException(500, "NVISION_MASTER_KEY not configured — cannot store secrets")
    return _fernet.encrypt(value.encode()).decode()

def decrypt_secret(value: str) -> str:
    """Decrypt a stored secret. Tolerates legacy plaintext values."""
    if not isinstance(value, str) or not value:
        return value
    if not _fernet:
        return value
    try:
        return _fernet.decrypt(value.encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        return value


# ========================= RTSP MASKING =========================
_RTSP_CRED_RE = re.compile(r'((?:rtsp|rtsps|rtmp|http|https)://)([^/@:\s]+)(?::[^/@\s]+)?@')

def mask_stream_url(url: Optional[str]) -> Optional[str]:
    """rtsp://user:secret@host/... -> rtsp://user:•••@host/... (never expose credentials)."""
    if not url:
        return url
    return _RTSP_CRED_RE.sub(r'\1\2:•••@', url)

def public_camera(cam: Dict[str, Any]) -> Dict[str, Any]:
    """Camera doc safe for API responses/logs: credentials in stream URLs are masked."""
    if not cam:
        return cam
    out = dict(cam)
    out.pop("_id", None)
    if out.get("rtsp_url"):
        out["rtsp_url"] = mask_stream_url(out["rtsp_url"])
    return out


# ========================= HELPERS =========================
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def new_id() -> str:
    return str(uuid.uuid4())

def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def check_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False

def make_token(user_id: str) -> str:
    payload = {"sub": user_id, "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(days=30)}
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

async def current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    if not creds:
        raise HTTPException(401, "Missing token")
    try:
        payload = pyjwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
        uid = payload.get("sub")
    except Exception:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": uid}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(401, "User not found")
    return user


# ========================= MODELS =========================
class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class CameraIn(BaseModel):
    name: str
    rtsp_url: Optional[str] = ""
    snapshot_url: Optional[str] = ""
    site: Optional[str] = "Default"
    tags: List[str] = []
    timezone: Optional[str] = "UTC"
    zones: List[Dict[str, Any]] = []

class CameraPatch(BaseModel):
    name: Optional[str] = None
    rtsp_url: Optional[str] = None
    snapshot_url: Optional[str] = None
    zones: Optional[List[Dict[str, Any]]] = None

class DetectionIn(BaseModel):
    camera_id: str
    name: str
    prompt: str
    sample_images_b64: List[str] = []          # base64 images without prefix
    template: Optional[str] = None
    sensitivity: float = 0.6                    # 0-1
    schedule: Optional[str] = "always"          # always | night | business_hours | custom
    zones: List[Dict[str, Any]] = []
    enabled: bool = True
    cooldown_seconds: int = 120                 # skip VLM re-eval within this window after a fire

class AnalyzeIn(BaseModel):
    detection_id: str
    image_b64: Optional[str] = None
    image_url: Optional[str] = None

class ChannelIn(BaseModel):
    name: str
    kind: str                                    # slack | webhook | email | whatsapp | sms | voice | teams
    config: Dict[str, Any] = {}                  # {url|email|phone|token|...}

class ChannelTestIn(BaseModel):
    channel_id: str
    message: str = "NVision test alert — this is a drill."

class MemoryQueryIn(BaseModel):
    query: str
    camera_id: Optional[str] = None
    limit: int = 10

class FeedbackIn(BaseModel):
    event_id: str
    correct: bool

class TopupIn(BaseModel):
    pack: str                                    # starter | growth | scale
    origin_url: Optional[str] = None

class RzpVerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class ApiKeyIn(BaseModel):
    name: str
    scope: str = "full"                          # read | full


# ========================= TEMPLATES =========================
TEMPLATES = [
    {"id": "trespasser_night", "name": "Trespasser (After Hours)", "icon": "moon",
     "prompt": "Detect if a person is present in the camera view. This camera is in a restricted zone during off-hours (after 10pm to 6am). Report a match only if a human figure is clearly visible.",
     "sensitivity": 0.65, "schedule": "night"},
    {"id": "ppe_helmet", "name": "PPE — Helmet Missing", "icon": "hard-hat",
     "prompt": "Inspect the image for workers/people. Return match=true ONLY if there is a person clearly visible AND they are NOT wearing a hard-hat/safety helmet. Ignore people wearing helmets. Ignore images without people.",
     "sensitivity": 0.7, "schedule": "business_hours"},
    {"id": "ppe_vest", "name": "PPE — Vest Missing", "icon": "shield",
     "prompt": "Return match=true only if you see a person without a high-visibility safety vest in an industrial setting.",
     "sensitivity": 0.7, "schedule": "business_hours"},
    {"id": "smoke_fire", "name": "Smoke / Fire", "icon": "flame",
     "prompt": "Detect any visible smoke plumes or open flames in the scene. Be strict — do not confuse steam, dust, or shadows for smoke.",
     "sensitivity": 0.75, "schedule": "always"},
    {"id": "vehicle_entry", "name": "Vehicle Entry", "icon": "car",
     "prompt": "Detect if a vehicle (car, truck, motorcycle, bicycle) is present in the frame. Report match=true when a vehicle is clearly visible.",
     "sensitivity": 0.55, "schedule": "always"},
    {"id": "zone_intrusion", "name": "Zone Intrusion", "icon": "shield-alert",
     "prompt": "Detect any human, animal, or vehicle entering the marked restricted zone. Report match=true only if the intruder is inside the zone (assume full frame if no zone drawn).",
     "sensitivity": 0.6, "schedule": "always"},
    {"id": "crowd_forming", "name": "Crowd Forming", "icon": "users",
     "prompt": "Count the number of people visible. Report match=true only if 5 or more people are gathered together in the frame.",
     "sensitivity": 0.6, "schedule": "always"},
    {"id": "door_open", "name": "Door Left Open", "icon": "door-open",
     "prompt": "Detect if a door in the scene appears to be open (not closed). Report match=true only if a door is clearly open.",
     "sensitivity": 0.6, "schedule": "always"},
    {"id": "quality_defect", "name": "Quality Defect", "icon": "scan-line",
     "prompt": "Inspect the product/surface in the image for defects (cracks, scratches, discoloration, misalignment, missing parts). Report match=true only if a clear defect is visible. Compare against reference sample images if provided.",
     "sensitivity": 0.7, "schedule": "always"},
    {"id": "camera_tamper", "name": "Camera Tampered", "icon": "eye-off",
     "prompt": "Check if the camera view appears obstructed, blurred, spray-painted, or intentionally covered. Report match=true if the view is severely degraded.",
     "sensitivity": 0.75, "schedule": "always"},
]


# ========================= AI (Vision + Memory Q&A) =========================
_genai_clients: Dict[str, Any] = {}

def _get_genai_client(api_key: str):
    if api_key not in _genai_clients:
        from google import genai
        _genai_clients[api_key] = genai.Client(api_key=api_key)
    return _genai_clients[api_key]


async def _user_byo_key(user_id: str, provider: str, field: str = "api_key") -> Optional[str]:
    """Return a user's decrypted BYO key for a provider, or None. Used to let
    accounts bring their own Gemini/Anthropic key via Settings instead of the
    server-wide env key."""
    user = await db.users.find_one({"id": user_id}, {"byo_keys": 1})
    v = ((user or {}).get("byo_keys", {}) or {}).get(provider)
    if isinstance(v, dict):
        raw = v.get(field, "")
    elif isinstance(v, str):
        raw = v
    else:
        raw = ""
    if not raw:
        return None
    return decrypt_secret(raw) or None


def _guess_image_mime(b64: str) -> str:
    head = b64[:16]
    if head.startswith("iVBOR"):
        return "image/png"
    if head.startswith("R0lGOD"):
        return "image/gif"
    if head.startswith("UklGR"):
        return "image/webp"
    return "image/jpeg"


async def run_vision_detection(prompt: str, image_b64: str, sample_b64s: List[str], sensitivity: float, zones: Optional[List[Dict[str, Any]]] = None, api_key: Optional[str] = None) -> Dict[str, Any]:
    """Analyze image with Gemini Flash vision, return {match, confidence, caption, objects}.
    Uses the caller's BYO key when provided, else the server-wide GEMINI_API_KEY."""
    key = api_key or GEMINI_API_KEY
    if not key:
        return {"match": False, "confidence": 0.0, "caption": "AI unavailable: no Gemini API key (add one in Settings → BYO Provider Keys, or set GEMINI_API_KEY)", "objects": []}

    zones_note = ""
    if zones:
        z_desc = "; ".join(
            f"'{z.get('name','zone')}' polygon (normalized 0-1): {z.get('points', [])}"
            for z in zones if z.get("points")
        )
        if z_desc:
            zones_note = (
                f"\nIMPORTANT — RESTRICTED ZONES: The detection is scoped to these zones only: {z_desc}. "
                "Coordinates are normalized (0,0)=top-left, (1,1)=bottom-right. "
                "ONLY report a match if the target is INSIDE one of these polygons. "
                "Anything outside the zones = no match, regardless of what you see."
            )

    system = (
        "You are NVision, a precise CCTV vision analyzer. "
        "Given a live camera frame, an operator's detection prompt, and optional reference sample images, "
        "you must return STRICT JSON with keys: match (bool), confidence (float 0-1), caption (one sentence), objects (array of short strings). "
        f"Be strict — the user's sensitivity threshold is {sensitivity:.2f}. Only report match=true when the described condition is genuinely present. "
        "Do not include markdown fences or prose outside JSON."
    )
    from google.genai import types as genai_types

    contents: List[Any] = []
    for sb in sample_b64s[:6]:
        if sb.startswith("data:"):
            sb = sb.split(",", 1)[-1]
        contents.append(genai_types.Part.from_bytes(data=base64.b64decode(sb), mime_type=_guess_image_mime(sb)))
    contents.append(genai_types.Part.from_bytes(data=base64.b64decode(image_b64), mime_type=_guess_image_mime(image_b64)))

    user_text = (
        f"Detection prompt: {prompt}{zones_note}\n\n"
        f"{'The first images are REFERENCE samples showing what to look for. The LAST image is the LIVE frame to analyze.' if sample_b64s else 'The image is the LIVE camera frame to analyze.'}\n\n"
        f"Respond with JSON only, e.g. {{\"match\": false, \"confidence\": 0.12, \"caption\": \"Empty corridor at night.\", \"objects\": [\"corridor\", \"door\"]}}"
    )
    contents.append(user_text)

    try:
        resp = await _get_genai_client(key).aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
            ),
        )
        text = (resp.text or "").strip()
        data = _parse_vlm_json(text)
        if data is None:
            return {"match": False, "confidence": 0.0, "caption": "Model returned non-JSON.", "objects": []}
        return {
            "match": bool(data.get("match", False)),
            "confidence": float(data.get("confidence", 0.0)),
            "caption": str(data.get("caption", ""))[:280],
            "objects": [str(o)[:40] for o in data.get("objects", [])][:8],
        }
    except Exception as e:
        logger.exception("vision detection failed")
        return {"match": False, "confidence": 0.0, "caption": f"Detection error: {e}", "objects": []}


def _parse_vlm_json(text: str) -> Optional[Dict[str, Any]]:
    """Parse the VLM's JSON answer robustly.
    JSON response mode returns clean JSON, but tolerate markdown fences and any
    trailing content by decoding the first complete JSON object."""
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


_anthropic_clients: Dict[str, Any] = {}

def _get_anthropic_client(api_key: str):
    if api_key not in _anthropic_clients:
        import anthropic
        _anthropic_clients[api_key] = anthropic.AsyncAnthropic(api_key=api_key)
    return _anthropic_clients[api_key]


async def answer_memory(question: str, events: List[Dict[str, Any]], api_key: Optional[str] = None) -> str:
    """Use Claude to answer a memory question over retrieved event captions.
    Uses the caller's BYO key when provided, else the server-wide ANTHROPIC_API_KEY."""
    if not events:
        return "No events matched your question in memory."

    lines = []
    for e in events[:20]:
        lines.append(f"[{e.get('timestamp','')}] Camera={e.get('camera_name','?')} match={e.get('match')} conf={e.get('confidence',0):.2f} — {e.get('caption','')}")
    context = "\n".join(lines)

    key = api_key or ANTHROPIC_API_KEY
    if not key:
        # Degraded mode: no LLM available — return the matched log directly.
        return "AI memory answers are disabled (add an Anthropic key in Settings, or set ANTHROPIC_API_KEY). Matching events:\n" + context[:1800]

    try:
        resp = await _get_anthropic_client(key).messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=(
                "You are NVision Memory — an assistant that answers questions about camera events. "
                "Answer using ONLY the event log provided. If the log does not answer the question, say so. "
                "Cite timestamps (like 2026-02-15T18:30) inline. Keep the answer under 120 words."
            ),
            messages=[{"role": "user", "content": f"EVENT LOG:\n{context}\n\nQUESTION: {question}"}],
        )
        answer = "".join(b.text for b in resp.content if b.type == "text")
        return answer[:2000] if answer else "No answer generated."
    except Exception as e:
        logger.exception("memory answer failed")
        return f"AI error: {e}"


# ========================= ALERTS =========================
CREDIT_COSTS = {
    "vlm_eval": 3,
    "whatsapp_sim": 0,        # simulator = free
    "voice_min_sim": 0,
    "slack": 0,
    "webhook": 0,
    "email": 0,
}

CREDIT_PACKS = {
    "starter": {"credits": 2000, "amount_inr": 499, "amount_usd": 6},
    "growth": {"credits": 10000, "amount_inr": 1999, "amount_usd": 25},
    "scale":  {"credits": 50000, "amount_inr": 7999, "amount_usd": 99},
}

async def deduct_credits(user_id: str, amount: int, reason: str) -> bool:
    user = await db.users.find_one({"id": user_id})
    bal = int(user.get("credits", 0)) if user else 0
    if bal < amount:
        return False
    await db.users.update_one({"id": user_id}, {"$inc": {"credits": -amount}})
    await db.credit_tx.insert_one({
        "id": new_id(), "user_id": user_id, "delta": -amount, "reason": reason, "ts": now_iso()
    })
    return True

async def add_credits(user_id: str, amount: int, reason: str):
    await db.users.update_one({"id": user_id}, {"$inc": {"credits": amount}})
    await db.credit_tx.insert_one({
        "id": new_id(), "user_id": user_id, "delta": amount, "reason": reason, "ts": now_iso()
    })


async def dispatch_alert(user_id: str, channel: Dict[str, Any], subject: str, body: str, snapshot_url: Optional[str] = None, snapshot_b64: Optional[str] = None) -> Dict[str, Any]:
    """Fires an alert. Slack/Webhook + Twilio/Plivo/Exotel BYO are REAL; email/teams remain simulated."""
    kind = channel.get("kind")
    cfg = channel.get("config", {})
    status = "sent"
    detail = ""

    try:
        if kind == "slack":
            url = cfg.get("webhook_url") or cfg.get("url")
            if not url:
                return {"status": "error", "detail": "missing webhook_url"}
            payload = {
                "text": f"*{subject}*\n{body}",
                "attachments": [{"image_url": snapshot_url}] if snapshot_url else [],
            }
            async with httpx.AsyncClient(timeout=10) as hx:
                r = await hx.post(url, json=payload)
                detail = f"HTTP {r.status_code}"
                status = "sent" if r.status_code < 300 else "error"

        elif kind == "webhook":
            url = cfg.get("url")
            secret = cfg.get("secret", "")
            if not url:
                return {"status": "error", "detail": "missing url"}
            payload = {"subject": subject, "body": body, "snapshot_url": snapshot_url, "snapshot_b64": snapshot_b64, "ts": now_iso()}
            body_b = json.dumps(payload).encode()
            headers = {"Content-Type": "application/json"}
            if secret:
                sig = hmac.new(secret.encode(), body_b, hashlib.sha256).hexdigest()
                headers["X-NVision-Signature"] = f"sha256={sig}"
            async with httpx.AsyncClient(timeout=10) as hx:
                r = await hx.post(url, content=body_b, headers=headers)
                detail = f"HTTP {r.status_code}"
                status = "sent" if r.status_code < 400 else "error"

        elif kind in ("whatsapp", "sms", "voice"):
            provider = cfg.get("provider", "twilio")
            to = cfg.get("to", "")
            if not to:
                status = "error"
                detail = "missing 'to' number"
            else:
                user = await db.users.find_one({"id": user_id})
                byo = (user or {}).get("byo_keys", {}) or {}
                prov_keys = byo.get(provider)
                if not isinstance(prov_keys, dict) or not prov_keys:
                    status = "error"
                    detail = f"No {provider} keys in Settings — add them under BYO Provider Keys"
                else:
                    msg = f"{subject}\n{body}"[:1500]
                    r = await _send_via_provider(provider, prov_keys, kind, to, msg)
                    status, detail = r["status"], r["detail"]

        elif kind in ("email", "teams"):
            # SIMULATED — Email via Resend/SendGrid and Teams webhook = Phase 2.
            status = "simulated"
            detail = f"[MOCKED] {kind} to {cfg.get('to') or cfg.get('email') or cfg.get('url','?')} — {subject}: {body[:120]}"
            logger.info(detail)

        else:
            return {"status": "error", "detail": f"unknown channel kind {kind}"}
    except Exception as e:
        logger.exception("dispatch failed")
        status = "error"
        detail = str(e)

    await db.alert_deliveries.insert_one({
        "id": new_id(), "user_id": user_id, "channel_id": channel.get("id"),
        "kind": kind, "status": status, "detail": detail, "subject": subject,
        "ts": now_iso(),
    })
    return {"status": status, "detail": detail}


async def _send_via_provider(provider: str, keys: Dict[str, Any], kind: str, to: str, msg: str) -> Dict[str, Any]:
    """Real dispatch via user's BYO provider keys. Returns {status, detail}.
    Stored keys are Fernet ciphertext — decrypted here, at dispatch time only."""
    keys = {fk: (decrypt_secret(fv) if isinstance(fv, str) else fv) for fk, fv in keys.items()}

    def _run():
        if provider == "twilio":
            sid = keys.get("sid") or keys.get("account_sid")
            token = keys.get("token") or keys.get("auth_token")
            frm = keys.get("from") or keys.get("from_number", "")
            if not (sid and token and frm):
                return {"status": "error", "detail": "twilio: need sid, token, from"}
            client = TwilioClient(sid, token)
            if kind == "whatsapp":
                from_num = frm if frm.startswith("whatsapp:") else f"whatsapp:{frm}"
                to_num = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
                m = client.messages.create(from_=from_num, to=to_num, body=msg)
            elif kind == "sms":
                m = client.messages.create(from_=frm, to=to, body=msg)
            elif kind == "voice":
                twiml = f'<Response><Say voice="alice">{msg[:600]}</Say></Response>'
                m = client.calls.create(from_=frm, to=to, twiml=twiml)
            else:
                return {"status": "error", "detail": f"twilio: unsupported kind {kind}"}
            return {"status": "sent", "detail": f"twilio sid={m.sid}"}

        elif provider == "plivo":
            auth_id = keys.get("auth_id") or keys.get("sid")
            auth_token = keys.get("auth_token") or keys.get("token")
            frm = keys.get("from") or keys.get("from_number", "")
            if not (auth_id and auth_token and frm):
                return {"status": "error", "detail": "plivo: need auth_id, auth_token, from"}
            import requests as _req
            if kind == "sms":
                r = _req.post(
                    f"https://api.plivo.com/v1/Account/{auth_id}/Message/",
                    auth=(auth_id, auth_token),
                    json={"src": frm, "dst": to, "text": msg[:800]},
                    timeout=10,
                )
                if 200 <= r.status_code < 300:
                    return {"status": "sent", "detail": f"plivo HTTP {r.status_code}"}
                return {"status": "error", "detail": f"plivo HTTP {r.status_code}: {r.text[:120]}"}
            elif kind == "whatsapp":
                # Plivo WhatsApp requires template — sending free-form works only in 24h session
                r = _req.post(
                    f"https://api.plivo.com/v1/Account/{auth_id}/Messages/",
                    auth=(auth_id, auth_token),
                    json={"src": frm, "dst": to, "type": "whatsapp", "text": msg[:800]},
                    timeout=10,
                )
                if 200 <= r.status_code < 300:
                    return {"status": "sent", "detail": f"plivo-wa HTTP {r.status_code}"}
                return {"status": "error", "detail": f"plivo-wa HTTP {r.status_code}: {r.text[:120]}"}
            else:
                return {"status": "error", "detail": f"plivo: unsupported kind {kind}"}

        elif provider == "exotel":
            api_key = keys.get("api_key")
            api_token = keys.get("api_token") or keys.get("token")
            account_sid = keys.get("account_sid") or keys.get("sid")
            frm = keys.get("from") or keys.get("from_number", "")
            subdomain = keys.get("subdomain", "api.exotel.com")
            if not (api_key and api_token and account_sid and frm):
                return {"status": "error", "detail": "exotel: need api_key, api_token, account_sid, from"}
            import requests as _req
            if kind == "sms":
                r = _req.post(
                    f"https://{subdomain}/v1/Accounts/{account_sid}/Sms/send",
                    auth=(api_key, api_token),
                    data={"From": frm, "To": to, "Body": msg[:600]},
                    timeout=10,
                )
                if 200 <= r.status_code < 300:
                    return {"status": "sent", "detail": f"exotel HTTP {r.status_code}"}
                return {"status": "error", "detail": f"exotel HTTP {r.status_code}: {r.text[:120]}"}
            elif kind == "voice":
                # Exotel Voice Call Connect
                caller_id = keys.get("caller_id", frm)
                r = _req.post(
                    f"https://{subdomain}/v1/Accounts/{account_sid}/Calls/connect",
                    auth=(api_key, api_token),
                    data={"From": to, "CallerId": caller_id, "Url": keys.get("call_url", "http://my.exotel.in/exoml/start_voice/12345")},
                    timeout=10,
                )
                if 200 <= r.status_code < 300:
                    return {"status": "sent", "detail": f"exotel-call HTTP {r.status_code}"}
                return {"status": "error", "detail": f"exotel-call HTTP {r.status_code}: {r.text[:120]}"}
            else:
                return {"status": "error", "detail": f"exotel: unsupported kind {kind}"}

        elif provider == "vonage":
            api_key = keys.get("api_key")
            api_secret = keys.get("api_secret")
            frm = keys.get("from") or keys.get("from_number", "NVision")
            if not (api_key and api_secret):
                return {"status": "error", "detail": "vonage: need api_key, api_secret"}
            import requests as _req
            if kind == "sms":
                r = _req.post("https://rest.nexmo.com/sms/json",
                              data={"api_key": api_key, "api_secret": api_secret, "from": frm, "to": to, "text": msg[:600]},
                              timeout=10)
                if 200 <= r.status_code < 300:
                    return {"status": "sent", "detail": f"vonage HTTP {r.status_code}"}
                return {"status": "error", "detail": f"vonage HTTP {r.status_code}: {r.text[:120]}"}
            return {"status": "error", "detail": f"vonage: kind {kind} not wired (SMS supported)"}

        elif provider == "messagebird":
            api_key = keys.get("api_key")
            frm = keys.get("from") or keys.get("from_number", "NVision")
            if not api_key:
                return {"status": "error", "detail": "messagebird: need api_key"}
            import requests as _req
            r = _req.post("https://rest.messagebird.com/messages",
                          headers={"Authorization": f"AccessKey {api_key}"},
                          data={"originator": frm, "recipients": to, "body": msg[:600]},
                          timeout=10)
            if 200 <= r.status_code < 300:
                return {"status": "sent", "detail": f"messagebird HTTP {r.status_code}"}
            return {"status": "error", "detail": f"messagebird HTTP {r.status_code}: {r.text[:120]}"}

        else:
            return {"status": "error", "detail": f"unknown provider {provider}"}

    try:
        return await asyncio.to_thread(_run)
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ========================= AUTH ROUTES =========================
@api.post("/auth/signup")
async def signup(body: SignupIn):
    existing = await db.users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(400, "Email already registered")
    uid = new_id()
    doc = {
        "id": uid,
        "email": body.email.lower(),
        "name": body.name,
        "password_hash": hash_pw(body.password),
        "credits": 500,                             # signup bonus
        "created_at": now_iso(),
        "byo_keys": {},                             # openai/anthropic/gemini/twilio/plivo/exotel
    }
    await db.users.insert_one(doc)
    await db.credit_tx.insert_one({"id": new_id(), "user_id": uid, "delta": 500, "reason": "signup_bonus", "ts": now_iso()})
    return {"token": make_token(uid), "user": {"id": uid, "email": doc["email"], "name": doc["name"], "credits": 500}}

@api.post("/auth/login")
async def login(body: LoginIn):
    u = await db.users.find_one({"email": body.email.lower()})
    if not u or not check_pw(body.password, u["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    return {"token": make_token(u["id"]), "user": {"id": u["id"], "email": u["email"], "name": u["name"], "credits": u.get("credits", 0)}}

@api.get("/auth/me")
async def me(user=Depends(current_user)):
    return user


# ========================= CAMERAS =========================
@api.post("/cameras")
async def create_camera(body: CameraIn, user=Depends(current_user)):
    doc = {
        "id": new_id(), "user_id": user["id"], "name": body.name,
        "rtsp_url": body.rtsp_url, "snapshot_url": body.snapshot_url,
        "site": body.site, "tags": body.tags, "timezone": body.timezone,
        "zones": body.zones,
        "status": "online" if body.snapshot_url or body.rtsp_url else "unknown",
        "created_at": now_iso(),
    }
    await db.cameras.insert_one(doc)
    return public_camera(doc)

@api.patch("/cameras/{cid}")
async def update_camera(cid: str, body: CameraPatch, user=Depends(current_user)):
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    # Never store a masked URL echoed back from a previous response
    if "rtsp_url" in updates and "•••" in updates["rtsp_url"]:
        updates.pop("rtsp_url")
    if updates:
        await db.cameras.update_one({"id": cid, "user_id": user["id"]}, {"$set": updates})
    cam = await db.cameras.find_one({"id": cid, "user_id": user["id"]}, {"_id": 0})
    if not cam:
        raise HTTPException(404, "Camera not found")
    return public_camera(cam)

@api.get("/cameras")
async def list_cameras(user=Depends(current_user)):
    cams = await db.cameras.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [public_camera(c) for c in cams]

@api.get("/cameras/{cid}")
async def get_camera(cid: str, user=Depends(current_user)):
    cam = await db.cameras.find_one({"id": cid, "user_id": user["id"]}, {"_id": 0})
    if not cam:
        raise HTTPException(404, "Camera not found")
    return public_camera(cam)

@api.delete("/cameras/{cid}")
async def delete_camera(cid: str, user=Depends(current_user)):
    await db.cameras.delete_one({"id": cid, "user_id": user["id"]})
    await db.detections.delete_many({"camera_id": cid, "user_id": user["id"]})
    return {"ok": True}


# ========================= DETECTIONS =========================
@api.get("/templates")
async def get_templates():
    return TEMPLATES

@api.post("/detections")
async def create_detection(body: DetectionIn, user=Depends(current_user)):
    cam = await db.cameras.find_one({"id": body.camera_id, "user_id": user["id"]})
    if not cam:
        raise HTTPException(404, "Camera not found")
    doc = {
        "id": new_id(), "user_id": user["id"], "camera_id": body.camera_id,
        "camera_name": cam["name"], "name": body.name, "prompt": body.prompt,
        "sample_images_b64": body.sample_images_b64[:6], "template": body.template,
        "sensitivity": body.sensitivity, "schedule": body.schedule, "zones": body.zones,
        "enabled": body.enabled, "created_at": now_iso(),
        "cooldown_seconds": body.cooldown_seconds,
        "fires_count": 0, "last_fired_at": None,
    }
    await db.detections.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.get("/detections")
async def list_detections(user=Depends(current_user)):
    ds = await db.detections.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return ds

@api.get("/detections/{did}")
async def get_detection(did: str, user=Depends(current_user)):
    d = await db.detections.find_one({"id": did, "user_id": user["id"]}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Not found")
    return d

@api.patch("/detections/{did}")
async def update_detection(did: str, body: Dict[str, Any], user=Depends(current_user)):
    allowed = {"enabled", "sensitivity", "prompt", "name", "schedule", "cooldown_seconds"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if updates:
        await db.detections.update_one({"id": did, "user_id": user["id"]}, {"$set": updates})
    d = await db.detections.find_one({"id": did, "user_id": user["id"]}, {"_id": 0})
    return d

@api.delete("/detections/{did}")
async def delete_detection(did: str, user=Depends(current_user)):
    await db.detections.delete_one({"id": did, "user_id": user["id"]})
    return {"ok": True}


# ========================= ANALYZE (core) =========================
async def _fetch_image_url_to_b64(url: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as hx:
            r = await hx.get(url)
            if r.status_code >= 400:
                return None
            return base64.b64encode(r.content).decode()
    except Exception:
        return None

async def run_detection_pipeline(user_id: str, det: Dict[str, Any], cam: Dict[str, Any], img_b64: str, source: str = "api") -> Dict[str, Any]:
    """Shared analyze path: credits -> VLM -> event -> alert fan-out.
    Used by the public /analyze endpoint and the worker ingest path."""
    ok = await deduct_credits(user_id, CREDIT_COSTS["vlm_eval"], f"vlm:{det['name']}")
    if not ok:
        logger.info("vlm skipped (insufficient credits) user=%s detection=%s", user_id, det["id"])
        return {"error": "insufficient_credits"}

    gemini_key = await _user_byo_key(user_id, "gemini")
    result = await run_vision_detection(
        det["prompt"], img_b64, det.get("sample_images_b64", []),
        det.get("sensitivity", 0.6),
        zones=cam.get("zones") or [],
        api_key=gemini_key,
    )
    is_match = result["match"] and result["confidence"] >= det.get("sensitivity", 0.6)
    logger.info("vlm eval source=%s camera=%s detection=%s match=%s conf=%.2f", source, cam["id"], det["id"], is_match, result["confidence"])

    event = {
        "id": new_id(), "user_id": user_id, "detection_id": det["id"],
        "detection_name": det["name"], "camera_id": cam["id"], "camera_name": cam["name"],
        "timestamp": now_iso(), "match": is_match, "confidence": result["confidence"],
        "caption": result["caption"], "objects": result["objects"],
        "snapshot_b64": img_b64[:250000],  # cap to ~250KB base64
        "source": source,
        "feedback": None, "acknowledged": False,
    }
    await db.events.insert_one(event)

    dispatched = []
    if is_match:
        await db.detections.update_one({"id": det["id"]}, {"$inc": {"fires_count": 1}, "$set": {"last_fired_at": now_iso()}})
        # fan out to all enabled channels
        channels = await db.channels.find({"user_id": user_id, "enabled": {"$ne": False}}, {"_id": 0}).to_list(50)
        for ch in channels:
            r = await dispatch_alert(
                user_id, ch,
                subject=f"NVision Alert: {det['name']}",
                body=f"[{cam['name']}] {result['caption']} (confidence {result['confidence']:.0%})",
                snapshot_url=None,
                snapshot_b64=img_b64[:250000],
            )
            dispatched.append({"channel": ch["name"], "kind": ch["kind"], **r})

    event.pop("_id", None)
    event.pop("snapshot_b64", None)  # don't ship base64 back
    return {"event": event, "dispatched": dispatched}


@api.post("/analyze")
async def analyze(body: AnalyzeIn, user=Depends(current_user)):
    det = await db.detections.find_one({"id": body.detection_id, "user_id": user["id"]})
    if not det:
        raise HTTPException(404, "Detection not found")
    cam = await db.cameras.find_one({"id": det["camera_id"], "user_id": user["id"]})
    if not cam:
        raise HTTPException(404, "Camera not found")

    # get image bytes
    img_b64 = body.image_b64
    if not img_b64 and body.image_url:
        img_b64 = await _fetch_image_url_to_b64(body.image_url)
    if not img_b64 and cam.get("snapshot_url"):
        img_b64 = await _fetch_image_url_to_b64(cam["snapshot_url"])
    if not img_b64:
        raise HTTPException(400, "No image provided (image_b64 or image_url or camera snapshot_url required)")

    if img_b64.startswith("data:"):
        img_b64 = img_b64.split(",", 1)[-1]

    out = await run_detection_pipeline(user["id"], det, cam, img_b64, source="api")
    if out.get("error") == "insufficient_credits":
        raise HTTPException(402, "Insufficient credits. Please top up.")
    return out


# ========================= INTERNAL (worker) =========================
class IngestIn(BaseModel):
    camera_id: str
    image_b64: str
    ts: Optional[str] = None

class CameraStatusIn(BaseModel):
    status: str                                  # online | offline


async def worker_auth(x_worker_token: Optional[str] = Header(None)):
    if not WORKER_TOKEN:
        raise HTTPException(503, "WORKER_TOKEN not configured on backend")
    if not x_worker_token or not hmac.compare_digest(x_worker_token, WORKER_TOKEN):
        raise HTTPException(401, "Invalid worker token")


def _within_cooldown(det: Dict[str, Any]) -> bool:
    last_fired = det.get("last_fired_at")
    if not last_fired:
        return False
    cooldown = int(det.get("cooldown_seconds", 120) or 0)
    if cooldown <= 0:
        return False
    try:
        last = datetime.fromisoformat(last_fired)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return (datetime.now(timezone.utc) - last).total_seconds() < cooldown


@api.get("/internal/cameras/active", dependencies=[Depends(worker_auth)])
async def internal_active_cameras():
    """Cameras with an RTSP URL and at least one enabled detection. Worker-only: returns raw RTSP URLs."""
    cams = await db.cameras.find({"rtsp_url": {"$nin": [None, ""]}}, {"_id": 0}).to_list(1000)
    out = []
    for cam in cams:
        n = await db.detections.count_documents({"camera_id": cam["id"], "enabled": True})
        if n > 0:
            out.append({
                "id": cam["id"], "user_id": cam["user_id"], "name": cam["name"],
                "rtsp_url": cam["rtsp_url"], "status": cam.get("status", "unknown"),
                "detections_enabled": n,
            })
    return out


@api.post("/internal/ingest", dependencies=[Depends(worker_auth)])
async def internal_ingest(body: IngestIn):
    """Worker posts a motion-qualified frame. Runs every enabled detection on the camera,
    enforcing the per-detection cooldown backend-side."""
    cam = await db.cameras.find_one({"id": body.camera_id})
    if not cam:
        raise HTTPException(404, "Camera not found")

    img_b64 = body.image_b64
    if img_b64.startswith("data:"):
        img_b64 = img_b64.split(",", 1)[-1]

    dets = await db.detections.find({"camera_id": cam["id"], "enabled": True}, {"_id": 0}).to_list(100)
    results = []
    for det in dets:
        if _within_cooldown(det):
            logger.info("cooldown skip camera=%s detection=%s cooldown=%ss last_fired=%s",
                        cam["id"], det["id"], det.get("cooldown_seconds", 120), det.get("last_fired_at"))
            results.append({"detection_id": det["id"], "skipped": "cooldown"})
            continue
        out = await run_detection_pipeline(cam["user_id"], det, cam, img_b64, source="worker")
        if out.get("error"):
            results.append({"detection_id": det["id"], "skipped": out["error"]})
        else:
            results.append({"detection_id": det["id"], "match": out["event"]["match"], "confidence": out["event"]["confidence"]})
    logger.info("ingest camera=%s detections=%d ts=%s", cam["id"], len(dets), body.ts or now_iso())
    return {"camera_id": cam["id"], "results": results}


@api.post("/internal/cameras/{cid}/status", dependencies=[Depends(worker_auth)])
async def internal_camera_status(cid: str, body: CameraStatusIn):
    """Worker heartbeat: camera.online / camera.offline. Fires an offline alert on transition."""
    if body.status not in ("online", "offline"):
        raise HTTPException(400, "status must be online|offline")
    cam = await db.cameras.find_one({"id": cid})
    if not cam:
        raise HTTPException(404, "Camera not found")
    prev = cam.get("status", "unknown")
    if prev == body.status:
        return {"ok": True, "status": body.status, "changed": False}

    await db.cameras.update_one({"id": cid}, {"$set": {"status": body.status, "status_changed_at": now_iso()}})
    logger.info("camera status change camera=%s %s -> %s", cid, prev, body.status)

    dispatched = []
    if body.status == "offline":
        channels = await db.channels.find({"user_id": cam["user_id"], "enabled": {"$ne": False}}, {"_id": 0}).to_list(50)
        for ch in channels:
            r = await dispatch_alert(
                cam["user_id"], ch,
                subject=f"NVision: camera offline — {cam['name']}",
                body=f"Camera '{cam['name']}' stopped responding and is now marked offline.",
            )
            dispatched.append({"channel": ch["name"], "kind": ch["kind"], **r})
    return {"ok": True, "status": body.status, "changed": True, "dispatched": dispatched}


# ========================= EVENTS =========================
@api.get("/events")
async def list_events(camera_id: Optional[str] = None, only_matches: bool = False, limit: int = 100, user=Depends(current_user)):
    q: Dict[str, Any] = {"user_id": user["id"]}
    if camera_id:
        q["camera_id"] = camera_id
    if only_matches:
        q["match"] = True
    events = await db.events.find(q, {"_id": 0, "snapshot_b64": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return events

@api.get("/events/{eid}")
async def get_event(eid: str, user=Depends(current_user)):
    e = await db.events.find_one({"id": eid, "user_id": user["id"]}, {"_id": 0})
    if not e:
        raise HTTPException(404, "Event not found")
    return e

@api.post("/events/feedback")
async def feedback(body: FeedbackIn, user=Depends(current_user)):
    await db.events.update_one({"id": body.event_id, "user_id": user["id"]},
                               {"$set": {"feedback": "correct" if body.correct else "false_alarm"}})
    return {"ok": True}

@api.post("/events/{eid}/ack")
async def ack_event(eid: str, user=Depends(current_user)):
    await db.events.update_one({"id": eid, "user_id": user["id"]}, {"$set": {"acknowledged": True}})
    return {"ok": True}


# ========================= MEMORY QUERY =========================
@api.post("/memory/query")
async def memory_query(body: MemoryQueryIn, user=Depends(current_user)):
    q: Dict[str, Any] = {"user_id": user["id"]}
    if body.camera_id:
        q["camera_id"] = body.camera_id

    # keyword filter over caption/objects/camera name
    words = [w.strip().lower() for w in re.findall(r"\w+", body.query) if len(w) > 2]
    stop = {"was", "were", "there", "the", "and", "any", "did", "what", "when", "where", "who", "how", "yesterday", "today", "camera", "cameras", "with", "for", "from", "into", "over", "under", "about"}
    kw = [w for w in words if w not in stop][:6]
    if kw:
        q["$or"] = [
            {"caption": {"$regex": w, "$options": "i"}} for w in kw
        ] + [
            {"objects": {"$regex": w, "$options": "i"}} for w in kw
        ] + [
            {"camera_name": {"$regex": w, "$options": "i"}} for w in kw
        ] + [
            {"detection_name": {"$regex": w, "$options": "i"}} for w in kw
        ]

    events = await db.events.find(q, {"_id": 0, "snapshot_b64": 0}).sort("timestamp", -1).limit(max(3, min(body.limit, 50))).to_list(50)
    if not events:
        # fallback — recent events irrespective of keyword
        events = await db.events.find({"user_id": user["id"]}, {"_id": 0, "snapshot_b64": 0}).sort("timestamp", -1).limit(15).to_list(15)

    anthropic_key = await _user_byo_key(user["id"], "anthropic")
    answer = await answer_memory(body.query, events, api_key=anthropic_key)
    return {"answer": answer, "citations": events[:body.limit]}


# ========================= CHANNELS =========================
@api.post("/channels")
async def create_channel(body: ChannelIn, user=Depends(current_user)):
    doc = {"id": new_id(), "user_id": user["id"], "name": body.name, "kind": body.kind,
           "config": body.config, "enabled": True, "created_at": now_iso()}
    await db.channels.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.get("/channels")
async def list_channels(user=Depends(current_user)):
    chs = await db.channels.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return chs

@api.post("/channels/test")
async def test_channel(body: ChannelTestIn, user=Depends(current_user)):
    ch = await db.channels.find_one({"id": body.channel_id, "user_id": user["id"]}, {"_id": 0})
    if not ch:
        raise HTTPException(404, "Channel not found")
    r = await dispatch_alert(user["id"], ch, subject="NVision Test", body=body.message)
    return r

@api.delete("/channels/{cid}")
async def delete_channel(cid: str, user=Depends(current_user)):
    await db.channels.delete_one({"id": cid, "user_id": user["id"]})
    return {"ok": True}

@api.patch("/channels/{cid}")
async def update_channel(cid: str, body: Dict[str, Any], user=Depends(current_user)):
    allowed = {"enabled", "name", "config"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if updates:
        await db.channels.update_one({"id": cid, "user_id": user["id"]}, {"$set": updates})
    ch = await db.channels.find_one({"id": cid, "user_id": user["id"]}, {"_id": 0})
    return ch

@api.get("/deliveries")
async def deliveries(user=Depends(current_user)):
    d = await db.alert_deliveries.find({"user_id": user["id"]}, {"_id": 0}).sort("ts", -1).limit(50).to_list(50)
    return d


# ========================= CREDITS / BILLING =========================
@api.get("/credits")
async def credits(user=Depends(current_user)):
    u = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0})
    txs = await db.credit_tx.find({"user_id": user["id"]}, {"_id": 0}).sort("ts", -1).limit(30).to_list(30)
    # burn rate: consumed in last 7 days
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    burn_docs = await db.credit_tx.find({"user_id": user["id"], "delta": {"$lt": 0}, "ts": {"$gte": since}}).to_list(500)
    burn = sum(-int(d["delta"]) for d in burn_docs)
    daily = burn / 7 if burn else 0
    days_left = (u.get("credits", 0) / daily) if daily > 0 else None
    return {
        "balance": u.get("credits", 0),
        "packs": CREDIT_PACKS,
        "transactions": txs,
        "burn_7d": burn,
        "daily_burn": round(daily, 1),
        "days_left": round(days_left, 1) if days_left else None,
        "rates": CREDIT_COSTS,
    }

@api.post("/credits/topup")
async def topup(body: TopupIn, user=Depends(current_user)):
    """Creates a Razorpay Order for a credit pack. Frontend opens Razorpay Checkout and calls /credits/verify on success."""
    pack = CREDIT_PACKS.get(body.pack)
    if not pack:
        raise HTTPException(400, "Unknown pack")
    if not rzp:
        raise HTTPException(500, "Razorpay not configured (missing RAZORPAY_KEY_ID/SECRET)")
    amount_paise = int(pack["amount_inr"]) * 100
    receipt = f"nv_{body.pack}_{new_id()[:8]}"
    try:
        order = rzp.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "payment_capture": 1,
            "notes": {"user_id": user["id"], "pack": body.pack},
        })
    except Exception as e:
        logger.exception("razorpay order failed")
        raise HTTPException(502, f"Razorpay error: {e}")

    await db.payment_transactions.insert_one({
        "id": new_id(),
        "user_id": user["id"],
        "razorpay_order_id": order["id"],
        "pack": body.pack,
        "amount_inr": pack["amount_inr"],
        "credits": pack["credits"],
        "status": "created",
        "created_at": now_iso(),
    })
    return {
        "order_id": order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "key_id": RAZORPAY_KEY_ID,
        "credits": pack["credits"],
        "pack": body.pack,
        "user": {"name": user.get("name",""), "email": user.get("email","")},
    }

@api.post("/credits/verify")
async def verify_payment(body: RzpVerifyIn, user=Depends(current_user)):
    """Verifies Razorpay signature and grants credits."""
    if not rzp:
        raise HTTPException(500, "Razorpay not configured")
    # signature = HMAC_SHA256(order_id + '|' + payment_id, key_secret)
    expected = hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        f"{body.razorpay_order_id}|{body.razorpay_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, body.razorpay_signature):
        raise HTTPException(400, "Invalid Razorpay signature")

    txn = await db.payment_transactions.find_one({"razorpay_order_id": body.razorpay_order_id, "user_id": user["id"]})
    if not txn:
        raise HTTPException(404, "Transaction not found")
    if txn.get("status") == "paid":
        return {"ok": True, "already": True, "credits": txn["credits"]}

    await db.payment_transactions.update_one(
        {"_id": txn["_id"]},
        {"$set": {
            "status": "paid",
            "razorpay_payment_id": body.razorpay_payment_id,
            "razorpay_signature": body.razorpay_signature,
            "paid_at": now_iso(),
        }},
    )
    await add_credits(user["id"], int(txn["credits"]), f"razorpay_topup:{txn['pack']}")
    new_bal = (await db.users.find_one({"id": user["id"]}))["credits"]
    return {"ok": True, "credits_added": txn["credits"], "new_balance": new_bal}

@api.post("/credits/razorpay/webhook")
async def razorpay_webhook(request: Request):
    """Optional webhook for reliability."""
    payload = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")
    if RAZORPAY_WEBHOOK_SECRET:
        try:
            rzp.utility.verify_webhook_signature(payload.decode(), sig, RAZORPAY_WEBHOOK_SECRET)
        except Exception:
            raise HTTPException(400, "Invalid signature")
    try:
        data = json.loads(payload.decode())
    except Exception:
        raise HTTPException(400, "Bad JSON")
    event = data.get("event", "")
    if event == "payment.captured":
        p = data.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = p.get("order_id")
        if order_id:
            txn = await db.payment_transactions.find_one({"razorpay_order_id": order_id, "status": {"$ne": "paid"}})
            if txn:
                await db.payment_transactions.update_one(
                    {"_id": txn["_id"]},
                    {"$set": {"status": "paid", "razorpay_payment_id": p.get("id"), "paid_at": now_iso()}},
                )
                await add_credits(txn["user_id"], int(txn["credits"]), f"razorpay_webhook:{txn['pack']}")
    return {"status": "ok"}


# ========================= API KEYS =========================
def _gen_api_key() -> str:
    return "nv_" + base64.urlsafe_b64encode(os.urandom(24)).decode().rstrip("=")

@api.post("/api-keys")
async def create_api_key(body: ApiKeyIn, user=Depends(current_user)):
    raw = _gen_api_key()
    doc = {"id": new_id(), "user_id": user["id"], "name": body.name, "scope": body.scope,
           "key_prefix": raw[:10], "key_hash": hashlib.sha256(raw.encode()).hexdigest(),
           "created_at": now_iso(), "last_used": None}
    await db.api_keys.insert_one(doc)
    doc.pop("_id", None)
    doc.pop("key_hash", None)
    return {**doc, "key": raw}   # only time we return the raw key

@api.get("/api-keys")
async def list_api_keys(user=Depends(current_user)):
    keys = await db.api_keys.find({"user_id": user["id"]}, {"_id": 0, "key_hash": 0}).sort("created_at", -1).to_list(50)
    return keys

@api.delete("/api-keys/{kid}")
async def del_api_key(kid: str, user=Depends(current_user)):
    await db.api_keys.delete_one({"id": kid, "user_id": user["id"]})
    return {"ok": True}


# ========================= ANALYTICS =========================
@api.get("/analytics/summary")
async def analytics_summary(user=Depends(current_user)):
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    total_events = await db.events.count_documents({"user_id": user["id"]})
    matches = await db.events.count_documents({"user_id": user["id"], "match": True})
    cams = await db.cameras.count_documents({"user_id": user["id"]})
    detections = await db.detections.count_documents({"user_id": user["id"]})
    correct = await db.events.count_documents({"user_id": user["id"], "feedback": "correct"})
    false_alarm = await db.events.count_documents({"user_id": user["id"], "feedback": "false_alarm"})
    precision = (correct / (correct + false_alarm)) if (correct + false_alarm) > 0 else None

    # events by day (last 7)
    docs = await db.events.find({"user_id": user["id"], "timestamp": {"$gte": since}}, {"_id": 0, "timestamp": 1, "match": 1}).to_list(5000)
    by_day: Dict[str, Dict[str, int]] = {}
    for d in docs:
        day = d["timestamp"][:10]
        b = by_day.setdefault(day, {"events": 0, "matches": 0})
        b["events"] += 1
        if d.get("match"):
            b["matches"] += 1
    daily = [{"day": k, **v} for k, v in sorted(by_day.items())]

    # busiest cameras
    pipeline = [
        {"$match": {"user_id": user["id"]}},
        {"$group": {"_id": "$camera_name", "events": {"$sum": 1}, "matches": {"$sum": {"$cond": ["$match", 1, 0]}}}},
        {"$sort": {"events": -1}}, {"$limit": 5},
    ]
    busiest = [{"camera": r["_id"], "events": r["events"], "matches": r["matches"]} async for r in db.events.aggregate(pipeline)]

    return {
        "totals": {"cameras": cams, "detections": detections, "events": total_events, "matches": matches},
        "precision": precision,
        "correct": correct, "false_alarm": false_alarm,
        "daily": daily,
        "busiest_cameras": busiest,
    }


# ========================= BYO KEYS =========================
@api.get("/settings/byo")
async def get_byo(user=Depends(current_user)):
    u = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    byo = u.get("byo_keys", {}) or {}
    # decrypt (stored values are Fernet ciphertext), then mask each provider's fields
    def _mask(fv):
        if not isinstance(fv, str) or not fv:
            return "•••" if fv else ""
        plain = decrypt_secret(fv)
        return (plain[:4] + "…" + plain[-3:]) if len(plain) > 8 else "•••"
    masked = {}
    for prov, v in byo.items():
        if isinstance(v, dict):
            masked[prov] = {fk: _mask(fv) for fk, fv in v.items()}
        elif isinstance(v, str):
            masked[prov] = _mask(v)
    return {"keys": masked}

@api.post("/settings/byo")
async def set_byo(body: Dict[str, Any], user=Depends(current_user)):
    """Body: {provider: {field: value, ...}} — merges into user.byo_keys.<provider>.
    Values are encrypted at rest with Fernet (NVISION_MASTER_KEY)."""
    updates: Dict[str, Any] = {}
    allowed = {"openai", "anthropic", "gemini", "twilio", "plivo", "exotel", "vonage", "messagebird"}
    for prov, v in body.items():
        if prov not in allowed:
            continue
        if isinstance(v, dict):
            for fk, fv in v.items():
                if fv and isinstance(fv, str) and "…" not in fv and fv != "•••":
                    updates[f"byo_keys.{prov}.{fk}"] = encrypt_secret(fv)
        elif isinstance(v, str) and v:
            updates[f"byo_keys.{prov}"] = encrypt_secret(v)
    if updates:
        await db.users.update_one({"id": user["id"]}, {"$set": updates})
    return {"ok": True}


# ========================= HEALTH =========================
@api.get("/")
async def root():
    return {"service": "NVision API", "status": "ok", "version": "0.1.0"}


# ========================= MOUNT =========================
app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown():
    client.close()
