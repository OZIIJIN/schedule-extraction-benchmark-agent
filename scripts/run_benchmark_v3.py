from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from versioned_outputs_v3 import write_text_version_only

BASE_DIR = Path(__file__).resolve().parent.parent
CASES_PATH = BASE_DIR / "cases" / "schedule_cases.json"
RAW_DIR = BASE_DIR / "outputs" / "v3" / "raw"
RAW_PATH = RAW_DIR / "benchmark_span_raw.json"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODELS = [
    "gemma3:4b",
]

PROMPT_TEMPLATE = """
너는 일정 문장에서 최종 제목을 생성하지 않고, 제거할 span만 표시하는 역할이야.
반드시 JSON만 출력해.
설명, 코드블록, 추가 문장은 절대 출력하지 마.

현재 시각:
{now}

사용자 입력:
{input}

규칙:
1. source_text에는 이번 일정에 해당하는 원문 조각을 그대로 넣어. 단일 일정이면 사용자 입력 전체를 넣어.
2. date_text에는 날짜/요일/상대 날짜 표현만 원문 그대로 넣어.
3. time_text에는 시간 표현만 원문 그대로 넣어.
4. 날짜 표현이 없으면 date_text는 null이야.
5. 시간 표현이 없으면 time_text는 null이야.
6. remove_spans를 구성하기 전에 먼저 이 문장에서 캘린더 제목이 될 핵심 명사(구)가 무엇인지 파악해.
   핵심 명사(구)란: 날짜도 아니고, 시간도 아니고, 말투/어미/조사도 아닌, "무슨 일정인지"를 나타내는 부분이야.
   예: "운동", "조깅", "보고서 제출", "팀 회의", "낚시 출발", "헬스장 PT"
   이것을 직접 출력하지는 말고, 이것을 제외한 나머지를 remove_spans에 넣어.
7. remove_spans = source_text 전체 - 핵심 명사(구).
   즉 날짜, 시간, 조사, 말투 어미, 요청 표현 등 핵심 명사(구)가 아닌 것은 전부 remove_spans에 넣어.
8. title을 직접 만들거나 요약하지 마.
9. "저녁 6시", "아침 8시", "새벽 6시", "오후 4시"처럼 시간대 단어와 숫자 시간이 붙어 있으면 전체를 time_text와 remove_spans에 넣어.
10. date_text나 time_text에 들어간 span은 remove_spans에도 넣어.
11. 동사가 핵심 명사(구)에 붙어있는 경우, 어미만 잘라서 remove_spans에 넣어. 어간은 남겨.
    예: "운동할 거야" → 핵심은 "운동", 어미 "할 거야"만 remove_spans에 넣어.
    예: "조깅할 거야" → 핵심은 "조깅", 어미 "할 거야"만 remove_spans에 넣어.
    예: "보고서 제출할게" → 핵심은 "보고서 제출", 어미 "할게"만 remove_spans에 넣어.
    예: "책 반납해야 돼" → 핵심은 "책 반납", 어미 "해야 돼"만 remove_spans에 넣어.
    예: "피부과 갈게" → 핵심은 "피부과", 어미 "갈게"만 remove_spans에 넣어.
12. "할거야", "할 거야", "할게", "갈게", "갈 거야", "갈래", "잡아줘", "해야 돼", "해야 해", "해둘게", "먹을래", "먹을 거야", "보러 갈게", "받을 거야" 같은 말투/요청 표현은 remove_spans에 넣어.
13. "엄마 생신 저녁", "월초 회식", "오늘 마감 확인", "낚시 출발", "헬스장 PT"처럼 일정명에 속한 단어는 remove_spans에 넣지 마.
14. "저녁 6시", "아침 8시", "새벽 6시", "오후 4시"처럼 시간대 단어와 숫자 시간이 붙어 있으면 전체를 time_text와 remove_spans에 넣어.
15. 문장 맨 앞의 "오늘", "내일", "모레"는 기본적으로 날짜 표현이므로 date_text와 remove_spans에 넣어.
16. "오늘 밤", "오늘 오전", "오늘 오후", "오늘 저녁"은 date_text를 "오늘"로, time_text를 "밤 ...", "오전 ...", "오후 ...", "저녁 ..."으로 분리해.
17. 이미 "20일", "다음주 수요일"처럼 명확한 날짜가 앞에 있고 그 뒤에 나오는 "오늘"은 일정명일 수 있으므로 remove_spans에 넣지 마.
18. source_text는 절대 고치지 말고 원문 그대로 유지해.
19. 값을 지어내지 마.

출력 JSON 스키마:
{{
  "source_text": "사용자 입력 원문 조각",
  "date_text": "내일",
  "time_text": "아침 9시 반",
  "remove_spans": ["내일", "아침 9시 반"]
}}
""".strip()


def load_cases() -> list[dict[str, Any]]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def build_prompt(now: str, user_input: str) -> str:
    return PROMPT_TEMPLATE.format(now=now, input=user_input)


def call_model(model: str, prompt: str) -> dict[str, Any]:
    start = time.perf_counter()
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0,
            },
        },
        timeout=180,
    )
    elapsed = round(time.perf_counter() - start, 3)
    response.raise_for_status()
    payload = response.json()

    return {
        "raw_response": payload.get("response"),
        "latency_sec": elapsed,
        "done": payload.get("done"),
        "eval_count": payload.get("eval_count"),
        "prompt_eval_count": payload.get("prompt_eval_count"),
    }


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    cases = load_cases()
    results: list[dict[str, Any]] = []

    for case in cases:
        for model in MODELS:
            prompt = build_prompt(case["now"], case["input"])
            try:
                result = call_model(model, prompt)
                results.append({
                    "case_id": case["id"],
                    "model": model,
                    "now": case["now"],
                    "input": case["input"],
                    "raw_response": result["raw_response"],
                    "latency_sec": result["latency_sec"],
                    "done": result["done"],
                    "eval_count": result["eval_count"],
                    "prompt_eval_count": result["prompt_eval_count"],
                })
                print(f"[OK] {model} / {case['id']} / {result['latency_sec']}s", flush=True)
            except Exception as exc:
                results.append({
                    "case_id": case["id"],
                    "model": model,
                    "now": case["now"],
                    "input": case["input"],
                    "raw_response": None,
                    "latency_sec": None,
                    "done": False,
                    "eval_count": None,
                    "prompt_eval_count": None,
                    "error": str(exc),
                })
                print(f"[ERROR] {model} / {case['id']} / {exc}", flush=True)

    versioned_path = write_text_version_only(
        RAW_PATH,
        json.dumps(results, ensure_ascii=False, indent=2),
    )
    print(f"saved: {versioned_path}")


if __name__ == "__main__":
    main()
