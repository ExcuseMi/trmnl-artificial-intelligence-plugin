import logging
import os

import httpx

logger = logging.getLogger(__name__)

AA_BASE = "https://artificialanalysis.ai/api/v2"
TRMNL_IPS_API = "https://trmnl.com/api/ips"


def _headers() -> dict:
    return {"x-api-key": os.environ["AA_API_KEY"]}


def _get(path: str) -> dict:
    url = f"{AA_BASE}{path}"
    logger.info("Fetching %s", url)
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, headers=_headers())
        resp.raise_for_status()
    return resp.json()


# ---------- public fetch functions ----------

def fetch_llms() -> dict:
    raw = _get("/data/llms/models")
    return _transform_llms(raw.get("data", []))


def fetch_text_to_image() -> dict:
    raw = _get("/data/media/text-to-image")
    return _transform_media(raw.get("data", []))


def fetch_text_to_speech() -> dict:
    raw = _get("/data/media/text-to-speech")
    return _transform_media(raw.get("data", []))


def fetch_text_to_video() -> dict:
    raw = _get("/data/media/text-to-video")
    return _transform_media(raw.get("data", []))


def fetch_image_to_video() -> dict:
    raw = _get("/data/media/image-to-video")
    return _transform_media(raw.get("data", []))


def fetch_trmnl_ips() -> list[str]:
    logger.info("Fetching TRMNL IPs")
    with httpx.Client(timeout=10) as client:
        resp = client.get(TRMNL_IPS_API)
        resp.raise_for_status()
    data = resp.json().get("data", {})
    return data.get("ipv4", []) + data.get("ipv6", [])


# ---------- transformations ----------

def _transform_llms(models: list[dict]) -> dict:
    parsed = []
    for m in models:
        evals = m.get("evaluations") or {}
        intelligence = evals.get("artificial_analysis_intelligence_index")
        if intelligence is None:
            continue

        entry = {
            "name": m.get("name", ""),
            "creator": (m.get("model_creator") or {}).get("name", ""),
            "intelligence": round(float(intelligence), 1),
        }
        coding = _round_or_none(evals.get("artificial_analysis_coding_index"))
        math = _round_or_none(evals.get("artificial_analysis_math_index"))
        if coding is not None:
            entry["coding"] = coding
        if math is not None:
            entry["math"] = math

        parsed.append(entry)

    parsed.sort(key=lambda x: x["intelligence"], reverse=True)
    for i, m in enumerate(parsed, 1):
        m["rank"] = i

    return {
        "models": parsed[:10],
        "total_models": len(parsed),
    }


def _transform_media(models: list[dict]) -> dict:
    parsed = []
    for m in models:
        elo = m.get("elo_rating") or m.get("elo")
        if elo is None:
            continue
        parsed.append({
            "name": m.get("name", ""),
            "creator": (m.get("model_creator") or {}).get("name", ""),
            "elo": round(float(elo)),
        })

    parsed.sort(key=lambda x: x["elo"], reverse=True)
    for i, m in enumerate(parsed, 1):
        m["rank"] = i

    return {
        "models": parsed[:10],
        "total_models": len(parsed),
    }


def _round_or_none(val) -> float | None:
    if val is None:
        return None
    try:
        return round(float(val), 1)
    except (TypeError, ValueError):
        return None
