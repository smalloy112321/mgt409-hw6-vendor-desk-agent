# Problem 2: Handbook Token Count and Cost Estimate

Files: `data/shop_handbook.md` (the Campus Customs Shop Handbook) and `data/prices.json` (gpt-6-luna prices).
Script: `count_tokens.py`. Run `python count_tokens.py` to reproduce every number below.

## Token count: **10,058 tokens**

The handbook is 28,903 characters and 6,127 words. I counted its tokens two independent ways, and they agree exactly.

1. **Counted locally with `tiktoken`:** the `o200k_base` encoding gives **10,058 tokens**. This needs no API call.
2. **Measured through the API:** I sent requests to `gpt-6-luna` through Portkey and read the `prompt_tokens` value the API reports.
   - A request with the handbook used 10,072 prompt tokens.
   - The same request with an empty instruction used 14 tokens of fixed message overhead.
   - Handbook = 10,072 − 14 = **10,058 tokens**.

A repeat of the same request reported 10,069 of 10,072 tokens as cached. That shows gpt-6-luna caches the handbook automatically when the start of the prompt is identical.

## Prices (`data/prices.json`, per 1M tokens)

| Input | Cached input | Cache write | Output |
|---|---|---|---|
| $0.10 | $0.01 | $0.125 | $0.50 |

## Cost of the handbook alone

**One call**

| Case | Math | Cost |
|---|---|---|
| Without cache | 10,058 × $0.10 ÷ 1,000,000 | **$0.0010058** |
| With cache, first call (writes the cache) | 10,058 × $0.125 ÷ 1,000,000 | **$0.0012573** |
| With cache, later calls (read from cache) | 10,058 × $0.01 ÷ 1,000,000 | **$0.0001006** |

**1,000 calls**

| Case | Math | Cost |
|---|---|---|
| Without cache | 1,000 × $0.0010058 | **$1.0058** |
| With cache | 1 write × $0.0012573 + 999 reads × $0.0001006 = $0.0012573 + $0.1004794 | **$0.1017** |
| Savings | $1.0058 − $0.1017 | **$0.9041 (89.9%)** |

## Assumptions
- The handbook sits at the very start of every request, so its whole prefix can be cached.
- The cache stays warm across all 1,000 calls.
- Only the handbook is priced here: not the instructions, the vendor document, tool definitions, or output tokens.

Problem 4 checks these estimates against real runs (`output/cache_test.md`). The real per-document cost was higher: about 2.8× without cache and 3.6× with cache. Each document takes two calls, the prompt carries about 770 more tokens than the handbook, and output tokens add cost. The percent saved was close: 87.2% actual vs. 89.9% estimated.
