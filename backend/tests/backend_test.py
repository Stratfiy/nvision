"""NVision backend API tests."""
import os
import base64
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://scout-ai-30.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

# Real gate image URL from the review request
GATE_IMG_URL = "https://images.pexels.com/photos/36162857/pexels-photo-36162857.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"

# Tiny real JPEG (a 4x4 checkered image) - non-uniform variance
_TINY_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/"
    "2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAAEAAQDASIAAhEBAxEB/8QA"
    "HwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2Jy"
    "ggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5"
    "usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iiigD//2Q=="
)

session = requests.Session()
session.headers.update({"Content-Type": "application/json"})

EMAIL = f"TEST_nvbe_{uuid.uuid4().hex[:8]}@example.com"
PASSWORD = "Testpass123!"
NAME = "NVision Backend Tester"

state = {}


def _auth_headers():
    return {"Authorization": f"Bearer {state['token']}", "Content-Type": "application/json"}


# --- Health ---
def test_root():
    r = requests.get(f"{API}/")
    assert r.status_code == 200
    j = r.json()
    assert j.get("service") == "NVision API"


# --- Auth ---
def test_signup_creates_user_with_500_credits():
    r = session.post(f"{API}/auth/signup", json={"email": EMAIL, "password": PASSWORD, "name": NAME})
    assert r.status_code == 200, r.text
    j = r.json()
    assert "token" in j and j["user"]["credits"] == 500
    assert j["user"]["email"] == EMAIL.lower()
    state["token"] = j["token"]
    state["user_id"] = j["user"]["id"]


def test_signup_email_uniqueness():
    r = session.post(f"{API}/auth/signup", json={"email": EMAIL, "password": PASSWORD, "name": NAME})
    assert r.status_code == 400


def test_login_and_me():
    r = session.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200
    token = r.json()["token"]
    r2 = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["email"] == EMAIL.lower()


def test_auth_guard():
    r = requests.get(f"{API}/cameras")
    assert r.status_code == 401
    r = requests.get(f"{API}/cameras", headers={"Authorization": "Bearer bogus.token.here"})
    assert r.status_code == 401


# --- Cameras ---
def test_create_and_list_camera():
    r = requests.post(f"{API}/cameras", headers=_auth_headers(),
                      json={"name": "Main Gate", "snapshot_url": GATE_IMG_URL, "site": "HQ"})
    assert r.status_code == 200, r.text
    cam = r.json()
    assert cam["name"] == "Main Gate" and cam["snapshot_url"] == GATE_IMG_URL
    state["camera_id"] = cam["id"]

    r2 = requests.get(f"{API}/cameras", headers=_auth_headers())
    assert r2.status_code == 200
    assert any(c["id"] == cam["id"] for c in r2.json())


# --- Templates ---
def test_templates():
    r = requests.get(f"{API}/templates")
    assert r.status_code == 200
    tpls = r.json()
    assert len(tpls) == 10
    ids = [t["id"] for t in tpls]
    assert "trespasser_night" in ids
    for t in tpls:
        assert "prompt" in t and "sensitivity" in t and "schedule" in t


# --- Detections ---
def test_create_detection_no_samples():
    r = requests.post(f"{API}/detections", headers=_auth_headers(), json={
        "camera_id": state["camera_id"],
        "name": "Person detection",
        "prompt": "Detect if a person is visible in the scene",
        "sensitivity": 0.5,
    })
    assert r.status_code == 200, r.text
    state["detection_id"] = r.json()["id"]


def test_create_detection_with_samples():
    r = requests.post(f"{API}/detections", headers=_auth_headers(), json={
        "camera_id": state["camera_id"],
        "name": "Person detection samples",
        "prompt": "Detect if a person is visible",
        "sample_images_b64": [_TINY_JPEG_B64, _TINY_JPEG_B64],
    })
    assert r.status_code == 200
    state["detection_id2"] = r.json()["id"]


def test_list_detections():
    r = requests.get(f"{API}/detections", headers=_auth_headers())
    assert r.status_code == 200
    assert len(r.json()) >= 2


# --- Analyze (core flow with real Gemini) ---
def test_analyze_deducts_credits_and_stores_event():
    # get balance before
    b = requests.get(f"{API}/credits", headers=_auth_headers()).json()["balance"]
    r = requests.post(f"{API}/analyze", headers=_auth_headers(),
                      json={"detection_id": state["detection_id"]})
    assert r.status_code == 200, r.text
    j = r.json()
    assert "event" in j and j["event"]["caption"], f"caption empty: {j}"
    conf = j["event"]["confidence"]
    assert isinstance(conf, (int, float)) and 0 <= conf <= 1
    state["event_id"] = j["event"]["id"]
    state["was_match"] = j["event"]["match"]

    b2 = requests.get(f"{API}/credits", headers=_auth_headers()).json()["balance"]
    assert b2 == b - 3, f"expected credits -3 got {b2} vs {b}"


# --- Events ---
def test_list_events():
    r = requests.get(f"{API}/events", headers=_auth_headers())
    assert r.status_code == 200
    evs = r.json()
    assert len(evs) >= 1
    # newest-first
    assert evs[0]["id"] == state["event_id"]

    r2 = requests.get(f"{API}/events?only_matches=true", headers=_auth_headers())
    assert r2.status_code == 200
    for e in r2.json():
        assert e["match"] is True


def test_event_feedback_and_ack():
    r = requests.post(f"{API}/events/feedback", headers=_auth_headers(),
                      json={"event_id": state["event_id"], "correct": True})
    assert r.status_code == 200
    r2 = requests.post(f"{API}/events/{state['event_id']}/ack", headers=_auth_headers())
    assert r2.status_code == 200
    ev = requests.get(f"{API}/events/{state['event_id']}", headers=_auth_headers()).json()
    assert ev["feedback"] == "correct" and ev["acknowledged"] is True


# --- Memory Query ---
def test_memory_query():
    r = requests.post(f"{API}/memory/query", headers=_auth_headers(),
                      json={"query": "Did you see any person at the gate?"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert "answer" in j and isinstance(j["answer"], str) and len(j["answer"]) > 0
    assert "citations" in j and isinstance(j["citations"], list)


# --- Channels ---
def test_channels_crud_and_test_dispatch():
    # webhook channel to httpbin
    r = requests.post(f"{API}/channels", headers=_auth_headers(), json={
        "name": "Test Webhook", "kind": "webhook", "config": {"url": "https://postman-echo.com/post"}
    })
    assert r.status_code == 200
    wh_id = r.json()["id"]
    state["webhook_channel"] = wh_id

    # slack channel (fake url - dispatch to httpbin so it doesn't fail HTTP)
    r = requests.post(f"{API}/channels", headers=_auth_headers(), json={
        "name": "Test Slack", "kind": "slack", "config": {"webhook_url": "https://postman-echo.com/post"}
    })
    assert r.status_code == 200
    state["slack_channel"] = r.json()["id"]

    # whatsapp channel — iteration 2: real dispatch. Without BYO keys or 'to', returns error.
    r = requests.post(f"{API}/channels", headers=_auth_headers(), json={
        "name": "WA sim", "kind": "whatsapp", "config": {"to": "+911234567890", "provider": "twilio"}
    })
    assert r.status_code == 200
    wa_id = r.json()["id"]

    # list
    r = requests.get(f"{API}/channels", headers=_auth_headers())
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert wh_id in ids and wa_id in ids

    # test webhook
    r = requests.post(f"{API}/channels/test", headers=_auth_headers(),
                      json={"channel_id": wh_id, "message": "hi"})
    assert r.status_code == 200
    assert r.json()["status"] == "sent", r.json()

    # test whatsapp -> error (no BYO twilio keys for this fresh user)
    r = requests.post(f"{API}/channels/test", headers=_auth_headers(),
                      json={"channel_id": wa_id, "message": "hi"})
    assert r.status_code == 200
    assert r.json()["status"] == "error"

    # patch (toggle enabled)
    r = requests.patch(f"{API}/channels/{wh_id}", headers=_auth_headers(), json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    # re-enable
    requests.patch(f"{API}/channels/{wh_id}", headers=_auth_headers(), json={"enabled": True})

    # delete WA
    r = requests.delete(f"{API}/channels/{wa_id}", headers=_auth_headers())
    assert r.status_code == 200


def test_deliveries():
    r = requests.get(f"{API}/deliveries", headers=_auth_headers())
    assert r.status_code == 200
    assert isinstance(r.json(), list) and len(r.json()) >= 1


# --- Credits ---
def test_credits_and_topup():
    r = requests.get(f"{API}/credits", headers=_auth_headers())
    assert r.status_code == 200
    j = r.json()
    for k in ("balance", "packs", "transactions", "burn_7d", "daily_burn", "rates"):
        assert k in j
    before = j["balance"]

    # Iteration 2: topup now creates a Razorpay order (not direct credit grant)
    r2 = requests.post(f"{API}/credits/topup", headers=_auth_headers(), json={"pack": "starter"})
    assert r2.status_code == 200, r2.text
    j2 = r2.json()
    assert j2["order_id"].startswith("order_")
    assert j2["amount"] == 49900
    assert j2["currency"] == "INR"
    assert j2["key_id"].startswith("rzp_test_")
    assert j2["credits"] == 2000
    assert j2["pack"] == "starter"


# --- API Keys ---
def test_api_keys():
    r = requests.post(f"{API}/api-keys", headers=_auth_headers(), json={"name": "test", "scope": "full"})
    assert r.status_code == 200
    j = r.json()
    assert j["key"].startswith("nv_")
    kid = j["id"]

    r2 = requests.get(f"{API}/api-keys", headers=_auth_headers())
    assert r2.status_code == 200
    keys = r2.json()
    assert any(k["id"] == kid for k in keys)
    # no raw key in list
    for k in keys:
        assert "key" not in k or not k.get("key", "").startswith("nv_")

    r3 = requests.delete(f"{API}/api-keys/{kid}", headers=_auth_headers())
    assert r3.status_code == 200


# --- Analytics ---
def test_analytics_summary():
    r = requests.get(f"{API}/analytics/summary", headers=_auth_headers())
    assert r.status_code == 200
    j = r.json()
    for k in ("totals", "precision", "daily", "busiest_cameras"):
        assert k in j
    assert j["totals"]["cameras"] >= 1
    assert j["totals"]["events"] >= 1


# --- BYO Keys ---
def test_byo_keys():
    r = requests.post(f"{API}/settings/byo", headers=_auth_headers(),
                      json={"openai": {"api_key": "sk-openai-testkey-1234567890"}, "anthropic": {"api_key": "sk-ant-abc12345"}, "gemini": {"api_key": "AIzagem12345"}})
    assert r.status_code == 200
    r2 = requests.get(f"{API}/settings/byo", headers=_auth_headers())
    assert r2.status_code == 200
    masked = r2.json()["keys"]
    assert "openai" in masked


# --- Detection delete + Camera delete cascade ---
def test_delete_detection_and_camera_cascade():
    # delete one detection
    r = requests.delete(f"{API}/detections/{state['detection_id2']}", headers=_auth_headers())
    assert r.status_code == 200

    # delete camera cascades detections
    r = requests.delete(f"{API}/cameras/{state['camera_id']}", headers=_auth_headers())
    assert r.status_code == 200
    r2 = requests.get(f"{API}/detections", headers=_auth_headers())
    assert not any(d["camera_id"] == state["camera_id"] for d in r2.json())
