"""Problem 4: run all 12 practice documents with and without prompt caching.

Every model call (each run makes 2) is saved to output/cache_test.json with the
setup, document, every token count the API reports, and its dollar cost.
"""

import json
from pathlib import Path

from pydantic_ai.messages import ModelResponse

from agent import HERE, cost_usd, make_agent, run
from tools import OUTPUT, now

DOCS = sorted((HERE / "data" / "practice_docs").iterdir())
KEY = {k["file"]: k for k in json.loads((HERE / "data" / "practice_key.json").read_text())}
OUT = OUTPUT / "cache_test.json"
FIELDS = ("vendor", "sku", "unit_price", "lead_time_days", "min_order", "decision")


def main() -> None:
    calls = []
    for setup, cache in (("without_cache", False), ("with_cache", True)):
        agent = make_agent(cache=cache)
        for doc in DOCS:
            rel = doc.relative_to(HERE)
            result = run(rel, agent, setup=setup)
            out = result.output.model_dump()
            correct = all(out[f] == KEY[doc.name][f] for f in FIELDS)
            responses = [m for m in result.all_messages() if isinstance(m, ModelResponse)]
            for i, resp in enumerate(responses, 1):
                u = resp.usage
                calls.append({
                    "setup": setup,
                    "doc": doc.name,
                    "call": i,
                    "time": now(),
                    "response_id": resp.provider_response_id,
                    "input_tokens": u.input_tokens,
                    "cached_input_tokens": u.cache_read_tokens,
                    "cache_write_tokens": u.cache_write_tokens,
                    "uncached_input_tokens": u.input_tokens - u.cache_read_tokens - u.cache_write_tokens,
                    "output_tokens": u.output_tokens,
                    "api_details": dict(u.details),
                    "cost_usd": cost_usd(u),
                    "run_correct_vs_key": correct,
                })
            print(f"{setup:14} {doc.name:32} calls={len(responses)} "
                  f"cached={sum(c['cached_input_tokens'] for c in calls[-len(responses):]):>6} "
                  f"cost=${sum(c['cost_usd']['total'] for c in calls[-len(responses):]):.6f} "
                  f"correct={correct}")
            OUT.write_text(json.dumps(calls, indent=2))


if __name__ == "__main__":
    main()
