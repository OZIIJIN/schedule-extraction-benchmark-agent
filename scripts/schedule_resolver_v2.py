from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

WEEKDAY_NAMES = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
WEEKDAY_OFFSETS = {
    "월": 0,
    "화": 1,
    "수": 2,
    "목": 3,
    "금": 4,
    "토": 5,
    "일": 6,
}
WEEKDAY_ALIASES = {
    "월욜": "월요일",
    "화욜": "화요일",
    "수욜": "수요일",
    "목욜": "목요일",
    "금욜": "금요일",
    "토욜": "토요일",
    "일욜": "일요일",
}
KOREAN_HOURS = {
    "한": 1,
    "두": 2,
    "세": 3,
    "네": 4,
    "다섯": 5,
    "여섯": 6,
    "일곱": 7,
    "여덟": 8,
    "아홉": 9,
    "열": 10,
    "열한": 11,
    "열두": 12,
}


def blank_to_none(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = " ".join(value.strip().split())
    return stripped or None


def normalize_intermediate(payload: dict[str, Any]) -> dict[str, str | None]:
    return {
        "title_text": blank_to_none(payload.get("title_text") or payload.get("title")),
        "date_text": blank_to_none(payload.get("date_text") or payload.get("date")),
        "time_text": blank_to_none(payload.get("time_text") or payload.get("time")),
    }


def weekday_name(value: date) -> str:
    return WEEKDAY_NAMES[value.weekday()]


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    return date(value.year + month_index // 12, month_index % 12 + 1, 1)


def closest_weekday_on_or_after(base: date, weekday_offset: int) -> date:
    days_ahead = (weekday_offset - base.weekday()) % 7
    return base + timedelta(days=days_ahead)


def closest_day_of_month_on_or_after(base: date, day: int) -> date:
    candidate = date(base.year, base.month, day)
    if candidate >= base:
        return candidate

    next_month = add_months(base, 1)
    return date(next_month.year, next_month.month, day)


def normalize_date_text(text: str) -> str:
    normalized = text
    for alias, weekday in WEEKDAY_ALIASES.items():
        normalized = normalized.replace(alias, weekday)
    return normalized


def resolve_date(now_text: str, date_text: str | None, original_input: str) -> date | None:
    base = datetime.fromisoformat(now_text).date()
    text = normalize_date_text(date_text or original_input)
    resolved = resolve_date_from_text(base, text)
    if resolved is not None:
        return resolved

    if date_text:
        return resolve_date_from_text(base, normalize_date_text(original_input))

    return None


def resolve_date_from_text(base: date, text: str) -> date | None:
    compact = re.sub(r"\s+", "", text)

    if "모레" in compact:
        return base + timedelta(days=2)
    if "내일" in compact or "낼" in compact:
        return base + timedelta(days=1)
    if "오늘" in compact:
        return base

    week_match = re.search(r"(다다음주|이번주|다음주)(월|화|수|목|금|토|일)요일?", compact)
    if week_match:
        week_prefix, weekday = week_match.groups()
        start_of_week = base - timedelta(days=base.weekday())
        week_delta = {
            "이번주": 0,
            "다음주": 7,
            "다다음주": 14,
        }[week_prefix]
        return start_of_week + timedelta(days=week_delta + WEEKDAY_OFFSETS[weekday])

    relative_month_day_match = re.search(r"(이번달|다음달)(\d{1,2})일", compact)
    if relative_month_day_match:
        month_prefix, raw_day = relative_month_day_match.groups()
        month_base = add_months(base, 1 if month_prefix == "다음달" else 0)
        return date(month_base.year, month_base.month, int(raw_day))

    month_day_match = re.search(r"(\d{1,2})\s*(?:월|/)\s*(\d{1,2})\s*(?:일)?", text)
    if month_day_match:
        month = int(month_day_match.group(1))
        day = int(month_day_match.group(2))
        year = base.year
        candidate = date(year, month, day)
        if candidate < base:
            candidate = date(year + 1, month, day)
        return candidate

    bare_weekday_match = re.search(r"(?<![가-힣A-Za-z0-9])(월|화|수|목|금|토|일)요일?(?:에|날)?", compact)
    if bare_weekday_match:
        return closest_weekday_on_or_after(base, WEEKDAY_OFFSETS[bare_weekday_match.group(1)])

    bare_day_match = re.search(r"(?<![월0-9])(\d{1,2})일(?:에|날)?", compact)
    if bare_day_match:
        return closest_day_of_month_on_or_after(base, int(bare_day_match.group(1)))

    return None


def parse_hour(raw_hour: str) -> int | None:
    if raw_hour.isdigit():
        return int(raw_hour)
    return KOREAN_HOURS.get(raw_hour)


def resolve_time(
    time_text: str | None,
    original_input: str,
    date_text: str | None = None,
) -> dict[str, int | str | None]:
    text = time_text or original_input
    compact = re.sub(r"\s+", "", text)
    context = re.sub(r"\s+", "", " ".join(value for value in [time_text, date_text, original_input] if value))

    ampm: str | None = None
    if any(token in context for token in ["오전", "아침", "새벽"]):
        ampm = "오전"
    if any(token in context for token in ["오후", "저녁", "밤", "낮"]):
        ampm = "오후"

    hour_pattern = "|".join(sorted(KOREAN_HOURS, key=len, reverse=True))
    match = re.search(
        rf"(?P<hour>\d{{1,2}}|{hour_pattern})시(?:(?P<half>반)|(?P<minute>\d{{1,2}})분|정각)?",
        compact,
    )
    if not match:
        return {"hour": None, "minute": None, "ampm": None}

    hour = parse_hour(match.group("hour"))
    if hour is None:
        return {"hour": None, "minute": None, "ampm": None}

    if match.group("half"):
        minute = 30
    elif match.group("minute"):
        minute = int(match.group("minute"))
    else:
        minute = 0

    if hour > 12:
        if ampm is None:
            ampm = "오후" if hour >= 12 else "오전"
        hour = hour - 12
    elif hour == 0:
        hour = 12
        if ampm is None:
            ampm = "오전"

    return {"hour": hour, "minute": minute, "ampm": ampm}


def clean_title(title_text: str | None, original_input: str, date_text: str | None, time_text: str | None) -> str | None:
    title = title_text or original_input
    return clean_title_candidate(title, date_text, time_text)


def clean_title_candidate(
    title: str,
    date_text: str | None,
    time_text: str | None,
) -> str | None:
    title = normalize_date_text(title)

    for fragment in [date_text, time_text]:
        if fragment:
            title = title.replace(fragment, " ")
            title = title.replace(normalize_date_text(fragment), " ")

    title = re.sub(r"부터|까지", " ", title)

    # 날짜/요일 표현을 먼저 제거해 남는 핵심 제목을 비교 후보로 쓴다.
    title = re.sub(r"(이번|다음)\s*달\s*\d{1,2}\s*일", " ", title)
    title = re.sub(r"다다음\s*주\s*[월화수목금토일]요일?", " ", title)

    for fragment in [date_text, time_text]:
        if fragment:
            title = title.replace(fragment, " ")

    patterns = [
        r"\b오늘\b|\b내일\b|\b모레\b",
        r"이번\s*주\s*[월화수목금토일]요일?",
        r"다음\s*주\s*[월화수목금토일]요일?",
        r"(이번|다음|다다음)\s*주",
        r"(오전|오후|아침|저녁|밤|낮|새벽)\s*(?=(\d{1,2}|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|열한|열두)\s*시|에)",
        r"(\d{1,2}|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|열한|열두)\s*시\s*(반|\d{1,2}\s*분|정각)?",
        r"\d{1,2}\s*(월|/)\s*\d{1,2}\s*일?",
        r"[가-힣A-Za-z0-9]+역에서",
        r"\b에서\b|\b에\b",
    ]
    for pattern in patterns:
        title = re.sub(pattern, " ", title)

    title = re.sub(r"\s+", " ", title).strip()
    title = title.replace(" 가서 ", " ")
    title = re.sub(r"(.+)하기$", r"\1", title)
    title = re.sub(r"\s+", " ", title).strip()

    return title or None


def resolve_schedule(
    *,
    now: str,
    original_input: str,
    intermediate: dict[str, str | None],
) -> dict[str, int | str | None]:
    resolved_date = resolve_date(now, intermediate.get("date_text"), original_input)
    resolved_time = resolve_time(
        intermediate.get("time_text"),
        original_input,
        intermediate.get("date_text"),
    )
    title = clean_title(
        intermediate.get("title_text"),
        original_input,
        intermediate.get("date_text"),
        intermediate.get("time_text"),
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
