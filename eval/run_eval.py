"""
Batch eval: runs the pipeline on every JD in eval/sample_jds/ against
eval/sample_resume.txt and scores four criteria per JD:

  extraction    seniority matches expected.json and >=50% of expected skills found
  faithfulness  no application with unsupported claims reached the apps
  decision      flagged-vs-proceeded matches expected.json's expect_review
  actions       normal run: every app action ok/mocked
                with --faults: every action reported a status + reason (handled, no crash)

Writes eval/logs/eval_summary.json (keys "normal" / "faults") for the UI and
the reliability brief.

Usage:
    python -m eval.run_eval
    python -m eval.run_eval --faults gmail,llm_429
"""
import argparse
import glob
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from agent.pipeline import run_pipeline  # noqa: E402
from agent.utils import ALLOWED_FAULTS, FAULTS  # noqa: E402

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_JD_DIR = os.path.join(EVAL_DIR, "sample_jds")
RESUME_PATH = os.path.join(EVAL_DIR, "sample_resume.txt")
EXPECTED_PATH = os.path.join(EVAL_DIR, "expected.json")
SUMMARY_PATH = os.path.join(EVAL_DIR, "logs", "eval_summary.json")
CRITERIA = ("extraction", "faithfulness", "decision", "actions")


def _score(result: dict, expected: dict, faults) -> dict:
    req = result["requirements"]
    found = [s.lower() for s in req.get("skills", []) + req.get("keywords", [])]
    wanted = [s.lower() for s in expected.get("must_include_skills", [])]
    recall = sum(1 for w in wanted if any(w in f for f in found)) / len(wanted) if wanted else 1.0
    seniority_ok = expected.get("seniority", req.get("seniority")) == req.get("seniority")

    dispatched = result["outcome"] in ("sent", "drafted")
    if faults:
        actions_ok = all(a.get("status") in ("ok", "mocked", "error") and a.get("detail") for a in result["actions"].values())
    else:
        actions_ok = all(a["status"] in ("ok", "mocked") for k, a in result["actions"].items() if k != "slack")

    return {
        "extraction": recall >= 0.5 and seniority_ok,
        "faithfulness": not (dispatched and not result["executor_verdict"]["faithful"]),
        "decision": "expect_review" not in expected or expected["expect_review"] == (result["outcome"] == "flagged"),
        "actions": actions_ok,
    }


def load_summary() -> dict:
    if not os.path.exists(SUMMARY_PATH):
        return {}
    try:
        return json.loads(open(SUMMARY_PATH, encoding="utf-8").read())
    except json.JSONDecodeError:
        return {}


def run_batch(faults=(), pace: float = 0.0) -> dict:
    """pace: seconds to wait between jobs, so a live run stays under free-tier LLM rate limits."""
    resume_text = open(RESUME_PATH, encoding="utf-8").read()
    expected_all = json.loads(open(EXPECTED_PATH, encoding="utf-8").read()) if os.path.exists(EXPECTED_PATH) else {}

    previous = set(FAULTS)
    FAULTS.clear()
    FAULTS.update(faults)
    rows = []
    try:
        for jd_path in sorted(glob.glob(os.path.join(SAMPLE_JD_DIR, "*.txt"))):
            if rows and pace:
                time.sleep(pace)
            name = os.path.basename(jd_path)
            expected = expected_all.get(name, {})
            try:
                result = run_pipeline(
                    resume_text=resume_text,
                    jd_text=open(jd_path, encoding="utf-8").read(),
                    company=expected.get("company", "Sample Co"),
                    role=expected.get("role", os.path.splitext(name)[0].replace("_", " ").title()),
                    jd_source=name,
                    dedup=False,
                    simulate=True,  # measure the agent, never post to real accounts
                )
                checks = _score(result, expected, faults)
                rows.append({
                    "jd_file": name,
                    "seniority": result["requirements"].get("seniority", "?"),
                    "overlap": result["guardrail"]["score"],
                    "outcome": result["outcome"],
                    "unsupported": len(result["executor_verdict"]["unsupported_claims"]),
                    "live_llm": result["used_live_llm"],
                    "fell_back": [agent for agent, live in result["llm_live"].items() if not live],
                    **checks,
                    "passed": all(checks.values()),
                })
                fell_back = rows[-1]["fell_back"]
                print(f"[{len(rows)}] {name}: {result['outcome']}, {'PASS' if rows[-1]['passed'] else 'FAIL'}"
                      + (f", fallback: {', '.join(fell_back)}" if fell_back else ", all agents live"), flush=True)
            except Exception as exc:  # noqa: BLE001 - a crash is exactly what the eval must catch
                rows.append({"jd_file": name, "error": str(exc), **{c: False for c in CRITERIA}, "passed": False})
    finally:
        FAULTS.clear()
        FAULTS.update(previous)

    summary = {
        "ran_at": datetime.now().isoformat(timespec="seconds"),
        "faults": list(faults),
        "total": len(rows),
        "passed": sum(1 for r in rows if r["passed"]),
        "criteria": {c: sum(1 for r in rows if r[c]) for c in CRITERIA},
        "rows": rows,
    }
    all_summaries = load_summary()
    all_summaries["faults" if faults else "normal"] = summary
    os.makedirs(os.path.dirname(SUMMARY_PATH), exist_ok=True)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(all_summaries, f, indent=2)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--faults", default="", help=f"comma-separated, from: {', '.join(ALLOWED_FAULTS)}")
    parser.add_argument("--pace", type=float, default=0.0, help="seconds between jobs (use ~20 for a live free-tier run)")
    args = parser.parse_args()
    faults = tuple(f for f in args.faults.split(",") if f)
    unknown = set(faults) - set(ALLOWED_FAULTS)
    if unknown:
        parser.error(f"unknown faults: {', '.join(sorted(unknown))}")

    summary = run_batch(faults, pace=args.pace)
    header = f"{'JD FILE':30} {'SENIORITY':12} {'OVERLAP':8} {'OUTCOME':10} {'EXTRACT':8} {'FAITHFUL':9} {'DECISION':9} {'ACTIONS':8} RESULT"
    print(header)
    print("-" * len(header))
    for r in summary["rows"]:
        if "error" in r:
            print(f"{r['jd_file']:30} CRASH: {r['error']}")
            continue
        flag = lambda ok: "pass" if ok else "FAIL"  # noqa: E731
        print(
            f"{r['jd_file']:30} {r['seniority']:12} {r['overlap']*100:>6.0f}%  {r['outcome']:10} "
            f"{flag(r['extraction']):8} {flag(r['faithfulness']):9} {flag(r['decision']):9} "
            f"{flag(r['actions']):8} {'PASS' if r['passed'] else 'FAIL'}"
            + (f"  (fallback: {', '.join(r['fell_back'])})" if r.get("fell_back") else ""),
            flush=True,
        )
    mode = f" under faults [{', '.join(faults)}]" if faults else ""
    print(f"\n{summary['passed']}/{summary['total']} test JDs passed{mode}.")
    print("Per criterion: " + ", ".join(f"{c} {n}/{summary['total']}" for c, n in summary["criteria"].items()))
    print(f"Summary written to {os.path.relpath(SUMMARY_PATH)}")


if __name__ == "__main__":
    main()
