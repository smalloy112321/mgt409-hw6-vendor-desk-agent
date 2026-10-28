"""Problem 2: count Handbook tokens and price it with gpt-6-luna rates.

Two counts:
  1. Local: tiktoken o200k_base (the GPT-4o/5-family tokenizer), no API call.
  2. API: send the Handbook to gpt-6-luna through Portkey and read the
     usage numbers the model reports. A second call with no Handbook gives
     the fixed message overhead, so Handbook tokens = with - without.
"""

import json
import os
from pathlib import Path

import tiktoken
from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

HERE = Path(__file__).parent
DATA = HERE / "data"
MODEL = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
CALLS = 1_000


def make_client() -> OpenAI:
    load_dotenv(find_dotenv(usecwd=True)) or load_dotenv(HERE.parent.parent / ".env")
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY not found. Add it to .env")
    return OpenAI(api_key=api_key, base_url=PORTKEY_BASE_URL)


def prompt_usage(client: OpenAI, system: str):
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": "Reply with OK."}],
        max_completion_tokens=16,
    )
    u = resp.usage
    details = getattr(u, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", 0) or 0
    return u.prompt_tokens, cached


def main() -> None:
    handbook = (DATA / "shop_handbook.md").read_text(encoding="utf-8")
    p = json.loads((DATA / "prices.json").read_text())[MODEL]

    local = len(tiktoken.get_encoding("o200k_base").encode(handbook))
    print(f"Handbook: {len(handbook):,} characters, {len(handbook.split()):,} words")
    print(f"Local count (tiktoken o200k_base): {local:,} tokens")

    client = make_client()
    base, _ = prompt_usage(client, "")
    with_hb, cached1 = prompt_usage(client, handbook)
    with_hb2, cached2 = prompt_usage(client, handbook)  # same prefix again -> cache hit?
    api = with_hb - base
    print(f"API prompt_tokens: no handbook={base}, with handbook={with_hb} "
          f"-> Handbook = {api:,} tokens")
    print(f"Cached tokens reported: call 1={cached1}, repeat call={cached2} (of {with_hb2})")

    n = api
    per_m = 1_000_000
    no_cache_1 = n * p["input_per_1m"] / per_m
    write_1 = n * p["cache_write_per_1m"] / per_m
    read_1 = n * p["cached_input_per_1m"] / per_m
    print("\nPrices per 1M tokens:", {k: v for k, v in p.items()})
    print(f"\nOne call, no caching:   {n:,} x ${p['input_per_1m']}/1M = ${no_cache_1:.6f}")
    print(f"One call, cache write:  {n:,} x ${p['cache_write_per_1m']}/1M = ${write_1:.6f}")
    print(f"One call, cache read:   {n:,} x ${p['cached_input_per_1m']}/1M = ${read_1:.6f}")
    print(f"\n{CALLS:,} calls, no caching: {CALLS:,} x ${no_cache_1:.6f} = ${CALLS * no_cache_1:.4f}")
    cached_total = write_1 + (CALLS - 1) * read_1
    print(f"{CALLS:,} calls, cached: 1 write ${write_1:.6f} + {CALLS - 1} reads x ${read_1:.6f} "
          f"= ${cached_total:.4f}")
    print(f"Savings: ${CALLS * no_cache_1 - cached_total:.4f} "
          f"({1 - cached_total / (CALLS * no_cache_1):.1%})")


if __name__ == "__main__":
    main()
