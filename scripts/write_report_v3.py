from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from versioned_outputs_v3 import latest_versioned_path

BASE_DIR = Path(__file__).resolve().parent.parent
SUMMARY_PATH = BASE_DIR / "outputs" / "v3" / "derived" / "evaluation_summary.json"
DETAILS_PATH = BASE_DIR / "outputs" / "v3" / "derived" / "evaluation_details.json"
REPORTS_DIR = BASE_DIR / "outputs" / "v3" / "reports"

MODEL_ORDER = [
    "gemma3:4b",
]


def top_failures(failure_counts: dict[str, int], limit: int = 3) -> list[str]:
    ordered = sorted(failure_counts.items(), key=lambda x: (-x[1], x[0]))
    return [f"{name} ({count})" for name, count in ordered[:limit] if count > 0]


def recommendation(summary: dict[str, Any]) -> str:
    models = summary["models"]
    if not models:
        return "No evaluation results available."

    ranked = sorted(
        models.items(),
        key=lambda x: (
            -(x[1]["avg_score"] or 0),
            (x[1]["avg_latency_sec"] or 999999),
        ),
    )
    best_model, best_stats = ranked[0]

    return (
        f"PoC v3 기준으로는 `{best_model}`이(가) 가장 우선 검토 대상이다. "
        f"평균 점수는 {best_stats['avg_score']}, 평균 응답 시간은 {best_stats['avg_latency_sec']}초였다. "
        "LLM은 제거할 span을 추출하고, resolver는 원문에서 span을 제거해 title을 복원한다."
    )


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    summary_path = latest_versioned_path(SUMMARY_PATH)
    details_path = latest_versioned_path(DETAILS_PATH)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    details = json.loads(details_path.read_text(encoding="utf-8"))

    today = datetime.now().strftime("%Y-%m-%d")
    sequence = 1
    while True:
        report_path = REPORTS_DIR / f"{today}-{sequence:02d}.md"
        if not report_path.exists():
            break
        sequence += 1

    lines: list[str] = []
    lines.append("# Schedule Extraction Benchmark Report v3")
    lines.append("")
    lines.append("## Date")
    lines.append(today)
    lines.append("")
    lines.append("## Approach")
    lines.append("LLM extracts `source_text`, `date_text`, `time_text`, and `remove_spans`; deterministic resolver removes spans from source text and builds the final schedule schema.")
    lines.append("")
    lines.append("## Summary")

    models = summary.get("models", {})
    if not models:
        lines.append("No results available.")
    else:
        ranked_models = [m for m in MODEL_ORDER if m in models] + [m for m in models if m not in MODEL_ORDER]
        for model in ranked_models:
            stats = models[model]
            lines.append(
                f"- `{model}`: avg_score={stats['avg_score']}, avg_latency={stats['avg_latency_sec']}s, json_valid_rate={stats['json_valid_rate']}"
            )

    lines.append("")
    lines.append("## Per-Model Results")

    for model in [m for m in MODEL_ORDER if m in models] + [m for m in models if m not in MODEL_ORDER]:
        stats = models[model]
        lines.append(f"### {model}")
        lines.append(f"- Case count: {stats['case_count']}")
        lines.append(f"- Average score: {stats['avg_score']}")
        lines.append(f"- Average latency: {stats['avg_latency_sec']}s")
        lines.append(f"- JSON valid rate: {stats['json_valid_rate']}")
        lines.append("- Field accuracy:")
        for field, acc in stats["field_accuracy"].items():
            lines.append(f"  - {field}: {acc}")
        failures = top_failures(stats["failure_counts"])
        if failures:
            lines.append("- Top failures:")
            for failure in failures:
                lines.append(f"  - {failure}")
        else:
            lines.append("- Top failures: none")
        lines.append("")

    lines.append("## Recommendation")
    lines.append(recommendation(summary))
    lines.append("")

    lines.append("## Notable Failure Cases")
    failure_rows = [row for row in details if row["failures"]]
    failure_rows = sorted(failure_rows, key=lambda r: (r["model"], -len(r["failures"]), r["case_id"]))

    if failure_rows:
        for row in failure_rows[:12]:
            lines.append(f"### {row['model']} / {row['case_id']}")
            lines.append(f"- Input: {row['input']}")
            lines.append(f"- Failures: {', '.join(row['failures'])}")
            lines.append(f"- Intermediate: `{json.dumps(row['intermediate'], ensure_ascii=False)}`")
            lines.append(f"- Expected: `{json.dumps(row['expected'], ensure_ascii=False)}`")
            lines.append(f"- Actual: `{json.dumps(row['actual'], ensure_ascii=False) if row['actual'] is not None else 'null'}`")
            if row.get("parse_error"):
                lines.append(f"- Parse error: `{row['parse_error']}`")
            lines.append("")
    else:
        lines.append("No failures found.")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"loaded: {summary_path}")
    print(f"loaded: {details_path}")
    print(f"saved: {report_path}")


if __name__ == "__main__":
    main()
