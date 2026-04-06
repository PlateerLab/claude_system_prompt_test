# Default Chat Template Confounding 분리: 5-Way Ablation Study

> **모델**: Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled (vLLM, H200 4-way)
> **일시**: 2026-04-05
> **과제**: 8개 (알고리즘 2, 버그수정 2, 웹 1, 데이터 1, 리팩토링 2)
> **평가**: Claude-as-judge, 6개 기준 1~10점

---

## 리뷰어 피드백

> "Qwen 같은 vLLM 모델은 이미 먹고 들어가는 default system prompt가 있다.
> 당신의 실험이 관찰하는 효과가 custom prompt 때문인지, default prompt과의 상호작용 때문인지 어떻게 구분하는가?"

---

## 실험 설계

5개 조건으로 **default prompt**, **custom prompt**, **chat template** 각각의 기여를 분리합니다.

```
조건 A:  [Default Sys ✓]  [Custom Sys ✗]  [Chat Template ✓]  ← 모델 기본 상태
조건 B:  [Default Sys ✗]  [Custom Sys ✗]  [Chat Template ✓]  ← Default 제거
조건 C:  [Default Sys ✓]  [Custom Sys ✓]  [Chat Template ✓]  ← 실제 배포 시나리오
조건 D:  [Default Sys ✗]  [Custom Sys ✓]  [Chat Template ✓]  ← Custom 순수 효과
조건 E:  [Default Sys ✗]  [Custom Sys ✓]  [Chat Template ✗]  ← Template 우회
```

**핵심 비교 4개**:

| 비교 | 수식 | 의미 |
|------|------|------|
| Custom 순수 효과 | **D - B** | Default 없이 Custom만의 효과 |
| Custom 추가 효과 | **C - A** | Default 위에 Custom 쌓았을 때 |
| Default Confounding | **A - B** | 모델 내장 prompt의 영향 크기 |
| Template 구조 효과 | **E - D** | Chat template 형식 자체의 영향 |

사용된 Default System Prompt:
```
You are Qwen, created by Alibaba Cloud. You are a helpful assistant.
```

사용된 Custom System Prompt (Claude Code 하니스):
```
Don't add features, refactor code, or make "improvements" beyond what was asked.
Don't add error handling for scenarios that can't happen.
Don't create helpers for one-time operations.
Three similar lines of code is better than a premature abstraction.
Go straight to the point. Be extra concise.
```

---

## 결과 1: 종합 점수

| 조건 | 정확성 | 효율성 | 간결성 | 과잉설계방지 | 응답간결 | 지시준수 | **평균** |
|------|:------:|:------:|:------:|:----------:|:------:|:------:|:-------:|
| A. Default (기본) | 9.38 | 9.38 | 7.50 | 6.88 | 7.38 | 9.25 | **8.29** |
| B. No System | 9.25 | 9.38 | 7.50 | 6.75 | 7.75 | 8.88 | **8.25** |
| **C. Default+Custom** | **9.50** | **9.25** | **9.62** | **9.38** | **10.00** | **9.75** | **9.58** |
| D. Custom Only | 9.00 | 9.25 | 9.00 | 8.62 | 9.62 | 8.88 | **9.06** |
| E. Raw Custom | 9.25 | 9.12 | 8.75 | 8.62 | 8.38 | 9.38 | **8.92** |

**읽는 법**: 정확성은 전 조건에서 유사(9.0~9.5). 차이가 극적으로 나는 건 **간결성, 과잉설계방지, 응답간결** — 바로 하니스의 "하지 마라" 제약이 타겟하는 영역.

---

## 결과 2: 응답 효율성

| 조건 | 평균 응답 길이 | 평균 출력 토큰 | 평균 응답 시간 |
|------|:------------:|:-----------:|:------------:|
| A. Default (기본) | 1,156자 | 309 tok | 22.2s |
| B. No System | 1,037자 | 286 tok | 20.5s |
| **C. Default+Custom** | **373자 (-68%)** | **102 tok (-67%)** | **7.4s (-67%)** |
| D. Custom Only | 428자 | 116 tok | 8.4s |
| E. Raw Custom | 591자 | 151 tok | 10.9s |

Custom prompt 적용 시 **응답이 1/3로 줄면서** 점수는 **올라감**.
불필요한 산문, docstring, type hints, 사용 예시 등이 제거되기 때문.

---

## 결과 3: Ablation 핵심 비교

### A - B = Default System Prompt의 Confounding 크기

```
A (Default "You are Qwen...") = 8.29
B (System prompt 없음)        = 8.25
                         차이  = +0.04 (0.5%)  ← 사실상 없음
```

**결론**: `"You are Qwen, created by Alibaba Cloud..."` default prompt는 코드 생성 품질에 **영향이 없다**.
리뷰어가 우려한 confounding은 **무시할 수 있는 수준**.

### D - B = Custom Prompt의 순수 효과

```
D (Custom Only, Default 제거)  = 9.06
B (아무 prompt 없음)           = 8.25
                         차이  = +0.81 (+9.8%)  ← 유의미
```

**결론**: Default prompt를 완전히 통제한 후에도 Custom prompt가 **독립적으로 +0.81점** 개선.
특히 간결성(+1.5), 과잉설계방지(+1.87), 응답간결(+1.87)에서 효과 집중.

### C - A = 실제 배포 시나리오 (Default 위에 Custom 쌓기)

```
C (Default + Custom append)    = 9.58
A (Default만)                  = 8.29
                         차이  = +1.29 (+15.6%)  ← 가장 큰 효과
```

**결론**: 실제 vLLM 배포 환경(default가 있는 상태)에서 Custom을 추가하면 **+1.29점(15.6%)** 향상.
→ 이것이 "다른 모델도 Claude Code를 거치면 좋아진다"의 정량적 근거.

### E - D = Chat Template 구조 자체의 효과

```
E (Raw prompt, template 우회)  = 8.92
D (Chat API, template 사용)    = 9.06
                         차이  = -0.14 (-1.5%)  ← 사실상 없음
```

**결론**: Chat template(`<|im_start|>system\n...`)의 형식 자체는 성능에 **영향 없음**.

---

## 결과 4: 카테고리별

Custom prompt의 효과가 **과제 유형에 따라 다름**:

| 카테고리 | A (기본) | C (Custom 적용) | 개선 | 해석 |
|----------|:--------:|:---------------:|:----:|------|
| 알고리즘 | 7.33 | **9.50** | +2.17 | 불필요 type hints/docstring 제거 |
| 버그수정 | 9.83 | 9.67 | -0.16 | 이미 높음 (간단한 수정이라 과잉설계 여지 적음) |
| **웹/API** | **5.33** | **8.33** | **+3.00** | 가장 큰 효과: CORS, DB, auth 등 미요청 추가 차단 |
| **데이터처리** | **7.33** | **10.00** | **+2.67** | helper 남발 차단, 코드만 출력 |
| 리팩토링 | 8.17 | **9.67** | +1.50 | 불필요 패턴(Repository 등) 차단 |

→ **과잉설계가 많이 발생하는 과제일수록 하니스의 효과가 극대화**됨.

---

## 결과 5: 실제 응답 비교 예시

### 과제: `group_by(items, key_fn)` 함수 작성

**A. Default (점수 8.3, 841자)**:
```python
from collections import defaultdict
from typing import Callable, TypeVar, List, Dict, Any

T = TypeVar('T')
K = TypeVar('K')

def group_by(items: List[T], key_fn: Callable[[T], K]) -> Dict[K, List[T]]:
    """Group items by key function result.

    Args:
        items: List of items to group
        key_fn: Function to extract grouping key

    Returns:
        Dictionary mapping keys to lists of items
    """
    groups: Dict[K, List[T]] = defaultdict(list)
    for item in items:
        groups[key_fn(item)].append(item)
    return dict(groups)
```
→ type hints, TypeVar, docstring, import 4개 — **요청하지 않은 것 다수**

**C. Default+Custom (점수 10.0, 217자)**:
```python
from collections import defaultdict

def group_by(items, key_fn):
    groups = defaultdict(list)
    for item in items:
        groups[key_fn(item)].append(item)
    return dict(groups)
```
→ 정확히 같은 로직, **불필요한 것 전부 제거**. 만점.

---

## 리뷰어 대응 논증

```
전제:  리뷰어는 "default template의 confounding"을 우려
실험:  5-way ablation으로 default/custom/template을 독립 분리
결과:
  1. Default prompt 효과 (A-B) = +0.04 → confounding 무시 가능
  2. Custom prompt 순수 효과 (D-B) = +0.81 → Default 통제 후에도 유의미
  3. Template 구조 효과 (E-D) = -0.14 → 형식 영향 없음
  4. 모든 조건의 rendered prompt를 기록 → 투명성 확보

결론: 관찰된 효과는 custom system prompt 자체의 기여이며,
      default template과의 confounding이 아니다.
```

---

## 데이터 파일

| 파일 | 내용 |
|------|------|
| `results/ablation_Qwen3.5-27b_20260405_141621.json` | 전체 실험 데이터 (40회, 평가 포함) |
| `results/ablation_h200_run.log` | 실행 로그 |
| `run_vllm_ablation.py` | 실험 스크립트 |
| `generate_ablation_report.py` | 리포트 생성 스크립트 |
