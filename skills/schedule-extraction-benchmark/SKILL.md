---
name: schedule-extraction-benchmark
description: 로컬 LLM의 한국어 일정 추출 성능을 비교하고 리포트를 생성한다.
---

이 스킬은 아래와 같은 요청이 들어왔을 때 사용한다.

- 로컬 LLM 일정 추출 성능 비교
- 상대 날짜 표현 처리 성능 확인
- 일정 추출 JSON 품질 점검
- 모델별 실패 패턴 분석
- 벤치마크 결과 리포트 작성

## 목적

한국어 자연어 입력에서 일정 정보를 추출하는 작업을 로컬 LLM으로 대체할 수 있는지 검토한다.

특히 아래 항목을 중점적으로 본다.

- 날짜 계산 정확도
- 시간 표현 정규화 정확도
- TODO / SCHEDULE 분류 정확도
- JSON 스키마 준수 여부
- 모델별 평균 응답 속도

## 관련 경로

- 테스트 케이스: `cases/`
- 원본 응답: `outputs/raw/`
- 정규화 결과: `outputs/derived/`
- 최종 리포트: `outputs/reports/`

## 사용 스크립트

- `scripts/run_benchmark.py`
    - 테스트 케이스를 기준으로 모델 실행
- `scripts/normalize_outputs.py`
    - 모델 응답을 공통 형식으로 정리
- `scripts/evaluate_results.py`
    - 기대값과 비교해 정확도 및 실패 유형 계산
- `scripts/write_report.py`
    - 평가 결과를 markdown 리포트로 생성

## 기본 실행 순서

1. `python3 scripts/run_benchmark.py`
2. `python3 scripts/normalize_outputs.py`
3. `python3 scripts/evaluate_results.py`
4. `python3 scripts/write_report.py`

## 평가 기준

최소 아래 항목은 확인한다.

- JSON 파싱 가능 여부
- title 일치 여부
- year / month / day 일치 여부
- dayOfWeek 일치 여부
- hour / minute / ampm 일치 여부
- type 일치 여부
- 평균 응답 시간

## 실패 유형

필요 시 아래 기준으로 분류한다.

- `INVALID_JSON`
- `DATE_RESOLUTION_FAILED`
- `DAY_OF_WEEK_MISMATCH`
- `TIME_NORMALIZATION_FAILED`
- `TYPE_CLASSIFICATION_FAILED`
- `TITLE_EXTRACTION_FAILED`
- `NULL_HANDLING_FAILED`
- `MISSING_REQUIRED_FIELD`

## 판단 시 유의사항

- 응답 속도가 빠르더라도 정확도가 낮으면 그대로 적는다.
- 정확도가 높더라도 응답 속도가 과하게 느리면 그대로 적는다.
- title은 exact match 기준으로 평가하되, 이후 완화가 필요하면 별도 논의한다.
- 현재 PoC는 운영 반영 전 검토 단계이므로, 최종 결론보다는 비교 근거 확보에 초점을 둔다.

## 최종 결과물

리포트에는 아래 내용이 들어가야 한다.

- 어떤 모델을 비교했는지
- 각 모델의 평균 점수
- 각 모델의 평균 응답 시간
- 필드별 정확도
- 자주 발생한 실패 유형
- 다음 검토 대상 모델 또는 후속 작업 제안
- 다음 검토 대상 모델 또는 후속 작업 제안