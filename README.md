# AI Job Application Agent

Built for the Multi-App AI Agent Hackathon (virtual, Sept 13, 2026), judged by Phillip Li
and Akira Tong.

Takes a resume and a job description and autonomously:

1. **Searches** live listings across three job boards (Arbeitnow, Remotive, RemoteOK — all
   free, no key required) or accepts a pasted JD
2. **Extracts** structured requirements from the JD (skills, seniority, must-haves, keywords)
3. **Tailors** the resume and writes a cover note, grounded strictly in the candidate's
   real, existing experience — the prompt explicitly forbids inventing skills or experience
4. Runs a **guardrail check** (keyword overlap). Low-match applications are flagged for
   human review instead of proceeding automatically
5. **Acts** across five apps: creates a Gmail **draft** (and sends it automatically if the
   score clears a second, stricter threshold — see Auto-send below), appends a tracking row
   to **Sheets**, creates a 7-day follow-up **Calendar** event, saves the tailored resume to
   **Drive**, and notifies **Slack** on every outcome — sent, drafted, or flagged
6. **Logs** every run — inputs, outputs, guardrail decision, action results — to
   `eval/logs/eval_log.json` for the reliability brief

Six external integrations in total, double the hackathon's three-app minimum: Gmail,
Sheets, Calendar, Drive, Slack, and three job boards behind one search interface.

## Auto-send: two gates, not one

Gmail always creates a draft. Whether that draft is also **sent automatically** is gated by
two separate thresholds, both of which must clear:

1. `GUARDRAIL_THRESHOLD` (default 40%) — the baseline guardrail. Below this, the run is
   flagged for review and Gmail, Sheets, Calendar, and Drive don't run at all.
2. `AUTO_SEND_THRESHOLD` (default 70%) — a materially stricter second bar. At or above
   this, the draft is sent immediately. Between the two thresholds, the draft is created
   but left for review — this is the default outcome for most applications, deliberately:
   overlap score is not a reliable proxy for "this cover note is actually good," and
   unreviewed sends at a low bar would hurt response rates more than they'd help.

Both thresholds are configurable in `.env`. The result badge always shows which of the
three outcomes occurred — auto-sent, drafted (awaiting review), or flagged for review —
and Slack is notified with the same distinction on every run.

**Job boards covered on purpose, and some left out on purpose.** Arbeitnow, Remotive, and
RemoteOK are genuine free public APIs with no key and no scraping involved. LinkedIn,
Indeed, and Glassdoor are not included: all three prohibit scraping in their Terms of
Service and run active anti-bot protection to enforce it, so there is no legitimate
free/no-key way to search them programmatically. That limit is stated plainly in the
reliability brief rather than worked around.

## Runs with zero setup

If `OPENROUTER_API_KEY`, `credentials.json`, or `SLACK_WEBHOOK_URL` are absent, the app
falls back to mock mode for that piece independently: a rule-based extractor/tailorer
stands in for the LLM, and the Google/Slack actions write to local files under
`eval/logs/` instead of calling real APIs. The job boards need no key at all — they're
public read-only APIs. Clone the repo and the full pipeline runs immediately; wire up real
credentials (below) whenever you're ready to go live.

The status row at the top of the app shows live/mock state for the LLM, Google Workspace,
and Slack independently.

## Setup (to go live)

### 1. OpenRouter API key (free, no card required)
1. Go to [openrouter.ai/keys](https://openrouter.ai/keys), sign up, and generate an API key.
2. Copy `.env.example` to `.env` and set `OPENROUTER_API_KEY`.
3. The default model is `meta-llama/llama-3.3-70b-instruct:free` — OpenRouter's most
   established free open-source model, stable since Dec 2024. Other free open-source
   options worth trying via `OPENROUTER_MODEL`:
   - `openai/gpt-oss-20b:free` — Apache 2.0, especially strong at structured/JSON output
   - `openai/gpt-oss-120b:free` — larger sibling, still free, more capable
   - `google/gemma-3-27b-it:free` — fast, low latency
   - `deepseek/deepseek-chat-v3-0324:free` — strong general writing/reasoning
   - `qwen/qwen3-235b-a22b:free` — strong at analysis/reasoning

   Free-tier models on OpenRouter rotate as providers add and retire them — check
   [openrouter.ai/models?max_price=0](https://openrouter.ai/models?max_price=0) if a model
   ID stops working. Any live-call failure (rate limit, retired model, network issue) falls
   back to the offline mock rather than breaking the run.

### 2. Google Workspace APIs (Gmail, Sheets, Calendar, Drive) — free, no billing
1. Create a project in [Google Cloud Console](https://console.cloud.google.com).
2. Enable the Gmail, Sheets, Calendar, and Drive APIs.
3. Create an OAuth 2.0 Client ID of type Desktop app.
4. Download the client secret JSON and save it as `credentials.json` in the project root.
5. On the OAuth consent screen, leave publish status as Testing and add your own Google
   account as a test user — this skips verification review, which matters given the
   turnaround before a hackathon deadline.
6. The first live Google action opens a browser window to authorize; a `token.json` is
   cached afterward. If that token later goes stale, the app detects it, discards it, and
   re-triggers authorization automatically instead of silently failing.

Scopes are intentionally narrow: `gmail.compose` (covers draft creation and the gated
send — the app never sends outside that gate), `spreadsheets`, `calendar.events`, and
`drive.file`. `credentials.json` and `token.json` are git-ignored.

### 3. Slack notifications (free, under two minutes)
1. Create an Incoming Webhook at
   [api.slack.com/messaging/webhooks](https://api.slack.com/messaging/webhooks) — no bot
   scopes or app review required.
2. Set `SLACK_WEBHOOK_URL` in `.env`.

### 4. Job boards — nothing to set up
Arbeitnow, Remotive, and RemoteOK are public, unauthenticated APIs. They work immediately.

### 5. Install and run
```bash
pip install -r requirements.txt
streamlit run app.py
```

### 6. Preflight check (run this first, on demo day)
```bash
python -m scripts.check_connections          # status only, no side effects
python -m scripts.check_connections --ping    # also sends a real Slack test message
                                               # and a real job-board search
```
Prints live/mock status for all six integrations so a broken credential shows up before
judging, not during it. `--ping` never creates a real Gmail draft, Sheet row, Calendar
event, or Drive file just from a check — only Slack (a harmless test message) and the job
boards (a read-only search) are actually exercised.

### 7. Batch eval (for the reliability brief)
```bash
python -m eval.run_eval
```
Runs the pipeline against every `.txt` file in `eval/sample_jds/` using
`eval/sample_resume.txt`, prints a pass/fail table, and appends full results to
`eval/logs/eval_log.json`. One sample JD (`data_engineer.txt`) is a deliberate poor fit so
the guardrail's flagging behavior shows up in the reliability brief, not just the happy path.

## Project structure
```
/
├── app.py                     # Streamlit UI
├── agent/
│   ├── llm.py                  # OpenRouter wrapper + offline mock fallback
│   ├── extract.py              # Skill 1: JD extraction
│   ├── tailor.py                # Skill 2: resume/cover note tailoring
│   ├── guardrail.py             # Skill 3: two-threshold guardrail (review + auto-send)
│   ├── google_auth.py           # Shared OAuth helper (stale-token recovery, mock fallback)
│   ├── utils.py                  # Retry/backoff + Google error classification
│   ├── gmail_action.py           # Skill 4: Gmail draft + gated auto-send
│   ├── sheets_action.py          # Skill 5: Sheets append
│   ├── calendar_action.py        # Skill 6: Calendar follow-up event
│   ├── drive_action.py           # Skill 7: Drive save
│   ├── slack_action.py           # Skill 8: Slack notification
│   ├── jobs_search.py            # Skill 0: multi-board live job search
│   └── pipeline.py               # Orchestrates the full flow + eval logging
├── scripts/
│   └── check_connections.py     # Preflight status check for all 6 integrations
├── eval/
│   ├── sample_resume.txt
│   ├── sample_jds/               # 4 placeholder JDs (incl. one deliberate poor fit)
│   ├── logs/                     # eval_log.json + mock action outputs (git-ignored)
│   └── run_eval.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Design

The UI follows the PRD §8 palette: professional-but-approachable instead of
generic SaaS-blue — terracotta CTAs, olive/sage success states, a cream
background, warm charcoal text, golden-amber flags for low-confidence review,
and warm-ivory cards with soft borders. A single Inter typeface keeps the
weight scale minimal. Status is communicated with small dot indicators,
outline badges, and the 4-step Extract → Tailor → Act → Log pipeline stepper,
so the multi-step agent stays visible during the demo. The palette lives in
`.streamlit/config.toml` for native widgets and is mirrored as design tokens
for the custom stepper, cards, badges, and action checklist.

## MVP vs. production scope

This build extends the hackathon MVP scope with two integrations (Slack, multi-board
search) beyond the original four: pasted or live-searched JD text (no resume file-upload
parsing yet), single one-shot LLM calls for extraction and tailoring, a two-threshold
keyword-overlap guardrail, a single tracking sheet, one static 7-day follow-up event, and
local/notebook-style hosting for the live demo. The planned production version adds resume
upload parsing, JD auto-scraping from additional (including paid) job-board sources,
multi-pass extraction with validation, ATS keyword scoring, a full analytics dashboard,
smart calendar scheduling, multi-user auth, and a continuous eval/regression pipeline.

## Reliability notes

- Every `*_action.py` skill is wrapped in `try/except` so one failing action never crashes
  the run — failures are classified and recorded in the log instead of a raw stack trace.
- The four Google actions retry transient failures (rate limits, 5xx errors) with
  exponential backoff via `agent/utils.py`, but fail fast on auth/permission errors rather
  than retrying something that can't succeed.
- `google_auth.py` recovers from a stale or revoked OAuth token automatically instead of
  caching a broken client for the rest of the run.
- The tailoring prompt carries an explicit, hard anti-hallucination constraint, and the
  offline mock tailorer only ever reorders and reuses lines already in the original resume
  for the same reason.
- Auto-send is gated by two independent thresholds (see above), not one — low-overlap
  applications are routed to `needs_review` and skip Gmail/Sheets/Calendar/Drive entirely,
  while Slack still fires so a human finds out either way.
- `scripts/check_connections.py` gives a single pre-demo status check across all six
  integrations instead of discovering a broken one mid-judging.

## What would make this better

Roughly in priority order if there were more than a day:

1. **Resume upload with real parsing** (PDF/DOCX via a proper parser, not pasted text) —
   the single biggest gap between this and something a real candidate would use daily.
2. **A second LLM-as-judge pass on tailoring faithfulness** — right now the anti-
   hallucination constraint is enforced only by the prompt; a cheap second pass that
   diffs claims in the tailored resume against the original and flags anything
   unsupported would make the "never invent experience" claim independently checkable,
   not just prompted-for.
3. **A smarter guardrail than keyword overlap** — overlap is transparent and easy to
   explain to judges, but it is a weak signal (it can't tell a well-matched but
   differently-worded resume from a poorly-matched one). An embedding-similarity or
   LLM-scored guardrail, kept alongside keyword overlap as a second opinion rather than a
   replacement, would catch cases keyword matching misses in both directions.
4. **Per-user auth and multi-tenant credential storage** — today one OAuth client and one
   `.env` serve one person; going further, credentials would need to move server-side and
   per-user.
5. **Application deduplication** — nothing currently stops the agent from applying to the
   same company/role twice across separate runs; the tracking sheet already has the data
   to check against, it's just not consulted yet.
6. **A real evaluation set instead of four hand-written JDs** — the reliability brief
   would be stronger with a larger, more varied test set (different seniorities,
   industries, and deliberately adversarial JDs) and a tracked pass-rate trend across
   iterations, not a single snapshot.
7. **Rate-limiting and cooldown on Slack/email actions** — nothing currently caps how many
   applications this could send in a burst if pointed at a large batch; a daily cap
   alongside the auto-send threshold would be a cheap, real safety improvement.
8. **Observability beyond the JSON log** — `eval_log.json` is fine for a hackathon, but a
   lightweight dashboard (even a second Streamlit page) reading that log over time would
   make trends in guardrail pass rate and action failures visible at a glance instead of
   requiring someone to read raw JSON.
