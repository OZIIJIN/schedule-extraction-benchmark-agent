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
6. remove_spans에는 source_text에서 제목이 아니므로 제거해야 하는 날짜/요일/시간 span만 넣어.
7. remove_spans에는 제목 단어를 절대 넣지 마.
8. title을 직접 만들거나 요약하지 마.
9. "저녁 6시", "아침 8시", "새벽 6시", "오후 4시"처럼 시간대 단어와 숫자 시간이 붙어 있으면 전체를 time_text와 remove_spans에 넣어.
10. "엄마 생신 저녁", "월초 회식", "오늘 마감 확인", "낚시 출발", "헬스장 PT"처럼 일정명에 속한 단어는 remove_spans에 넣지 마.
11. date_text나 time_text에 들어간 span은 remove_spans에도 넣어.
12. 값을 지어내지 마.

좋은 예:
입력: 내일 아침 9시 반에 헬스장 가서 PT
출력:
{{
  "source_text": "내일 아침 9시 반에 헬스장 가서 PT",
  "date_text": "내일",
  "time_text": "아침 9시 반",
  "remove_spans": ["내일", "아침 9시 반"]
}}

좋은 예:
입력: 다음주 금요일 저녁 6시 엄마 생신 저녁
출력:
{{
  "source_text": "다음주 금요일 저녁 6시 엄마 생신 저녁",
  "date_text": "다음주 금요일",
  "time_text": "저녁 6시",
  "remove_spans": ["다음주 금요일", "저녁 6시"]
}}

좋은 예:
입력: 1일 저녁 6시 월초 회식
출력:
{{
  "source_text": "1일 저녁 6시 월초 회식",
  "date_text": "1일",
  "time_text": "저녁 6시",
  "remove_spans": ["1일", "저녁 6시"]
}}

좋은 예:
입력: 20일 오후 4시 오늘 마감 확인
출력:
{{
  "source_text": "20일 오후 4시 오늘 마감 확인",
  "date_text": "20일",
  "time_text": "오후 4시",
  "remove_spans": ["20일", "오후 4시"]
}}

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
