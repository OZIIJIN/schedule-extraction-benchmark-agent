from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from versioned_outputs_v2 import write_text_with_version

BASE_DIR = Path(__file__).resolve().parent.parent
CASES_PATH = BASE_DIR / "cases" / "schedule_cases.json"
NORMALIZED_PATH = BASE_DIR / "outputs" / "v2" / "derived" / "resolved_outputs.json"
DERIVED_DIR = BASE_DIR / "outputs" / "v2" / "derived"
DETAILS_PATH = DERIVED_DIR / "evaluation_details.json"
SUMMARY_PATH = DERIVED_DIR / "evaluation_summary.json"

FIELDS = ["title", "year", "month", "day", "dayOfWeek", "hour", "minute", "ampm", "type"]


def load_expected_map() -> dict[str, dict[str, Any]]:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    return {case["id"]: case["expected"] for case in cases}


def classify_failures(expected: dict[str, Any], actual: dict[str, Any] | None, json_valid: bool) -> list[str]:
    failures: list[str] = []

    if not json_valid or actual is None:
        return ["INVALID_JSON"]

    if set(actual.keys()) != set(FIELDS):
        failures.append("MISSING_REQUIRED_FIELD")

    if expected["title"] != actual["title"]:
        failures.append("TITLE_EXTRACTION_FAILED")

    if (
        expected["year"] != actual["year"]
        or expected["month"] != actual["month"]
        or expected["day"] != actual["day"]
    ):
        failures.append("DATE_RESOLUTION_FAILED")

    if expected["dayOfWeek"] != actual["dayOfWeek"]:
        failures.append("DAY_OF_WEEK_MISMATCH")

    if expected["type"] != actual["type"]:
        failures.append("TYPE_CLASSIFICATION_FAILED")

    expected_time = (expected["hour"], expected["minute"], expected["ampm"])
    actual_time = (actual["hour"], actual["minute"], actual["ampm"])
    if expected_time != actual_time:
        failures.append("TIME_NORMALIZATION_FAILED")

    for value in actual.values():
        if value == "":
            failures.append("NULL_HANDLING_FAILED")
            break

    return failures


def main() -> None:
    expected_map = load_expected_map()
    normalized_items = json.loads(NORMALIZED_PATH.read_text(encoding="utf-8"))

    details: list[dict[str, Any]] = []
    per_model_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for item in normalized_items:
        case_id = item["case_id"]
        model = item["model"]
        expected = expected_map[case_id]
        actual = item.get("normalized_output")
        json_valid = item.get("json_valid", False)

        field_matches: dict[str, bool] = {}
        for field in FIELDS:
            field_matches[field] = bool(json_valid and actual is not None and expected.get(field) == actual.get(field))

        score = round(sum(1 for matched in field_matches.values() if matched) / len(FIELDS), 4)
        failures = classify_failures(expected, actual, json_valid)

        row = {
            "case_id": case_id,
            "model": model,
            "input": item["input"],
            "latency_sec": item.get("latency_sec"),
            "json_valid": json_valid,
            "score": score,
            "field_matches": field_matches,
            "failures": failures,
            "expected": expected,
            "intermediate": item.get("intermediate"),
            "actual": actual,
            "parse_error": item.get("parse_error"),
        }
        details.append(row)
        per_model_rows[model].append(row)

    summary: dict[str, Any] = {"models": {}}

    for model, rows in per_model_rows.items():
        avg_latency_values = [r["latency_sec"] for r in rows if isinstance(r["latency_sec"], (int, float))]
        avg_latency = round(sum(avg_latency_values) / len(avg_latency_values), 3) if avg_latency_values else None
        avg_score = round(sum(r["score"] for r in rows) / len(rows), 4) if rows else None
        json_valid_rate = round(sum(1 for r in rows if r["json_valid"]) / len(rows), 4) if rows else None

        field_accuracy = {}
        for field in FIELDS:
            field_accuracy[field] = round(sum(1 for r in rows if r["field_matches"][field]) / len(rows), 4)

        failure_counts: dict[str, int] = defaultdict(int)
        for row in rows:
            for failure in row["failures"]:
                failure_counts[failure] += 1

        summary["models"][model] = {
            "case_count": len(rows),
            "avg_score": avg_score,
            "avg_latency_sec": avg_latency,
            "json_valid_rate": json_valid_rate,
            "field_accuracy": field_accuracy,
            "failure_counts": dict(sorted(failure_counts.items(), key=lambda x: x[0])),
        }

    details_versioned_path = write_text_with_version(
        DETAILS_PATH,
        json.dumps(details, ensure_ascii=False, indent=2),
    )
    summary_versioned_path = write_text_with_version(
        SUMMARY_PATH,
        json.dumps(summary, ensure_ascii=False, indent=2),
    )

    print(f"saved: {DETAILS_PATH}")
    print(f"saved: {details_versioned_path}")
    print(f"saved: {SUMMARY_PATH}")
    print(f"saved: {summary_versioned_path}")


if __name__ == "__main__":
    main()
