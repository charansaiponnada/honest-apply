"""
FastAPI server for the AI Job Application Agent.

  /        3D landing page (web/index.html)
  /app     the agent app (web/app.html)
  /api/*   JSON endpoints, plus live event streams for agent runs and batches

Run from the repo root: uvicorn main:app --reload
"""
import asyncio
import json
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from agent.composio_client import APP_TOOLKITS, connect_link, connected_apps, is_enabled as composio_enabled  # noqa: E402
from agent.crm_action import is_live as crm_is_live  # noqa: E402
from agent.github_profile import fetch_profile, profile_skills, valid_username  # noqa: E402
from agent.google_auth import is_live as google_is_live  # noqa: E402
from agent.guardrail import _auto_send_threshold, _threshold  # noqa: E402
from agent.jobs_search import fetch_pool  # noqa: E402
from agent.llm import _model_name, _quota_exhausted, is_live as llm_is_live  # noqa: E402
from agent.pipeline import load_eval_log, run_pipeline  # noqa: E402
from agent.recommend import recommend  # noqa: E402
from agent.reply_tracker import simulate_reply, sync_replies  # noqa: E402
from agent.resume_parse import parse_resume  # noqa: E402
from agent.slack_action import is_live as slack_is_live  # noqa: E402
from agent.undo import undo_run  # noqa: E402
from agent.utils import ALLOWED_FAULTS, FAULTS  # noqa: E402
from eval.run_eval import load_summary, run_batch  # noqa: E402

ROOT = Path(__file__).parent
WEB_DIR = ROOT / "web"
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_HISTORY_FIELDS = ("run_id", "started_at", "company", "role", "jd_source", "outcome", "executor_mode",
                   "faults", "used_live_llm", "undone", "replied", "reply_link")
_USER_ID = dict(default="", max_length=200, pattern=r"^[\w.@+-]*$")
_SLACK_CHANNEL = dict(default="", max_length=80, pattern=r"^#?[\w.-]*$")
_GITHUB = dict(default="", max_length=39, pattern=r"^[A-Za-z0-9-]*$")
_background: set[asyncio.Task] = set()

app = FastAPI(title="AI Job Application Agent")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


def _event_stream(job) -> StreamingResponse:
    """Run job(emit) in a worker thread and stream every emitted event to the browser as SSE."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def emit(event: dict) -> None:  # called from the worker thread
        loop.call_soon_threadsafe(queue.put_nowait, event)

    async def worker() -> None:
        try:
            await asyncio.to_thread(job, emit)
        except Exception as exc:  # noqa: BLE001 - surface to the client instead of a dead stream
            await queue.put({"type": "error", "detail": str(exc)})
        finally:
            await queue.put(None)

    task = asyncio.create_task(worker())
    _background.add(task)
    task.add_done_callback(_background.discard)

    async def stream():
        while (event := await queue.get()) is not None:
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/", include_in_schema=False)
def landing():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/app", include_in_schema=False)
def agent_app():
    return FileResponse(WEB_DIR / "app.html")


@app.get("/api/status")
def status():
    return {
        "llm": llm_is_live() and not _quota_exhausted(),
        "model": _model_name() + (" (daily quota used up: rule-based fallback)" if _quota_exhausted() else ""),
        "google": google_is_live(),
        "crm": crm_is_live(),
        "slack": slack_is_live(),
        "review_threshold": _threshold(),
        "send_threshold": _auto_send_threshold(),
        "faults": sorted(FAULTS),
        "available_faults": list(ALLOWED_FAULTS),
    }


@app.get("/api/defaults")
def defaults():
    resume = ROOT / "resume.txt"
    if not resume.exists():
        resume = ROOT / "eval" / "sample_resume.txt"
    return {"resume": resume.read_text(encoding="utf-8").strip()}


@app.get("/api/jobs")
def jobs(limit: int = 60):
    pool, error = fetch_pool(limit=max(1, min(limit, 120)))
    return {"jobs": pool, "error": error}


class ResumeUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    data_base64: str = Field(min_length=1, max_length=7_000_000)  # ~5 MB file after base64


@app.post("/api/resume/parse")
def resume_parse(req: ResumeUpload):
    try:
        return {"text": parse_resume(req.filename, req.data_base64)}
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get("/api/github/{username}")
def github(username: str):
    if not valid_username(username):
        raise HTTPException(422, "Not a valid GitHub username.")
    profile = fetch_profile(username)
    return {"username": username, "repo_count": len(profile["repos"]), "skills": profile_skills(profile)[:12],
            "error": profile["error"]}


class RecommendRequest(BaseModel):
    resume_text: str = Field(min_length=20, max_length=50_000)
    github_username: str = Field(**_GITHUB)
    limit: int = Field(default=10, ge=1, le=25)


@app.post("/api/recommendations")
def recommendations(req: RecommendRequest):
    pool, error = fetch_pool(limit=120)
    profile = fetch_profile(req.github_username) if req.github_username else None
    return {
        "jobs": recommend(req.resume_text, pool, profile, req.limit),
        "pool_size": len(pool),
        "error": error,
        "github_error": profile["error"] if profile else None,
    }


class RunRequest(BaseModel):
    resume_text: str = Field(min_length=20, max_length=50_000)
    jd_text: str = Field(min_length=20, max_length=50_000)
    company: str = Field(default="", max_length=200)
    role: str = Field(default="", max_length=200)
    jd_source: str = Field(default="pasted text", max_length=2000)
    recipient: str = Field(default="", max_length=320)
    allow_send: bool = False
    user_id: str = Field(**_USER_ID)
    slack_channel: str = Field(**_SLACK_CHANNEL)
    github_username: str = Field(**_GITHUB)


@app.post("/api/run")
async def run(req: RunRequest):
    recipient = req.recipient.strip()
    if recipient and not _EMAIL_RE.fullmatch(recipient):
        raise HTTPException(422, "Recipient must be a valid email address.")

    def job(emit):
        result = run_pipeline(
            resume_text=req.resume_text,
            jd_text=req.jd_text,
            company=req.company.strip() or "Unknown Co",
            role=req.role.strip() or "Unknown Role",
            jd_source=req.jd_source,
            recipient=recipient,
            allow_send=req.allow_send,
            user_id=req.user_id,
            slack_channel=req.slack_channel,
            github_username=req.github_username,
            progress_cb=emit,
        )
        emit({"type": "result", "result": result})

    return _event_stream(job)


class BatchJob(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    company_name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=20, max_length=50_000)
    url: str = Field(default="", max_length=2000)


class BatchRequest(BaseModel):
    resume_text: str = Field(min_length=20, max_length=50_000)
    jobs: list[BatchJob] = Field(min_length=1, max_length=5)
    user_id: str = Field(**_USER_ID)
    slack_channel: str = Field(**_SLACK_CHANNEL)
    github_username: str = Field(**_GITHUB)


@app.post("/api/apply-batch")
async def apply_batch(req: BatchRequest):
    """Run the full agent on each selected job in turn. Drafts only (job boards give no recipient),
    and every gate and the duplicate check still apply per job."""

    def job(emit):
        summary = []
        for index, posting in enumerate(req.jobs, 1):
            emit({"type": "batch", "index": index, "total": len(req.jobs),
                  "company": posting.company_name, "role": posting.title})
            try:
                result = run_pipeline(
                    resume_text=req.resume_text,
                    jd_text=posting.description,
                    company=posting.company_name,
                    role=posting.title,
                    jd_source=posting.url or "recommended job",
                    user_id=req.user_id,
                    slack_channel=req.slack_channel,
                    github_username=req.github_username,
                    progress_cb=emit,
                )
            except Exception as exc:  # noqa: BLE001 - one job failing shouldn't stop the batch
                summary.append({"company": posting.company_name, "role": posting.title, "outcome": "error", "detail": str(exc)})
                continue
            emit({"type": "result", "result": result})
            summary.append({"run_id": result["run_id"], "company": posting.company_name, "role": posting.title,
                            "outcome": result["outcome"], "overlap": result["guardrail"]["score"]})
        emit({"type": "batch_done", "summary": summary})

    return _event_stream(job)


@app.get("/api/history")
def history():
    rows = []
    for entry in load_eval_log():
        if not entry.get("run_id"):  # older log format, before run ids
            continue
        row = {k: entry.get(k) for k in _HISTORY_FIELDS}
        row["overlap"] = entry.get("guardrail", {}).get("score", 0.0)
        row["seniority"] = entry.get("requirements", {}).get("seniority")
        rows.append(row)
    return list(reversed(rows))


@app.post("/api/undo/{run_id}")
def undo(run_id: str):
    result = undo_run(run_id)
    if result is None:
        raise HTTPException(404, "Run not found.")
    return result


@app.post("/api/replies/sync")
def replies_sync():
    return sync_replies()


@app.post("/api/replies/simulate/{run_id}")
def replies_simulate(run_id: str):
    if google_is_live():
        raise HTTPException(409, "A Google account is connected, so replies are read from Gmail. Use Sync replies.")
    if not simulate_reply(run_id):
        raise HTTPException(404, "Run not found.")
    return sync_replies()


class FaultsRequest(BaseModel):
    faults: list[str] = []


def _checked_faults(names: list[str]) -> list[str]:
    unknown = set(names) - set(ALLOWED_FAULTS)
    if unknown:
        raise HTTPException(422, f"Unknown faults: {', '.join(sorted(unknown))}")
    return names


@app.get("/api/faults")
def get_faults():
    return {"faults": sorted(FAULTS), "available": list(ALLOWED_FAULTS)}


@app.post("/api/faults")
def set_faults(req: FaultsRequest):
    names = _checked_faults(req.faults)
    FAULTS.clear()
    FAULTS.update(names)
    return get_faults()


@app.post("/api/eval")
async def eval_run(req: FaultsRequest):
    return await asyncio.to_thread(run_batch, tuple(_checked_faults(req.faults)))


@app.get("/api/eval/summary")
def eval_summary():
    return load_summary()


@app.get("/api/connections")
def connections(user_id: str = ""):
    """Per app: connected through the user's Composio account, through server .env keys, or not at all."""
    composio_apps = connected_apps(user_id)
    server_keys = {"gmail": google_is_live(), "calendar": google_is_live(), "crm": crm_is_live(), "slack": slack_is_live()}
    return {
        "composio": composio_enabled(),
        "apps": {
            name: {
                "connected": name in composio_apps or server_keys[name],
                "via": "composio" if name in composio_apps else "env" if server_keys[name] else None,
            }
            for name in APP_TOOLKITS
        },
    }


class LinkRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=200, pattern=r"^[\w.@+-]+$")


@app.post("/api/connections/{app_name}/link")
def connection_link(app_name: str, req: LinkRequest, request: Request):
    if app_name not in APP_TOOLKITS:
        raise HTTPException(404, "Unknown app.")
    if not composio_enabled():
        raise HTTPException(409, "One-click Connect needs COMPOSIO_API_KEY on the server.")
    try:
        url = connect_link(req.user_id, app_name, callback_url=f"{request.base_url}app?connected={app_name}")
    except Exception as exc:  # noqa: BLE001 - surface Composio's reason to the user
        raise HTTPException(502, f"Composio couldn't create a connect link: {exc}")
    return {"redirect_url": url}
