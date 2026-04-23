from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "agent" / "state"


def latest_versioned_json(directory: Path, stem: str) -> Path:
    candidates = sorted(directory.glob(f"{stem}-[0-9][0-9].json"))
    if not candidates:
        raise FileNotFoundError(f"No versioned files found for {directory / stem}")
    return candidates[-1]


def load_summary_and_details(version: str) -> tuple[Path, dict[str, Any], Path, list[dict[str, Any]]]:
    derived_dir = BASE_DIR / "outputs" / version / "derived"
    summary_path = latest_versioned_json(derived_dir, "evaluation_summary")
    details_path = latest_versioned_json(derived_dir, "evaluation_details")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    details = json.loads(details_path.read_text(encoding="utf-8"))
    return summary_path, summary, details_path, details


def build_analysis(version: str, summary: dict[str, Any], details: list[dict[str, Any]]) -> dict[str, Any]:
    models = summary.get("models", {})
    if not models:
        raise ValueError("No models found in summary")

    model_name, model_stats = next(iter(models.items()))
    failures = [row for row in details if row.get("failures")]
    dialog_failures = [row for row in failures if int(row["case_id"].split("_")[1]) >= 125]
    failure_counts = Counter()
    for row in failures:
        failure_counts.update(row["failures"])

    examples = []
    for row in failures[:10]:
        examples.append({
            "case_id": row["case_id"],
            "input": row["input"],
            "failures": row["failures"],
            "actual": row.get("actual"),
            "expected": row.get("expected"),
            "intermediate": row.get("intermediate"),
        })

    return {
        "version": version,
        "model": model_name,
        "summary": {
            "avg_score": model_stats.get("avg_score"),
            "avg_latency_sec": model_stats.get("avg_latency_sec"),
            "json_valid_rate": model_stats.get("json_valid_rate"),
            "field_accuracy": model_stats.get("field_accuracy", {}),
        },
        "failure_counts": dict(sorted(failure_counts.items())),
        "failure_case_count": len(failures),
        "dialog_failure_count": len(dialog_failures),
        "examples": examples,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v3", choices=["v2", "v3"])
    args = parser.parse_args()

    summary_path, summary, details_path, details = load_summary_and_details(args.version)
    analysis = build_analysis(args.version, summary, details)

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = STATE_DIR / f"latest_analysis_{args.version}.json"
    output_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"loaded: {summary_path}")
    print(f"loaded: {details_path}")
    print(f"saved: {output_path}")


if __name__ == "__main__":
    main()
