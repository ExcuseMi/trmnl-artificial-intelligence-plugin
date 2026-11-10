"""Run: python3 backend/test_fetcher.py (no dependencies beyond the backend's own)."""
import sys
import types

sys.modules.setdefault("httpx", types.ModuleType("httpx"))
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from fetcher import _transform_llms  # noqa: E402


def model(**extra):
    m = {"name": "M", "model_creator": {"name": "C"},
         "evaluations": {"artificial_analysis_intelligence_index": 50}}
    m.update(extra)
    return m


def first(m):
    return _transform_llms([m])["models"][0]


# performance_v3 is read (from 2026-12-10 the old block is empty)
e = first(model(performance_v3={"mean_output_tokens_per_second": 54.57, "mean_time_to_first_token_seconds": 3.91},
                performance={}))
assert e["speed_tps"] == 54.6 and e["ttft_s"] == 3.9, e
# v3 wins over the old block
e = first(model(performance_v3={"mean_output_tokens_per_second": 10, "mean_time_to_first_token_seconds": 1},
                performance={"median_output_tokens_per_second": 99, "median_time_to_first_token_seconds": 9}))
assert e["speed_tps"] == 10 and e["ttft_s"] == 1, e
# old block still used when v3 is missing
e = first(model(performance={"median_output_tokens_per_second": 65.89, "median_time_to_first_token_seconds": 3.36}))
assert e["speed_tps"] == 65.9 and e["ttft_s"] == 3.4, e
# neither: no speed keys, model still listed, not in fastest
r = _transform_llms([model()])
assert "speed_tps" not in r["models"][0] and r["fastest"] == [], r
print("ok")
