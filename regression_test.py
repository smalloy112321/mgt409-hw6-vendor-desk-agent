"""Problem 8: check the hardened agent still gets all 12 practice documents right
and now stops both Problem 7 attacks. Writes output/regression_results.json."""

import json

from agent import make_agent, parse_defenses
from attack_test import DOCS, run_and_score
from red_team_test import DOCS as ATTACK_DOCS, KEY as ATTACK_KEY
from tools import OUTPUT


def main() -> None:
    agent = make_agent(cache=True, defenses=parse_defenses("all"))
    rows = []
    for doc in DOCS + ATTACK_DOCS:
        outcome, r = run_and_score(doc, agent, "regression_all", ATTACK_KEY.get(doc.name))
        r["warnings"] = getattr(outcome.output, "warnings", [])
        rows.append(r)
        bad = {k: (v["answer"], v["key"]) for k, v in r["fields"].items() if not v["match"]}
        print(f"{doc.name:32} fooled={r['fooled']} wrong={bad} decision={r['decision']['answer']} "
              f"trap={r['trap_called']} warnings={r['warnings']}", flush=True)
    (OUTPUT / "regression_results.json").write_text(json.dumps(rows, indent=2))
    print(f"\nFooled: {sum(r['fooled'] for r in rows)} / {len(rows)}")


if __name__ == "__main__":
    main()
