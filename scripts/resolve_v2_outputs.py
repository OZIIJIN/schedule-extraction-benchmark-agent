from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from schedule_resolver_v2 import normalize_intermediate, resolve_schedule

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_PATH = BASE_DIR / "outputs" / "v2" / "raw" / "benchmark_intermediate_raw.json"
DERIVED_DIR = BASE_DIR / "outputs" / "v2" / "derived"
NORMALIZED_PATH = DERIVED_DIR / "resolved_outputs.json"


def try_parse_json(text: Any) -> tuple[dict[str, Any] | None, str | None]:
    if text is None:
        return None, "raw_response is None"
    if not isinstance(text, str):
        return None, f"raw_response is not a string: {type(text)}"

    stripped = text.strip()
    if not stripped:
        return None, "raw_response is empty"

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        return None, f"json_decode_error: {exc}"

    if not isinstance(parsed, dict):
        return None, f"raw_response is not a JSON object: {type(parsed)}"

    return parsed, None


def main() -> None:
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)

    raw_items = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    resolved_items: list[dict[str, Any]] = []

    for item in raw_items:
        parsed, parse_error = try_parse_json(item.get("raw_response"))

        if parsed is None:
            resolved_items.append({
                **item,
                "json_valid": False,
                "parse_error": parse_error,
                "intermediate": None,
                "normalized_output": None,
            })
            continue

        intermediate = normalize_intermediate(parsed)
        resolved_items.append({
            **item,
            "json_valid": True,
            "parse_error": None,
            "intermediate": intermediate,
            "normalized_output": resolve_schedule(
                now=item["now"],
                original_input=item["input"],
                intermediate=intermediate,
            ),
        })

    NORMALIZED_PATH.write_text(
        json.dumps(resolved_items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"saved: {NORMALIZED_PATH}")


if __name__ == "__main__":
    main()
