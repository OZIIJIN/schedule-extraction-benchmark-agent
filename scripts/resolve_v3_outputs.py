from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from schedule_resolver_v3 import normalize_intermediate, resolve_schedule
from versioned_outputs_v3 import latest_versioned_path, write_text_version_only

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_PATH = BASE_DIR / "outputs" / "v3" / "raw" / "benchmark_span_raw.json"
DERIVED_DIR = BASE_DIR / "outputs" / "v3" / "derived"
RESOLVED_PATH = DERIVED_DIR / "resolved_outputs.json"


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

    raw_path = latest_versioned_path(RAW_PATH)
    raw_items = json.loads(raw_path.read_text(encoding="utf-8"))
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

    versioned_path = write_text_version_only(
        RESOLVED_PATH,
        json.dumps(resolved_items, ensure_ascii=False, indent=2),
    )
    print(f"loaded: {raw_path}")
    print(f"saved: {versioned_path}")


if __name__ == "__main__":
    main()
