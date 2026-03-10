import logging
import os

import httpx

logger = logging.getLogger(__name__)

AA_BASE = "https://artificialanalysis.ai/api/v2"
TRMNL_IPS_API = "https://trmnl.com/api/ips"

LOCALHOST_IPS = {"127.0.0.1", "::1", "172.0.0.0/8"}


def _headers() -> dict:
    return {"x-api-key": os.environ["AA_API_KEY"]}


def fetch_llm_models() -> dict:
    url = f"{AA_BASE}/data/llms/models"
    logger.info("Fetching LLM models from %s", url)
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, headers=_headers())
        resp.raise_for_status()
    raw = resp.json()
    return _transform_llms(raw.get("data", []))


def fetch_trmnl_ips() -> list[str]:
    logger.info("Fetching TRMNL IPs")
    with httpx.Client(timeout=10) as client:
        resp = client.get(TRMNL_IPS_API)
        resp.raise_for_status()
    data = resp.json().get("data", {})
    return data.get("ipv4", []) + data.get("ipv6", [])


# ---------- transformation ----------

def _transform_llms(models: list[dict]) -> dict:
    parsed = []
    for m in models:
        evals = m.get("evaluations") or {}
        perf = m.get("performance") or {}
        pricing = m.get("pricing") or {}

        intelligence = evals.get("artificial_analysis_intelligence_index")
        if intelligence is None:
            continue

        creator = (m.get("model_creator") or {}).get("name", "")
        parsed.append({
            "name": m.get("name", ""),
            "creator": creator,
            "intelligence": round(float(intelligence), 1),
            "coding": _round_or_none(evals.get("artificial_analysis_coding_index")),
            "math": _round_or_none(evals.get("artificial_analysis_math_index")),
            "speed_tps": _round_or_none(perf.get("output_speed")),
            "ttft_s": _round_or_none(perf.get("time_to_first_token")),
            "price_input": _round_or_none(pricing.get("input_cost_per_million_tokens")),
            "price_output": _round_or_none(pricing.get("output_cost_per_million_tokens")),
        })

    parsed.sort(key=lambda x: x["intelligence"], reverse=True)
    for i, m in enumerate(parsed, 1):
        m["rank"] = i

    fastest = sorted(
        [m for m in parsed if m["speed_tps"] is not None],
        key=lambda x: x["speed_tps"],
        reverse=True,
    )[:5]

    best_value = _best_value(parsed)

    return {
        "top_models": parsed[:10],
        "fastest_models": fastest,
        "best_value_models": best_value,
        "total_models": len(parsed),
    }


def _best_value(models: list[dict]) -> list[dict]:
    candidates = [
        m for m in models
        if m["price_output"] is not None and m["price_output"] > 0
    ]
    scored = sorted(
        candidates,
        key=lambda x: x["intelligence"] / x["price_output"],
        reverse=True,
    )
    return scored[:5]


def _round_or_none(val) -> float | None:
    if val is None:
        return None
    try:
        return round(float(val), 2)
    except (TypeError, ValueError):
        return None
