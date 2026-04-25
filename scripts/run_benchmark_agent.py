from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = BASE_DIR / "state" / "benchmark_state.json"
PYTHON = str(BASE_DIR / ".venv" / "bin" / "python")


def run_step(args: list[str]) -> None:
    subprocess.run(args, cwd=BASE_DIR, check=True)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_versioned_json(directory: Path, stem: str) -> Path:
    candidates = sorted(directory.glob(f"{stem}-[0-9][0-9].json"))
    if not candidates:
        raise FileNotFoundError(f"No versioned files found for {directory / stem}")
    return candidates[-1]


def latest_report(version: str) -> Path:
    reports_dir = BASE_DIR / "outputs" / version / "reports"
    candidates = sorted(reports_dir.glob("*.md"))
    if not candidates:
        raise FileNotFoundError(f"No reports found in {reports_dir}")
    return candidates[-1]


def update_state(version: str) -> None:
    state = load_json(STATE_PATH)
    analysis_path = BASE_DIR / "state" / f"latest_analysis_{version}.json"
    plan_path = BASE_DIR / "state" / f"next_action_{version}.json"
    analysis = load_json(analysis_path)
    plan = load_json(plan_path)
    raw_dir = BASE_DIR / "outputs" / version / "raw"
    derived_dir = BASE_DIR / "outputs" / version / "derived"

    raw_stem = "benchmark_intermediate_raw" if version == "v2" else "benchmark_span_raw"
    latest_raw = latest_versioned_json(raw_dir, raw_stem)
    latest_summary = latest_versioned_json(derived_dir, "evaluation_summary")
    report_path = latest_report(version)

    state["current"] = {
        "latest_run_ref": latest_raw.name,
        "latest_score": analysis["summary"]["avg_score"],
        "latest_latency_sec": analysis["summary"]["avg_latency_sec"],
        "latest_report": str(report_path.relative_to(BASE_DIR)),
    }
    state["next_action"] = plan
    state.setdefault("history", []).append({
        "version": version,
        "run_ref": latest_raw.name,
        "summary_ref": latest_summary.name,
        "report_ref": str(report_path.relative_to(BASE_DIR)),
        "score": analysis["summary"]["avg_score"],
        "latency_sec": analysis["summary"]["avg_latency_sec"],
        "failure_case_count": analysis["failure_case_count"],
        "action": plan["action"],
        "reason": plan["reason"],
    })
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v3", choices=["v2", "v3"])
    parser.add_argument("--run-pipeline", action="store_true", help="run benchmark/resolve/evaluate/report before analysis")
    parser.add_argument("--runner-script", help="override benchmark runner script path")
    args = parser.parse_args()

    if args.run_pipeline:
        run_script = args.runner_script or f"scripts/run_benchmark_{args.version}.py"
        resolve_script = f"scripts/resolve_{args.version}_outputs.py"
        evaluate_script = f"scripts/evaluate_results_{args.version}.py"
        report_script = f"scripts/write_report_{args.version}.py"

        run_step([PYTHON, run_script])
        run_step([PYTHON, resolve_script])
        run_step([PYTHON, evaluate_script])
        run_step([PYTHON, report_script])

    run_step([PYTHON, "scripts/analyze_failures.py", "--version", args.version])
    run_step([PYTHON, "scripts/plan_next_action.py", "--version", args.version])
    update_state(args.version)
    print(f"saved: {STATE_PATH}")


if __name__ == "__main__":
    main()
