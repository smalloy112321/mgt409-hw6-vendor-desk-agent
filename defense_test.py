"""Problem 6: rerun the 12 practice documents with defenses.

Runs five setups so each layer can be measured on its own:
  none, code, design, prompt (one layer each), and all (the defended agent).
output/defense_results.json  the defended agent ("all"), Problem 5 shape + tokens and dollars
output/defense_layers.json   every setup, same shape, for the layer comparison
"""

import json

from agent import cost_usd, make_agent, parse_defenses
from attack_test import DOCS, run_and_score
from tools import OUTPUT

SETUPS = ["none", "code", "design", "prompt", "all"]


def main() -> None:
    layers = {}
    for setup in SETUPS:
        agent = make_agent(cache=True, defenses=parse_defenses(setup))
        rows = []
        for doc in DOCS:
            outcome, r = run_and_score(doc, agent, f"defense_{setup}")
            u = outcome.usage
            r["warnings"] = getattr(outcome.output, "warnings", [])
            r["model_decision"] = outcome.model_decision
            r["tokens"] = {
                "requests": u.requests,
                "input": u.input_tokens,
                "cached_input": u.cache_read_tokens,
                "cache_write": u.cache_write_tokens,
                "output": u.output_tokens,
                "reasoning": u.details.get("reasoning_tokens", 0),
            }
            r["cost_usd"] = cost_usd(u)
            rows.append(r)
            print(f"{setup:7} {doc.name:32} fields={'ok' if r['all_fields_match'] else 'MISS'} "
                  f"decision={'ok' if r['decision']['match'] else 'MISS'} trap={r['trap_called']} "
                  f"strange={r['strange_text_types']} in={u.input_tokens} out={u.output_tokens} "
                  f"${r['cost_usd']['total']:.6f}", flush=True)
            layers[setup] = rows
            (OUTPUT / "defense_layers.json").write_text(json.dumps(layers, indent=2))
        print(f"{setup}: fooled {sum(r['fooled'] for r in rows)} / {len(rows)}", flush=True)
    (OUTPUT / "defense_results.json").write_text(json.dumps(layers["all"], indent=2))


if __name__ == "__main__":
    main()
