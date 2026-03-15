import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

AA_BASE = "https://artificialanalysis.ai/api/v2"
TRMNL_IPS_API = "https://trmnl.com/api/ips"


def _headers() -> dict:
    return {"x-api-key": os.environ["AA_API_KEY"]}


def _get(path: str, retries: int = 3) -> dict:
    url = f"{AA_BASE}{path}"
    logger.info("Fetching %s", url)
    delay = 10
    with httpx.Client(timeout=30) as client:
        for attempt in range(retries):
            resp = client.get(url, headers=_headers())
            if resp.status_code == 429 and attempt < retries - 1:
                reset = resp.headers.get("X-RateLimit-Reset")
                wait = max(int(reset) - int(time.time()), delay) if reset else delay
                logger.warning("429 on %s — retrying in %ds (attempt %d/%d)", url, wait, attempt + 1, retries)
                time.sleep(wait)
                delay *= 2
                continue
            resp.raise_for_status()
            return resp.json()
    resp.raise_for_status()  # final attempt failed


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


def fetch_image_editing() -> dict:
    raw = _get("/data/media/image-editing")
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

        pricing = m.get("pricing") or {}
        entry = {
            "name": m.get("name", ""),
            "creator": (m.get("model_creator") or {}).get("name", ""),
            "intelligence": round(float(intelligence), 1),
        }
        for key, val in {
            "coding":       evals.get("artificial_analysis_coding_index"),
            "math":         evals.get("artificial_analysis_math_index"),
            "speed_tps":    m.get("median_output_tokens_per_second"),
            "ttft_s":       m.get("median_time_to_first_token_seconds"),
            "price_input":  pricing.get("price_1m_input_tokens"),
            "price_output": pricing.get("price_1m_output_tokens"),
        }.items():
            rounded = _round_or_none(val)
            if rounded is not None:
                entry[key] = rounded

        parsed.append(entry)

    parsed.sort(key=lambda x: x["intelligence"], reverse=True)
    for i, m in enumerate(parsed, 1):
        m["rank"] = i

    fastest = sorted(
        [m for m in parsed if "speed_tps" in m],
        key=lambda x: x["speed_tps"],
        reverse=True,
    )[:5]

    best_value = sorted(
        [m for m in parsed if m.get("price_output", 0) > 0],
        key=lambda x: x["intelligence"] / x["price_output"],
        reverse=True,
    )[:5]

    return {
        "models": parsed[:10],
        "fastest": fastest,
        "best_value": best_value,
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
