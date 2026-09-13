# PRD: AI Job Application Agent
**Version:** 1.0 (Hackathon Build) · **Date:** September 9, 2026
**Author:** Charan Sai Ponnada
**Event:** Multi-App AI Agent Hackathon (Sept 13, 2026, Arga Labs)

> **Build-day changes (Sept 13):** Streamlit replaced by FastAPI + a three.js landing page and a
> vanilla JS app (one service, one URL). Apps the agent acts in are now Gmail, Google Calendar,
> **HubSpot CRM** (replaces Sheets, so teams get a real pipeline) and Slack; Drive dropped. Still
> exactly 3 agents. Added: receipts (source-line citations verified in code), seniority and
> duplicate gates, LLM tool calling in the Executor, app chaining, a reply tracker, a chaos panel,
> one-click undo and a 10-job, 4-check eval. Gmail sends only when a Google account is connected,
> the user opts in, and every gate passes. The sections below are the original pre-event plan.

---

## 1. Problem Statement

Engineering students applying to jobs waste hours per application: rewriting resumes to match each JD, drafting cover notes, tracking who they applied to and when, and remembering to follow up. Most give up on tailoring and mass-apply with a generic resume, which lowers response rates. There's no free, open tool that closes this loop end-to-end.

## 2. Goal

Build an AI agent that takes a resume + a job description and autonomously: extracts what the JD actually wants, tailors the resume and writes a cover note against it, drafts the application, logs it, and schedules a follow-up — across at least 3 real external apps, at zero cost.

## 3. Core Loop

```
Resume (Drive) + Job Description
        │
        ▼
 [1] JD Requirement Extraction  → structured JSON (skills, seniority, must-haves)
        │
        ▼
 [2] Resume/Cover Note Tailoring → grounded strictly in [1], no fabricated experience
        │
        ▼
 [3] Multi-App Action Layer
        ├─ Gmail    → draft application email (never auto-send in MVP)
        ├─ Sheets   → append tracking row (company, role, date, status)
        ├─ Calendar → create 7-day follow-up reminder
        └─ Drive    → store tailored resume version
        │
        ▼
 [4] Reliability Layer → confidence check, human-review flag, eval logging
```

## 4. Target User

Final-year engineering students / early-career job seekers doing high-volume applications who want tailored quality without the manual time cost. (Same audience as the standalone open-source version of this project.)

---

## 5. Scope: MVP (Hackathon) vs. Production

| Area | MVP (Sept 13, single day) | Production (post-hackathon) |
|---|---|---|
| **Input** | Paste resume text + paste JD text or URL | Resume upload (PDF/DOCX) with parsing, JD auto-scraped from company career pages |
| **JD extraction** | Single LLM call → JSON (skills, keywords, seniority) | Multi-pass extraction + validation, company/role taxonomy |
| **Tailoring** | One-shot resume rewrite + cover note, grounded in extracted JSON | Iterative refinement, tone/style controls, multiple resume variants, ATS keyword scoring |
| **Gmail** | Creates a **draft** only (human sends) | Optional auto-send with user-approved templates, thread tracking for replies |
| **Sheets tracking** | Single sheet, manual columns (company, role, JD link, date, status) | Full dashboard: response rates, funnel stages, analytics |
| **Calendar** | One static 7-day follow-up event | Smart scheduling around existing calendar, interview prep reminders |
| **Drive** | Store tailored resume as a new file | Versioned resume history, org-by-company folder structure |
| **Auth** | Single Google account, OAuth for personal use | Multi-user auth, per-user credential isolation |
| **Reliability** | ~10-JD test set, pass/fail log, confidence flag for low-overlap matches | Continuous eval pipeline, regression testing, guardrail tuning over time |
| **Job discovery** | Manual JD input | Agent actively pulls listings from company career pages (per earlier decision to avoid LinkedIn/Indeed aggregators) |
| **Hosting** | Local / notebook / single free-tier deploy for demo | Proper backend + open-source repo, deployable by other students |

---

## 6. Agent Skills Required

The agent needs these discrete capabilities — build/test each as its own function so failures are isolated and debuggable during judging:

1. **JD parsing skill** — turns unstructured JD text into structured requirements JSON
2. **Resume tailoring skill** — rewrites resume content constrained to the candidate's real, existing experience (no invention)
3. **Cover note generation skill** — short, JD-specific note grounded in the same extracted JSON
4. **Gmail draft-creation skill** — composes and attaches via Gmail API, does not send
5. **Sheets append skill** — writes a structured row per application
6. **Calendar event-creation skill** — schedules follow-up with correct date math
7. **Drive read/write skill** — pulls the base resume, stores the tailored version
8. **Confidence/guardrail skill** — scores keyword overlap between resume and JD; below threshold → flags for human review instead of proceeding automatically
9. **Eval logging skill** — records every run's input, output, and pass/fail against your test set, in a format you can screenshot for the reliability brief

---

## 7. Tech Stack (Zero-Rupee Build)

| Layer | Choice | Why it's free | Free-tier limit to know |
|---|---|---|---|
| LLM | Gemini API (free tier via Google AI Studio) | No-cost inference tier | ~15 req/min, 1,500 req/day on Gemini Flash — plenty for a demo + 10-JD test set |
| LLM (backup) | Ollama running a local model (Llama 3 / Phi-3) on your laptop | Zero API calls at all | Limited by your machine's RAM/GPU, no rate limit |
| Agent orchestration | Python + a lightweight framework (LangGraph, or a plain function-calling loop) or Amazon Strands SDK (open-source, you already use it at Aynstyn) | Open source, no license cost | — |
| Gmail / Sheets / Calendar / Drive | Google Workspace APIs via OAuth on your personal Gmail | Free for personal-use quota, no billing account needed | Gmail API ~250 quota units/user/sec, Sheets/Calendar/Drive APIs all have generous free daily quotas — irrelevant at hackathon scale |
| Backend | FastAPI (Python) | Open source | — |
| Frontend/demo UI | React (Vite) or Streamlit if you want to skip frontend build time entirely | Free, fast to build | — |
| Hosting for demo | Local machine + ngrok/Cloudflare Tunnel, or Render/Railway free web-service tier | $0 | Free hosting tiers sleep after inactivity — fine for a live demo, not for 24/7 uptime |
| Tracking sheet | Google Sheets (already one of your 3 apps) | Free | — |
| Repo | GitHub public repo | Free, doubles as your submission artifact | — |

**Zero-cost guardrails to watch:** stay inside free LLM API quotas, don't enable Google Cloud billing (these OAuth scopes work under "Testing" publish status without billing enabled), skip paid hosting entirely — for judging day, a laptop + tunnel is enough since you're demoing live anyway.

---

## 7a. How to Set It Up at Zero Cost

**1. LLM access**
- Go to Google AI Studio (aistudio.google.com) → generate a free Gemini API key. No card required.
- Optional fallback: install Ollama locally (`ollama pull llama3`) so you have an offline backup if you hit rate limits mid-demo.

**2. Google Workspace APIs (Gmail, Sheets, Calendar, Drive)**
- Create a project in Google Cloud Console (free, no billing needed for these low-volume API calls).
- Enable the Gmail API, Sheets API, Calendar API, and Drive API for that project.
- Create OAuth 2.0 credentials (Desktop app type is simplest for a hackathon script).
- Leave the OAuth consent screen in **"Testing"** mode and add your own Gmail as a test user — this skips Google's verification review entirely, which you don't have time for before the 13th.
- Store the client secret + generated token locally (`.json` files), never commit them to the public repo — add them to `.gitignore`.

**3. Backend**
- `pip install fastapi uvicorn google-api-python-client google-auth-oauthlib google-generativeai`
- All open-source, no paid packages needed.

**4. Frontend**
- If time is tight, skip React and use Streamlit (`pip install streamlit`) — you get a working UI in ~50 lines of Python, no separate frontend build/deploy step.

---

## 7b. Deployment (Demo Day)

You don't need a production deployment for judging — you need something reliable for a 2-minute live demo plus a fallback recording. Two zero-cost paths:

**Option A — Local + tunnel (simplest, recommended for demo day)**
1. Run your FastAPI/Streamlit app locally: `uvicorn main:app --reload` or `streamlit run app.py`
2. Expose it with a free tunnel: `ngrok http 8000` (or Cloudflare Tunnel, also free) — gives you a public URL if judges need to click through, otherwise just demo on your own screen
3. Record a 2-minute backup video of a full successful run *before* judging starts, in case live wifi/API calls fail

**Option B — Free-tier cloud hosting (if you want a persistent live link)**
1. Push your repo to GitHub
2. Deploy the backend on Render or Railway free web-service tier (connect the GitHub repo, auto-deploys on push)
3. Set your Gemini API key and Google OAuth credentials as environment variables in the host's dashboard — never hardcode them
4. Deploy the frontend (if separate) on Vercel's free tier, pointed at your backend URL
5. Note: free tiers spin down after inactivity, so ping the URL a minute before your demo slot to "wake" it

**Submission checklist:**
- Public GitHub repo with a clear README (what it does, setup steps, the 3+ apps integrated)
- `.env.example` showing required environment variables (never commit real keys)
- The 2-minute demo video
- The reliability brief (from Section 9) as a short markdown/PDF in the repo

---

## 8. UI / Demo Design

Since usefulness (20%) and demo clarity (10%) are judged, a clean minimal UI matters even though it's not the biggest scoring weight — pick something you can build in under an hour.

**Theme direction:** professional-but-approachable, not generic SaaS-blue. Suggested palette:

| Role | Color | Hex |
|---|---|---|
| Primary (CTA, accents) | Terracotta | `#C2622D` |
| Secondary (success states) | Olive / sage | `#7A8450` |
| Background | Cream | `#FBF3E7` |
| Text primary | Warm charcoal | `#3A2E27` |
| Warning/flag (low-confidence review) | Golden amber | `#D9A441` |
| Card surfaces | Warm ivory with soft border | `#FFFDF8` / `#E8DCC8` border |

**Typography:** one clean sans-serif (Inter or system-ui), single weight scale — don't spend hackathon time on custom fonts.

**Key screens/elements for the demo:**
- Input panel: resume text box + JD text/URL box, single "Run agent" button
- Live pipeline view: 3-agent progress indicator (Researcher → Tailor → Executor) so judges *see* the multi-step agent working across apps, not just a final output
- Result card: tailored resume diff (before/after), cover note, and a row showing what happened in each app (draft created ✓, sheet logged ✓, reminder set ✓)
- Confidence badge: green (proceeded automatically) vs amber (flagged for review) — this visually sells your reliability layer
- Simple eval panel: "9/10 test JDs passed" style summary, screenshot-able for your reliability brief

---

## 9. Reliability & Evaluation Plan

- Build a fixed test set of ~10 real JDs across varied roles before the demo
- For each run, log: extraction accuracy (did it get the right skills/seniority?), tailoring faithfulness (no fabricated experience — check manually or with a second LLM-as-judge pass), and end-to-end action success (did all 3+ app actions complete without manual fixes?)
- Anything below your confidence threshold routes to "flagged for review" rather than silently failing or over-claiming
- Package this as a short one-page brief: what you tested, pass rate, known failure modes, what you'd fix in production

---

## 10. Hackathon Day Timeline (Sept 13, 9 AM–5 PM Pacific)

| Time | Focus |
|---|---|
| 9:00–9:30 | Opening, confirm OAuth/API keys work end to end before building |
| 9:30–11:00 | Skills 1–2 (JD extraction, tailoring) working standalone |
| 11:00–1:00 | Skills 4–7 (Gmail, Sheets, Calendar, Drive actions wired in) |
| 1:00–2:00 | Skill 8 (guardrail/confidence check) + basic UI |
| 2:00–3:00 | Skill 9 (eval logging) + run the 10-JD test set |
| 3:00–4:00 | Polish UI, write reliability brief, rehearse 2-min demo |
| 4:00–4:40 | Judging & selection |

---

## 11. Success Metrics (for judging alignment)

- **Technical execution (30%):** all 4 apps genuinely integrated and working live, not mocked
- **Reliability & eval (25%):** documented test set + pass rate + failure-mode honesty
- **Usefulness (20%):** solves a real, personally-validated problem (this is literally your own planned open-source project)
- **Originality (15%):** the guardrail/confidence-flagging layer + grounding tailoring strictly in extracted JD JSON (anti-hallucination) differentiates it from generic "auto-apply bot" submissions
- **Demo clarity (10%):** the 3-agent live pipeline view exists specifically to make the multi-step agent visible in under 2 minutes

---

## 12. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| OAuth setup eats hackathon time | Set up and test all 4 Google API scopes *before* the event starts |
| LLM hallucinates fabricated resume experience | Hard-constrain tailoring prompt to only reorder/rephrase existing resume content, never add new claims; guardrail skill double-checks |
| Free API tier rate limits during demo | Cache/test with a small fixed test set beforehand; don't hammer live during judging |
| Demo breaks live | Have a recorded 2-min backup demo video as fallback |