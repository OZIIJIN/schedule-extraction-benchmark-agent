---
name: schedule-extraction-benchmark
description: 로컬 LLM의 한국어 일정 추출 성능을 비교, 개선, 재설계하고 리포트를 생성한다. 일정 추출 PoC 실행뿐 아니라 LLM-only, rule-based, hybrid, 중간표현 추출 등 새 버전 실험을 설계하거나 코드로 구현할 때도 사용한다.
---

이 스킬은 아래와 같은 요청이 들어왔을 때 사용한다.

- 로컬 LLM 일정 추출 성능 비교
- 상대 날짜 표현 처리 성능 확인
- 일정 추출 JSON 품질 점검
- 모델별 실패 패턴 분석
- 벤치마크 결과 리포트 작성
- 기존 결과를 바탕으로 PoC v2, hybrid 방식, 중간표현 추출 방식 등 새 실험 구조를 제안하거나 구현
- 대화 중 사용자가 "그럼 그 방식으로 코드 짜줘", "v2로 만들어줘", "내 테스트 케이스에 맞게 개선해줘"처럼 이전 벤치마크 논의를 이어서 구현을 요청

이 주제의 후속 대화에서는 사용자가 스킬을 직접 언급하지 않아도 이 스킬을 계속 기준으로 삼는다.

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
- 새 실험 버전은 기존 결과를 덮어쓰지 않도록 `outputs/<version>/` 또는 명확한 별도 파일명 아래에 저장한다.

## 사용 스크립트

- `scripts/run_benchmark.py`
    - 테스트 케이스를 기준으로 모델 실행
- `scripts/normalize_outputs.py`
    - 모델 응답을 공통 형식으로 정리
- `scripts/evaluate_results.py`
    - 기대값과 비교해 정확도 및 실패 유형 계산
- `scripts/write_report.py`
    - 평가 결과를 markdown 리포트로 생성
- 새 실험 버전을 만들 때는 기존 스크립트를 임의로 깨지 말고, 기존 버전 번호를 확인한 뒤 `_v2`, `_v3`, `_v4`처럼 다음 숫자로 증가시킨 별도 스크립트 또는 명확한 파이프라인 엔트리포인트를 추가한다.

## 기본 실행 순서

1. `python3 scripts/run_benchmark.py`
2. `python3 scripts/normalize_outputs.py`
3. `python3 scripts/evaluate_results.py`
4. `python3 scripts/write_report.py`

새 실험 버전도 같은 흐름을 유지한다.

1. 테스트 케이스 기준으로 모델 또는 파이프라인 실행
2. 원본 응답 또는 중간 산출물 저장
3. 공통 최종 스키마로 정규화 또는 resolve
4. 기대값과 비교 평가
5. 리포트 생성

예를 들어 LLM이 중간표현을 먼저 뽑는 hybrid 실험에서는 LLM 원본 응답, 중간표현, resolver 결과, 평가 결과를 분리해서 저장한다.

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
- LLM-only 성능이 낮으면 바로 튜닝으로 결론 내리지 말고, rule-based 또는 hybrid 구조로 분리 가능한 실패인지 먼저 검토한다.
- 날짜 계산, 요일 계산, 시간 정규화, 최종 JSON 조립은 가능하면 deterministic 코드로 분리하고, LLM은 자연어 span 또는 제목 후보 추출처럼 언어 이해가 필요한 부분에 제한하는 방안을 우선 검토한다.
- 새 버전 구현 시에도 기존 테스트 케이스로 같은 평가 기준을 적용해 이전 방식과 비교 가능하게 만든다.

## 최종 결과물

리포트에는 아래 내용이 들어가야 한다.

- 어떤 모델을 비교했는지
- 각 모델의 평균 점수
- 각 모델의 평균 응답 시간
- 필드별 정확도
- 자주 발생한 실패 유형
- 다음 검토 대상 모델 또는 후속 작업 제안
