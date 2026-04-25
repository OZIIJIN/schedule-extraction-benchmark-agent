from __future__ import annotations

import json
import os
import subprocess
import time
import tempfile
from pathlib import Path
from typing import Any
import base64

import requests

from prompt_v3 import build_prompt
from versioned_outputs_v3 import write_text_version_only

BASE_DIR = Path(__file__).resolve().parent.parent
CASES_PATH = BASE_DIR / "cases" / "schedule_cases.json"
RAW_DIR = BASE_DIR / "outputs" / "v3" / "raw"
RAW_PATH = RAW_DIR / "benchmark_span_raw.json"

VERTEX_PROJECT_ID = os.environ.get("VERTEX_PROJECT_ID")
VERTEX_LOCATION = os.environ.get("VERTEX_LOCATION", "global")
VERTEX_MODEL = os.environ.get("VERTEX_MODEL", "gemini-2.5-flash")
VERTEX_ACCESS_TOKEN = os.environ.get("VERTEX_ACCESS_TOKEN")
VERTEX_SERVICE_ACCOUNT_JSON_PATH = os.environ.get("VERTEX_SERVICE_ACCOUNT_JSON_PATH") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
VERTEX_TIMEOUT_SEC = int(os.environ.get("VERTEX_TIMEOUT_SEC", "180"))


def load_cases() -> list[dict[str, Any]]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def require_env(name: str, value: str | None) -> str:
    if value:
        return value
    raise RuntimeError(f"missing required environment variable: {name}")


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def load_service_account(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    return json.loads(path.read_text(encoding="utf-8"))


def sign_with_private_key(private_key_pem: str, message: bytes) -> bytes:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as key_file:
        key_file.write(private_key_pem)
        key_path = key_file.name
    try:
        result = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", key_path, "-binary"],
            input=message,
            capture_output=True,
            check=True,
        )
        return result.stdout
    finally:
        Path(key_path).unlink(missing_ok=True)


def mint_access_token_from_service_account(path_str: str) -> str:
    account = load_service_account(path_str)
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claim = {
        "iss": account["client_email"],
        "scope": "https://www.googleapis.com/auth/cloud-platform",
        "aud": account["token_uri"],
        "iat": now,
        "exp": now + 3600,
    }
    signing_input = f"{b64url(json.dumps(header, separators=(',', ':')).encode())}.{b64url(json.dumps(claim, separators=(',', ':')).encode())}".encode()
    signature = sign_with_private_key(account["private_key"], signing_input)
    assertion = f"{signing_input.decode()}.{b64url(signature)}"

    response = requests.post(
        account["token_uri"],
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError(f"token exchange failed: {payload}")
    return access_token


def resolve_access_token() -> str:
    if VERTEX_ACCESS_TOKEN:
        return VERTEX_ACCESS_TOKEN
    if VERTEX_SERVICE_ACCOUNT_JSON_PATH:
        return mint_access_token_from_service_account(VERTEX_SERVICE_ACCOUNT_JSON_PATH)
    raise RuntimeError(
        "missing credentials: set VERTEX_ACCESS_TOKEN or VERTEX_SERVICE_ACCOUNT_JSON_PATH"
    )


def call_model(model: str, prompt: str, access_token: str) -> dict[str, Any]:
    project_id = require_env("VERTEX_PROJECT_ID", VERTEX_PROJECT_ID)
    api_host = "https://aiplatform.googleapis.com" if VERTEX_LOCATION == "global" else f"https://{VERTEX_LOCATION}-aiplatform.googleapis.com"
    url = (
        f"{api_host}/v1/projects/{project_id}/locations/{VERTEX_LOCATION}/"
        f"publishers/google/models/{model}:generateContent"
    )

    start = time.perf_counter()
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        },
        timeout=VERTEX_TIMEOUT_SEC,
    )
    elapsed = round(time.perf_counter() - start, 3)
    response.raise_for_status()
    payload = response.json()

    candidates = payload.get("candidates") or []
    raw_response = None
    if candidates:
        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        if parts:
            raw_response = parts[0].get("text")

    usage = payload.get("usageMetadata") or {}
    return {
        "raw_response": raw_response,
        "latency_sec": elapsed,
        "done": True,
        "eval_count": usage.get("candidatesTokenCount"),
        "prompt_eval_count": usage.get("promptTokenCount"),
    }


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    model = VERTEX_MODEL
    access_token = resolve_access_token()
    cases = load_cases()
    results: list[dict[str, Any]] = []

    for case in cases:
        prompt = build_prompt(case["now"], case["input"])
        try:
            result = call_model(model, prompt, access_token)
            results.append({
                "case_id": case["id"],
                "model": f"vertex:{model}",
                "now": case["now"],
                "input": case["input"],
                "raw_response": result["raw_response"],
                "latency_sec": result["latency_sec"],
                "done": result["done"],
                "eval_count": result["eval_count"],
                "prompt_eval_count": result["prompt_eval_count"],
            })
            print(f"[OK] vertex:{model} / {case['id']} / {result['latency_sec']}s", flush=True)
        except Exception as exc:
            results.append({
                "case_id": case["id"],
                "model": f"vertex:{model}",
                "now": case["now"],
                "input": case["input"],
                "raw_response": None,
                "latency_sec": None,
                "done": False,
                "eval_count": None,
                "prompt_eval_count": None,
                "error": str(exc),
            })
            print(f"[ERROR] vertex:{model} / {case['id']} / {exc}", flush=True)

    versioned_path = write_text_version_only(
        RAW_PATH,
        json.dumps(results, ensure_ascii=False, indent=2),
    )
    print(f"saved: {versioned_path}")


if __name__ == "__main__":
    main()
