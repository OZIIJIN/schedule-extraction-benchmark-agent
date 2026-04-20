from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
CASES_PATH = BASE_DIR / "cases" / "schedule_cases.json"
RAW_DIR = BASE_DIR / "outputs" / "v2" / "raw"
RAW_PATH = RAW_DIR / "benchmark_intermediate_raw.json"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODELS = [
    "gemma3:4b"
]

PROMPT_TEMPLATE = """
너는 일정 문장에서 중간표현만 추출하는 역할이야.
반드시 JSON만 출력해.
설명, 코드블록, 추가 문장은 절대 출력하지 마.

현재 시각:
{now}

사용자 입력:
{input}

규칙:
1. 날짜를 계산하지 말고, 문장에 나온 날짜/요일 표현을 원문 그대로 date_text에 복사해.
2. 날짜 표현을 표준어로 고치거나, 줄이거나, 자연스럽게 다시 쓰지 마.
3. "다다음주"는 반드시 "다다음주"로 유지하고, 절대 "다음주"로 바꾸지 마.
4. "낼", "금욜", "화욜" 같은 구어체/축약 표현도 원문 그대로 유지해.
5. date_text에는 날짜/요일/상대 날짜 표현만 넣고, 시간 표현은 넣지 마.
6. time_text에는 시간 표현만 원문 그대로 넣어.
7. 날짜 표현이 없으면 date_text는 null이야.
8. 시간 표현이 없으면 time_text는 null이야.
9. title_text는 일정의 핵심 제목만 자연스러운 명사구로 뽑아.
10. title_text에는 날짜, 요일, 시간 표현을 넣지 마.
11. 장소는 제목의 핵심이 아니면 빼.
12. 값을 지어내지 마.

좋은 예:
입력: 다다음주 화요일 오전 9시 계약 미팅
출력:
{{
  "title_text": "계약 미팅",
  "date_text": "다다음주 화요일",
  "time_text": "오전 9시"
}}

나쁜 예:
{{
  "title_text": "계약 미팅",
  "date_text": "다음 주 화요일",
  "time_text": "오전 9시"
}}

좋은 예:
입력: 다음주 금욜 저녁 7시 친구 약속
출력:
{{
  "title_text": "친구 약속",
  "date_text": "다음주 금욜",
  "time_text": "저녁 7시"
}}

좋은 예:
입력: 다다음주 수요일 오후 4시 회고
출력:
{{
  "title_text": "회고",
  "date_text": "다다음주 수요일",
  "time_text": "오후 4시"
}}

출력 JSON 스키마:
{{
  "title_text": "일정 제목 후보",
  "date_text": "내일",
  "time_text": "아침 9시 반"
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

    RAW_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"saved: {RAW_PATH}")


if __name__ == "__main__":
    main()
