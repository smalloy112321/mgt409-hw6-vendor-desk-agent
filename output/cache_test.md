# Problem 4: Prompt Cache Test

Script: `cache_test.py`. Raw data for every model call: `output/cache_test.json` (48 calls).
Model: `gpt-6-luna` via Portkey. Prices from `data/prices.json` (per 1M tokens): input $0.10, cached input
$0.01, cache write $0.125, output $0.50.

## How each setup was built

| Setup | How | Proof from the API's token counts |
|---|---|---|
| **with_cache** | Instructions + handbook are identical on every request, so the provider can reuse the prefix. | **24 of 24 calls** report cached tokens. 254,636 of 259,370 input tokens (98.2%) were read from cache. |
| **without_cache** | A new random `Request ID` is placed at the very start of the instructions on *every* model request (not just every run), so no request ever shares a prefix with an earlier one. | **0 cached tokens in all 24 calls.** |

Both setups also send Portkey's `x-portkey-cache-force-refresh` header, so Portkey never replays a stored
response and every token count comes from a fresh model call. Each document makes **2 model calls**: one to
call `read_document`, one to return the answer.

## Results (12 practice documents, 24 calls per setup)

| | without_cache | with_cache |
|---|---|---|
| Input tokens | 260,031 | 259,370 |
| Cached input tokens (read) | **0** | **254,636** |
| Cache write tokens | 257,007 | 1,710 |
| Uncached input tokens | 3,024 | 3,024 |
| Output tokens (incl. reasoning) | 2,511 (985 reasoning) | 2,513 (993 reasoning) |
| Cost: uncached input | $0.000302 | $0.000302 |
| Cost: cached input | $0.000000 | $0.002546 |
| Cost: cache write | $0.032126 | $0.000214 |
| Cost: output | $0.001255 | $0.001257 |
| **Total cost** | **$0.033684** | **$0.004319** |
| **Cost per document** | **$0.002807** | **$0.000360** |
| Cost per model call | $0.001404 | $0.000180 |
| Correct vs. answer key | 8 / 12 | 8 / 12 (same answers) |

**Saved by caching: $0.029365, or 87.2%.**

Math: per document = total ÷ 12. Savings = 1 − 0.004319 ÷ 0.033684 = 87.2%.

## Real numbers vs. Problem 2 estimates

Problem 2 priced only the handbook (10,058 tokens) on one call: $0.0010058 without cache and $0.0001006 cached.

| | Problem 2 estimate | Actual, per model call | Actual, per document (2 calls) |
|---|---|---|---|
| No cache | $0.0010058 | $0.0014035 (+40%) | $0.0028070 (2.8×) |
| Cached | $0.0001006 | $0.0001800 (+79%) | $0.0003599 (3.6×) |
| 1,000 units | $1.0058 / $0.1017 (calls) | $1.40 / $0.18 (calls) | $2.81 / $0.36 (documents) |
| Savings | 89.9% | 87.2% | 87.2% |

Why the real numbers are higher:
1. **Two calls per document**, so the handbook is sent twice per document, not once.
2. **The prompt is bigger than the handbook.** The average call is about 10,820 input tokens, roughly 770 more than the handbook. The extra comes from `prompt.md`, the tool and output schemas, and, on the second call, the document text.
3. **Without cache, the API charges cache writes ($0.125) instead of plain input ($0.10).** Problem 2 assumed $0.10.
4. **Output tokens are not in the Problem 2 estimate.** They are about $0.00005 per call, which barely matters without cache but is 29% of the cached bill.

The savings percentage (87% vs. 90%) is close to the estimate. Output tokens and the uncached tail cost the same in both setups, so they pull the percentage down a little.

## Projection: 1,000 documents a day for 30 days (30,000 documents)

| Setup | Per day | 30 days | Math |
|---|---|---|---|
| without_cache | $2.81 | **$84.21** | 30,000 × $0.0028070 |
| with_cache | $0.36 | **$10.80** | 30,000 × $0.0003599 |
| Saved | $2.45 | **$73.41 (87.2%)** | |

This assumes the same document mix, 2 calls per document, and a warm cache all day. With 1,000 documents a
day the cache would almost never go cold. A cold start costs one extra handbook write of about $0.0013.

## Surprises

1. **"No cache" costs more than list price.** Every no-cache call still reports about 10,700 **cache-write** tokens, so the API writes the prompt to cache even though nothing reuses it. Writes cost $0.125/1M instead of $0.10/1M, so the no-cache run cost $0.0337. If the same tokens had been billed as plain input, it would have cost $0.0273, which is 24% less. Not caching doesn't merely forgo a discount; it pays a 25% premium on every call.
2. **The cache was already warm before the with-cache run started.** The very first with-cache call (p01) read 10,604 tokens from cache. The same prompt had been cached during the Problem 3 runs earlier in the session, and the cache lasted that long. As a result, the with-cache run paid for only 1,710 write tokens in total (the small varying tails), not a full handbook write.
3. **After caching, output is the biggest cost to watch.** Output tokens are only 1% of tokens but 29% of the cached bill, because output costs 50× the cached-input price. Next in line are the roughly 126 tokens per call that never get cached ($0.10/1M). Shorter reasons and less reasoning are now the cheapest further savings.
4. **The second call per document is nearly a full repeat.** Call 2 resends everything from call 1 plus the document text. Without cache that doubles the bill. With cache it is almost free, because call 2's prefix is call 1's prompt.
5. **Caching did not change the answers.** Both setups got the same 8 of 12 right. The 4 misses (p02, p03, p07, p12) all come from text inside the documents that "corrects" the price, vendor, or lead time. That is a document-trust problem, not a cost problem, and is a topic for the attack and defense problems. No trap tool was called (`trap_calls.json` is still `[]`).
