"""NVision ingestion worker.

Pulls active RTSP cameras from the backend, runs a cheap motion gate on
downscaled low-fps frames, and POSTs qualifying frames to the backend for
VLM analysis. The VLM is NEVER called from here — cost control lives in the
backend (per-detection cooldown) and in this worker's motion gate.

Config via env:
  BACKEND_URL                 backend base URL (default http://localhost:8000)
  WORKER_TOKEN                shared secret for /api/internal/* (required)
  POLL_INTERVAL_SECONDS       camera list refresh (default 15)
  SAMPLE_FPS                  motion sampling rate, 2-5 (default 3)
  MAX_FRAME_WIDTH             downscale ceiling in px (default 640)
  MOTION_MIN_AREA_PCT         min contour area as % of frame (default 0.5)
  MOTION_SUSTAINED_FRAMES     consecutive motion frames required (default 2)
  INGEST_MIN_INTERVAL_SECONDS min seconds between ingest POSTs per camera (default 20)
  JPEG_QUALITY                snapshot quality (default 80)
"""
import base64
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone

# Force TCP transport before cv2 opens any RTSP stream
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|stimeout;10000000")

import cv2
import requests

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")
WORKER_TOKEN = os.environ.get("WORKER_TOKEN", "")
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL_SECONDS", "15"))
SAMPLE_FPS = min(5.0, max(2.0, float(os.environ.get("SAMPLE_FPS", "3"))))
MAX_FRAME_WIDTH = int(os.environ.get("MAX_FRAME_WIDTH", "640"))
MOTION_MIN_AREA_PCT = float(os.environ.get("MOTION_MIN_AREA_PCT", "0.5"))
MOTION_SUSTAINED_FRAMES = int(os.environ.get("MOTION_SUSTAINED_FRAMES", "2"))
INGEST_MIN_INTERVAL = float(os.environ.get("INGEST_MIN_INTERVAL_SECONDS", "20"))
PREVIEW_INTERVAL = float(os.environ.get("PREVIEW_INTERVAL_SECONDS", "15"))
JPEG_QUALITY = int(os.environ.get("JPEG_QUALITY", "80"))
OFFLINE_AFTER_FAILURES = 3
BACKOFF_START = 2.0
BACKOFF_CAP = 60.0

logging.basicConfig(level=logging.INFO, format="%(asctime)s - worker - %(levelname)s - %(message)s")
log = logging.getLogger("nvision.worker")

_CRED_RE = re.compile(r"((?:rtsp|rtsps|rtmp|http|https)://)([^/@:\s]+)(?::[^/@\s]+)?@")


def mask_url(url: str) -> str:
    """Never log RTSP credentials."""
    return _CRED_RE.sub(r"\1\2:•••@", url or "")


def api(method: str, path: str, **kwargs):
    kwargs.setdefault("timeout", 30)
    headers = kwargs.pop("headers", {})
    headers["X-Worker-Token"] = WORKER_TOKEN
    return requests.request(method, f"{BACKEND_URL}/api{path}", headers=headers, **kwargs)


class CameraWorker(threading.Thread):
    """Supervised per-camera loop: connect -> motion gate -> ingest -> reconnect."""

    def __init__(self, cam: dict):
        super().__init__(daemon=True, name=f"cam-{cam['id'][:8]}")
        self.cam_id = cam["id"]
        self.cam_name = cam["name"]
        self.rtsp_url = cam["rtsp_url"]
        self.stop_event = threading.Event()
        self.reported_status = None

    def stop(self):
        self.stop_event.set()

    def report_status(self, status: str):
        if status == self.reported_status:
            return
        try:
            r = api("POST", f"/internal/cameras/{self.cam_id}/status", json={"status": status})
            if r.ok:
                self.reported_status = status
                log.info("camera=%s status=%s reported", self.cam_id, status)
            else:
                log.warning("camera=%s status report failed HTTP %s", self.cam_id, r.status_code)
        except requests.RequestException as e:
            log.warning("camera=%s status report error: %s", self.cam_id, e)

    def push_preview(self, frame):
        """Send a periodic still (no motion required) for the UI preview / zone editor."""
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ok:
            return
        try:
            api("POST", f"/internal/cameras/{self.cam_id}/frame", json={
                "image_b64": base64.b64encode(buf.tobytes()).decode(),
                "ts": datetime.now(timezone.utc).isoformat(),
            }, timeout=30)
        except requests.RequestException:
            pass

    def ingest(self, frame) -> bool:
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ok:
            return False
        payload = {
            "camera_id": self.cam_id,
            "image_b64": base64.b64encode(buf.tobytes()).decode(),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        try:
            r = api("POST", "/internal/ingest", json=payload, timeout=90)
            log.info("ingest camera=%s bytes=%d HTTP %s", self.cam_id, len(buf), r.status_code)
            return r.ok
        except requests.RequestException as e:
            log.warning("ingest camera=%s failed: %s", self.cam_id, e)
            return False

    def run(self):
        backoff = BACKOFF_START
        failures = 0
        log.info("camera=%s starting loop url=%s", self.cam_id, mask_url(self.rtsp_url))
        while not self.stop_event.is_set():
            cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                cap.release()
                failures += 1
                log.warning("camera=%s connect failed (attempt %d), retry in %.0fs", self.cam_id, failures, backoff)
                if failures >= OFFLINE_AFTER_FAILURES:
                    self.report_status("offline")
                if self.stop_event.wait(backoff):
                    break
                backoff = min(backoff * 2, BACKOFF_CAP)
                continue

            log.info("camera=%s connected", self.cam_id)
            failures = 0
            backoff = BACKOFF_START
            self.report_status("online")
            try:
                self.stream_loop(cap)
            finally:
                cap.release()
            if not self.stop_event.is_set():
                failures += 1
                log.warning("camera=%s stream dropped, reconnecting in %.0fs", self.cam_id, backoff)
                if failures >= OFFLINE_AFTER_FAILURES:
                    self.report_status("offline")
                if self.stop_event.wait(backoff):
                    break
                backoff = min(backoff * 2, BACKOFF_CAP)
        log.info("camera=%s loop stopped", self.cam_id)

    def stream_loop(self, cap):
        subtractor = cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=32, detectShadows=True)
        sample_interval = 1.0 / SAMPLE_FPS
        next_sample = time.monotonic()
        last_ingest = 0.0
        last_preview = 0.0
        motion_streak = 0
        read_errors = 0
        warmup_frames = int(SAMPLE_FPS * 3)  # let the background model settle

        while not self.stop_event.is_set():
            # keep the stream drained; only decode/process at the sample rate
            if not cap.grab():
                read_errors += 1
                if read_errors >= 25:
                    return  # stream is dead — reconnect with backoff
                time.sleep(0.1)
                continue
            read_errors = 0

            now = time.monotonic()
            if now < next_sample:
                continue
            next_sample = now + sample_interval

            ok, frame = cap.retrieve()
            if not ok or frame is None:
                continue

            if frame.shape[1] > MAX_FRAME_WIDTH:
                scale = MAX_FRAME_WIDTH / frame.shape[1]
                frame = cv2.resize(frame, (MAX_FRAME_WIDTH, int(frame.shape[0] * scale)))

            # periodic preview still for the UI (independent of motion/VLM)
            if time.monotonic() - last_preview >= PREVIEW_INTERVAL:
                self.push_preview(frame)
                last_preview = time.monotonic()

            fg = subtractor.apply(frame)
            if warmup_frames > 0:
                warmup_frames -= 1
                continue
            # drop shadows (127) and noise, then measure moving regions
            _, fg = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)
            fg = cv2.dilate(fg, None, iterations=2)
            contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            min_area = frame.shape[0] * frame.shape[1] * (MOTION_MIN_AREA_PCT / 100.0)
            moving = any(cv2.contourArea(c) >= min_area for c in contours)

            if moving:
                motion_streak += 1
            else:
                motion_streak = 0

            if motion_streak >= MOTION_SUSTAINED_FRAMES:
                if time.monotonic() - last_ingest >= INGEST_MIN_INTERVAL:
                    log.info("motion camera=%s streak=%d area_gate=%.0fpx", self.cam_id, motion_streak, min_area)
                    if self.ingest(frame):
                        last_ingest = time.monotonic()
                motion_streak = 0


def main():
    if not WORKER_TOKEN:
        raise SystemExit("WORKER_TOKEN env var is required")
    log.info("worker starting backend=%s sample_fps=%.1f max_width=%d min_area=%.2f%% sustained=%d",
             BACKEND_URL, SAMPLE_FPS, MAX_FRAME_WIDTH, MOTION_MIN_AREA_PCT, MOTION_SUSTAINED_FRAMES)

    workers: dict = {}
    while True:
        try:
            r = api("GET", "/internal/cameras/active")
            r.raise_for_status()
            cams = {c["id"]: c for c in r.json()}
        except requests.RequestException as e:
            log.warning("camera poll failed: %s", e)
            time.sleep(POLL_INTERVAL)
            continue

        # start new / restart changed
        for cam_id, cam in cams.items():
            w = workers.get(cam_id)
            if w and w.is_alive() and w.rtsp_url == cam["rtsp_url"]:
                continue
            if w:
                log.info("camera=%s config changed or thread dead — restarting", cam_id)
                w.stop()
            workers[cam_id] = CameraWorker(cam)
            workers[cam_id].start()

        # stop removed
        for cam_id in list(workers):
            if cam_id not in cams:
                log.info("camera=%s no longer active — stopping", cam_id)
                workers[cam_id].stop()
                del workers[cam_id]

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
