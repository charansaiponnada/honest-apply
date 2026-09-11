"""
AI Job Application Agent — product UI.

Run with: streamlit run app.py
"""
import glob
import json
import os

import altair as alt
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

EVAL_LOG_PATH = os.path.join("eval", "logs", "eval_log.json")

# ---------------------------------------------------------------------------
# Page config + design tokens (PRD §8: terracotta / cream / sage / ivory)
# ---------------------------------------------------------------------------
st.set_page_config(page_title="AI Job Application Agent", page_icon=":material/work:", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --background: #FBF3E7;
        --foreground: #3A2E27;
        --card: #FFFDF8;
        --muted: #F3E9DB;
        --muted-foreground: #6E5D4F;
        --border: #E8DCC8;
        --primary: #C2622D;
        --primary-hover: #A9521F;
        --primary-foreground: #FFFFFF;
        --secondary: #F3E9DB;
        --secondary-foreground: #3A2E27;
        --success-bg: #EDF1E2; --success-fg: #4E5A2F; --success-border: #D5DFC2;
        --warning-bg: #FBF0D9; --warning-fg: #8F6519; --warning-border: #F0DDB5;
        --destructive-bg: #F9E6E0; --destructive-fg: #8F2E15; --destructive-border: #EEBFB1;
        --radius: 10px;
        --shadow-sm: 0 1px 2px rgba(90, 74, 58, 0.06);
    }

    html, body, .stApp {
        background-color: var(--background) !important;
        color: var(--foreground) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    .block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1180px; }

    h1, h2, h3, h4, p, label, span, div, .stMarkdown { color: var(--foreground); }
    .stCaption, [data-testid="stCaptionContainer"] p { color: var(--muted-foreground) !important; font-size: 0.82rem !important; }

    /* header */
    .app-header { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap;
        border-bottom: 1px solid var(--border); padding-bottom: 1rem; margin-bottom: 1.3rem; }
    .app-title { font-size: 1.4rem; font-weight: 600; letter-spacing: -0.02em; margin-bottom: 0.2rem; }
    .app-subtitle { color: var(--muted-foreground); font-size: 0.85rem; max-width: 620px; line-height: 1.5; }

    .status-row { display: flex; flex-wrap: wrap; gap: 1.1rem; }
    .status-item { display: flex; align-items: center; font-size: 0.78rem; color: var(--muted-foreground); white-space: nowrap; }
    .status-dot { width: 6px; height: 6px; border-radius: 50%; margin-right: 0.4rem; flex-shrink: 0; }
    .status-dot-live { background-color: #7A8450; }
    .status-dot-mock { background-color: #D9A441; }
    .status-dot-static { background-color: #9B8F7B; }

    .section-label {
        font-size: 0.72rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.06em; color: var(--muted-foreground); margin: 0 0 0.6rem;
    }

    /* buttons */
    .stButton > button {
        background-color: var(--primary);
        color: var(--primary-foreground);
        border: 1px solid var(--primary);
        border-radius: 6px;
        padding: 0.45em 1.1em;
        font-weight: 500;
        font-size: 0.85rem;
        box-shadow: none;
    }
    .stButton > button:hover { background-color: var(--primary-hover); border-color: var(--primary-hover); color: var(--primary-foreground); }
    .stDownloadButton > button {
        background-color: var(--card); color: var(--foreground); border: 1px solid var(--border);
        border-radius: 6px; font-size: 0.8rem; font-weight: 500; padding: 0.4em 0.9em;
    }

    /* cards */
    .card {
        background-color: var(--card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 1rem 1.2rem;
        margin-bottom: 0.9rem;
        box-shadow: var(--shadow-sm);
    }
    .card-flush { padding: 0; overflow: hidden; }

    /* metric cards */
    .metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.8rem; margin-bottom: 1.4rem; }
    .metric-card {
        background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
        padding: 0.95rem 1.1rem; box-shadow: var(--shadow-sm);
    }
    .metric-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted-foreground); margin-bottom: 0.4rem; }
    .metric-value { font-size: 1.55rem; font-weight: 600; letter-spacing: -0.02em; line-height: 1; }
    .metric-sub { font-size: 0.72rem; color: var(--muted-foreground); margin-top: 0.3rem; }
    @media (max-width: 900px) { .metric-grid { grid-template-columns: repeat(2, 1fr); } }

    /* badges */
    .badge {
        display: inline-flex; align-items: center; padding: 0.18rem 0.65rem;
        border-radius: 999px; font-size: 0.74rem; font-weight: 500; border: 1px solid transparent;
    }
    .badge-warning { background: var(--warning-bg); color: var(--warning-fg); border-color: var(--warning-border); }
    .badge-success { background: var(--success-bg); color: var(--success-fg); border-color: var(--success-border); }
    .badge-neutral { background: var(--secondary); color: var(--secondary-foreground); border-color: var(--border); }

    /* stepper */
    .stepper { display: flex; align-items: center; flex-wrap: wrap; margin: 0.2rem 0 1.1rem; }
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
    .action-row { display: flex; align-items: flex-start; font-size: 0.85rem; padding: 0.32rem 0; border-bottom: 1px solid var(--border); }
    .action-row:last-child { border-bottom: none; }
    .action-icon {
        width: 16px; height: 16px; border-radius: 50%; display: inline-flex; align-items: center;
        justify-content: center; font-size: 0.65rem; font-weight: 700; margin-right: 0.55rem; flex-shrink: 0; margin-top: 0.15rem;
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
    .empty-state {
        text-align: center; padding: 2.5rem 1rem; color: var(--muted-foreground);
        border: 1px dashed var(--border); border-radius: var(--radius); font-size: 0.85rem;
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
    .stTabs [data-baseweb="tab-list"] { gap: 1.5rem; border-bottom: 1px solid var(--border); }
    .stTabs [data-baseweb="tab"] { font-size: 0.85rem; font-weight: 500; color: var(--muted-foreground); padding-bottom: 0.6rem; }
    .stTabs [aria-selected="true"] { color: var(--foreground) !important; }
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

# Four pipeline stages, named exactly as the PRD demo expects:
# Extract -> Tailor -> Act -> Log. The guardrail is the gate that drives the
# "Act" step; eval logging is the final "Log" step.
STEP_LABELS = {
    "extract": "Extract",
    "tailor": "Tailor",
    "act": "Act",
    "log": "Log",
}


# ---------------------------------------------------------------------------
# Shared render helpers
# ---------------------------------------------------------------------------
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
        cls, state = "status-dot-static", "available"
    elif live:
        cls, state = "status-dot-live", "live"
    else:
        cls, state = "status-dot-mock", "mock"
    return f'<span class="status-item"><span class="status-dot {cls}"></span>{label} &mdash; {state}</span>'


def metric_card(label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="metric-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div>{sub_html}</div>'
    )


def outcome_for(entry: dict) -> str:
    """
    Classifies a logged run into Flagged / Auto-sent / Drafted. The eval log only
    stores {status, detail} for each action (not the full "sent" flag), so this
    keys off the "auto-sent" phrase gmail_action.py always includes in its detail
    message on both the live and mock auto-send paths.
    """
    guardrail = entry.get("guardrail", {})
    if guardrail.get("needs_review"):
        return "Flagged"
    gmail_detail = entry.get("actions", {}).get("gmail", {}).get("detail", "")
    return "Auto-sent" if "auto-sent" in gmail_detail else "Drafted"


@st.cache_data(ttl=2)
def load_application_history() -> pd.DataFrame:
    if not os.path.exists(EVAL_LOG_PATH):
        return pd.DataFrame()
    try:
        entries = json.loads(open(EVAL_LOG_PATH).read())
    except json.JSONDecodeError:
        return pd.DataFrame()
    if not entries:
        return pd.DataFrame()

    rows = []
    for e in entries:
        guardrail = e.get("guardrail", {})
        rows.append(
            {
                "Started": e.get("started_at", ""),
                "Company": e.get("company", ""),
                "Role": e.get("role", ""),
                "Seniority": e.get("requirements", {}).get("seniority", "?"),
                "Overlap": guardrail.get("score", 0.0),
                "Outcome": outcome_for(e),
                "Live LLM": e.get("used_live_llm", False),
                "Passed": e.get("passed", False),
                "Source": e.get("jd_source", ""),
            }
        )
    df = pd.DataFrame(rows)
    return df.sort_values("Started", ascending=False).reset_index(drop=True)


OUTCOME_COLORS = {"Auto-sent": "#7A8450", "Drafted": "#B08A6A", "Flagged": "#D9A441"}


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
live_llm = llm_is_live()
live_google = google_is_live()
live_slack = slack_is_live()

st.markdown('<div class="app-header">', unsafe_allow_html=True)
header_left, header_right = st.columns([2, 1])
with header_left:
    st.markdown('<div class="app-title">AI Job Application Agent</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="app-subtitle">Searches live listings, extracts requirements, tailors the resume and '
        "cover note against your real experience, and acts across six integrations — gated by a confidence "
        "guardrail and a stricter auto-send threshold on top of it.</div>",
        unsafe_allow_html=True,
    )
with header_right:
    status_html = '<div class="status-row" style="justify-content:flex-end;">'
    status_html += status_dot("OpenRouter", live_llm)
    status_html += status_dot("Google", live_google)
    status_html += status_dot("Slack", live_slack)
    status_html += status_dot("Job boards", None)
    status_html += "</div>"
    st.markdown(status_html, unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

tab_dashboard, tab_run, tab_batch = st.tabs(
    [":material/dashboard: Dashboard", ":material/rocket_launch: Run agent", ":material/fact_check: Test suite"]
)

# ---------------------------------------------------------------------------
# Tab 1: Dashboard — application tracking
# ---------------------------------------------------------------------------
with tab_dashboard:
    history = load_application_history()

    if history.empty:
        st.markdown(
            '<div class="empty-state">No applications tracked yet. Run the agent or the test suite '
            "to populate this dashboard.</div>",
            unsafe_allow_html=True,
        )
    else:
        total = len(history)
        auto_sent = int((history["Outcome"] == "Auto-sent").sum())
        drafted = int((history["Outcome"] == "Drafted").sum())
        flagged = int((history["Outcome"] == "Flagged").sum())
        avg_overlap = history["Overlap"].mean() * 100 if total else 0.0

        metrics_html = '<div class="metric-grid">'
        metrics_html += metric_card("Total applications", str(total))
        metrics_html += metric_card("Auto-sent", str(auto_sent), f"{auto_sent/total*100:.0f}% of total")
        metrics_html += metric_card("Awaiting review", str(drafted), f"{drafted/total*100:.0f}% of total")
        metrics_html += metric_card("Flagged for review", str(flagged), f"{flagged/total*100:.0f}% of total")
        metrics_html += "</div>"
        st.markdown(metrics_html, unsafe_allow_html=True)

        table_col, chart_col = st.columns([3, 1])

        with table_col:
            st.markdown('<div class="section-label">Application history</div>', unsafe_allow_html=True)
            filter_row = st.columns([2, 2, 1])
            search_q = filter_row[0].text_input("Search company or role", label_visibility="collapsed", placeholder="Search company or role")
            outcome_filter = filter_row[1].multiselect(
                "Outcome", options=["Auto-sent", "Drafted", "Flagged"], default=[], label_visibility="collapsed", placeholder="Filter by outcome"
            )

            filtered = history.copy()
            if search_q:
                mask = filtered["Company"].str.contains(search_q, case=False, na=False) | filtered["Role"].str.contains(search_q, case=False, na=False)
                filtered = filtered[mask]
            if outcome_filter:
                filtered = filtered[filtered["Outcome"].isin(outcome_filter)]

            display_df = filtered.copy()
            display_df["Overlap"] = (display_df["Overlap"] * 100).round(0).astype(int).astype(str) + "%"
            st.dataframe(
                display_df[["Started", "Company", "Role", "Seniority", "Overlap", "Outcome"]],
                width="stretch", hide_index=True, height=340,
            )
            filter_row[2].download_button(
                "Export CSV", data=history.to_csv(index=False), file_name="application_history.csv",
                mime="text/csv", width="stretch",
            )

        with chart_col:
            st.markdown('<div class="section-label">Outcome mix</div>', unsafe_allow_html=True)
            counts = history["Outcome"].value_counts().reindex(["Auto-sent", "Drafted", "Flagged"]).fillna(0).reset_index()
            counts.columns = ["Outcome", "Count"]
            chart = (
                alt.Chart(counts)
                .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(
                    x=alt.X("Outcome:N", axis=alt.Axis(labelAngle=0, title=None)),
                    y=alt.Y("Count:Q", title=None),
                    color=alt.Color("Outcome:N", scale=alt.Scale(domain=list(OUTCOME_COLORS.keys()), range=list(OUTCOME_COLORS.values())), legend=None),
                )
                .properties(height=280)
                .configure_view(strokeWidth=0)
                .configure_axis(grid=False, domainColor="#E8DCC8", labelColor="#6E5D4F", labelFontSize=11)
            )
            st.altair_chart(chart, width="stretch")
            st.markdown(
                f'<div class="metric-sub" style="margin-top:-0.5rem;">Average overlap across all runs: {avg_overlap:.0f}%</div>',
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------------------
# Tab 2: Run agent
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
        if search_col.button("Search", icon=":material/search:", width="stretch"):
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
        st.markdown('<div class="card">', unsafe_allow_html=True)
        company = st.text_input("Company", key="company_input")
        role = st.text_input("Role", key="role_input")
        spreadsheet_id = st.text_input(
            "Google Sheet ID (optional)", value="", help="Leave blank to use local mock tracking."
        )
        run_clicked = st.button("Run agent", icon=":material/bolt:", width="stretch")
        st.markdown("</div>", unsafe_allow_html=True)

        review_t = float(os.getenv("GUARDRAIL_THRESHOLD", 0.40)) * 100
        send_t = float(os.getenv("AUTO_SEND_THRESHOLD", 0.70)) * 100
        st.caption(f"Review threshold: {review_t:.0f}%  ·  Auto-send threshold: {send_t:.0f}%")

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
                mapped = "act" if step == "guardrail" else step
                progress[mapped] = status
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
            progress["log"] = "done"
            render_stepper(progress_placeholder, progress)
            st.session_state.last_result = result
            st.session_state.last_resume_text = resume_text
            load_application_history.clear()

    if "last_result" in st.session_state:
        result = st.session_state.last_result
        guardrail = result["guardrail"]
        gmail_sent = result["actions"].get("gmail", {}).get("sent", False)

        st.markdown('<div class="section-label" style="margin-top:1.6rem;">Result</div>', unsafe_allow_html=True)

        badge_col, score_col = st.columns([1, 3])
        with badge_col:
            if guardrail["needs_review"]:
                st.markdown('<span class="badge badge-warning">Flagged for review</span>', unsafe_allow_html=True)
            elif gmail_sent:
                st.markdown('<span class="badge badge-success">Auto-sent</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="badge badge-neutral">Drafted &mdash; awaiting review</span>', unsafe_allow_html=True)
        with score_col:
            st.caption(
                f"Keyword overlap: {guardrail['score']*100:.0f}% "
                f"({len(guardrail['matched'])} matched / {len(guardrail['missing'])} missing)"
            )

        overview_tab, resume_tab, cover_tab, actions_tab, req_tab = st.tabs(
            [
                ":material/analytics: Overview",
                ":material/description: Tailored resume",
                ":material/mail: Cover note",
                ":material/checklist: Actions",
                ":material/tune: Requirements",
            ]
        )

        with overview_tab:
            if guardrail["needs_review"]:
                st.markdown(
                    '<div class="callout">Gmail, Sheets, Calendar, and Drive were skipped because this '
                    "application was flagged for review. Slack was still notified.</div>",
                    unsafe_allow_html=True,
                )
            else:
                summary = "sent automatically" if gmail_sent else "drafted and waiting for your review"
                st.markdown(
                    f'<div class="card">Application to <strong>{result["role"]}</strong> at '
                    f'<strong>{result["company"]}</strong> was {summary}. '
                    f"A follow-up reminder was scheduled, the tracking sheet was updated, and the "
                    f"tailored resume was saved.</div>",
                    unsafe_allow_html=True,
                )
            st.caption(f"Company: {result['company']}  ·  Role: {result['role']}  ·  Source: {result['jd_source']}")

        with resume_tab:
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

        with cover_tab:
            st.markdown(f'<div class="card">{result["cover_note"]}</div>', unsafe_allow_html=True)

        with actions_tab:
            action_labels = {
                "gmail": "Gmail draft",
                "sheets": "Sheet row",
                "calendar": "Calendar reminder",
                "drive": "Drive file",
                "slack": "Slack notification",
            }
            rows_html = '<div class="card card-flush" style="padding: 0.2rem 1.2rem;">'
            for key, label in action_labels.items():
                a = result["actions"].get(key)
                if a is None:
                    continue
                if key == "gmail" and a.get("sent"):
                    label = "Gmail — sent"
                icon_cls = "action-icon-success" if a.get("status") in ("ok", "mocked") else "action-icon-error"
                icon_char = "&#10003;" if a.get("status") in ("ok", "mocked") else "&#10005;"
                mock_tag = ' <span class="action-mock-tag">(mock)</span>' if a.get("status") == "mocked" else ""
                rows_html += (
                    f'<div class="action-row"><span class="action-icon {icon_cls}">{icon_char}</span>'
                    f'<span><strong>{label}</strong>{mock_tag} &mdash; {a.get("detail", "")}</span></div>'
                )
            rows_html += "</div>"
            st.markdown(rows_html, unsafe_allow_html=True)

        with req_tab:
            req = result["requirements"]
            c1, c2 = st.columns(2)
            with c1:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.write(f"**Seniority:** {req.get('seniority', '?')}")
                st.write(f"**Skills:** {', '.join(req.get('skills', [])) or '—'}")
                st.markdown("</div>", unsafe_allow_html=True)
            with c2:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.write(f"**Must-haves:** {'; '.join(req.get('must_haves', [])) or '—'}")
                st.write(f"**Keywords:** {', '.join(req.get('keywords', [])) or '—'}")
                st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Tab 3: Test suite
# ---------------------------------------------------------------------------
with tab_batch:
    st.caption(
        "Runs the pipeline against every sample JD in eval/sample_jds/ using "
        "eval/sample_resume.txt, for the reliability brief."
    )
    if st.button("Run test batch", icon=":material/fact_check:"):
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

        load_application_history.clear()
        df = pd.DataFrame(rows)
        st.dataframe(df, width="stretch", hide_index=True)
        passed = sum(1 for r in rows if r["Result"] == "PASS")
        st.caption(f"{passed}/{len(rows)} test JDs passed. Full run details logged to eval/logs/eval_log.json")