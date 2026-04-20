from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_PATH = BASE_DIR / "outputs" / "raw" / "benchmark_raw.json"
DERIVED_DIR = BASE_DIR / "outputs" / "derived"
NORMALIZED_PATH = DERIVED_DIR / "normalized_outputs.json"

EXPECTED_KEYS = [
    "title",
    "year",
    "month",
    "day",
    "dayOfWeek",
    "hour",
    "minute",
    "ampm",
    "type",
]


def to_none_if_blank(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return None
        return stripped
    return value


def to_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return None
        try:
            return int(stripped)
        except ValueError:
            return None
    return None


def normalize_type(value: Any) -> str | None:
    value = to_none_if_blank(value)
    if value is None:
        return None
    if not isinstance(value, str):
        return None

    upper = value.upper()
    if upper in {"SCHEDULE", "TODO"}:
        return upper
    return None


def normalize_ampm(value: Any) -> str | None:
    value = to_none_if_blank(value)
    if value is None:
        return None
    if value in {"오전", "오후"}:
        return value
    return None


def normalize_day_of_week(value: Any) -> str | None:
    value = to_none_if_blank(value)
    if value is None:
        return None

    mapping = {
        "월": "월요일",
        "화": "화요일",
        "수": "수요일",
        "목": "목요일",
        "금": "금요일",
        "토": "토요일",
        "일": "일요일",
        "월요일": "월요일",
        "화요일": "화요일",
        "수요일": "수요일",
        "목요일": "목요일",
        "금요일": "금요일",
        "토요일": "토요일",
        "일요일": "일요일",
    }
    return mapping.get(value)


def try_parse_json(text: Any) -> tuple[dict[str, Any] | None, str | None]:
    if text is None:
        return None, "raw_response is None"

    if not isinstance(text, str):
        return None, f"raw_response is not a string: {type(text)}"

    stripped = text.strip()
    if not stripped:
        return None, "raw_response is empty"

    try:
        return json.loads(stripped), None
    except json.JSONDecodeError as exc:
        return None, f"json_decode_error: {exc}"


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    title = to_none_if_blank(payload.get("title"))
    if isinstance(title, str):
        title = " ".join(title.split())

    normalized = {
        "title": title if isinstance(title, str) else None,
        "year": to_int_or_none(payload.get("year")),
        "month": to_int_or_none(payload.get("month")),
        "day": to_int_or_none(payload.get("day")),
        "dayOfWeek": normalize_day_of_week(payload.get("dayOfWeek")),
        "hour": to_int_or_none(payload.get("hour")),
        "minute": to_int_or_none(payload.get("minute")),
        "ampm": normalize_ampm(payload.get("ampm")),
        "type": normalize_type(payload.get("type")),
    }

    return normalized


def main() -> None:
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)

    raw_items = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    normalized_items: list[dict[str, Any]] = []

    for item in raw_items:
        parsed, parse_error = try_parse_json(item.get("raw_response"))

        if parsed is None:
            normalized_items.append({
                **item,
                "json_valid": False,
                "parse_error": parse_error,
                "normalized_output": None,
            })
            continue

        normalized_items.append({
            **item,
            "json_valid": True,
            "parse_error": None,
            "normalized_output": normalize_payload(parsed),
        })

    NORMALIZED_PATH.write_text(
        json.dumps(normalized_items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"saved: {NORMALIZED_PATH}")


if __name__ == "__main__":
    main()