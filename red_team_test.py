"""Problem 7: run our two attacks on the agent with no defenses, then with all defenses.

Writes output/red_team_results.json (Problem 5 shape, scored against
data/my_attacks/my_attacks_key.json).
"""

import json

from agent import HERE, cost_usd, make_agent, parse_defenses
from attack_test import run_and_score
from tools import OUTPUT

ATTACKS = HERE / "data" / "my_attacks"
KEY = {k["file"]: k for k in json.loads((ATTACKS / "my_attacks_key.json").read_text())}
DOCS = [ATTACKS / name for name in KEY]


def main() -> None:
    results = {}
    for setup in ("none", "all"):
        agent = make_agent(cache=True, defenses=parse_defenses(setup))
        rows = []
        for doc in DOCS:
            outcome, r = run_and_score(doc, agent, f"red_team_{setup}", KEY[doc.name])
            r["warnings"] = getattr(outcome.output, "warnings", [])
            r["model_decision"] = outcome.model_decision
            r["cost_usd"] = cost_usd(outcome.usage)["total"]
            rows.append(r)
            bad = {k: (v["answer"], v["key"]) for k, v in r["fields"].items() if not v["match"]}
            print(f"{setup:5} {doc.name:30} fooled={r['fooled']} wrong={bad} "
                  f"decision={r['decision']['answer']} trap={r['trap_called']} warnings={r['warnings']}")
        results[setup] = rows
    (OUTPUT / "red_team_results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
