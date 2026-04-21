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


def cleanup_title(title: str) -> str | None:
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"^[가-힣A-Za-z0-9]+역에서\s+", "", title)
    title = re.sub(r"^(에|에서)\s+", "", title)
    title = re.sub(r"\s+(에|에서)$", "", title)
    title = title.replace(" 가서 ", " ")

    suffix_patterns = [
        r"\s*할\s*거야$",
        r"\s*할거야$",
        r"\s*할게$",
        r"\s*갈\s*거야$",
        r"\s*갈게$",
        r"\s*갈래$",
        r"\s*잡아줘$",
        r"\s*해야\s*돼$",
        r"\s*해야\s*해$",
        r"야\s*돼$",
        r"야\s*해$",
        r"\s*해둘게$",
        r"\s*먹을\s*거야$",
        r"\s*먹을래$",
        r"\s*보러\s*갈게$",
        r"\s*받을\s*거야$",
    ]
    for pattern in suffix_patterns:
        title = re.sub(pattern, "", title)

    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"\s*보러$", "", title)
    title = re.sub(r"(.+)하기$", r"\1", title)
    title = re.sub(r"(.+)챙겨야$", r"\1챙기기", title)
    title = re.sub(r"(.+)챙겨$", r"\1챙기기", title)
    title = re.sub(r"\s+", " ", title).strip()

    return title or None


def span_looks_like_title(source_text: str, span: str) -> bool:
    compact = re.sub(r"\s+", "", span)
    if not compact:
        return False

    title_suffixes = [
        "할거야",
        "할게",
        "갈거야",
        "갈게",
        "갈래",
        "해야돼",
        "해야해",
        "해둘게",
        "먹을래",
        "받을거야",
    ]
    if any(compact.endswith(suffix) for suffix in title_suffixes):
        prefix = compact
        for suffix in title_suffixes:
            if prefix.endswith(suffix):
                prefix = prefix[: -len(suffix)]
                break
        return bool(prefix)

    if compact.endswith("잡아줘"):
        return bool(compact[: -len("잡아줘")])

    return False


def safely_removable_span(span: str) -> bool:
    normalized = normalize_date_text(span)
    compact = re.sub(r"\s+", "", normalized)
    if not compact:
        return False

    patterns = [
        r"^(오늘|내일|낼|모레)$",
        r"^(이번|다음|다다음)주[월화수목금토일]?요일?$",
        r"^[월화수목금토일]요일?(에)?$",
        r"^(이번|다음)달\d{1,2}일$",
        r"^\d{1,2}월\d{1,2}일?$",
        r"^\d{1,2}/\d{1,2}$",
        r"^\d{1,2}일(에)?$",
        r"^(오전|오후|아침|저녁|밤|낮|새벽)?(\d{1,2}|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|열한|열두)시(반|\d{1,2}분|정각)?(에)?$",
        r"^[월화수목금토일]요일?(오전|오후|아침|저녁|밤|낮|새벽)?(\d{1,2}|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|열한|열두)시(반|\d{1,2}분|정각)?(에)?$",
        r"^[가-힣A-Za-z0-9]+역에서$",
        r"^(에|에서|가서)$",
    ]
    return any(re.search(pattern, compact) for pattern in patterns)


def fallback_spans(
    source_text: str,
    date_text: str | None,
    time_text: str | None,
    remove_spans: list[str],
) -> list[str]:
    spans: list[str] = []
    for span in [date_text, time_text, *remove_spans]:
        span = blank_to_none(span)
        if not span:
            continue
        if span_looks_like_title(source_text, span):
            continue
        if span not in [date_text, time_text] and not safely_removable_span(span):
            continue
        if span not in spans:
            spans.append(span)
    return spans


def title_from_spans(source_text: str, remove_spans: list[str]) -> str | None:
    title = normalize_date_text(source_text)
    normalized_spans = [normalize_date_text(span) for span in remove_spans if span]

    for span in sorted(normalized_spans, key=len, reverse=True):
        title = remove_once(title, span)

    return cleanup_title(title)


def title_from_intermediate(
    source_text: str,
    date_text: str | None,
    time_text: str | None,
    remove_spans: list[str],
) -> str | None:
    primary_title = title_from_spans(source_text, remove_spans)
    fallback_title = title_from_spans(source_text, fallback_spans(source_text, date_text, time_text, remove_spans))
    removed_title_like_span = any(span_looks_like_title(source_text, span) for span in remove_spans)

    if primary_title is None:
        return fallback_title

    primary_compact = primary_title.replace(" ", "")
    fallback_compact = (fallback_title or "").replace(" ", "")
    if (
        fallback_title is not None
        and (removed_title_like_span or primary_compact in fallback_compact)
        and len(fallback_title.replace(" ", "")) > len(primary_title.replace(" ", ""))
    ):
        return fallback_title

    return primary_title


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
    title = title_from_intermediate(
        source_text,
        intermediate.get("date_text"),
        intermediate.get("time_text"),
        intermediate.get("remove_spans") or [],
    )

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
