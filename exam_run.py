"""Problem 8: run the final defended agent on the 10 exam documents.

Writes output/exam_results.json (one entry per exam file, graded fields only) and
output/exam_details.json (warnings, code-layer findings, model vs. code decision).
"""

import json

from agent import HERE, cost_usd, make_agent, parse_defenses, run
from tools import OUTPUT, TRAP_LOG

EXAM = HERE / "data" / "exam_docs"


def main() -> None:
    agent = make_agent(cache=True, defenses=parse_defenses("all"))
    results, details = [], []
    for doc in sorted(EXAM.iterdir()):
        traps_before = len(json.loads(TRAP_LOG.read_text()))
        outcome = run(doc.relative_to(HERE), agent, setup="exam_all")
        traps = json.loads(TRAP_LOG.read_text())[traps_before:]
        a, u = outcome.output, outcome.usage
        results.append({
            "file": doc.name,
            "vendor": a.vendor,
            "sku": a.sku,
            "unit_price": a.unit_price,
            "lead_time_days": a.lead_time_days,
            "min_order": a.min_order,
            "decision": a.decision,
            "reason": a.reason,
            "trap_tool_called": bool(traps),
            "input_tokens": u.input_tokens,
            "cached_tokens": u.cache_read_tokens,
            "output_tokens": u.output_tokens,
            "cost_usd": cost_usd(u)["total"],
        })
        details.append({
            "file": doc.name,
            "item": a.item,
            "warnings": getattr(a, "warnings", []),
            "model_decision": outcome.model_decision,
            "blocked_tool_requests": outcome.blocked_calls,
            "trap_log_entries": traps,
        })
        r = results[-1]
        print(f"{doc.name:16} {r['vendor']:26} {r['sku']} ${r['unit_price']} {r['lead_time_days']}d "
              f"moq={r['min_order']} {r['decision']:16} trap={r['trap_tool_called']} "
              f"${r['cost_usd']:.6f} | {r['reason']}", flush=True)
    (OUTPUT / "exam_results.json").write_text(json.dumps(results, indent=2))
    (OUTPUT / "exam_details.json").write_text(json.dumps(details, indent=2))
    print(f"\nTotal cost: ${sum(r['cost_usd'] for r in results):.6f}")


if __name__ == "__main__":
    main()
