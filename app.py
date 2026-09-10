"""
AI Job Application Agent — product UI.

Run with: streamlit run app.py
"""
import glob
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agent.pipeline import run_pipeline  # noqa: E402
from agent.tailor import diff_lines  # noqa: E402
from agent.llm import is_live as llm_is_live  # noqa: E402
from agent.google_auth import is_live as google_is_live  # noqa: E402
from agent.slack_action import is_live as slack_is_live  # noqa: E402
from agent.jobs_search import search_jobs  # noqa: E402

# ---------------------------------------------------------------------------
# Page config + design tokens (neutral, shadcn/ui-inspired system)
# ---------------------------------------------------------------------------
st.set_page_config(page_title="AI Job Application Agent", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --background: #fafafa;
        --foreground: #09090b;
        --card: #ffffff;
        --muted: #f4f4f5;
        --muted-foreground: #71717a;
        --border: #e4e4e7;
        --primary: #18181b;
        --primary-foreground: #fafafa;
        --secondary: #f4f4f5;
        --secondary-foreground: #18181b;
        --success-bg: #f0fdf4; --success-fg: #15803d; --success-border: #bbf7d0;
        --warning-bg: #fffbeb; --warning-fg: #b45309; --warning-border: #fde68a;
        --destructive-bg: #fef2f2; --destructive-fg: #b91c1c; --destructive-border: #fecaca;
        --radius: 8px;
    }

    html, body, .stApp {
        background-color: var(--background) !important;
        color: var(--foreground) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    .block-container { padding-top: 2.5rem; max-width: 1100px; }

    h1, h2, h3, h4, p, label, span, div, .stMarkdown { color: var(--foreground); }
    .stCaption, [data-testid="stCaptionContainer"] p { color: var(--muted-foreground) !important; font-size: 0.82rem !important; }

    .app-title { font-size: 1.5rem; font-weight: 600; letter-spacing: -0.02em; margin-bottom: 0.15rem; }
    .app-subtitle { color: var(--muted-foreground); font-size: 0.88rem; max-width: 640px; line-height: 1.5; margin-bottom: 1rem; }

    .section-label {
        font-size: 0.72rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.06em; color: var(--muted-foreground); margin: 1.4rem 0 0.5rem;
    }

    /* status row */
    .status-row { display: flex; flex-wrap: wrap; gap: 1.1rem; margin-bottom: 1.4rem; }
    .status-item { display: flex; align-items: center; font-size: 0.8rem; color: var(--muted-foreground); }
    .status-dot { width: 7px; height: 7px; border-radius: 50%; margin-right: 0.45rem; flex-shrink: 0; }
    .status-dot-live { background-color: #22c55e; }
    .status-dot-mock { background-color: #f59e0b; }
    .status-dot-static { background-color: #a1a1aa; }

    /* buttons */
    .stButton > button {
        background-color: var(--primary);
        color: var(--primary-foreground);
        border: 1px solid var(--primary);
        border-radius: 6px;
        padding: 0.45em 1.1em;
        font-weight: 500;
        font-size: 0.85rem;
    }
    .stButton > button:hover { background-color: #27272a; border-color: #27272a; color: var(--primary-foreground); }

    /* cards */
    .card {
        background-color: var(--card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 1rem 1.2rem;
        margin-bottom: 0.9rem;
    }

    /* badges */
    .badge {
        display: inline-flex; align-items: center; padding: 0.18rem 0.65rem;
        border-radius: 999px; font-size: 0.75rem; font-weight: 500; border: 1px solid transparent;
    }
    .badge-warning { background: var(--warning-bg); color: var(--warning-fg); border-color: var(--warning-border); }
    .badge-success { background: var(--success-bg); color: var(--success-fg); border-color: var(--success-border); }
    .badge-neutral { background: var(--secondary); color: var(--secondary-foreground); border-color: var(--border); }

    /* stepper */
    .stepper { display: flex; align-items: center; flex-wrap: wrap; margin: 0.4rem 0 1.2rem; }
    .step-circle {
        width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center;
        justify-content: center; font-size: 0.68rem; font-weight: 600;
        border: 1.5px solid var(--border); color: var(--muted-foreground); background: var(--card);
        flex-shrink: 0;
    }
    .step-label { margin: 0 1rem 0 0.5rem; font-size: 0.8rem; color: var(--muted-foreground); font-weight: 500; }
    .step-line { width: 28px; height: 1.5px; background: var(--border); margin-right: 1rem; }
    .step-running .step-circle { border-color: var(--foreground); color: var(--foreground); }
    .step-running .step-label { color: var(--foreground); }
    .step-done .step-circle { background: var(--foreground); border-color: var(--foreground); color: var(--background); }
    .step-done .step-label { color: var(--foreground); }
    .step-skipped .step-circle { border-style: dashed; }
    .step-skipped .step-label { text-decoration: line-through; }

    /* action checklist */
    .action-row { display: flex; align-items: flex-start; font-size: 0.85rem; padding: 0.3rem 0; }
    .action-icon {
        width: 16px; height: 16px; border-radius: 50%; display: inline-flex; align-items: center;
        justify-content: center; font-size: 0.65rem; font-weight: 700; margin-right: 0.55rem; flex-shrink: 0; margin-top: 0.1rem;
    }
    .action-icon-success { background: var(--success-bg); color: var(--success-fg); }
    .action-icon-error { background: var(--destructive-bg); color: var(--destructive-fg); }
    .action-mock-tag { color: var(--muted-foreground); font-weight: 400; }

    /* callout */
    .callout {
        border-left: 3px solid var(--warning-border); background: var(--warning-bg);
        padding: 0.7rem 1rem; border-radius: 0 var(--radius) var(--radius) 0;
        font-size: 0.82rem; color: var(--warning-fg); margin-bottom: 0.9rem;
    }

    /* diff lines */
    .diff-line { font-size: 0.8rem; padding: 0.15rem 0; line-height: 1.55; color: var(--foreground); }
    .diff-tag {
        display: inline-block; font-size: 0.62rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.03em; background: var(--muted); color: var(--muted-foreground);
        padding: 0.05rem 0.35rem; border-radius: 4px; margin-right: 0.45rem; vertical-align: middle;
    }

    /* misc streamlit overrides */
    div[data-testid="stDataFrame"] { background-color: var(--card); border-radius: var(--radius); border: 1px solid var(--border); }
    .stTextArea textarea, .stTextInput input { border-radius: 6px !important; border-color: var(--border) !important; font-size: 0.85rem !important; }
    [data-testid="stExpander"] { border: 1px solid var(--border) !important; border-radius: var(--radius) !important; background: var(--card); }
    </style>
    """,
    unsafe_allow_html=True,
)

SAMPLE_RESUME = ""
resume_path = os.path.join("eval", "sample_resume.txt")
if os.path.exists(resume_path):
    SAMPLE_RESUME = open(resume_path).read()

SAMPLE_JD = ""
jd_path = os.path.join("eval", "sample_jds", "backend_engineer.txt")
if os.path.exists(jd_path):
    SAMPLE_JD = open(jd_path).read()

STEP_LABELS = {
    "extract": "Extract",
    "tailor": "Tailor",
    "guardrail": "Guardrail",
    "act": "Act",
}


def render_stepper(placeholder, progress: dict) -> None:
    keys = list(STEP_LABELS.keys())
    html = '<div class="stepper">'
    for i, key in enumerate(keys):
        status = progress.get(key, "pending")
        icon = {"done": "&#10003;", "skipped": "&#8211;", "running": str(i + 1), "pending": str(i + 1)}[status]
        html += f'<div class="step-{status}" style="display:flex;align-items:center;">'
        html += f'<div class="step-circle">{icon}</div><div class="step-label">{STEP_LABELS[key]}</div></div>'
        if i < len(keys) - 1:
            html += '<div class="step-line"></div>'
    html += "</div>"
    placeholder.markdown(html, unsafe_allow_html=True)


def status_dot(label: str, live: bool | None) -> str:
    if live is None:
        cls = "status-dot-static"
        state = "available"
    elif live:
        cls = "status-dot-live"
        state = "live"
    else:
        cls = "status-dot-mock"
        state = "mock"
    return f'<span class="status-item"><span class="status-dot {cls}"></span>{label} &mdash; {state}</span>'


st.markdown('<div class="app-title">AI Job Application Agent</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">Searches live listings, extracts requirements, tailors the resume and '
    "cover note against your real experience, and acts across six integrations — gated by a confidence "
    "guardrail and a stricter auto-send threshold on top of it.</div>",
    unsafe_allow_html=True,
)

live_llm = llm_is_live()
live_google = google_is_live()
live_slack = slack_is_live()
status_html = '<div class="status-row">'
status_html += status_dot("OpenRouter LLM", live_llm)
status_html += status_dot("Google Workspace", live_google)
status_html += status_dot("Slack", live_slack)
status_html += status_dot("Job boards", None)
status_html += "</div>"
st.markdown(status_html, unsafe_allow_html=True)

tab_run, tab_batch = st.tabs(["Run agent", "Test suite"])

# ---------------------------------------------------------------------------
# Tab 1: single run
# ---------------------------------------------------------------------------
with tab_run:
    if "jd_text_area" not in st.session_state:
        st.session_state.jd_text_area = SAMPLE_JD
    if "company_input" not in st.session_state:
        st.session_state.company_input = "Northstar Systems"
    if "role_input" not in st.session_state:
        st.session_state.role_input = "Backend Engineer"

    with st.expander("Search live job boards"):
        kw_col, remote_col, search_col = st.columns([3, 1, 1])
        keyword = kw_col.text_input("Keyword (role or skill)", value="engineer", key="job_search_kw")
        remote_only = remote_col.checkbox("Remote only", key="job_search_remote")
        if search_col.button("Search", use_container_width=True):
            jobs, err = search_jobs(keyword, remote_only=remote_only, limit=6)
            st.session_state.job_search_results = jobs
            st.session_state.job_search_error = err

        err = st.session_state.get("job_search_error")
        if err:
            st.caption(err)
        for i, job in enumerate(st.session_state.get("job_search_results", [])):
            row = st.columns([5, 1])
            tag = " &middot; remote" if job["remote"] else ""
            row[0].markdown(
                f'<span class="badge badge-neutral">{job["source"]}</span>&nbsp;'
                f'<strong>{job["title"]}</strong> &mdash; {job["company_name"]}{tag}',
                unsafe_allow_html=True,
            )
            if row[1].button("Use listing", key=f"use_job_{i}"):
                st.session_state.jd_text_area = job["description"] or job["title"]
                st.session_state.company_input = job["company_name"]
                st.session_state.role_input = job["title"]
                st.rerun()

    col_in, col_meta = st.columns([3, 1])
    with col_in:
        resume_text = st.text_area("Resume", value=SAMPLE_RESUME, height=260)
        jd_text = st.text_area("Job description (paste text, or pull one above)", key="jd_text_area", height=220)
    with col_meta:
        company = st.text_input("Company", key="company_input")
        role = st.text_input("Role", key="role_input")
        spreadsheet_id = st.text_input(
            "Google Sheet ID (optional)", value="", help="Leave blank to use local mock tracking."
        )
        run_clicked = st.button("Run agent", use_container_width=True)

    if "progress" not in st.session_state:
        st.session_state.progress = {k: "pending" for k in STEP_LABELS}

    progress_placeholder = st.empty()
    render_stepper(progress_placeholder, st.session_state.progress)

    if run_clicked:
        if not resume_text.strip() or not jd_text.strip():
            st.error("Resume and job description are both required.")
        else:
            progress = {k: "pending" for k in STEP_LABELS}
            render_stepper(progress_placeholder, progress)

            def cb(step, status):
                progress[step] = status
                render_stepper(progress_placeholder, progress)

            with st.spinner("Running pipeline..."):
                result = run_pipeline(
                    resume_text=resume_text,
                    jd_text=jd_text,
                    company=company or "Unknown Co",
                    role=role or "Unknown Role",
                    spreadsheet_id=spreadsheet_id.strip() or None,
                    progress_cb=cb,
                )
            st.session_state.last_result = result
            st.session_state.last_resume_text = resume_text

    if "last_result" in st.session_state:
        result = st.session_state.last_result
        guardrail = result["guardrail"]

        st.markdown('<div class="section-label">Result</div>', unsafe_allow_html=True)

        badge_col, score_col = st.columns([1, 3])
        with badge_col:
            gmail_sent = result["actions"].get("gmail", {}).get("sent", False)
            if guardrail["needs_review"]:
                st.markdown('<span class="badge badge-warning">Flagged for review</span>', unsafe_allow_html=True)
            elif gmail_sent:
                st.markdown('<span class="badge badge-success">Auto-sent</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="badge badge-neutral">Drafted &mdash; awaiting review</span>', unsafe_allow_html=True)
        with score_col:
            st.caption(
                f"Keyword overlap: {guardrail['score']*100:.0f}% "
                f"(review threshold {guardrail['threshold']*100:.0f}%, "
                f"auto-send threshold {guardrail['auto_send_threshold']*100:.0f}%) &middot; "
                f"{len(guardrail['matched'])} matched / {len(guardrail['missing'])} missing"
            )

        req = result["requirements"]
        with st.expander("Extracted JD requirements"):
            c1, c2 = st.columns(2)
            c1.write(f"**Seniority:** {req.get('seniority', '?')}")
            c1.write(f"**Skills:** {', '.join(req.get('skills', [])) or '—'}")
            c2.write(f"**Must-haves:** {'; '.join(req.get('must_haves', [])) or '—'}")
            c2.write(f"**Keywords:** {', '.join(req.get('keywords', [])) or '—'}")

        st.markdown('<div class="section-label">Tailored resume</div>', unsafe_allow_html=True)
        orig_resume_used = st.session_state.get("last_resume_text", resume_text)
        col_before, col_after = st.columns(2)
        with col_before:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.caption("Original")
            st.text(orig_resume_used)
            st.markdown("</div>", unsafe_allow_html=True)
        with col_after:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.caption("Tailored")
            diffed = diff_lines(orig_resume_used, result["tailored_resume"])
            for status, line in diffed:
                if status == "reworded":
                    st.markdown(f'<div class="diff-line"><span class="diff-tag">edited</span>{line}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="diff-line">{line}</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-label">Cover note</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card">{result["cover_note"]}</div>', unsafe_allow_html=True)

        st.markdown('<div class="section-label">Application actions</div>', unsafe_allow_html=True)
        action_labels = {
            "gmail": "Gmail draft",
            "sheets": "Sheet row",
            "calendar": "Calendar reminder",
            "drive": "Drive file",
            "slack": "Slack notification",
        }
        if guardrail["needs_review"]:
            st.markdown(
                '<div class="callout">Gmail, Sheets, Calendar, and Drive were skipped because this '
                "application was flagged for review. Slack was still notified.</div>",
                unsafe_allow_html=True,
            )
        for key, label in action_labels.items():
            a = result["actions"].get(key)
            if a is None:
                continue
            if key == "gmail" and a.get("sent"):
                label = "Gmail — sent"
            icon_cls = "action-icon-success" if a.get("status") in ("ok", "mocked") else "action-icon-error"
            icon_char = "&#10003;" if a.get("status") in ("ok", "mocked") else "&#10005;"
            mock_tag = ' <span class="action-mock-tag">(mock)</span>' if a.get("status") == "mocked" else ""
            st.markdown(
                f'<div class="action-row"><span class="action-icon {icon_cls}">{icon_char}</span>'
                f'<span><strong>{label}</strong>{mock_tag} &mdash; {a.get("detail", "")}</span></div>',
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------------------
# Tab 2: batch eval
# ---------------------------------------------------------------------------
with tab_batch:
    st.caption(
        "Runs the pipeline against every sample JD in eval/sample_jds/ using "
        "eval/sample_resume.txt, for the reliability brief."
    )
    if st.button("Run test batch"):
        jd_files = sorted(glob.glob(os.path.join("eval", "sample_jds", "*.txt")))
        resume = SAMPLE_RESUME
        rows = []
        bar = st.progress(0.0)
        for i, jd_file in enumerate(jd_files):
            jd_text_b = open(jd_file).read()
            stem = os.path.splitext(os.path.basename(jd_file))[0]
            role_b = stem.replace("_", " ").title()
            result_b = run_pipeline(
                resume_text=resume,
                jd_text=jd_text_b,
                company="Sample Co",
                role=role_b,
                jd_source=os.path.basename(jd_file),
            )
            gmail_state = (
                "n/a (flagged)"
                if result_b["guardrail"]["needs_review"]
                else ("auto-sent" if result_b["actions"].get("gmail", {}).get("sent") else "drafted")
            )
            rows.append(
                {
                    "JD file": os.path.basename(jd_file),
                    "Seniority": result_b["requirements"].get("seniority", "?"),
                    "Overlap": f"{result_b['guardrail']['score']*100:.0f}%",
                    "Needs review": result_b["guardrail"]["needs_review"],
                    "Gmail": gmail_state,
                    "Result": "PASS" if result_b["passed"] else "FAIL",
                    "Live LLM": result_b["used_live_llm"],
                }
            )
            bar.progress((i + 1) / max(len(jd_files), 1))

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)
        passed = sum(1 for r in rows if r["Result"] == "PASS")
        st.caption(f"{passed}/{len(rows)} test JDs passed. Full run details logged to eval/logs/eval_log.json")
