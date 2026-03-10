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


@app.get("/webhook")
@require_trmnl_ip
def webhook():
    data = db.get_snapshot("llms")
    if data is None:
        # Fetch on-demand if nothing cached yet (first run)
        try:
            data = fetcher.fetch_llm_models()
            db.save_snapshot("llms", data)
        except Exception as e:
            logger.error("On-demand fetch failed: %s", e)
            return jsonify({"error": "Data unavailable, try again later"}), 503
    return jsonify(data)


# ---------- startup ----------

def _bootstrap():
    db.init_db()
    sched.refresh_trmnl_ips()
    sched.refresh_llm_data()
    scheduler = sched.create_scheduler()
    scheduler.start()
    logger.info("Scheduler started. IP whitelist: %s", ENABLE_IP_WHITELIST)


_bootstrap()
