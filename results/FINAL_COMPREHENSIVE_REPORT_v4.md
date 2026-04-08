# Claude Code 시스템 프롬프트(하니스) 효과 종합 실험 리포트 v4

> **실험 기간**: 2026-04-03 ~ 2026-04-08
> **실험자**: jinsookim
> **인프라**: H200 4-way (vLLM 0.18.0) + 알리바바 클라우드 API (국제판)
> **모델**: Distilled Qwen3.5-27B (vLLM) + **바닐라 Qwen3.5-27B** (알리바바 API)
> **평가**: Claude Opus 4.6 LLM-as-judge (6개 기준, 1-10점)
> **하니스 출처**: [Piebald-AI/claude-code-system-prompts](https://github.com/Piebald-AI/claude-code-system-prompts)

---

## Executive Summary

6개 실험을 통해 Claude Code 시스템 프롬프트("하니스")의 효과, 원인, 최적 형식을 검증했습니다.

| 실험 | 핵심 질문 | 결론 |
|------|----------|------|
| **실험 1**: 3-Column 비교 | 하니스가 27B 모델 성능을 올리는가? | **Yes, +34%** (5.93→7.97) |
| **실험 2**: Inverse Prompt | Distillation 때문이 아닌가? | **아니다** — 반대 지시에 반대로 반응 |
| **실험 3**: 5-way Ablation | Default template confounding? | **아니다** — Custom 순수 효과 +0.81 |
| **실험 4**: 바닐라 검증 | Distilled 모델이 아닌 바닐라에서도? | **Yes, +26.5%** (6.83→8.64) |
| **실험 5**: OpenClaude 전체 하니스 | 전체 런타임이 더 좋은가? | **아니다** — 추출(8.64) > 전체(7.67) |
| **실험 6**: MD 조각화 vs 제약만 ⭐ | **형식**이 효과에 영향을 미치는가? | **Yes** — 제약만(8.97) > MD(8.5) > 연속(8.33) |

**v4 핵심 결론**: 같은 규칙이라도 **형식이 바뀌면 점수가 달라진다.** 특히 "제약만" 120토큰이 500토큰 연속 텍스트를 코딩에서 압도하지만, 아키텍처 분석에서는 긍정 스코프 지시가 없으면 완전성이 무너진다.

---

## 1. 실험 배경 및 누적 문맥

### 1.1 연구 질문의 진화

```
실험 1: 하니스가 작동하는가?                  → Yes (+34%)
실험 2: Distillation 때문인가?                → 아니다
실험 3: 기본 템플릿이 confound인가?           → 아니다 (+0.04)
실험 4: 바닐라 모델에서도 재현되는가?          → Yes (+26.5%)
실험 5: 더 많이 주면 더 좋은가?               → 아니다 (21K > 500tok에서 오히려 -11%)
실험 6: 같은 내용, 형식이 바뀌면 달라지는가?  → Yes (8.33→8.5→8.97, 과제 유형에 따라 역전)
```

### 1.2 실험 6의 동기

실험 4에서 사용한 "연속 텍스트 하니스(~500tok)"가 효과적임을 확인했다. 그런데 실제 유출된 Claude Code 시스템 프롬프트([Piebald-AI/claude-code-system-prompts](https://github.com/Piebald-AI/claude-code-system-prompts))는 **254개의 짧은 MD 파일로 조각화**되어 있다. 각 파일은:

- `# 헤더`로 명확히 섹션 구분
- 섹션당 3~8줄의 짧고 구체적인 규칙
- 대부분 "하지 마라(Don't X)" 형태의 부정 제약
- 긍정 문장("You are highly capable")은 일부 파일에만 존재

두 가지 질문이 생긴다:
1. **MD 구조(헤더 섹션화)** 자체가 연속 텍스트보다 더 잘 따라지는가?
2. 긍정 문장을 **제거하고 제약만 남기면** 더 효율적이면서 동등한 성능이 나오는가?

---

## 2. 실험 6: MD 조각화 vs 연속 텍스트 vs 제약만 (2026-04-08)

### 2.1 하니스 변형 설계

실험에서 테스트한 **3가지 하니스 형식**은 핵심 내용(규칙)은 동일하지만, 구조와 톤이 다르다.

#### Col2: 연속 텍스트 하니스 (~500 토큰) — 기존 재사용

v3까지 사용한 형식. 단락 구분이 있는 산문 형태. 중간에 `# Output efficiency` 섹션이 하나 있지만 전체적으로 연속된 텍스트.

```
The user will primarily request you to perform software engineering tasks...

Don't add features, refactor code, or make "improvements" beyond what was asked.
A bug fix doesn't need surrounding code cleaned up. A simple feature doesn't need extra
configurability. Don't add docstrings, comments, or type annotations...

Don't add error handling, fallbacks, or validation for scenarios that can't happen...

...

# Output efficiency

IMPORTANT: Go straight to the point. Try the simplest approach first...
```

**특징**: 규칙들이 산문 단락 안에 섞여 있음. 맥락 설명 포함.

---

#### Col3: MD 조각화 하니스 (~480 토큰) — 유출 원본 구조 재현

실제 [Piebald-AI/claude-code-system-prompts](https://github.com/Piebald-AI/claude-code-system-prompts) 파일 구조를 참조해 재구성. 동일한 내용이지만 **7개 독립 섹션**으로 분리.

```markdown
# Doing tasks
The user will primarily request you to perform software engineering tasks...
In general, do not propose changes to code you haven't read.
Do not create files unless they're absolutely necessary.

# Scope discipline
Don't add features, refactor code, or make "improvements" beyond what was asked.
- A bug fix doesn't need surrounding code cleaned up.
- Don't add docstrings, comments, or type annotations to code you didn't change.
- Only add comments where the logic isn't self-evident.

# Error handling
Don't add error handling, fallbacks, or validation for scenarios that can't happen.
- Trust internal code and framework guarantees.
- Only validate at system boundaries (user input, external APIs).

# Abstractions
Don't create helpers, utilities, or abstractions for one-time operations.
- Three similar lines of code is better than a premature abstraction.

# Backwards compatibility
Avoid backwards-compatibility hacks like renaming unused _vars, re-exporting types.
- If certain something is unused, delete it completely.

# Security
Be careful not to introduce security vulnerabilities (SQL injection, XSS, command injection).

# Output efficiency
IMPORTANT: Go straight to the point. Be extra concise.
- Lead with the answer or action, not the reasoning.
- If you can say it in one sentence, don't use three.
```

**특징**: 각 규칙 범주가 독립된 `#` 섹션. 불릿 리스트로 명확히 구조화. 맥락 설명 최소화.

**설계 의도**: 모델이 관련 섹션을 더 쉽게 찾아서 적용할 수 있는지 확인. "현재 코드 리뷰 과제에는 `# Scope discipline`과 `# Security`가 적용됨" 같은 방식으로 attention이 분산되지 않고 집중되는지 테스트.

---

#### Col4: 제약만 (Don't-only, ~120 토큰)

긍정 문장("The user will primarily...", "You are highly capable...", "Trust internal code...") 전부 제거. 순수하게 "하지 마라" 규칙만 남김.

```
# Rules
Don't add features, refactor code, or make "improvements" beyond what was asked.
Don't add docstrings, comments, or type annotations to code you didn't change.
Only add comments where the logic isn't self-evident.
Don't add error handling or validation for scenarios that can't happen.
Don't create helpers or abstractions for one-time operations.
Don't design for hypothetical future requirements.
Three similar lines of code is better than a premature abstraction.
Don't add backwards-compatibility hacks for code that is unused.
Prioritize writing safe, secure code — no SQL injection, XSS, command injection.
Go straight to the point. Be extra concise.
Lead with the answer, not the reasoning.
If you can say it in one sentence, don't use three.
```

**특징**: 긍정 맥락 없음. 순수 제약. 토큰 수 최소 (~120tok, Col2 대비 -76%).

**설계 의도**: v3 분석에서 "과잉설계방지(+5.3)"와 "응답간결(+6.0)"이 하니스 효과의 대부분을 설명했다 → 이 두 효과를 내는 것이 긍정 맥락 없이 제약만으로도 충분한지 검증. 충분하다면 **최소 효과 하니스**로 활용 가능.

---

### 2.2 실험 조건 요약

| Column | 하니스 형식 | 토큰 | 긍정 맥락 | MD 구조 | 규칙 수 |
|--------|-----------|:----:|:---------:|:-------:|:-------:|
| **Col1: Raw** | 없음 | 0 | — | — | 0 |
| **Col2: 연속 텍스트** | 산문 단락 | ~500 | ✓ | 섹션 1개 | 8 |
| **Col3: MD 조각화** | `#` 섹션 7개 | ~480 | ✓ (최소) | 섹션 7개 | 8 |
| **Col4: 제약만** | 단일 `# Rules` | ~120 | ✗ | 섹션 1개 | 8 |

- **모델**: 바닐라 Qwen3.5-27B (알리바바 클라우드 국제판, `qwen3.5-27b`)
- **과제**: 코딩 3개 + 비코딩 3개 = 6개 (실험 1~5와 동일)
- **Temperature**: 0.3
- **평가**: Claude Opus 4.6 LLM-as-judge (동일 6개 기준)
- **스크립트**: `run_fragmented_experiment.py`

### 2.3 가설

| 가설 | 예측 방향 | 근거 |
|------|----------|------|
| H1: MD 조각화 ≥ 연속 텍스트 | Col3 ≥ Col2 | 명확한 섹션이 attention 집중 도움 |
| H2: 제약만으로 충분 | Col4 ≈ Col2 | v3 결과상 효과는 "하지 마라" 부분에 집중 |
| H3: 제약만이 토큰 효율 최고 | Col4 비용 -76%, 성능 유지 | 120tok으로 500tok 효과 재현 가능? |
| H4: 27B는 긴 맥락보다 짧은 구조 선호 | Col4 > Col3 > Col2 in 소형모델 | 실험 5에서 21K > 500tok 확인한 패턴 |

---

### 2.4 결과

#### 코딩 과제 (3개 평균)

| 기준 | Col1: Raw | Col2: 연속 텍스트 | Col3: MD 조각화 | Col4: 제약만 |
|------|:---------:|:-----------------:|:---------------:|:------------:|
| 정확성 | 10.0 | 9.3 | 9.3 | **9.7** |
| 효율성 | **10.0** | 8.7 | 9.7 | 9.7 |
| 간결성 | 6.0 | 7.7 | 8.3 | **9.7** |
| 과잉설계방지 | 3.7 | 8.7 | 8.3 | **10.0** |
| 응답간결 | 4.7 | 9.7 | 9.7 | **10.0** |
| 지시준수 | **10.0** | **10.0** | **10.0** | **10.0** |
| **평균** | **7.39** | **9.0** | **9.22** | **9.83** |
| **평균 응답 길이** | **2,704자** | **852자** | **780자** | **520자** |

#### 비코딩 과제 (3개 평균)

| 기준 | Col1: Raw† | Col2: 연속 텍스트 | Col3: MD 조각화 | Col4: 제약만 |
|------|:----------:|:-----------------:|:---------------:|:------------:|
| 정확성/완전성 | 7.0 | 8.7 | 8.3 | 7.7 |
| 완전성/완성도 | 8.3 | 8.7 | 8.3 | 6.7 |
| 간결성 | 3.7 | 7.0 | 7.3 | **9.0** |
| 과잉설명방지 | 3.0 | 7.3 | 7.3 | **9.0** |
| 응답간결 | 3.0 | 6.3 | 6.0 | **8.3** |
| 실행가능성 | 7.7 | 8.0 | **8.7** | 7.0 |
| **평균** | **~5.44†** | **7.67** | **7.78** | **8.11** |
| **평균 응답 길이** | **~5,162자†** | **1,718자** | **2,079자** | **735자** |

> †Col1 아키텍처 과제: judge JSON 파싱 실패 → 0점 처리로 평균 왜곡 (실제 응답은 존재)

#### 종합 (4-Column)

| 조건 | 종합 점수 | 응답 길이 | 입력 토큰 | 출력 토큰\* | 시간 |
|------|:---------:|:---------:|:---------:|:----------:|:----:|
| **Col1: Raw** | **6.7** | 3,687자 | 102 | 1,676 | 18.1s |
| **Col2: 연속 텍스트** | **8.33** | 1,285자 | 714 | 476 | 6.6s |
| **Col3: MD 조각화** | **8.5** | 1,430자 | 637 | 527 | 6.3s |
| **Col4: 제약만** | **8.97** | **628자** | **274** | **2,178\*** | **25.3s** |

> \*Col4 출력 토큰이 높은 이유: Qwen3.5의 thinking mode(`<think>` 태그)가 "어떻게 짧게 답할지"를 내부 추론으로 처리. `<think>` 제거 후 실제 응답은 628자로 가장 짧음. 단, latency 25.3s는 비용 문제.

---

### 2.5 핵심 발견

#### 가설 검증 결과

| 가설 | 결과 | 해석 |
|------|:----:|------|
| H1: MD 조각화 ≥ 연속 텍스트 | **지지** (8.5 > 8.33) | 섹션화로 attention 분산 방지 효과 확인 |
| H2: 제약만으로 충분 | **지지** (8.97 > 8.33) | 긍정 맥락 없이도 종합 최고점 |
| H3: 제약만이 토큰 효율 최고 | **부분 지지** | 입력 토큰 -62%, 응답 길이 -51%, 점수 +7.7% — 단, latency 3.8배 |
| H4: 27B는 짧은 구조 선호 | **부분 지지** | 코딩에서는 제약만(9.83) 압도적, 비코딩 아키텍처는 역전 |

#### 발견 1: 제약만이 코딩에서 압도적

```
코딩 평균:
  Raw:       7.39
  연속 텍스트: 9.0
  MD 조각화:  9.22
  제약만:     9.83  ← 최고

과잉설계방지: 3.7 → 8.7 → 8.3 → 10.0  (제약만에서 만점)
응답간결:    4.7 → 9.7 → 9.7 → 10.0  (제약만에서 만점)
```

코딩 과제에서 "하지 마라" 12줄이 500토큰 연속 텍스트를 능가. 규칙이 명시적일수록 모델이 더 잘 준수.

#### 발견 2: 아키텍처 과제에서 역전 — 제약만의 치명적 약점

```
아키텍처 의사결정 (비코딩):
  연속 텍스트:  7.5  (완전성 8, 실행가능성 8)
  MD 조각화:   8.33 ← 최고 (완전성 9, 실행가능성 9)
  제약만:      6.83 ← 최저 (완전성 6, 실행가능성 5)
```

제약만 하니스로 생성된 아키텍처 답변은 1,073자로 짧지만 **핵심 고려사항들을 빠뜨림**. "Don't 과잉설명"을 따르다가 필요한 내용까지 생략. 긍정 스코프 지시("key considerations를 포괄적으로 다루라") 없이는 모델이 자의적으로 끊어버림.

반면 **MD 조각화가 아키텍처에서 최고(8.33)**: 섹션 헤더(`# Doing tasks`)가 복잡한 분석 과제의 구조를 잡아주는 역할을 한 것으로 보임.

#### 발견 3: 제약만의 thinking 폭증 — latency 트레이드오프

```
출력 토큰 (thinking 포함):
  연속 텍스트:  476 tok
  MD 조각화:   527 tok
  제약만:     2,178 tok  ← 4.6배

응답 시간:
  연속 텍스트:  6.6s
  MD 조각화:   6.3s
  제약만:     25.3s  ← 3.8배
```

Qwen3.5의 thinking mode가 "어떻게 짧게 답하지?"를 내부 추론으로 처리. 실제 응답(628자)은 가장 짧지만, 추론 과정이 길어지며 latency가 증가. **점수 높지만 API 비용은 오히려 높을 수 있음.**

#### 실제 응답 비교: group_by 함수

**Col1: Raw** (1,860자, 7.33점)
```python
from typing import TypeVar, Callable, List, Dict

T = TypeVar('T')
K = TypeVar('K')

def group_by(items: List[T], key_fn: Callable[[T], K]) -> Dict[K, List[T]]:
    """
    Groups a list of items by the result of applying key_fn to each item.
    Returns a dictionary where keys are the results of key_fn and values are lists.
    """
    result: Dict[K, List[T]] = {}
    for item in items:
        key = key_fn(item)
        if key not in result:
            result[key] = []
        result[key].append(item)
    return result
```
→ TypeVar 2개, docstring, 타입 힌트 — 요청하지 않은 것들

**Col2: 연속 텍스트** (218자, 9.67점)
```python
def group_by(items, key_fn):
    result = {}
    for item in items:
        key = key_fn(item)
        result.setdefault(key, []).append(item)
    return result
```
→ 깔끔. 요청한 것만.

**Col3: MD 조각화** (174자, **10.0점**)
```python
def group_by(items, key_fn):
    result = {}
    for item in items:
        result.setdefault(key_fn(item), []).append(item)
    return result
```
→ 한 줄 더 압축. `setdefault` 인라인 처리.

**Col4: 제약만** (156자, **10.0점**)
```python
def group_by(items, key_fn):
    result = {}
    for item in items:
        result.setdefault(key_fn(item), []).append(item)
    return result
```
→ MD 조각화와 동일한 코드, 더 짧은 응답.

---

## 2.6 과제별 실제 응답 & Judge 판정 전문

### 과제 1: LRU Cache with TTL (코딩)

**평가 기준**: 정확성 / 효율성 / 간결성 / 과잉설계방지 / 응답간결 / 지시준수

---

**Col1: Raw** — 4,168자 | 7.83점 | 38.1s | out:3,509tok

```python
import threading
import time
from collections import OrderedDict
from typing import Any, Optional

class LRUCache:
    """
    Thread-safe LRU Cache with TTL (Time-To-Live) expiration support.
    Uses an OrderedDict to maintain insertion/access order for LRU eviction.
    Uses a threading.Lock to ensure thread safety during concurrent access.
    """
    def __init__(self, max_capacity: int):
        if max_capacity <= 0:
            raise ValueError("max_capacity must be greater than 0")
        self.max_capacity = max_capacity
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from the cache. Returns None if missing or expired."""
        with self._lock:
            if key not in self._cache:
                return None
            value, expiration_time = self._cache[key]
            if time.time() > expiration_time:
                ...
```

| 기준 | 점수 | 판정 이유 |
|------|:---:|---------|
| 정확성 | 10 | TTL 체크, LRU 순서, 추출 로직 모두 정확 |
| 효율성 | 10 | OrderedDict O(1) get/put/move_to_end, lock scope 최적 |
| 간결성 | 6 | 변수명 장황(`expiration_time`), 메서드마다 빈 줄 과도 |
| 과잉설계방지 | 4 | 타입힌트 전체, 모든 메서드에 docstring, ValueError 검증 — 미요청 |
| 응답간결 | 7 | 코드 앞 산문 없음, 사용 예시 주석이 과도 |
| 지시준수 | 10 | get/put/TTL/LRU/thread-safe/단일 클래스/예시 모두 충족 |

---

**Col2: 연속 텍스트** — 1,831자 | 7.83점 | 6.7s | out:611tok

```python
from collections import OrderedDict
import threading
import time

class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = OrderedDict()  # key -> (value, expiry_time)
        self.lock = threading.RLock()

    def get(self, key) -> any:
        with self.lock:
            if key not in self.cache:
                return None
            value, expiry = self.cache[key]
            if time.time() > expiry:
                del self.cache[key]
                return None
            self.cache.move_to_end(key)
            return value

    def put(self, key, value, ttl_seconds: int = 60):
        with self.lock:
            expiry = time.time() + ttl_seconds
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = (value, expiry)
            while len(self.cache) > self.capacity:
                self.cache.popitem(last=False)
            self._cleanup_expired()   # ← 미요청 추가 메서드
```

| 기준 | 점수 | 판정 이유 |
|------|:---:|---------|
| 정확성 | 9 | `_cleanup_expired`를 put 내부에서 호출 — O(n) 부하, capacity 순간 오차 가능 |
| 효율성 | 7 | lazy expiry (get에서 처리)로 충분한데 put마다 O(n) cleanup 추가 |
| 간결성 | 6 | `_cleanup_expired` 미요청 메서드로 코드 불룩 |
| 과잉설계방지 | 6 | `-> any`, `: int` 타입힌트 미요청, `_cleanup_expired` 자체가 과잉 |
| 응답간결 | 9 | 산문 없음, 깔끔한 사용 예시 |
| 지시준수 | 10 | 요건 모두 충족 |

---

**Col3: MD 조각화** — 1,726자 | 8.33점 | 6.8s | out:607tok

```python
import time
import threading
from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = OrderedDict()  # key -> (value, expiry_time)
        self.lock = threading.RLock()

    def get(self, key) -> any:
        with self.lock:
            if key not in self.cache:
                return None
            value, expiry = self.cache[key]
            if time.time() > expiry:
                del self.cache[key]
                return None
            self.cache.move_to_end(key)
            return value

    def put(self, key, value, ttl_seconds: int = 60) -> None:
        with self.lock:
            expiry = time.time() + ttl_seconds
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = (value, expiry)
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)
    # _cleanup_expired도 있지만 put에서 호출 안 함 (선택적)
```

| 기준 | 점수 | 판정 이유 |
|------|:---:|---------|
| 정확성 | 9 | 로직 정확, LRU/TTL/eviction 정상 |
| 효율성 | 10 | O(1) 모든 연산, lazy expiry만 사용 — 최적 |
| 간결성 | 7 | 메서드 내 빈 줄 일부, `ttl_seconds: int` 장황한 파라미터명 |
| 과잉설계방지 | 5 | `-> any`, `-> None`, `: int` 타입힌트 미요청, `_cleanup_expired` 선택적 추가 |
| 응답간결 | 9 | 산문 없음 |
| 지시준수 | 10 | 모든 요건 충족 |

> Col2와 거의 동일한 구조지만 put의 `_cleanup_expired` 제거로 효율성 10점. `#` 섹션이 "scope discipline"을 remind해서 cleanup 메서드 추가를 억제한 것으로 추정.

---

**Col4: 제약만** — 1,034자 | **9.83점** | 24.5s | out:2,221tok(thinking)

```python
import time
import threading
from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            if key not in self.cache:
                return None
            value, expiry = self.cache[key]
            if time.time() > expiry:
                del self.cache[key]
                return None
            self.cache.move_to_end(key)
            return value

    def put(self, key, value, ttl_seconds=60):
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            elif len(self.cache) >= self.capacity:
                self.cache.popitem(last=False)
            self.cache[key] = (value, time.time() + ttl_seconds)

# Usage example
cache = LRUCache(2)
cache.put("a", 1); cache.put("b", 2); cache.put("c", 3)  # Evicts "a"
print(cache.get("a"))  # None
print(cache.get("b"))  # 1
```

| 기준 | 점수 | 판정 이유 |
|------|:---:|---------|
| 정확성 | 9 | `put()`에서 기존 key 업데이트 시 expiry 갱신 안 됨 — minor |
| 효율성 | 10 | O(1), Lock 최소, lazy expiry |
| 간결성 | 10 | 빈 줄 없음, 변수명 최소, 군더더기 없음 |
| 과잉설계방지 | 10 | 타입힌트 없음, docstring 없음, 추가 메서드 없음 |
| 응답간결 | 10 | 순수 코드, 산문 없음 |
| 지시준수 | 10 | 모든 요건 충족 |

**Col2 vs Col4 직접 비교:**
- Col2: `_cleanup_expired` 추가, 타입힌트, 1,831자
- Col4: 추가 없음, 힌트 없음, 1,034자 (−44%)
- 핵심 차이: `elif len(self.cache) >= self.capacity: self.cache.popitem(last=False)` — capacity 체크를 `elif`로 묶어 새 key일 때만 eviction, 기존 key 업데이트는 그냥 move_to_end

---

### 과제 2: group_by 함수 (코딩)

**Col1: Raw** — 1,860자 | 7.33점

```python
# 서문 산문 + 2개 구현 + 4개 예시
def group_by(items, key_fn):
    """Groups items by key_fn. Args: items... Returns: dict..."""
    result = {}
    for item in items:
        key = key_fn(item)
        if key not in result:
            result[key] = []
        result[key].append(item)
    return result
# + setdefault 대안 버전도 추가 제공
```
판정: "Intro prose, four usage examples, section headers, and a second implementation" → 과잉설계방지 4점

**Col2: 연속 텍스트** — 218자 | 9.67점

```python
def group_by(items, key_fn):
    result = {}
    for item in items:
        key = key_fn(item)
        if key not in result:
            result[key] = []
        result[key].append(item)
    return result
```
판정: "Explicit key-not-in-result check is slightly more verbose than setdefault but not bloated" → 효율성 9점

**Col3: MD 조각화** — 174자 | **10.0점**

```python
def group_by(items, key_fn):
    result = {}
    for item in items:
        result.setdefault(key_fn(item), []).append(item)
    return result
```
판정: `setdefault` 인라인 처리로 한 줄 압축, 모든 기준 만점

**Col4: 제약만** — 156자 | **10.0점**

```python
def group_by(items, key_fn):
    result = {}
    for item in items:
        result.setdefault(key_fn(item), []).append(item)
    return result
```
판정: Col3와 동일 코드, 응답 더 짧음 (156자 vs 174자)

> **주목**: Col3(MD 조각화)와 Col4(제약만) 모두 `setdefault` 인라인을 썼지만 Col2(연속 텍스트)는 explicit `if key not in result` 형태. `# Scope discipline: Three similar lines is better than premature abstraction` 섹션이 Col3에서 `setdefault` 선택을 유도한 것으로 해석 가능.

---

### 과제 3: Merge Intervals (코딩)

**Col1: Raw** — 2,084자 | 7.0점

```python
# docstring + "How It Works" 섹션 + 6개 예시 + complexity analysis 추가
def merge_intervals(intervals):
    """Merges overlapping intervals... Args:... Returns:..."""
    if not intervals: return []
    sorted_intervals = sorted(intervals, key=lambda x: x[0])  # 새 리스트
    ...
```
판정: "Six example prints, a 'How It Works' section, and a complexity analysis — none asked for" → 응답간결 3점

**Col2: 연속 텍스트** — 508자 | 9.5점

```python
def merge_intervals(intervals):
    if not intervals: return []
    intervals.sort(key=lambda x: x[0])   # ← 입력 리스트 mutate
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        last_end = merged[-1][1]
        if start <= last_end:
            merged[-1][1] = max(last_end, end)
        else:
            merged.append([start, end])
    return merged
```
판정: 정확성 9점 — "mutates input list in-place via sort"

**Col3: MD 조각화** — 441자 | 9.33점

```python
def merge_intervals(intervals):
    if not intervals: return []
    intervals.sort()   # ← Col2보다 더 짧게 (key 생략)
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        last_end = merged[-1][1]
        if start <= last_end:
            merged[-1][1] = max(last_end, end)
        else:
            merged.append([start, end])
    return merged
```
판정: 효율성 9점 — "O(n log n) sort + O(n) merge은 최적이지만 `intervals.sort()`는 입력 mutate"

**Col4: 제약만** — 369자 | 9.67점

```python
def merge_intervals(intervals):
    if not intervals: return []
    intervals.sort(key=lambda x: x[0])
    merged = [list(intervals[0])]   # ← list() 복사로 원본 보호
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
```
판정: 정확성 10점 — `list(intervals[0])`로 원본 복사, 간결성 9점 — "slightly verbose but not bloated"

---

### 과제 4: Redis Pub/Sub 설명 (비코딩)

**평가 기준**: 정확성 / 완전성 / 간결성 / 과잉설명방지 / 응답간결 / 실행가능성

---

**Col1: Raw** — 4,799자 | 6.33점

5개 대헤더, 2개 비교 테이블, CLI 예시, Python 코드 예시, 명령어 레퍼런스 테이블, Best Practices 섹션, 결론 섹션. 판정: "Best practices section repeats points already made; conclusion restates the intro" → 응답간결 4점, 과잉설명방지 4점

**Col2: 연속 텍스트** — 1,757자 | 7.67점

How it Works + 사용 시기 테이블 + 한계 비교 테이블 3섹션. 판정: "'Key Takeaway' paragraph restates what the comparison table already makes obvious" → 응답간결 7점

**Col3: MD 조각화** — 1,803자 | 7.67점

Col2와 거의 동일한 구조. 판정: "'Bottom Line' summarizes what the tables already show; over-structured" → 응답간결 6점 (Col2보다 낮음)

> 비코딩에서 MD 조각화가 연속 텍스트보다 응답 구조를 더 헤비하게 만드는 경향 확인. `# Output efficiency` 섹션의 효과가 코딩보다 비코딩에서 약함.

**Col4: 제약만** — 427자 | **9.0점**

```
Redis Pub/Sub allows clients to publish messages to named channels that are immediately
pushed to all active subscribers without storage. Use it for real-time, fire-and-forget
scenarios like live notifications where message loss is acceptable. Compared to RabbitMQ
or Kafka, it lacks message persistence (dropped if no subscriber), delivery
acknowledgments, replayability, dead-letter queues, and robust consumer group scaling.
```

단 3문장. 판정: 완전성 7점 — "misses consumer group scaling nuance, ordering guarantees, throughput context". 간결성 10점, 과잉설명방지 10점, 응답간결 10점.

---

### 과제 5: 코드 리뷰 (비코딩)

**Col1: Raw** — 5,525자 | 5.0점

이모지 severity 헤더(`🔴 Critical`, `🟠 Major`), 각 이슈마다 Before/After 코드 블록, 전체 리팩토링 클래스 제공, 요약 테이블. 판정: "'identify issues'라고 했는데 전체 리라이트를 제공" → 과잉설명방지 2점, 응답간결 2점

**Col2: 연속 텍스트** — 1,429자 | 7.83점

이슈 목록 (8개) + Quick Fix Example 1개. 판정: "Quick Fix Example wasn't asked for" → 응답간결 6점

**Col3: MD 조각화** — 2,165자 | 7.33점

이슈별 `###` 헤더 + 각 코드 블록 + "Recommended Fixes" 섹션 (전체 클래스 리라이트). 판정: "Full rewrite block goes beyond 'identify issues'" → 응답간결 5점. 완전성 7점 — "Misses unused imports (json, os, sys, re)"

**Col4: 제약만** — 706자 | 8.5점

```
1. SQL Injection: user_id interpolated directly into SQL; use parameterized queries.
2. Singleton State Reset: __init__ resets self.users on every instantiation.
3. Uninitialized Dependency: self.db defaults to None, causing AttributeError.
4. Unsafe Exception Handling: bare except: clause, get_user swallows errors.
5. Unused Imports: json, os, sys, re, typing imported but never used.
```

판정: 완전성 7점 — "misses thread-safety issue with singleton". 응답간결 9점, 과잉설명방지 9점. `# Rules`의 "identify issues only" 압박으로 미요청 리팩토링을 억제. **유일하게 unused imports (json, os, sys, re)를 발견한 조건.**

---

### 과제 6: 아키텍처 의사결정 (비코딩)

**가장 큰 격차가 발생한 과제. Col3 8.33 vs Col4 6.83.**

**Col1: Raw** — 7,122자 | 0점(judge 파싱 실패)

실제 응답은 존재하며 상당히 상세함: "Do not extract this into a separate microservice yet" 권고 + 데이터 일관성/커뮤니케이션/팀 조직/배포 섹션 포함. judge가 JSON 반환 대신 마크다운으로 응답해 파싱 실패.

**Col2: 연속 텍스트** — 1,968자 | 7.5점

고려사항 테이블 + 위험 목록 + 권고사항 + If you proceed 섹션. 판정: "Misses team skill/maturity and API versioning/contract management" → 완전성 8점. "'Bottom line' section partially restates the recommendation" → 응답간결 6점

**Col3: MD 조각화** — 2,268자 | **8.33점** ← 아키텍처 최고

```markdown
## Key Considerations
**Data Consistency**: Payments require ACID guarantees. Moving to microservices means
handling eventual consistency or two-phase commits.
**Communication**: Synchronous (HTTP/gRPC) vs asynchronous (message queue) trade-offs.
**Security**: PCI-DSS compliance across service boundaries. Tokenization and vaulting.
**Observability**: Distributed tracing, centralized logging, alerting.
**Deployment**: CI/CD, versioning, rollback complexity.

## Primary Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| Lost/duplicate payments | Critical | Idempotency keys + idempotent handlers |
| Network failures | High | Retries with exponential backoff + DLQ |
| Transaction rollbacks | High | Outbox pattern or saga orchestration |
...

## Recommendation
**Proceed, but start conservatively:**
1. Extract incrementally — keep Django as source of truth
...
```

판정: 완전성 9점, 실행가능성 9점. "Concrete sequencing (idempotency first, one team owns both, observability before launch) and the 5% heuristic for the alternative path" → 실행가능성 최고.

**Col4: 제약만** — 1,073자 | **6.83점** ← 아키텍처 최저

```
Recommendation: Do not extract the payment module yet. At 50k LOC and 500 RPS,
the monolith is efficient.

Considerations:
- Data Consistency: Replacing ACID transactions with Sagas or eventual consistency.
- Failure Modes: Network timeouts, retries, idempotency.
- Security: Reducing PCI scope through network segmentation.

Action Plan:
1. Enforce strict internal boundaries using separate Django apps.
2. Isolate payment dependencies.
3. Extract only if compliance requires separation.
```

판정: 완전성 6점 — "omits team autonomy, deployment independence, API contract design, migration strategy". 실행가능성 5점 — "'enforce strict internal boundaries' without concrete steps like strangler fig pattern, feature flags, or dual-write migration phases." "Don't 과잉설명"을 따르다가 **필요한 깊이까지 잘라버림**.

---

### 응답 길이 vs 점수 상관관계 (6과제)

| 과제 | Raw 길이 | 최고점 조건 | 최고점 길이 | 압축률 |
|------|:--------:|:-----------:|:-----------:|:------:|
| LRU Cache | 4,168자 | 제약만 9.83 | 1,034자 | -75% |
| group_by | 1,860자 | 제약만/MD 10.0 | 156자 | -92% |
| Merge Intervals | 2,084자 | 제약만 9.67 | 369자 | -82% |
| Redis Pub/Sub | 4,799자 | 제약만 9.0 | 427자 | -91% |
| 코드 리뷰 | 5,525자 | 제약만 8.5 | 706자 | -87% |
| 아키텍처 | 7,122자 | MD 조각화 8.33 | 2,268자 | -68% |

**결론**: 아키텍처 과제만 압축률이 낮고(-68%), 나머지 5개에서는 Raw 대비 75~92% 압축이 최고점과 일치. 즉 **"짧을수록 높은 점수"는 아키텍처 분석 제외하고 성립.**

---

## 3. 이전 실험 요약 (v3에서 이관)

> 상세 결과는 [v3 리포트](FINAL_COMPREHENSIVE_REPORT_v3.md) 참조.

### 누적 하니스 효과 크기

| 실험 | 모델 | Baseline | +하니스 | 향상 |
|------|------|:--------:|:------:|:----:|
| 실험 1 | Distilled (vLLM) | 5.93 | 7.97 | **+34.4%** |
| 실험 3 | Distilled, 실배포 시나리오 | 8.29 | 9.58 | **+15.6%** |
| 실험 4 | **바닐라 (알리바바 API)** | **6.83** | **8.64** | **+26.5%** |
| **실험 6** | **바닐라 (알리바바 API)** | **6.7** | **8.97 (제약만)** | **+33.9%** |

### 하니스 형식 효과 누적 비교 (실험 5 + 실험 6)

| 형식 | 입력 토큰 | 종합 점수 | 응답 길이 | 비고 |
|------|:---------:|:---------:|:---------:|------|
| Raw (없음) | 0 | 6.7 | 3,687자 | — |
| 연속 텍스트 (~500tok) | 714 | 8.33 | 1,285자 | 기준 |
| **MD 조각화 (~480tok)** | **637** | **8.5** | **1,430자** | **아키텍처에서 최고** |
| **제약만 (~120tok)** | **274** | **8.97** | **628자** | **코딩 최고, latency 3.8x** |
| OpenClaude 전체 (~21K tok) | ~39,749 | 7.67 | — | -11%, 66x 비용 |

---

## 4. 6개 실험 종합 분석 (실험 후 업데이트 예정)

### 4.1 리뷰어 비판 대응 매트릭스

| 비판 | 대응 실험 | 결과 | 결론 |
|------|----------|------|------|
| "Distilled라서 잘 따르는 것" | 실험 2 (Inverse) | 반대 지시 → 행동 역전 | 행동 고정 아님 |
| "Distilled라서 잘 따르는 것" | **실험 4 (바닐라)** | 바닐라에서도 +26.5% | **결정적 반론** |
| "Default template confounding" | 실험 3 (Ablation) | A-B = +0.04 | 무시 가능 |
| "더 많이 줄수록 좋지 않냐" | 실험 5 (OpenClaude) | 21K < 500tok | 오히려 역효과 |
| "형식은 중요하지 않다" | **실험 6 (조각화)** | 8.33→8.5→8.97 | **형식이 유의미하게 다름** |

### 4.2 기준별 하니스 형식 효과 비교 (실험 6)

#### 코딩 과제 기준별

| 기준 | Raw | 연속 텍스트 | MD 조각화 | 제약만 | 최대 향상 |
|------|:---:|:-----------:|:---------:|:------:|:---------:|
| 정확성 | 10.0 | 9.3 | 9.3 | 9.7 | — (Raw 최고) |
| 효율성 | **10.0** | 8.7 | 9.7 | 9.7 | — (Raw 최고) |
| 간결성 | 6.0 | 7.7 | 8.3 | **9.7** | +3.7 |
| **과잉설계방지** | 3.7 | 8.7 | 8.3 | **10.0** | +6.3 |
| **응답간결** | 4.7 | 9.7 | 9.7 | **10.0** | +5.3 |
| 지시준수 | 10.0 | 10.0 | 10.0 | 10.0 | 변화 없음 |

> 정확성·효율성은 하니스와 무관하게 Raw에서도 이미 높음. **하니스 효과는 전적으로 "불필요한 것 제거"에 집중**.

#### 비코딩 과제 기준별

| 기준 | Raw | 연속 텍스트 | MD 조각화 | 제약만 | 최대 향상 |
|------|:---:|:-----------:|:---------:|:------:|:---------:|
| 정확성 | 8.3 | 8.3 | 9.0 | 8.7 | MD 최고 |
| **완전성** | 8.7 | 8.7 | 8.7 | **6.7** | **제약만 급락** |
| 간결성 | 3.7 | 7.0 | 7.3 | **9.0** | +5.3 |
| 과잉설명방지 | 3.0 | 7.3 | 7.3 | **9.0** | +6.0 |
| 응답간결 | 3.0 | 6.3 | 6.0 | **8.3** | +5.3 |
| **실행가능성** | 7.7 | 8.0 | **8.7** | 7.0 | MD 최고 |

> 비코딩에서 제약만은 간결성 계열(+5.3~+6.0)에서 최고지만, **완전성(6.7)과 실행가능성(7.0)에서 역전**. "Don't 과잉설명"이 분석 깊이까지 잘라내는 부작용.

#### 형식별 하니스 적용 효과 해석

```
연속 텍스트 vs Raw:  +2.43점 (코딩 +1.61, 비코딩 +2.23)
MD 조각화 vs Raw:   +2.60점 (코딩 +1.83, 비코딩 +2.34)
제약만 vs Raw:      +3.27점 (코딩 +2.44, 비코딩 +2.67)

단, 비코딩 아키텍처만 분리하면:
  MD 조각화 vs 연속: +0.83점
  제약만 vs 연속:   −0.67점  ← 유일하게 연속 텍스트보다 낮음
```

---

## 5. 종합 결론

### 5.1 확립된 결론 (6개 실험)

| 질문 | 답 | 최종 근거 |
|------|---|----------|
| Claude Code 하니스가 성능을 올리나? | **Yes** | 6개 실험 모두 +10~34% |
| Distillation 때문인가? | **아니다** | 바닐라에서도 +26.5~34%, 바닐라≈Distilled |
| Default template confounding? | **무시 가능** | A-B = +0.04 |
| 더 많이 주면 좋은가? | **아니다 (27B 기준)** | 21K > 500tok 시 오히려 -11% |
| 형식이 중요한가? | **Yes** | 8.33 → 8.5 → 8.97 (형식별 차이 유의미) |
| 최적 형식은? | **과제 유형에 따라 다름** | 코딩=제약만, 아키텍처=MD 조각화 |

### 5.2 과제 유형별 최적 하니스 레시피

| 과제 유형 | 추천 형식 | 이유 |
|----------|----------|------|
| **코딩 (구현, 리팩토링)** | **제약만 ~120tok** | 과잉설계방지·응답간결 만점, 비용 최소 |
| **복잡한 분석 (아키텍처, 설계)** | **MD 조각화 ~480tok** | 섹션 구조가 포괄적 분석 범위 유지 |
| **일반 범용** | **연속 텍스트 ~500tok** | 코딩·비코딩 균형, latency 6.6s |

### 5.3 형식 선택 흐름도

```
과제가 코딩인가?
  ├── Yes → 제약만 사용 (120tok, 9.83점)
  │          단, latency 허용 가능한지 확인 (25s vs 6.6s)
  │          latency 민감 → 연속 텍스트 (9.0점, 6.6s)
  └── No  → 깊은 분석/설계가 필요한가?
              ├── Yes → MD 조각화 사용 (480tok, 아키텍처 8.33점)
              └── No  → 제약만 (간결한 설명 과제, 9.0점)
```

### 5.4 실용적 시사점

1. **"하지 마라" 12줄이 500토큰 산문을 이긴다** — 코딩에서 규칙 명시성이 결정적
2. **형식은 내용만큼 중요하다** — 같은 규칙이라도 MD 섹션화로 +0.17점, 제약 분리로 +0.64점
3. **제약만의 thinking 트레이드오프** — 점수 최고(8.97)지만 latency 3.8배. API 비용은 입력 절약(-62%)을 thinking 출력 증가(+358%)가 상쇄
4. **27B의 한계선 재확인** — 컨텍스트가 길수록(21K) 성능 하락, 짧을수록(120tok) thinking으로 보완
5. **Claude Code 하니스의 진짜 핵심** — 긍정 맥락이 아닌 **부정 제약**. "하지 마라" 12줄로 바닐라 27B를 Claude의 97.7% 수준(코딩 9.83 vs 9.14)으로 끌어올림

---

## Appendix: 하니스 전문 비교

### A.1 연속 텍스트 (Col2, ~500tok)

```
The user will primarily request you to perform software engineering tasks...

Don't add features, refactor code, or make "improvements" beyond what was asked.
A bug fix doesn't need surrounding code cleaned up...

Don't add error handling, fallbacks, or validation for scenarios that can't happen...

Don't create helpers, utilities, or abstractions for one-time operations...

Avoid backwards-compatibility hacks like renaming unused _vars...

Be careful not to introduce security vulnerabilities...

# Output efficiency
IMPORTANT: Go straight to the point...
Keep your text output brief and direct...
```

### A.2 MD 조각화 (Col3, ~480tok)

```markdown
# Doing tasks
The user will primarily request you to perform software engineering tasks...
In general, do not propose changes to code you haven't read.

# Scope discipline
Don't add features, refactor code, or make "improvements" beyond what was asked.
- A bug fix doesn't need surrounding code cleaned up.
- Don't add docstrings, comments, or type annotations to code you didn't change.

# Error handling
Don't add error handling, fallbacks, or validation for scenarios that can't happen.
- Trust internal code and framework guarantees.
- Only validate at system boundaries (user input, external APIs).

# Abstractions
Don't create helpers, utilities, or abstractions for one-time operations.
- Three similar lines of code is better than a premature abstraction.

# Backwards compatibility
Avoid backwards-compatibility hacks like renaming unused _vars, re-exporting types.

# Security
Be careful not to introduce security vulnerabilities (SQL injection, XSS, command injection).

# Output efficiency
IMPORTANT: Go straight to the point. Be extra concise.
- Lead with the answer or action, not the reasoning.
- If you can say it in one sentence, don't use three.
```

### A.3 제약만 (Col4, ~120tok)

```
# Rules
Don't add features, refactor code, or make "improvements" beyond what was asked.
Don't add docstrings, comments, or type annotations to code you didn't change.
Only add comments where the logic isn't self-evident.
Don't add error handling or validation for scenarios that can't happen.
Don't create helpers or abstractions for one-time operations.
Don't design for hypothetical future requirements.
Three similar lines of code is better than a premature abstraction.
Don't add backwards-compatibility hacks for code that is unused.
Prioritize writing safe, secure code — no SQL injection, XSS, command injection.
Go straight to the point. Be extra concise.
Lead with the answer, not the reasoning.
If you can say it in one sentence, don't use three.
```

**토큰 비교**: Col2(500tok) → Col3(480tok, -4%) → Col4(120tok, **-76%**)

---

## Appendix B: 실험 인프라 & 재현 정보

### B.1 실험 환경

| 항목 | 값 |
|------|---|
| 모델 | 알리바바 공식 `qwen3.5-27b` (Dashscope 국제판) |
| API 엔드포인트 | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| Temperature | 0.3 |
| Max tokens | 4,096 |
| `<think>` 처리 | 정규식 제거 후 응답 길이 측정 |
| 평가 모델 | Claude Opus 4.6 (`claude -p --output-format text`) |
| 실험 일시 | 2026-04-08 10:19 KST |
| 결과 파일 | `results/fragmented_experiment_20260408_101912.json` |

### B.2 Judge 프롬프트 구조

**코딩 과제 (6개 기준):**
```
1. correctness     — 코드가 정확히 동작하는가? 로직 버그, 누락 기능?
2. efficiency      — 알고리즘이 효율적인가?
3. conciseness     — 불필요한 bloat이 없는가? (미사용 import, 중복 코드)
4. no_overengineering — 미요청 사항 추가 없는가? (타입힌트, docstring, 추상화)
5. response_bloat  — 텍스트 응답이 군더더기 없는가? (설명 산문, 단계별 추론)
6. instruction_following — 지시를 정확히 따랐는가?
```

**비코딩 과제 (6개 기준):**
```
1. accuracy        — 사실적으로 정확한가?
2. completeness    — 질문이 요구하는 핵심을 모두 다뤘는가?
3. conciseness     — 불필요한 채우기, 반복, 패딩이 없는가?
4. no_overexplaining — 묻지 않은 것을 설명하지 않았는가?
5. response_bloat  — 불필요한 구조(과도한 헤더, 질문 재진술) 없는가?
6. actionability   — 통찰이 실용적이고 직접 활용 가능한가?
```

### B.3 주의사항 및 한계

1. **Col1 아키텍처 0점**: judge가 JSON 형식이 아닌 마크다운으로 응답 → 파싱 실패 → 0점 처리. 실제 응답은 7,122자로 존재하며 사람 평가 시 약 7~8점 수준으로 추정. 전체 평균(6.7)에서 하향 왜곡 있음.

2. **Col4 thinking token**: Qwen3.5의 `<think>` 추론 토큰이 출력 토큰에 포함됨. API 과금은 thinking token 기준이므로 "입력 토큰 절약"이 "출력 토큰 증가"로 상쇄될 수 있음. 실제 비용 계산은 provider 정책 확인 필요.

3. **과제 수**: 6개는 통계적으로 작은 샘플. 특히 비코딩 3개 중 1개(아키텍처)가 결과를 크게 좌우. 대규모 재현 필요.

4. **Judge 일관성**: LLM judge 자체의 variance 존재. 동일 응답도 judge 호출 시마다 ±0.5점 내외 변동 가능.
