from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
CASES_PATH = BASE_DIR / "cases" / "schedule_cases.json"
RAW_DIR = BASE_DIR / "outputs" / "raw"
RAW_PATH = RAW_DIR / "benchmark_raw.json"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODELS = [
    "qwen2.5:7b",
    "qwen2.5:3b",
    "qwen2.5:1.5b",
    "llama3.2:1b",
    "gemma3:4b",
    "llama3.2:3b"
]

PROMPT_TEMPLATE = """
너는 한 문장에서 일정 관련 정보를 추출하는 역할이야.
반드시 JSON만 출력해.
설명, 코드블록, 추가 문장은 절대 출력하지 마.

현재 시각:
{now}

사용자 입력:
{input}

규칙:
1. 반드시 현재 시각을 기준으로 날짜를 계산한다.
2. 년, 월, 일, 요일을 계산해서 채운다.
3. 시간 정보가 있으면 type은 "SCHEDULE", 없으면 "TODO"다.
4. TODO이면 hour, minute, ampm는 null이다.
5. "10시", "오전 10시", "10시 정각"은 minute를 0으로 설정한다.
6. "9시 반"은 minute를 30으로 설정한다.
7. 시간은 12시간 형식으로 반환한다.
8. 오전/오후는 "오전" 또는 "오후"만 사용한다.
9. 값이 없으면 빈 문자열이 아니라 null을 사용한다.
10. 애매하거나 알 수 없는 내용은 지어내지 말고 null로 둔다.
11. 제목은 가능한 한 자연스럽고 구체적인 명사구로 추출한다.

출력 JSON 스키마:
{{
  "title": "일정 제목",
  "year": 2026,
  "month": 4,
  "day": 21,
  "dayOfWeek": "화요일",
  "hour": 9,
  "minute": 30,
  "ampm": "오전",
  "type": "SCHEDULE"
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
                "temperature": 0
            }
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
                print(f"[OK] {model} / {case['id']} / {result['latency_sec']}s")
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
                print(f"[ERROR] {model} / {case['id']} / {exc}")

    RAW_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"saved: {RAW_PATH}")


if __name__ == "__main__":
    main()