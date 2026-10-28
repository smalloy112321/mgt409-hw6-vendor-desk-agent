"""Campus Customs vendor desk agent (entry point).

Usage:
    python agent.py --doc data/practice_docs/p01_bluehen_quote.html                    # all defenses
    python agent.py --doc data/practice_docs/p01_bluehen_quote.html --defenses none    # Problem 3 agent
    python agent.py --doc ... --defenses code,prompt                                   # any mix

Defense layers (see output/harness.md, Safety):
    code    sanitize.py strips hidden text before the model sees the document
    design  dangerous tools need human sign-off; document fenced as data; code makes the decision
    prompt  safety rules in prompts/prompt.md
"""

import argparse
import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from openai import AsyncOpenAI

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults, Tool, ToolDenied
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RunUsage

from models import ALL_DEFENSES, AgentDeps, DefendedDecision, VendorDecision
from rules import decide, item_mismatch
from tools import DANGEROUS_TOOLS, OUTPUT, append_json, log_trap, now, read_document

HERE = Path(__file__).parent
MODEL = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
USAGE_LOG = OUTPUT / "usage_log.json"
AUDIT_LOG = OUTPUT / "audit_trail.json"
SAFETY_BLOCK = re.compile(r"<!-- SAFETY RULES START.*?<!-- SAFETY RULES END -->\n*", re.S)
MAX_SIGNOFF_ROUNDS = 3
LINKS = re.compile(r"https?://\S+|www\.\S+|[\w.+-]+@[\w-]+\.[\w.]+")


def parse_defenses(value: str) -> frozenset[str]:
    if value in ("all", ""):
        return ALL_DEFENSES
    if value == "none":
        return frozenset()
    chosen = frozenset(v.strip() for v in value.split(","))
    if unknown := chosen - ALL_DEFENSES:
        raise ValueError(f"Unknown defense(s): {', '.join(sorted(unknown))}")
    return chosen


def load_instructions(prompt_rules: bool = True) -> str:
    prompt = (HERE / "prompts" / "prompt.md").read_text(encoding="utf-8")
    if not prompt_rules:
        prompt = SAFETY_BLOCK.sub("", prompt)
    handbook = (HERE / "data" / "shop_handbook.md").read_text(encoding="utf-8")
    return f"{prompt}\n\n{handbook}"


def make_agent(cache: bool = True, defenses: frozenset[str] = frozenset()) -> Agent:
    """Build the agent. cache=False puts a fresh random ID at the very start of the
    instructions on every model request, so no request shares a prefix with any
    earlier one and the provider has nothing to reuse from its prompt cache."""
    load_dotenv(find_dotenv(usecwd=True))
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY not found. Add it to .env")
    # Always ask Portkey for a fresh answer so its own response cache never replays an old call.
    client = AsyncOpenAI(api_key=api_key, base_url=PORTKEY_BASE_URL,
                         default_headers={"x-portkey-cache-force-refresh": "true"})
    model = OpenAIResponsesModel(MODEL, provider=OpenAIProvider(openai_client=client))
    text = load_instructions(prompt_rules="prompt" in defenses)
    instructions = text if cache else (lambda: f"Request ID: {uuid.uuid4()}\n\n{text}")
    answer_type = DefendedDecision if "prompt" in defenses else VendorDecision
    if "design" in defenses:
        # Design layer: the dangerous tools stay in the system but can only run with a
        # human sign-off. A request from the model pauses the run instead of executing.
        tools = [read_document] + [Tool(t, requires_approval=True) for t in DANGEROUS_TOOLS]
        output_type = [answer_type, DeferredToolRequests]
    else:
        tools = [read_document, *DANGEROUS_TOOLS]
        output_type = answer_type
    agent = Agent(
        model,
        name="vendor_desk",
        instructions=instructions,
        deps_type=AgentDeps,
        output_type=output_type,
        tools=tools,
    )
    agent.defenses = defenses
    return agent


def cost_usd(usage) -> dict:
    """Price a run with prices.json. input_tokens includes cached tokens."""
    p = json.loads((HERE / "data" / "prices.json").read_text())[MODEL]
    cached = usage.cache_read_tokens
    written = usage.cache_write_tokens
    uncached = usage.input_tokens - cached - written
    parts = {
        "uncached_input": uncached * p["input_per_1m"] / 1e6,
        "cached_input": cached * p["cached_input_per_1m"] / 1e6,
        "cache_write": written * p["cache_write_per_1m"] / 1e6,
        "output": usage.output_tokens * p["output_per_1m"] / 1e6,
    }
    return {k: round(v, 8) for k, v in parts.items()} | {"total": round(sum(parts.values()), 8)}


@dataclass
class RunOutcome:
    output: VendorDecision
    usage: RunUsage
    messages: list[ModelMessage]
    blocked_calls: list[dict] = field(default_factory=list)
    model_decision: dict | None = None

    def all_messages(self) -> list[ModelMessage]:
        return self.messages


def run(doc: Path, agent: Agent | None = None, setup: str = "default") -> RunOutcome:
    agent = agent or make_agent(defenses=ALL_DEFENSES)
    defenses = getattr(agent, "defenses", frozenset())
    deps = AgentDeps(doc_path=doc, defenses=defenses)
    usage = RunUsage()
    blocked: list[dict] = []
    start = time.perf_counter()
    result = agent.run_sync(f"Review this vendor document: {doc}", deps=deps, usage=usage)

    # Design layer: any send_email / approve_payment request is logged and denied.
    # Nothing executes; a human would have to approve it outside this agent.
    for _ in range(MAX_SIGNOFF_ROUNDS):
        if not isinstance(result.output, DeferredToolRequests):
            break
        denials = {}
        for call in result.output.approvals:
            args = call.args_as_dict()
            log_trap(doc, call.tool_name, args, "blocked: needs human sign-off (denied, not executed)")
            deps.audit.append({"tool": call.tool_name, "args": args, "result": "BLOCKED: needs human sign-off"})
            blocked.append({"tool": call.tool_name, "args": args})
            denials[call.tool_call_id] = ToolDenied(
                "Blocked: this tool needs a human sign-off and cannot be used while reviewing a vendor document."
            )
        result = agent.run_sync(message_history=result.all_messages(), deps=deps, usage=usage,
                                deferred_tool_results=DeferredToolResults(approvals=denials))
    if isinstance(result.output, DeferredToolRequests):
        raise RuntimeError("Agent kept requesting tools that need human sign-off.")

    answer = result.output
    model_decision = None
    if "design" in defenses:
        # Design layer: the model supplies facts; code applies the handbook checks.
        model_decision = {"decision": answer.decision, "reason": answer.reason}
        decision, reason = decide(answer.vendor, answer.sku, answer.unit_price,
                                  answer.lead_time_days, answer.min_order)
        if mismatch := item_mismatch(answer.sku, answer.item):
            decision = "do_not_recommend"
            reason = f"Price check cannot be verified: {mismatch}, so it needs human review."
        update = {"decision": decision, "reason": reason}
        if isinstance(answer, DefendedDecision):
            # Never pass a link or address from the document on to the buyer.
            notes = answer.warnings + deps.flags + ([mismatch] if mismatch else [])
            update["warnings"] = [LINKS.sub("[link removed]", w) for w in notes]
        answer = answer.model_copy(update=update)
    seconds = round(time.perf_counter() - start, 2)

    append_json(USAGE_LOG, {
        "time": now(),
        "doc": str(doc),
        "setup": setup,
        "defenses": sorted(defenses),
        "model": MODEL,
        "seconds": seconds,
        "requests": usage.requests,
        "input_tokens": usage.input_tokens,
        "cached_input_tokens": usage.cache_read_tokens,
        "cache_write_tokens": usage.cache_write_tokens,
        "output_tokens": usage.output_tokens,
        "reasoning_tokens": usage.details.get("reasoning_tokens", 0),
        "cost_usd": cost_usd(usage),
    })
    append_json(AUDIT_LOG, {
        "time": now(),
        "doc": str(doc),
        "defenses": sorted(defenses),
        "tool_calls": deps.audit,
        "model_decision": model_decision,
        "final_answer": answer.model_dump(),
    })
    return RunOutcome(answer, usage, result.all_messages(), blocked, model_decision)


def main() -> None:
    parser = argparse.ArgumentParser(description="Campus Customs vendor desk agent")
    parser.add_argument("--doc", required=True, type=Path, help="Path to one vendor document")
    parser.add_argument("--defenses", default="all",
                        help="all (default), none, or a comma list of code,design,prompt")
    args = parser.parse_args()
    if not args.doc.exists():
        parser.error(f"Document not found: {args.doc}")
    defenses = parse_defenses(args.defenses)
    print(json.dumps(run(args.doc, make_agent(defenses=defenses)).output.model_dump(), indent=2))


if __name__ == "__main__":
    main()
