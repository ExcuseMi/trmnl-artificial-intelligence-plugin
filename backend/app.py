import fcntl
import logging
import os
from functools import wraps

from flask import Flask, jsonify, request

import db
import fetcher
import scheduler as sched

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

ENABLE_IP_WHITELIST = os.environ.get("ENABLE_IP_WHITELIST", "false").lower() == "true"
LOCALHOST_IPS = {"127.0.0.1", "::1"}


# ---------- IP whitelist ----------

def require_trmnl_ip(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not ENABLE_IP_WHITELIST:
            return f(*args, **kwargs)

        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        client_ip = client_ip.split(",")[0].strip()

        allowed = db.get_trmnl_ips() or set()
        allowed |= LOCALHOST_IPS

        if client_ip not in allowed:
            logger.warning("Blocked request from %s", client_ip)
            return jsonify({"error": "Forbidden"}), 403
        return f(*args, **kwargs)
    return wrapper


# ---------- routes ----------

@app.get("/health")
def health():
    return jsonify({"status": "ok"})


def _snapshot_route(snapshot_type: str, fetch_fn):
    data = db.get_snapshot(snapshot_type)
    if data is None:
        try:
            data = fetch_fn()
            db.save_snapshot(snapshot_type, data)
        except Exception as e:
            logger.error("On-demand fetch failed for %s: %s", snapshot_type, e)
            return jsonify({}), 200
    return jsonify({"data": data}), 200


@app.get("/llms")
@require_trmnl_ip
def get_llms():
    return _snapshot_route("llms", fetcher.fetch_llms)


@app.get("/text-to-image")
@require_trmnl_ip
def get_text_to_image():
    return _snapshot_route("text-to-image", fetcher.fetch_text_to_image)


@app.get("/text-to-speech")
@require_trmnl_ip
def get_text_to_speech():
    return _snapshot_route("text-to-speech", fetcher.fetch_text_to_speech)


@app.get("/text-to-video")
@require_trmnl_ip
def get_text_to_video():
    return _snapshot_route("text-to-video", fetcher.fetch_text_to_video)


@app.get("/image-to-video")
@require_trmnl_ip
def get_image_to_video():
    return _snapshot_route("image-to-video", fetcher.fetch_image_to_video)


@app.get("/all")
@require_trmnl_ip
def get_all():
    sources = [
        ("llms",           fetcher.fetch_llms),
        ("text-to-image",  fetcher.fetch_text_to_image),
        ("text-to-speech", fetcher.fetch_text_to_speech),
        ("text-to-video",  fetcher.fetch_text_to_video),
        ("image-to-video", fetcher.fetch_image_to_video),
    ]
    result = {}
    errors = {}
    for snapshot_type, fetch_fn in sources:
        data = db.get_snapshot(snapshot_type)
        if data is None:
            try:
                data = fetch_fn()
                db.save_snapshot(snapshot_type, data)
            except Exception as e:
                logger.error("On-demand fetch failed for %s: %s", snapshot_type, e)
                errors[snapshot_type] = "unavailable"
                continue
        result[snapshot_type] = data

    return jsonify({"data": result}), 200


# ---------- startup ----------

_BOOTSTRAP_LOCK_PATH = "/data/scheduler.lock"
_bootstrap_lock_fd = None  # held open for process lifetime to keep the lock


def _bootstrap():
    global _bootstrap_lock_fd
    db.init_db()

    # Only one gunicorn worker should run the scheduler and initial fetch.
    # Grab a non-blocking exclusive file lock; the other workers skip silently.
    lock_fd = open(_BOOTSTRAP_LOCK_PATH, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_fd.close()
        logger.info("Another worker holds the bootstrap lock — skipping scheduler init")
        return

    _bootstrap_lock_fd = lock_fd  # keep open so the lock is held until process exits

    sched.refresh_trmnl_ips()
    sched.refresh_all()
    scheduler = sched.create_scheduler()
    scheduler.start()
    logger.info("Scheduler started. IP whitelist: %s", ENABLE_IP_WHITELIST)


_bootstrap()
