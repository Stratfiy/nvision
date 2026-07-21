"""NVision iteration 2: Razorpay checkout, Zone editor, Twilio BYO WhatsApp dispatch."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://scout-ai-30.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

GATE_IMG_URL = "https://images.pexels.com/photos/36162857/pexels-photo-36162857.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
PASSWORD = "Testpass123!"


@pytest.fixture(scope="module")
def user_ctx():
    email = f"TEST_it2_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": PASSWORD, "name": "IT2 Tester"})
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    return {"email": email, "token": tok, "headers": {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}}


@pytest.fixture(scope="module")
def fresh_user_ctx():
    """A completely fresh user WITHOUT BYO keys — used for the 'no twilio keys' test."""
    email = f"TEST_it2fresh_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": PASSWORD, "name": "IT2 Fresh"})
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    return {"email": email, "token": tok, "headers": {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}}


# ============ RAZORPAY ============
def test_razorpay_topup_starter_returns_order(user_ctx):
    r = requests.post(f"{API}/credits/topup", headers=user_ctx["headers"], json={"pack": "starter"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["order_id"].startswith("order_"), j
    assert j["amount"] == 49900  # ₹499 * 100 paise
    assert j["currency"] == "INR"
    assert j["key_id"].startswith("rzp_test_"), j["key_id"]
    assert j["credits"] == 2000
    assert j["pack"] == "starter"
    assert "user" in j and "email" in j["user"]


def test_razorpay_topup_invalid_pack_400(user_ctx):
    r = requests.post(f"{API}/credits/topup", headers=user_ctx["headers"], json={"pack": "foo"})
    assert r.status_code == 400, r.text


def test_razorpay_verify_bad_signature_400(user_ctx):
    r = requests.post(f"{API}/credits/verify", headers=user_ctx["headers"], json={
        "razorpay_order_id": "order_fakeXYZ",
        "razorpay_payment_id": "pay_fakeXYZ",
        "razorpay_signature": "invalid_signature_deadbeef",
    })
    assert r.status_code == 400, r.text
    assert "signature" in r.text.lower()


# ============ CAMERA ZONES ============
def test_camera_create_with_zones_and_patch(user_ctx):
    zones = [{"name": "A", "points": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]}]
    r = requests.post(f"{API}/cameras", headers=user_ctx["headers"], json={
        "name": "Zone cam", "snapshot_url": GATE_IMG_URL, "zones": []
    })
    assert r.status_code == 200
    cam = r.json()
    cid = cam["id"]
    assert cam.get("zones", []) == []

    # PATCH zones
    r2 = requests.patch(f"{API}/cameras/{cid}", headers=user_ctx["headers"], json={"zones": zones})
    assert r2.status_code == 200, r2.text
    cam2 = r2.json()
    assert cam2["zones"] == zones

    # GET reflects zones
    r3 = requests.get(f"{API}/cameras/{cid}", headers=user_ctx["headers"])
    assert r3.status_code == 200
    assert r3.json()["zones"] == zones


def test_zone_aware_analyze_returns_valid_event(user_ctx):
    zones = [{"name": "Center", "points": [[0.3, 0.3], [0.7, 0.3], [0.7, 0.7], [0.3, 0.7]]}]
    r = requests.post(f"{API}/cameras", headers=user_ctx["headers"], json={
        "name": "Zone analyze cam", "snapshot_url": GATE_IMG_URL, "zones": zones
    })
    assert r.status_code == 200
    cid = r.json()["id"]

    r = requests.post(f"{API}/detections", headers=user_ctx["headers"], json={
        "camera_id": cid, "name": "person detection",
        "prompt": "Detect any person visible in the scene.",
        "sensitivity": 0.5,
    })
    assert r.status_code == 200
    did = r.json()["id"]

    r = requests.post(f"{API}/analyze", headers=user_ctx["headers"], json={"detection_id": did})
    assert r.status_code == 200, r.text
    j = r.json()
    assert "event" in j and isinstance(j["event"]["caption"], str) and len(j["event"]["caption"]) > 0


# ============ TWILIO BYO ============
def test_byo_twilio_save_and_get_masked(user_ctx):
    r = requests.post(f"{API}/settings/byo", headers=user_ctx["headers"], json={
        "twilio": {"sid": "AC_test_1234567890", "token": "tok_test_abcdefghij", "from": "whatsapp:+14155238886"}
    })
    assert r.status_code == 200
    assert r.json().get("ok") is True

    r2 = requests.get(f"{API}/settings/byo", headers=user_ctx["headers"])
    assert r2.status_code == 200
    keys = r2.json()["keys"]
    assert "twilio" in keys
    assert isinstance(keys["twilio"], dict)
    # Should have sid, token, from — masked (partial redaction)
    for f in ("sid", "token", "from"):
        assert f in keys["twilio"], f"missing field {f} in masked twilio"
    # Verify masking present ("…" character indicates truncation)
    assert "…" in keys["twilio"]["sid"] or "•" in keys["twilio"]["sid"]


def test_whatsapp_with_byo_twilio_attempts_real_call(user_ctx):
    """With BYO Twilio fake creds, dispatch attempts real API call and fails → status=error (NOT simulated)."""
    r = requests.post(f"{API}/channels", headers=user_ctx["headers"], json={
        "name": "WA test", "kind": "whatsapp",
        "config": {"to": "+15551234567", "provider": "twilio"}
    })
    assert r.status_code == 200
    ch_id = r.json()["id"]

    r = requests.post(f"{API}/channels/test", headers=user_ctx["headers"], json={
        "channel_id": ch_id, "message": "hi"
    })
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "error", f"expected error (fake creds); got {j}"
    # detail should reference twilio (real call attempted)
    assert "twilio" in j.get("detail", "").lower() or "auth" in j.get("detail", "").lower() or "20003" in j.get("detail", "").lower(), j


def test_whatsapp_without_byo_returns_no_keys_error(fresh_user_ctx):
    r = requests.post(f"{API}/channels", headers=fresh_user_ctx["headers"], json={
        "name": "WA no-keys", "kind": "whatsapp",
        "config": {"to": "+15551234567", "provider": "twilio"}
    })
    assert r.status_code == 200
    ch_id = r.json()["id"]

    r = requests.post(f"{API}/channels/test", headers=fresh_user_ctx["headers"], json={
        "channel_id": ch_id, "message": "hi"
    })
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "error"
    assert "no twilio keys" in j.get("detail", "").lower(), j


# ============ REGRESSION: Slack + Webhook + Email/Teams ============
def test_slack_and_webhook_channels_still_send(fresh_user_ctx):
    # webhook
    r = requests.post(f"{API}/channels", headers=fresh_user_ctx["headers"], json={
        "name": "WH", "kind": "webhook", "config": {"url": "https://postman-echo.com/post"}
    })
    assert r.status_code == 200
    wh_id = r.json()["id"]
    r = requests.post(f"{API}/channels/test", headers=fresh_user_ctx["headers"],
                      json={"channel_id": wh_id, "message": "hi"})
    assert r.status_code == 200
    assert r.json()["status"] == "sent", r.json()

    # slack (send to postman-echo — 200 response passes)
    r = requests.post(f"{API}/channels", headers=fresh_user_ctx["headers"], json={
        "name": "SL", "kind": "slack", "config": {"webhook_url": "https://postman-echo.com/post"}
    })
    assert r.status_code == 200
    sl_id = r.json()["id"]
    r = requests.post(f"{API}/channels/test", headers=fresh_user_ctx["headers"],
                      json={"channel_id": sl_id, "message": "hi"})
    assert r.status_code == 200
    assert r.json()["status"] == "sent", r.json()


def test_email_and_teams_remain_simulated(fresh_user_ctx):
    for kind, cfg in [("email", {"to": "x@example.com"}), ("teams", {"url": "https://outlook.office.com/webhook/xxx"})]:
        r = requests.post(f"{API}/channels", headers=fresh_user_ctx["headers"], json={
            "name": f"{kind} ch", "kind": kind, "config": cfg
        })
        assert r.status_code == 200
        ch_id = r.json()["id"]
        r = requests.post(f"{API}/channels/test", headers=fresh_user_ctx["headers"],
                          json={"channel_id": ch_id, "message": "hi"})
        assert r.status_code == 200
        assert r.json()["status"] == "simulated", (kind, r.json())
