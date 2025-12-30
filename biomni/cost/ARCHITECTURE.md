# Cost Tracking Architecture

## 개요

Cost tracking 시스템은 LLM 호출의 토큰 사용량을 추적하고 비용을 계산하는 모듈입니다.

## 파일 구조 및 역할

### 핵심 모듈

1. **`models.py`** - 데이터 모델
   - `TokenUsage`: 단일 LLM 호출의 토큰 사용량 정보
   - `CostRecord`: 토큰 사용량에 대한 비용 정보
   - 역할: 데이터 구조 정의 및 검증

2. **`token_tracker.py`** - 토큰 추적
   - `TokenTracker`: 토큰 사용량 히스토리 관리
   - `extract_token_usage()`: 다양한 LLM 제공자의 응답에서 토큰 정보 추출
   - `track_llm_call()`: 토큰 사용량 기록
   - 역할: 토큰 사용량 수집 및 저장

3. **`llm_wrapper.py`** - LLM 래퍼
   - `CostTrackingLLMWrapper`: BaseChatModel을 래핑하여 자동 추적
   - `invoke()`, `stream()` 메서드 인터셉트
   - 역할: LLM 호출을 가로채서 토큰 추적

4. **`pricing.py`** - 가격 정보
   - `PRICING_TABLE`: 모델별 가격 테이블
   - `get_model_pricing()`: 모델 가격 정보 조회
   - 역할: 모델별 가격 정보 관리

5. **`cost_calculator.py`** - 비용 계산
   - `CostCalculator`: 토큰 사용량을 비용으로 변환
   - `calculate_llm_cost()`: 단일 호출 비용 계산
   - `calculate_session_cost()`: 세션 전체 비용 계산 및 그룹화
   - 역할: 토큰 → 비용 변환 및 집계

6. **`report.py`** - 리포트 생성
   - `CostReport`: 비용 리포트 생성 및 저장
   - `generate_session_report()`: 세션 리포트 생성
   - `generate_workflow_report()`: 워크플로우 리포트 생성
   - 역할: 리포트 생성 및 포맷팅

7. **`utils.py`** - 유틸리티 함수
   - `get_default_token_tracker()`: 기본 TokenTracker 생성
   - `get_default_cost_report()`: 기본 CostReport 생성
   - `is_cost_tracking_enabled()`: 비용 추적 활성화 여부 확인
   - 역할: 편의 함수 제공

## 데이터 흐름

```
LLM 호출
  ↓
CostTrackingLLMWrapper.invoke() / stream()
  ↓
TokenTracker.extract_token_usage()  [토큰 정보 추출]
  ↓
TokenTracker.track_llm_call()  [TokenUsage 객체 생성 및 저장]
  ↓
TokenTracker.token_usage_history  [히스토리 저장]
  ↓
CostReport.generate_session_report()
  ↓
CostCalculator.calculate_session_cost()
  ↓
  ├─ CostCalculator.calculate_llm_cost()  [개별 비용 계산]
  ├─ CostRecord 생성
  └─ 그룹화 (by_model, by_context) 및 summary 계산
  ↓
CostReport.save_report()  [JSON 파일로 저장]
```

## 파일 간 의존성

```
models.py (독립)
  ↑
token_tracker.py → models.py
  ↑
llm_wrapper.py → token_tracker.py
  ↑
pricing.py (독립)
  ↑
cost_calculator.py → models.py, pricing.py
  ↑
report.py → token_tracker.py, cost_calculator.py, models.py
  ↑
utils.py → token_tracker.py, cost_calculator.py, report.py
  ↑
__init__.py → 모든 모듈
```

## 주요 최적화 사항

### 1. 중복 순회 제거
- **문제**: `report.py`에서 summary를 별도로 계산하며 `token_usages`를 중복 순회
- **해결**: `cost_calculator.calculate_session_cost()`에서 그룹화와 함께 summary도 계산
- **효과**: O(n) → O(n) (중복 제거로 실제 순회 횟수 감소)

### 2. 단일 순회 그룹화
- **문제**: `by_model`과 `by_context`를 별도로 계산
- **해결**: 단일 순회로 두 그룹을 동시에 계산
- **효과**: O(2n) → O(n)

### 3. 메모리 최적화
- `include_cost_records` 파라미터로 대용량 데이터셋에서 상세 레코드 제외 가능
- `token_usage_history`는 메모리에 저장 (필요시 지속성 계층 추가 가능)

### 4. 딕셔너리 접근 캐싱
- 반복적인 딕셔너리 접근을 변수에 캐싱하여 성능 향상

## 사용 패턴

### 1. 기본 사용 (Chainlit)
```python
# 1. TokenTracker 생성
tracker = get_default_token_tracker(session_id="user_123")

# 2. LLM 래핑
llm = CostTrackingLLMWrapper(
    llm=base_llm,
    token_tracker=tracker,
    context="agent_main"
)

# 3. LLM 호출 (자동 추적)
response = llm.invoke(messages)

# 4. 리포트 생성
report = CostReport()
cost_data = report.generate_session_report(tracker)
report.save_report(cost_data)
```

### 2. 여러 컨텍스트에서 공유
```python
# 같은 tracker를 여러 wrapper에서 공유
tracker = TokenTracker(session_id="session_1")

# 메인 에이전트
agent_llm = CostTrackingLLMWrapper(llm, tracker, context="agent_main")

# 데이터베이스 쿼리
db_llm = CostTrackingLLMWrapper(llm, tracker, context="database_query")

# 워크플로우 생성
workflow_llm = CostTrackingLLMWrapper(llm, tracker, context="workflow_generation")
```

## 성능 특성

- **시간 복잡도**: O(n) - n은 LLM 호출 횟수
- **공간 복잡도**: O(n) - 모든 TokenUsage 객체 저장
- **최적화된 순회**: 리포트 생성 시 단일 순회로 모든 집계 수행

## 확장 가능성

1. **지속성 계층**: 현재는 메모리 저장, 필요시 DB 저장 추가 가능
2. **실시간 모니터링**: WebSocket 등을 통한 실시간 비용 업데이트
3. **예산 관리**: 세션별 예산 설정 및 초과 알림
4. **비용 예측**: 과거 데이터 기반 비용 예측

## 주의사항

1. **메모리 사용**: `token_usage_history`가 무제한으로 증가할 수 있음
   - 해결: 필요시 `reset_session()` 호출 또는 히스토리 제한 옵션 추가

2. **세션 관리**: 여러 사용자가 같은 tracker를 공유하면 데이터 혼합 가능
   - 해결: 사용자별로 별도의 tracker 인스턴스 사용

3. **가격 정보 업데이트**: `pricing.py`의 가격 정보를 정기적으로 업데이트 필요
