from __future__ import annotations

PROMPT_TEMPLATE = """
너의 역할은 일정 문장에서 최종 title을 직접 생성하지 않고,
원문에서 title로 남아야 할 정확한 표면 구간을 먼저 판단한 뒤,
그 외 나머지를 remove_spans로 표시하는 것이다.

반드시 JSON만 출력해.
설명, 코드블록, 추가 문장은 절대 출력하지 마.

현재 시각:
{now}

사용자 입력:
{input}

규칙:
1. source_text는 단일 일정이면 사용자 입력 전체를 그대로 넣어. 고치거나 요약하지 마.
2. date_text는 날짜/요일/상대 날짜의 원문 span만 넣어. 없으면 null.
3. time_text는 시간의 원문 span만 넣어. 없으면 반드시 null.
4. time_text를 추론해서 넣지 마. 원문에 없는 시간을 만들어 넣으면 안 된다.
5. 먼저 이 문장에서 캘린더 title로 남아야 할 정확한 원문 구간(title_candidate)을 내부적으로 판단해.
6. title_candidate는 날짜/시간 표현이 아니고, 조사/말투/요청 어미도 아니며, "무슨 일정인지"를 나타내는 핵심 명사(구)다.
7. title_candidate는 직접 출력하지 마. 대신 source_text에서 title_candidate에 포함되지 않는 나머지 원문 span들을 remove_spans에 넣어.
8. remove_spans는 원문에 실제로 있는 정확한 표면 span이어야 한다. title_candidate의 일부를 remove_spans에 넣으면 안 된다.
9. date_text나 time_text에 들어간 span은 remove_spans에도 포함해.
10. 시간대 단어와 숫자 시간이 붙어 있으면 하나의 time_text로 본다.
    예: "저녁 6시", "아침 8시", "새벽 6시", "오후 4시"
11. 문장 맨 앞의 "오늘", "내일", "모레"는 기본적으로 날짜 표현으로 본다.
12. "오늘 밤", "오늘 오전", "오늘 오후", "오늘 저녁"은 date_text를 "오늘"로, time_text를 "밤 ...", "오전 ...", "오후 ...", "저녁 ..."으로 분리한다.
13. 이미 앞에 "20일", "다음주 수요일"처럼 명확한 날짜가 있고 뒤에 나오는 "오늘"은 title 일부일 수 있으므로 제거하지 마.
14. 동사 어간과 말투 어미가 붙어 있더라도, title_candidate의 핵심 의미는 남기고 어미만 remove_spans에 넣어.
    예: "운동할 거야"에서는 "운동"이 남고 "할 거야"만 제거된다.
    예: "조깅할 거야"에서는 "조깅"이 남고 "할 거야"만 제거된다.
    예: "보고서 제출할게"에서는 "보고서 제출"이 남고 "할게"만 제거된다.
15. title을 직접 생성하거나 요약하지 마. remove_spans만 정확히 고르라.
16. 값을 지어내지 마.

예시:
입력: 내일 운동할 거야
출력:
{{
  "source_text": "내일 운동할 거야",
  "date_text": "내일",
  "time_text": null,
  "remove_spans": ["내일", "할 거야"]
}}

입력: 이번주 금요일 자료 백업
출력:
{{
  "source_text": "이번주 금요일 자료 백업",
  "date_text": "이번주 금요일",
  "time_text": null,
  "remove_spans": ["이번주 금요일"]
}}

입력: 20일 오후 4시 오늘 마감 확인
출력:
{{
  "source_text": "20일 오후 4시 오늘 마감 확인",
  "date_text": "20일",
  "time_text": "오후 4시",
  "remove_spans": ["20일", "오후 4시"]
}}

입력: 내일 아침 7시에 조깅할 거야
출력:
{{
  "source_text": "내일 아침 7시에 조깅할 거야",
  "date_text": "내일",
  "time_text": "아침 7시에",
  "remove_spans": ["내일", "아침 7시에", "할 거야"]
}}

출력 JSON 스키마:
{{
  "source_text": "사용자 입력 원문 조각",
  "date_text": "내일",
  "time_text": "아침 9시 반",
  "remove_spans": ["내일", "아침 9시 반"]
}}
""".strip()


def build_prompt(now: str, user_input: str) -> str:
    return PROMPT_TEMPLATE.format(now=now, input=user_input)
