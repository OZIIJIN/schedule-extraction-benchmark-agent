from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = BASE_DIR / "state" / "benchmark_state.json"


def load_state() -> dict[str, Any]:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def load_analysis(version: str) -> dict[str, Any]:
    path = BASE_DIR / "agent" / "state" / f"latest_analysis_{version}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def decide_action(state: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    goal = state["goal"]
    avg_score = analysis["summary"]["avg_score"]
    avg_latency = analysis["summary"]["avg_latency_sec"]
    failure_counts = analysis["failure_counts"]
    field_accuracy = analysis["summary"]["field_accuracy"]

    goal_met = bool(
        avg_score is not None
        and avg_latency is not None
        and avg_score >= goal["target_score"]
        and avg_latency <= goal["max_latency_sec"]
    )
    if goal_met:
        return {
            "action": "stop",
            "reason": "score and latency targets are both satisfied",
            "goal_status": "met",
            "recommended_targets": [],
        }

    if any(key in failure_counts for key in ["DATE_RESOLUTION_FAILED", "DAY_OF_WEEK_MISMATCH", "TIME_NORMALIZATION_FAILED", "TYPE_CLASSIFICATION_FAILED"]):
        return {
            "action": "resolver_update",
            "reason": "date/time/type failures remain",
            "goal_status": "not_met",
            "recommended_targets": ["scripts/schedule_resolver_v2.py", "scripts/schedule_resolver_v3.py"],
        }

    title_failures = failure_counts.get("TITLE_EXTRACTION_FAILED", 0)
    if title_failures > 0:
        if avg_latency is not None and avg_latency > goal["max_latency_sec"]:
            return {
                "action": "prompt_simplify",
                "reason": "title failures remain and latency is above target",
                "goal_status": "not_met",
                "recommended_targets": ["scripts/run_benchmark_v2.py", "scripts/run_benchmark_v3.py"],
            }
        return {
            "action": "prompt_or_resolver_update",
            "reason": f"title failures remain ({title_failures} cases)",
            "goal_status": "not_met",
            "recommended_targets": ["scripts/run_benchmark_v2.py", "scripts/run_benchmark_v3.py", "scripts/schedule_resolver_v3.py"],
        }

    if avg_latency is not None and avg_latency > goal["max_latency_sec"]:
        return {
            "action": "latency_optimization",
            "reason": "accuracy target is met but latency is above target",
            "goal_status": "not_met",
            "recommended_targets": ["scripts/run_benchmark_v2.py", "scripts/run_benchmark_v3.py"],
        }

    if field_accuracy.get("title", 0) == 1.0 and avg_score == 1.0:
        return {
            "action": "stop",
            "reason": "all tracked fields match expected outputs",
            "goal_status": "met_partial",
            "recommended_targets": [],
        }

    return {
        "action": "manual_review",
        "reason": "no rule matched cleanly",
        "goal_status": "unknown",
        "recommended_targets": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v3", choices=["v2", "v3"])
    args = parser.parse_args()

    state = load_state()
    analysis = load_analysis(args.version)
    plan = decide_action(state, analysis)

    output_path = BASE_DIR / "agent" / "state" / f"next_action_{args.version}.json"
    output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"loaded: {STATE_PATH}")
    print(f"saved: {output_path}")


if __name__ == "__main__":
    main()
