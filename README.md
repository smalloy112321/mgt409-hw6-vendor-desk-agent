# Campus Customs Vendor Desk Agent (MGT 409, Homework 6)

A PydanticAI agent that reads one vendor document (HTML quote, PDF quote, or `.eml` email), pulls out
vendor, SKU, unit price, lead time, and minimum order, and recommends buy or don't buy using the rules
in the Campus Customs Shop Handbook. Every AI call goes to `gpt-6-luna` through Portkey.

The full write-up is in **`output/hw6_report.html`**. Open it by double click; it works offline.

## Run the agent

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then paste your PORTKEY_API_KEY into .env
python agent.py --doc data/practice_docs/p01_bluehen_quote.html
```

- **Defenses:** all three layers (code, design, prompt) are on by default.
- **No defenses:** add `--defenses none` to run the original Problem 3 agent.
- **Any mix:** for example `--defenses code,prompt`.
- **Output:** the answer prints as JSON. Each run is also appended to `output/usage_log.json` and `output/audit_trail.json`.
- **Trap tools:** `send_email` and `approve_payment` never send or pay anything. They only log to `output/trap_calls.json`, and with defenses on they need a human sign-off.

## Re-run each problem

| Problem | Command | Output |
|---|---|---|
| 2 Size up the handbook | `python count_tokens.py` | printed; written up in `output/handbook_estimate.md` |
| 3 Agent on p01 and p08 | `python agent.py --doc data/practice_docs/p08_chapelst_email.eml --defenses none` | `output/harness.md` |
| 4 Cache test | `python cache_test.py` | `output/cache_test.json`, `.md` |
| 5 Attack (no defenses) | `python attack_test.py` | `output/attack_results.json`, `.md` |
| 6 Defenses, layer by layer | `python defense_test.py` | `output/defense_results.json`, `.md` |
| 6 Sign-off gate test | `python gate_test.py` | `output/gate_test.json` |
| 7 Red team | `python make_attacks.py` then `python red_team_test.py` | `data/my_attacks/`, `output/red_team.md` |
| 8 Hardened check and exam | `python regression_test.py` then `python exam_run.py` | `output/exam_results.json` |
| 9 Report | `python build_report.py` | `output/hw6_report.html` |

## Layout

- **Agent:**
  - `agent.py`: entry point and logging
  - `tools.py`: tools
  - `models.py`: output types
  - `prompts/prompt.md`: instructions
- **Defenses:**
  - `sanitize.py`: code layer, which strips hidden text
  - `rules.py`: design layer, where code makes the decision
- **`data/`:**
  - `shop_handbook.md`, `prices.json`
  - `practice_docs/` and `practice_key.json`
  - `exam_docs/`
  - `my_attacks/`: our two red-team documents and their answer key
- **`output/`:** all results and write-ups
- **`AI_prompts.md`:** the prompts used for each problem

## Notes

- **Secrets:** `.env` is git-ignored. `.env.example` holds placeholders only.
- **Fonts:** `report_assets/` holds the fonts embedded in the report: Lato, Cormorant Garamond, and Graduate, all under the SIL Open Font License.
- **Pillow:** used only by `make_attacks.py`, to draw the "scanned" PDF.
