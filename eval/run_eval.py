"""
Batch test runner: runs the pipeline against every .txt JD in
eval/sample_jds/ using eval/sample_resume.txt, prints a pass/fail summary
table, and appends every run to eval/logs/eval_log.json — this is the raw
material for the reliability brief (Section 9 of the PRD).

Usage:
    python -m eval.run_eval
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from agent.pipeline import run_pipeline  # noqa: E402

SAMPLE_JD_DIR = os.path.join(os.path.dirname(__file__), "sample_jds")
RESUME_PATH = os.path.join(os.path.dirname(__file__), "sample_resume.txt")


def _guess_company_role(filename: str) -> tuple[str, str]:
    stem = os.path.splitext(os.path.basename(filename))[0]
    role = stem.replace("_", " ").title()
    return "Sample Co", role


def main() -> None:
    resume_text = open(RESUME_PATH, encoding="utf-8").read()
    jd_files = sorted(glob.glob(os.path.join(SAMPLE_JD_DIR, "*.txt")))

    if not jd_files:
        print("No sample JDs found in eval/sample_jds/.")
        return

    rows = []
    for jd_path in jd_files:
        jd_text = open(jd_path, encoding="utf-8").read()
        company, role = _guess_company_role(jd_path)
        result = run_pipeline(
            resume_text=resume_text,
            jd_text=jd_text,
            company=company,
            role=role,
            jd_source=os.path.basename(jd_path),
        )
        rows.append(
            {
                "jd_file": os.path.basename(jd_path),
                "seniority": result["requirements"].get("seniority", "?"),
                "overlap_score": result["guardrail"]["score"],
                "needs_review": result["guardrail"]["needs_review"],
                "gmail": (
                    "n/a (flagged)"
                    if result["guardrail"]["needs_review"]
                    else ("auto-sent" if result["actions"].get("gmail", {}).get("sent") else "drafted")
                ),
                "status": "PASS" if result["passed"] else "FAIL",
                "live_llm": result["used_live_llm"],
            }
        )

    header = f"{'JD FILE':28} {'SENIORITY':12} {'OVERLAP':8} {'REVIEW?':8} {'GMAIL':14} {'RESULT':6} {'LIVE LLM':8}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r['jd_file']:28} {r['seniority']:12} {r['overlap_score']:<8} "
            f"{str(r['needs_review']):8} {r['gmail']:14} {r['status']:6} {str(r['live_llm']):8}"
        )

    passed = sum(1 for r in rows if r["status"] == "PASS")
    print(f"\n{passed}/{len(rows)} test JDs passed.")
    print("Full run details logged to eval/logs/eval_log.json")


if __name__ == "__main__":
    main()
