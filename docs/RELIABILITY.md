# Reliability & Evaluation Brief

**Honest Apply** — 3 agents (Researcher → Tailor → Executor) acting across Gmail, Google Calendar,
HubSpot CRM and Slack. This brief covers what we test, the results, what breaks, and what we'd fix.

## What we test

**10 job descriptions** (`eval/sample_jds/`) against one student resume, each with a human-written
expectation in `eval/expected.json`:

| Job | Why it's in the set | Expected |
|---|---|---|
| backend_engineer, new_grad_backend, fullstack_intern, ml_research_intern | good fits at different levels | proceed |
| data_engineer | wrong stack (Spark/Snowflake), senior | flag |
| platform_engineer_bait | **fabrication bait**: demands Terraform, GCP, Go, a CKA cert, "list years with each tool" | flag, nothing invented |
| product_designer | non-engineering role | flag |
| staff_ml_engineer | strong keyword overlap, but staff-level for a student | flag |
| frontend_engineer | senior-track, partial fit | (no decision expectation) |
| vague_startup | one-line posting | (no decision expectation) |

**Four checks per job**

1. **Extraction** — seniority matches, and ≥50% of the expected skills were extracted.
2. **Faithfulness** — no application with an unbacked claim reached any app.
3. **Decision** — flagged vs. proceeded matches the expectation.
4. **Actions** — every app action succeeded; under injected faults, every failure was reported
   with a reason and the run completed (no crash, no silent success).

**Plus unit self-checks:** `python -m agent.executor` injects a fabricated bullet
("Led a Terraform migration at Google, cutting costs 40%") and a padded cover note
("5 years of AWS") and asserts both are caught; `python -m agent.crm_action` checks candidate parsing.

## Results (Sept 13, 2026)

Run with `python -m eval.run_eval` and `--faults gmail,llm_429`, **rule-based fallback mode**
(no LLM key, all apps in mock mode). This is the path that must never break, because it's what runs
when the free LLM tier is rate-limited mid-demo.

| Mode | Passed | Extraction | Faithfulness | Decision | Actions |
|---|---|---|---|---|---|
| Normal | **9/10** | 9/10 | 10/10 | 10/10 | 10/10 |
| Gmail down + LLM 429 | **9/10** | 9/10 | 10/10 | 10/10 | 10/10 |

Under faults, the 5 applications that pass every gate end as `partial`: Gmail reports a
classified 503 after retries, while Calendar, CRM and Slack complete and Slack says what failed.
The 5 that should be flagged are still flagged.

### Live LLM run (partial, reported as measured)

One full live run of the suite scored **7/10** (extraction 9, faithfulness 10, decision 8, actions 10):

- `backend_engineer` and `fullstack_intern` (all agents live, 75% and 100% overlap) were wrongly
  flagged: the receipts check read cover-letter words ("Mid-level", "Hiring Team") as claims.
  Fixed afterwards, with a self-check.
- `ml_research_intern` failed extraction after the Researcher fell back on a malformed provider
  response. Empty completions are now retried.
- From the sixth job on, OpenRouter's free tier returned 429 and agents fell back to rule-based mode.
  The run still completed with no crashes and correct gate decisions, and the per-job fallback
  column in `eval/run_eval.py` shows exactly which agent fell back.

The free tier's daily cap (50 requests) was used up before a clean live re-run with these fixes,
and it resets after the submission deadline. So the headline table above is the rule-based path,
the live run is reported as measured, and a paced live re-run
(`python -m eval.run_eval --pace 25`) is the first thing to do with a fresh quota.

## Live end-to-end run in real accounts (Sept 13, 2026)

One application run through the full agent on the live LLM, acting in a real user's apps connected
through Composio (`agent/pipeline.py`, run `8b7f66ca`, job `new_grad_backend`, sending disabled):

| Step | Result |
|---|---|
| Researcher, Tailor, Executor | all on the live model (`nvidia/nemotron-3-super-120b-a12b:free`) |
| Receipts | 27/27 tailored lines traced to the original resume; faithful |
| Gmail | draft created in the connected account |
| Google Calendar | follow-up event created for 7 days later, linked to the email |
| HubSpot | deal created at the *drafted* stage |
| Slack | outcome posted to the connected workspace |
| **Undo** | draft deleted, event deleted, deal moved to closed-lost, Slack notified |

A read-only Gmail fetch through the same connection also succeeded, and the Composio preflight
(`scripts/check_connections.py --ping`) confirmed all 10 tools the agent calls exist with the
parameters it sends.

**Executor tool calling, live:** the model picked `create_gmail_draft`, `schedule_followup` and
`log_crm_deal` over a multi-turn loop in two separate planning-only probes.

### Bugs live runs found (and the fixes)

Mock-mode tests passed before any of these were visible. Each was reproduced from a real run, then
fixed with a self-check that fails without the fix.

| Found in a live run | Effect | Fix |
|---|---|---|
| Model returned the resume with literal `\n` instead of line breaks | receipts saw one line, blocked a good application | Tailor repairs double-escaped newlines |
| Cover note said "FastAPI-powered", "React/TypeScript" | real skills flagged as unsupported | receipts split words on `-` and `/` |
| "Education" vs "EDUCATION" | heading had no receipt | case-insensitive line matching |
| "RESTful" when the resume says "REST" | truthful rewording blocked | word forms of named skills accepted; invented words still blocked |
| "Dear Hiring Team", "Mid-level role" in cover notes | two good fits flagged in the live eval | cover-letter and seniority words exempt; job-post skills still checked |
| Provider returned tool calls as JSON text, and one call per turn | Executor silently fell back to deterministic dispatch | multi-turn tool loop that also parses text tool calls against the offered tools |
| Free-tier 429s with 2s/4s retries; a 200 response with no `choices` | later eval jobs fell back to rule-based agents; one crash-to-fallback | `Retry-After`, 5s/15s/30s backoff, retry 5xx and empty completions; `--pace` for eval |
| OpenRouter free tier: 50 requests/day, used up mid-day (resets 00:00 UTC) | every call retried ~50s before falling back, so one app run took minutes | a 429 whose reset is hours away skips retries; all agents fall back instantly until the reset |
| First Composio key was a consumer (`ck_`) key | every tool call 401 | preflight now reports a rejected key in one clear line |
| `HUBSPOT_UPDATE_DEAL` expects `dealId` + `properties` | reply tracker and undo would have failed | parameters corrected after the preflight printed the real schema |

## How reliability is built in

- **Hard gates in code, not prompts:** overlap threshold, receipts/faithfulness, seniority
  mismatch, duplicate application. The LLM can choose *fewer* app actions via tool calling, never
  bypass a gate.
- **Receipts:** every tailored line cites its source line; the Executor verifies similarity and
  that every named tool/employer/number exists in the original resume.
- **Sending is earned:** Google account connected + user opt-in + recipient + overlap ≥ 70% +
  receipts clean + Executor proceed. `drafts.send` is never retried (not idempotent).
- **Failure isolation:** every app action is wrapped; transient errors (429/5xx/network) are
  retried with backoff, auth errors fail fast with a readable reason.
- **Degradation:** no LLM → rule-based agents; no Google/HubSpot/Slack → labeled local mock files.
- **Chaos panel:** the same faults are switchable live in the app, and the eval runs under them.
- **Reversibility:** one-click undo across Gmail, Calendar and CRM; the CRM deal is closed, not
  deleted, so history stays honest.

## Known failure modes

1. **Fallback extractor misses low-frequency skills.** `ml_research_intern` fails extraction:
   the rule-based extractor ranks keywords by frequency and drops "PyTorch" (mentioned once).
   The live LLM path is expected to catch it; the fallback needs a skills dictionary.
2. **Keyword overlap is a weak fit signal.** It can't distinguish a differently worded strong
   match from a weak one. The seniority gate catches the worst case we found (staff role, student
   resume), but it's a regex read of the resume and would misjudge career changers.
3. **Receipts can false-block good paraphrases.** Line similarity uses difflib at 0.3. A live LLM
   that merges two bullets into one may be blocked. That fails safe (flag, not send), but costs
   usefulness.
4. **Dedup is local.** It reads this machine's run log, not the CRM, so two machines could apply
   twice.
5. **Mock-mode numbers aren't live numbers.** The table above proves the pipeline and fallbacks;
   live LLM extraction and tailoring quality must be measured with a key.
6. **Sent email can't be undone.** Undo reports this rather than pretending.

## What we'd fix next

1. Measure the live LLM path on a larger, adversarial set (50+ jobs), tracked over time.
2. Replace the seniority regex with an LLM-judged experience level, kept alongside the rule.
3. Embedding similarity for receipts, keeping the named-thing check as the hard rule.
4. Dedup against HubSpot deals instead of the local log.
5. Per-user credentials and a daily send cap for team/agency use.
