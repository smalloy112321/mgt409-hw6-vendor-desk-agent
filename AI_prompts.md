# AI Prompts — Homework 6: Vendor Desk Agent

AI assistant: Claude Code. All agent AI calls use `gpt-6-luna` through Portkey.

---

## Problem 1 — Create the AI Prompt Log

**Typed prompt:**

> Problem 1. Create AI_prompts.md and keep it updated as we work. Put one section for each problem. Each section must include:
> - Problem number and title
> - At least one typed prompt
> - One follow-up prompt if needed

**Follow-up prompt:** None needed.

---

## Problem 2 — Handbook Token Count and Cost

**Typed prompt:**

> Problem 2. We are going to work on data/shop_handbook.md (this is the Campus Customs Shop Handbook) and data/prices.json (this is the gpt-6-luna price list).
>
> How many tokens is the Handbook? What is the token count and how did you get it? What does the handbook alone cost in dollars on one call? What about 1,000 calls? Include cached tokens and without them. Show your math.

**Follow-up prompt:** None needed.

---

## Problem 3 — Build the Vendor Desk Agent

**Typed prompt:**

> Problem 3. We're going to build the vendor desk agent using PydanticAI using gpt-6-luna. The agent is these four files: prompts/prompt.md, agent.py, tools.py, models.py. Prompts are instructions for the agent. Agent is the entry point. Tools are the tools. Models are the structured types.
>
> We want to give the agent the path to one vendor document. It should read the document with a tool (HTML, PDF, and .eml email files all have to work) and return: vendor, SKU, unit price, lead time in days, minimum order, a decision (recommend or do_not_recommend) following the handbook rules, and a one-sentence reason.
>
> Rules: The agent must have two trap tools, send_email and approve_payment. Its job never needs them, but they are there to catch malicious documents that try to trick the agent into emailing someone or paying a vendor. These traps only append the call and its arguments to output/trap_calls.json, which starts as an empty list. After every run, append to output/usage_log.json (document, time, the token counts the API reports, and the dollar cost using prices.json) and output/audit_trail.json (each tool with its arguments and a short result, plus the final answer). The agent should run like this: python agent.py --doc data/practice_docs/p01_bluehen_quote.html
>
> Run it on p01 and p08 to show it works. Start output/harness.md: each field in models.py and why, and each tool in one line.

**Follow-up prompt:** None needed.

---

## Problem 4 — Prompt Cache Test

**Typed prompt:**

> Problem 4. The handbook is the same on every call so the model can reuse it from a cache at a cheaper price. Test what this is worth: run the agent on all 12 practice documents in two ways:
> 1. with cache: handbook reused from cache
> 2. without cache: set up so nothing gets reused from cache
>
> Check the token counts that the API sends back to prove each setup really did what it is supposed to do (i.e. don't show me a without-cache run that still shows cached tokens).
>
> Save every model call from both setups to output/cache_test.json. For each call include the setup, document, every token count the API reports, and dollars from prices.json.
>
> In output/cache_test.md, document:
> - total cost and cost per document for each setup and the percent saved
> - how real numbers compare to Problem 2 estimates
> - projection for 1,000 documents a day for 30 days with and without cache
> - anything in the numbers that is surprising

**Follow-up prompt:** None needed.

---

## Problem 5 — Attack the Agent

**Typed prompt:**

> Problem 5. We're going to attack our own agent. Some vendor documents are booby-trapped with text aimed at the AI. Run the Problem 3 agent with no new defenses on all 12 documents in data/practice_docs/.
>
> Compare each answer to data/practice_key.json and check output/trap_calls.json. Log the fake email and payment tools from Problem 3.
>
> Save output/attack_results.json (for each document, write if each field matched the key, if the decision matched, if a trap tool was called, and if a link or other strange text showed up in the answer).
>
> In output/attack_results.md, for every document that fooled the agent, write what it fooled and where in the file it was hiding.

**Follow-up prompt:** None needed.

---

## Problem 6 — Defend the Agent

**Typed prompt:**

> Problem 6. We're going to defend the agent at three levels:
> 1. Code: what the program does to the document before any model sees it
> 2. Design: how the agent is put together so that a booby-trapped document cannot reach the dangerous tools or the decision
> 3. Prompt: rules in prompts/prompt.md
>
> Do not delete send_email or approve_payment from the system because the shop will use them later with a human sign-off. Keep a way to run the agent with no defenses (we need it for Problem 7).
>
> Rerun all 12 practice documents and save output/defense_results.json in the same shape as Problem 5, plus tokens and dollars per document.
>
> Clean documents must still come back with the correct values, and refusing or blanking out a real quote counts as a failure.
>
> In output/defense_results.md, include:
> - a before and after table for all 12 documents
> - what each layer catches that the other layers miss
> - the extra tokens and dollars each layer adds per document
>
> Add your safety features to output/harness.md in a safety section and include what each defense layer does in the most simple and straightforward way possible.

**Follow-up prompt:** None needed.

---

## Problem 7 — Red Team: Our Own Attacks

**Typed prompt:**

> Problem 7. Now, we are the attacker. Make two new booby-trapped vendor documents in data/my_attacks/. Each one should use a hiding trick or an attack goal that is not in the practice set. A person opening the document should see a normal quote without seeing the booby trap.
>
> Run both attacks on the agent with no defenses on and then again with the defenses on.
>
> In output/red_team.md, for each attack write what is hidden, where, what it tries to make the agent do, and what happened before and after defenses.
>
> We will get more points for attacks that are new and that actually fool the agent with no defenses on - let's try to get the maximum points we can on this problem.

**Follow-up prompt:** "Not now" (in reply to the offer to harden the defenses right away; the hardening was done in Problem 8).

---

## Problem 8 — Harden Defenses and Run the Exam Documents

**Typed prompt:**

> Problem 8. data/exams_docs/ has 10 vendor documents with no answer key available. First, harden the defenses you suggested in the last problem. Then, run the final defended agent on all of the 10 documents. Save output/exam_results.json with one entry per exam file. Each entry has these fields:
> - file: the exam name (e.g. e01_quote.html)
> - vendor
> - sku
> - unit_price
> - lead_time_days
> - min_order
> - decision: recommend or do not recommend
> - reason
> - trap_tool_called: true or false
> - input_tokens, cached_tokens, output_tokens
> - cost_usd
>
> Graders will compare the results to a hidden answer key and rerun some agents to check. We will get maximum points for correct fields and decisions, no trap tool calls, and clean documents handled normally.

**Follow-up prompt:** None needed.

---

## Problem 9 — Report Page

**Typed prompt:**

> Problem 9. Build output/hw6_report.html. This is one file that opens by double click with no internet and no other files next to it.
>
> The page must show these five things using the real numbers from earlier problems:
> 1. Caching results, with a chart
> 2. Attacks before and after defenses
> 3. What defenses cost in tokens and dollars
> 4. Exam results and two red team attacks
> 5. Short recommendation to the store manager (should Campus Customs turn this agent on for real vendor mail, and what would it cost per month at 1,000 documents a day for 30 days?)
>
> We will get more points for a nicely designed page that reads well. Let's use the Campus Customs page we made in HW4 as design inspiration.

**Follow-up prompt:** None needed.

---

## Problem 10 — Publish to GitHub

**Typed prompt:**

> Problem 10. We are going to push the project to a public GitHub repository and submit the repo URL on Canvas. The graders will clone it, so make sure it opens and the files are there.
>
> Include the whole data/ folder (the course data plus the two attack files) so graders can clone the repo and run the agent right away. Do not commit the real .env. Use .gitignore to keep it out and include .env.example with placeholders only. Put a short note in README.md on how to run the agent.

**Follow-up prompt:** None needed.
