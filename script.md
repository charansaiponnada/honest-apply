# Demo video script (2:00)

Record **http://localhost:8000/demo** full screen. It's 11 screens; move with **→ / ←**, the **Next** button,
or the dots at the bottom. Every screen has its own URL (`/demo#apps`, `/demo#chaos`, …) if you need a retake.

## Before you record

- [ ] Server running: `uvicorn main:app` from the repo root; open `/demo` and press **Ctrl+Shift+R** once.
- [ ] Screen 2 (*Connect apps*): your email is filled in and Gmail, Google Calendar, HubSpot and Slack all say **Connected**.
- [ ] Slack channel set (for example `#job-applications`) and that channel open in a second window for the cut-away.
- [ ] Pick the mode in the header: **Live apps** if all four apps are connected (real draft, event, deal and
      Slack posts, and you can cut to them), or **Simulated** (the default; no accounts needed, identical flow,
      apps marked as mock). Say which one on screen 2: "connected live" or "simulated for the demo".
- [ ] Pick dark or light with the sun/moon button and keep it for the whole video.
- [ ] Browser zoom 110–125% so text is readable at 1080p; hide bookmarks bar and notifications.
- [ ] Do one full rehearsal first (the demo can be re-run as often as you like), then record.
- [ ] Optional cut-aways: Gmail Drafts, Google Calendar (7 days out), HubSpot Deals, the Slack channel.

## Script

| Time | Screen | Do | Say |
|---|---|---|---|
| 0:00–0:10 | **1 · Intro** | Hold, then *Start* | "Students mass-apply with generic resumes, and AI auto-apply bots make it worse by inventing experience. Honest Apply is the job agent that won't lie for you." |
| 0:10–0:22 | **2 · Connect apps** | Point at the four *Connected* badges | "It's one agent acting across four real apps: Gmail, Google Calendar, HubSpot and Slack, each connected in one click through Composio, on my own accounts." |
| 0:22–0:30 | **3 · The job** | Click **Run the agent** | "Here's a backend job and a resume. Let's apply." |
| 0:30–0:45 | **4 · Agents at work** | Let the three agents and the four apps light up | "Three stages. The Researcher reads the job. The Tailor rewrites the resume only from lines that already exist. The Executor checks everything, then uses tool calling to choose which apps to act in." |
| 0:45–0:57 | **5 · Receipts** | Hover two tailored lines | "Every tailored line cites the resume line it came from, and the check runs in code, not in a prompt. One line it can't match, and nothing gets sent." |
| 0:57–1:12 | **6 · Apps hand off** | Point across the four cards; optional 2-second cut to Gmail / HubSpot / Slack | "And the apps hand off to each other: a Gmail draft, a follow-up on the calendar with the email link, a HubSpot deal with both links, and one Slack message with all of them." |
| 1:12–1:22 | **7 · They reply** | Click **Simulate the employer's reply** | "When the employer replies, the deal moves to Replied, the reminder cancels itself, and Slack pings me." |
| 1:22–1:36 | **8 · Honesty gate** | Click **Run the bait job** | "Now a job built to bait fabrication: Terraform, GCP, a certification this resume doesn't have. The gates stop it. No email, no deal. Just the skills gap, sent to Slack." |
| 1:36–1:47 | **9 · Chaos test** | Click **Break Gmail and run** | "Reliability: I break Gmail mid-run on purpose. It retries, reports why, finishes the other apps, and ends as partial instead of crashing." |
| 1:47–1:54 | **10 · Undo** | Click **Undo the application** | "And if I change my mind, one click reverses it everywhere." |
| 1:54–2:00 | **11 · Proof** | Hold on the KPIs | "Tested on ten job descriptions, normally and with failures injected. Honest Apply: apply at volume, without lying." |

About 290 words, a comfortable pace for two minutes. If you run long, drop the Receipts hover (screen 5) to one line.

## If something goes wrong on camera

- **A step shows an error toast:** press ← then → to reload the screen state, or open `/demo#job` and run again. Re-runs are never blocked as duplicates here.
- **The LLM is rate-limited:** the run still completes with the rule-based agents ("rule-based fallback" appears on screen 4). That's expected behavior and worth keeping in.
- **Undo says "Already undone":** run *The job* again, then undo that one.
- **Composio sign-in needed:** click *Connect* on screen 2; Composio returns you to the same screen.

## What the demo touches for real

With apps connected, screens 3–6 create a real Gmail draft, Calendar event, HubSpot deal and Slack posts; screen 8
posts a flagged message to Slack; screen 10 deletes the draft and event and closes the deal. The job posts and resume
come from `eval/`, so every run is the same.
