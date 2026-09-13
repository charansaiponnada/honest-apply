# Honest Apply — the job agent that won't lie for you

Built for the Multi-App AI Agent Hackathon (virtual, Sept 13, 2026).

Paste a resume and a job. **Three agents** read the job, tailor the candidate's *real*
experience to it, prove every line, and then act across **four apps that hand off to each
other**: Gmail, Google Calendar, HubSpot CRM and Slack. Built for individual job seekers,
and ready for the teams who place candidates (career centers, staffing agencies).

```
Job post + resume
   │
   ▼
[1] Researcher ─ job post → structured requirements (skills, seniority, must-haves, keywords)
   │
   ▼
[2] Tailor ───── resume + cover note, every line citing the original line it came from
   │
   ▼
[3] Executor ─── review: receipts check (code) + fit review (LLM)
   │             gates (code): overlap · receipts · seniority · duplicate
   │             act: LLM tool calling picks which apps to use — can do less, never skip a gate
   ▼
Gmail draft ──link──▶ Calendar follow-up ──links──▶ HubSpot deal ──all links──▶ Slack
   ▲                                                                              │
   └──────── reply tracker: Gmail reply → deal "replied" → reminder cancelled → Slack
```

## Demo video

**[Watch the 2-minute demo](ADD_VIDEO_LINK_BEFORE_SUBMITTING)**

## Project overview

**The problem:** students and early-career candidates applying at volume either spend an hour
tailoring each application or mass-apply with a generic resume, and "AI auto-apply" tools make it
worse by inventing experience. **What we built:** one multi-step agent (three specialized stages)
that tailors a real resume to a real job, proves every line is true, and only then does the busywork
across the apps the candidate already uses — email, calendar, CRM and chat — including follow-up
when the employer replies.

## External apps used

| App | What the agent does there | How it connects |
|---|---|---|
| **Gmail** | Creates the application draft; sends only when every gate passes and the user allows it; reads replies | Per-user **Connect** via Composio, or server OAuth |
| **Google Calendar** | Books a 7-day follow-up linked to the email; cancels it when a reply arrives | Per-user Composio, or server OAuth |
| **HubSpot CRM** | Creates a deal for the application; moves it to *replied*, or *closed-lost* on undo | Per-user Composio, or `HUBSPOT_TOKEN` |
| **Slack** | Reports every outcome with links, or why it stopped and the skills gap | Per-user Composio, or incoming webhook |
| Job boards (Arbeitnow, Remotive, RemoteOK) | Read-only source of live job posts | Public APIs |
| OpenRouter | LLM for the three agents, including tool calling | `OPENROUTER_API_KEY` |

## What makes it different

| | |
|---|---|
| **Receipts** | The Tailor cites a source line for every tailored line. The Executor verifies each in code (line similarity + every named tool, employer and number must exist in the original resume, cover note included). One unbacked claim blocks every app. |
| **Hard gates in code** | Keyword overlap below `GUARDRAIL_THRESHOLD`, an unbacked claim, a senior job for a student resume, or a repeat application → nothing is sent; Slack gets a skills-gap report instead. |
| **Apps that work together** | Each app's output feeds the next: the email link goes into the reminder, both go onto the CRM deal, Slack gets all three. The reply tracker closes the loop across all four. |
| **Chaos panel** | Switch off Gmail, Calendar, HubSpot, Slack, the LLM (429) or the Google token from the UI or the eval CLI. The real retry, error-classification and fallback code handles it. |
| **One-click undo** | Deletes the Gmail draft and Calendar event, moves the CRM deal to closed-lost, and tells Slack. A sent email can't be recalled, and undo says so. |
| **GitHub-verified skills** | Enter a GitHub username: job skills the resume lacks but public repos show (repo language, topic, or README mention) are added in a labeled section naming the repos, so the resume gets current without inventing anything. Short names like "Go" only count as a repo language, never as a word in prose. |
| **Recommendations + batch apply** | Live listings ranked by how many proven skills (resume + GitHub) they ask for, senior roles ranked down for early-career resumes. Select up to 5 and the agent applies to each in turn: drafts only, every gate and the duplicate check per job, live progress, one-click undo from the Tracker. |
| **Resume upload** | PDF or text upload, parsed server-side; scanned PDFs get a clear error instead of an empty resume. |
| **Sending is earned** | Gmail sends only if a Google account is connected, the user turned on *Allow sending*, a recipient is set, overlap clears `AUTO_SEND_THRESHOLD`, and every receipt checks out. Otherwise it's a draft. |

## Setup instructions

### Run it

```bash
uv sync                       # or: pip install -r requirements.txt
uvicorn main:app --reload     # run from the repo root
```

Open http://localhost:8000 for the landing page and http://localhost:8000/app for the agent.

The agent UI is a React + [shadcn/ui](https://ui.shadcn.com) app (Vite, Tailwind v4, Base UI) in `frontend/`.
Its production build is committed in `web/app-dist`, so running the server needs no Node. To change the UI:

```bash
cd frontend
npm install
npm run dev     # http://localhost:5173/app/, proxies /api to uvicorn on :8000
npm run build   # typechecks, then writes ../web/app-dist (served at /app)
```
With no keys at all, every integration runs in a clearly labeled **mock mode** (local files
under `eval/logs/`), so the whole pipeline works on a fresh clone.

### Connect your own apps (in the app)

With `COMPOSIO_API_KEY` set, the **Your apps** card in `/app` shows a **Connect** button for
Gmail, Google Calendar, HubSpot and Slack. The user enters their email, clicks Connect, signs in
on Composio's hosted page, and lands back in the app. [Composio](https://composio.dev) runs the
OAuth flow and stores and refreshes the tokens; the agent then acts on *that user's* accounts.
No Google Cloud project, HubSpot token or webhook needed per user.

Per app, per run: the user's Composio connection → server `.env` credentials → mock. Undo and the
reply tracker use whichever account the run used. Run `python -m scripts.check_connections --ping`
after adding the key: it confirms every Composio tool the agent calls exists and prints its
parameters.

### Or go live with server keys (all free)

Copy `.env.example` to `.env`, then:

1. **LLM:** OpenRouter key from [openrouter.ai/keys](https://openrouter.ai/keys) → `OPENROUTER_API_KEY`.
   The default free model is `nvidia/nemotron-3-super-120b-a12b:free`; override with `OPENROUTER_MODEL`.
   `python -m scripts.check_connections --ping` tells you whether the model returns tool calls
   (if not, the Executor falls back to deterministic dispatch and the UI says so).
2. **Gmail + Calendar:** Google Cloud project → enable Gmail and Calendar APIs → OAuth client
   (Desktop app) → save as `credentials.json`. Keep the consent screen in *Testing* and add yourself
   as a test user. Scopes: `gmail.compose`, `gmail.readonly` (reply tracker), `calendar.events`.
   The first Google action opens a browser; `token.json` is cached. If you authorized with an older
   scope set, delete `token.json` once.
3. **HubSpot CRM:** free account → Settings → Integrations → Private Apps → token with
   `crm.objects.companies`, `crm.objects.contacts`, `crm.objects.deals` read/write → `HUBSPOT_TOKEN`.
   Deals use the default pipeline's stage IDs; rename the stage labels in HubSpot (e.g. *Drafted,
   Sent, Replied*) or override the IDs with `HUBSPOT_STAGE_*`.
4. **Slack:** [Incoming Webhook](https://api.slack.com/messaging/webhooks) → `SLACK_WEBHOOK_URL`.
5. **Job boards:** nothing to set up. Arbeitnow, Remotive and RemoteOK are public APIs. LinkedIn,
   Indeed and Glassdoor are left out on purpose: their terms prohibit scraping.

Preflight before demoing: `python -m scripts.check_connections --ping`.

### Deploy (one service)

Render/Railway web service, start command `uvicorn main:app --host 0.0.0.0 --port $PORT`.
Set the `.env` values as environment variables. Hosts have no browser for Google OAuth, so
authorize locally once and paste the contents of `token.json` into `GOOGLE_TOKEN_JSON`.
Free tiers sleep, so open the URL a minute before the demo.

## Reliability testing

```bash
python -m eval.run_eval                       # 10 job descriptions, 4 checks each
python -m eval.run_eval --faults gmail,llm_429 # same suite with Gmail down and the LLM rate-limited
python -m agent.executor                      # receipts self-check (catches an injected fake bullet)
python -m agent.crm_action                    # candidate parsing self-check
```

The same runs are one click in the app's **Reliability** tab. Checks per job: extraction
(seniority + expected skills), faithfulness (nothing unbacked reached an app), decision
(flag-vs-proceed matches `eval/expected.json`), actions (all succeed, or under faults, every
failure is reported with a reason and nothing crashes). Results, known failure modes and what we'd
fix next: [docs/RELIABILITY.md](docs/RELIABILITY.md).

## Project structure

```
main.py                    FastAPI: landing, app, JSON API, live run event stream
web/                       index.html (three.js landing), app.html + app.js + styles.css (no build step)
agent/
  extract.py               Agent 1 — Researcher
  tailor.py                Agent 2 — Tailor (with receipts)
  executor.py              Agent 3 — receipts check, fit review, tool selection
  pipeline.py              orchestration, gates, app chaining, run log
  gmail_action.py          Gmail draft / gated send / undo
  calendar_action.py       Calendar follow-up / undo
  crm_action.py            HubSpot company + contact + deal / stage changes
  slack_action.py          Slack messages
  reply_tracker.py         Gmail reply → CRM stage → cancel reminder → Slack
  undo.py                  reverse a run across apps
  guardrail.py             keyword overlap + thresholds
  llm.py                   OpenRouter JSON + tool calling, mock fallback
  google_auth.py           OAuth (file or GOOGLE_TOKEN_JSON)
  utils.py                 retries, error classification, chaos faults
  jobs_search.py           live job boards
eval/                      run_eval.py, expected.json, sample_jds/ (10), sample_resume.txt
scripts/check_connections.py
skills/                    SKILL.md per agent skill
```
