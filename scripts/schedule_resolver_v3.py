from __future__ import annotations

import re
from typing import Any

from schedule_resolver_v2 import (
    blank_to_none,
    normalize_date_text,
    resolve_date,
    resolve_time,
    weekday_name,
)


def normalize_remove_spans(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    spans: list[str] = []
    for item in value:
        span = blank_to_none(item)
        if span and span not in spans:
            spans.append(span)
    return spans


def normalize_intermediate(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_text": blank_to_none(payload.get("source_text")),
        "date_text": blank_to_none(payload.get("date_text") or payload.get("date")),
        "time_text": blank_to_none(payload.get("time_text") or payload.get("time")),
        "remove_spans": normalize_remove_spans(payload.get("remove_spans")),
    }


def remove_once(text: str, fragment: str) -> str:
    escaped = re.escape(fragment)
    return re.sub(escaped, " ", text, count=1)


def title_from_spans(source_text: str, remove_spans: list[str]) -> str | None:
    title = normalize_date_text(source_text)
    normalized_spans = [normalize_date_text(span) for span in remove_spans if span]

    for span in sorted(normalized_spans, key=len, reverse=True):
        title = remove_once(title, span)

    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"^(에|에서)\s+", "", title)
    title = re.sub(r"\s+(에|에서)$", "", title)
    title = title.replace(" 가서 ", " ")
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"(.+)하기$", r"\1", title)
    title = re.sub(r"\s+", " ", title).strip()

    return title or None


def resolve_schedule(
    *,
    now: str,
    original_input: str,
    intermediate: dict[str, Any],
) -> dict[str, int | str | None]:
    source_text = intermediate.get("source_text") or original_input
    resolved_date = resolve_date(now, intermediate.get("date_text"), original_input)
    resolved_time = resolve_time(
        intermediate.get("time_text"),
        original_input,
        intermediate.get("date_text"),
    )
    title = title_from_spans(source_text, intermediate.get("remove_spans") or [])

    return {
        "title": title,
        "year": resolved_date.year if resolved_date else None,
        "month": resolved_date.month if resolved_date else None,
        "day": resolved_date.day if resolved_date else None,
        "dayOfWeek": weekday_name(resolved_date) if resolved_date else None,
        "hour": resolved_time["hour"],
        "minute": resolved_time["minute"],
        "ampm": resolved_time["ampm"],
        "type": "SCHEDULE" if resolved_time["hour"] is not None else "TODO",
    }
