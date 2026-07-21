"""NVision — AI Vision Platform Backend (MVP v0.1)."""
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header, UploadFile, File, Form
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
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="NVision API", version="0.1.0")
api = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("nvision")


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
async def run_vision_detection(prompt: str, image_b64: str, sample_b64s: List[str], sensitivity: float) -> Dict[str, Any]:
    """Analyze image with Gemini 3 Flash vision, return {match, confidence, caption, objects}."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
    except Exception as e:
        logger.exception("emergentintegrations import failed")
        return {"match": False, "confidence": 0.0, "caption": f"AI unavailable: {e}", "objects": []}

    system = (
        "You are NVision, a precise CCTV vision analyzer. "
        "Given a live camera frame, an operator's detection prompt, and optional reference sample images, "
        "you must return STRICT JSON with keys: match (bool), confidence (float 0-1), caption (one sentence), objects (array of short strings). "
        f"Be strict — the user's sensitivity threshold is {sensitivity:.2f}. Only report match=true when the described condition is genuinely present. "
        "Do not include markdown fences or prose outside JSON."
    )
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"detect-{new_id()}",
        system_message=system,
    ).with_model("gemini", "gemini-3-flash-preview")

    contents = []
    for sb in sample_b64s[:4]:
        contents.append(ImageContent(image_base64=sb))
    contents.append(ImageContent(image_base64=image_b64))

    user_text = (
        f"Detection prompt: {prompt}\n\n"
        f"{'The first images are REFERENCE samples showing what to look for. The LAST image is the LIVE frame to analyze.' if sample_b64s else 'The image is the LIVE camera frame to analyze.'}\n\n"
        f"Respond with JSON only, e.g. {{\"match\": false, \"confidence\": 0.12, \"caption\": \"Empty corridor at night.\", \"objects\": [\"corridor\", \"door\"]}}"
    )

    try:
        resp = await chat.send_message(UserMessage(text=user_text, file_contents=contents))
        text = str(resp)
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if not m:
            return {"match": False, "confidence": 0.0, "caption": "Model returned non-JSON.", "objects": []}
        data = json.loads(m.group(0))
        return {
            "match": bool(data.get("match", False)),
            "confidence": float(data.get("confidence", 0.0)),
            "caption": str(data.get("caption", ""))[:280],
            "objects": [str(o)[:40] for o in data.get("objects", [])][:8],
        }
    except Exception as e:
        logger.exception("vision detection failed")
        return {"match": False, "confidence": 0.0, "caption": f"Detection error: {e}", "objects": []}


async def answer_memory(question: str, events: List[Dict[str, Any]]) -> str:
    """Use Claude Sonnet to answer a memory question over retrieved event captions."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception:
        return "AI unavailable."
    if not events:
        return "No events matched your question in memory."

    lines = []
    for e in events[:20]:
        lines.append(f"[{e.get('timestamp','')}] Camera={e.get('camera_name','?')} match={e.get('match')} conf={e.get('confidence',0):.2f} — {e.get('caption','')}")
    context = "\n".join(lines)

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"memq-{new_id()}",
        system_message=(
            "You are NVision Memory — an assistant that answers questions about camera events. "
            "Answer using ONLY the event log provided. If the log does not answer the question, say so. "
            "Cite timestamps (like 2026-02-15T18:30) inline. Keep the answer under 120 words."
        ),
    ).with_model("anthropic", "claude-sonnet-4-6")

    try:
        resp = await chat.send_message(UserMessage(text=f"EVENT LOG:\n{context}\n\nQUESTION: {question}"))
        return str(resp)[:2000]
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


async def dispatch_alert(user_id: str, channel: Dict[str, Any], subject: str, body: str, snapshot_url: Optional[str] = None) -> Dict[str, Any]:
    """Fires an alert. Slack/Webhook are REAL; email/whatsapp/sms/voice are SIMULATED (logged)."""
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
            payload = {"subject": subject, "body": body, "snapshot_url": snapshot_url, "ts": now_iso()}
            body_b = json.dumps(payload).encode()
            headers = {"Content-Type": "application/json"}
            if secret:
                sig = hmac.new(secret.encode(), body_b, hashlib.sha256).hexdigest()
                headers["X-NVision-Signature"] = f"sha256={sig}"
            async with httpx.AsyncClient(timeout=10) as hx:
                r = await hx.post(url, content=body_b, headers=headers)
                detail = f"HTTP {r.status_code}"
                status = "sent" if r.status_code < 400 else "error"

        elif kind in ("email", "whatsapp", "sms", "voice", "teams"):
            # SIMULATED — logs the alert. Real providers = Phase 2 (BYO keys UI ready).
            status = "simulated"
            detail = f"[MOCKED] {kind} to {cfg.get('to') or cfg.get('phone') or cfg.get('email') or cfg.get('channel','?')} — {subject}: {body[:120]}"
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
        "status": "online" if body.snapshot_url or body.rtsp_url else "unknown",
        "created_at": now_iso(),
    }
    await db.cameras.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.get("/cameras")
async def list_cameras(user=Depends(current_user)):
    cams = await db.cameras.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return cams

@api.get("/cameras/{cid}")
async def get_camera(cid: str, user=Depends(current_user)):
    cam = await db.cameras.find_one({"id": cid, "user_id": user["id"]}, {"_id": 0})
    if not cam:
        raise HTTPException(404, "Camera not found")
    return cam

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
        "fires_count": 0,
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
    allowed = {"enabled", "sensitivity", "prompt", "name", "schedule"}
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

    # credits
    ok = await deduct_credits(user["id"], CREDIT_COSTS["vlm_eval"], f"vlm:{det['name']}")
    if not ok:
        raise HTTPException(402, "Insufficient credits. Please top up.")

    # run vision
    result = await run_vision_detection(det["prompt"], img_b64, det.get("sample_images_b64", []), det.get("sensitivity", 0.6))
    is_match = result["match"] and result["confidence"] >= det.get("sensitivity", 0.6)

    event = {
        "id": new_id(), "user_id": user["id"], "detection_id": det["id"],
        "detection_name": det["name"], "camera_id": cam["id"], "camera_name": cam["name"],
        "timestamp": now_iso(), "match": is_match, "confidence": result["confidence"],
        "caption": result["caption"], "objects": result["objects"],
        "snapshot_b64": img_b64[:250000],  # cap to ~250KB base64
        "feedback": None, "acknowledged": False,
    }
    await db.events.insert_one(event)

    dispatched = []
    if is_match:
        await db.detections.update_one({"id": det["id"]}, {"$inc": {"fires_count": 1}})
        # fan out to all enabled channels
        channels = await db.channels.find({"user_id": user["id"], "enabled": {"$ne": False}}, {"_id": 0}).to_list(50)
        for ch in channels:
            r = await dispatch_alert(
                user["id"], ch,
                subject=f"NVision Alert: {det['name']}",
                body=f"[{cam['name']}] {result['caption']} (confidence {result['confidence']:.0%})",
                snapshot_url=None,
            )
            dispatched.append({"channel": ch["name"], "kind": ch["kind"], **r})

    event.pop("_id", None)
    event.pop("snapshot_b64", None)  # don't ship base64 back
    return {"event": event, "dispatched": dispatched}


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

    answer = await answer_memory(body.query, events)
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
    """MVP: simulated Stripe/Razorpay top-up. In production this returns a Stripe checkout URL."""
    pack = CREDIT_PACKS.get(body.pack)
    if not pack:
        raise HTTPException(400, "Unknown pack")
    await add_credits(user["id"], pack["credits"], f"topup:{body.pack}")
    return {"ok": True, "added": pack["credits"], "new_balance": (await db.users.find_one({"id": user["id"]}))["credits"]}


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
    byo = u.get("byo_keys", {})
    # mask keys
    masked = {k: (v[:4] + "…" + v[-3:]) if v and len(v) > 8 else ("" if not v else "•••") for k, v in byo.items()}
    return {"keys": masked}

@api.post("/settings/byo")
async def set_byo(body: Dict[str, str], user=Depends(current_user)):
    updates = {f"byo_keys.{k}": v for k, v in body.items() if k in {"openai", "anthropic", "gemini", "twilio", "plivo", "exotel"}}
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
