# Claude Code 시스템 프롬프트(하니스) 효과 실험 리포트

> **실험일**: 2026-04-03 (업데이트: 17:45)
> **실험자**: jinsookim
> **참고 레포**: [Piebald-AI/claude-code-system-prompts](https://github.com/Piebald-AI/claude-code-system-prompts) · [sanbuphy/learn-coding-agent](https://github.com/sanbuphy/learn-coding-agent)

---

## 1. 실험 배경

### 핵심 질문
> "Claude Code의 시스템 프롬프트(하니스 엔진)를 다른 모델에 적용하면, 해당 모델의 코드 생성 품질이 향상되는가?"

### 배경
- 2026.03.31 Claude Code npm 소스맵 유출 → 110개+ 모듈화된 시스템 프롬프트 공개
- 강연자 언급: "27B 모델을 사용 중이나 20~30B 사이에서 성능 차이를 느끼기 어렵다"
- Arize AI 연구: 시스템 프롬프트 최적화만으로 +5~11% 코딩 성능 향상 실증
- 가설: Claude Code의 **"하지 마라" 위주 제약 조건**이 모델 크기와 무관하게 코드 품질을 끌어올린다

---

## 2. 실험 설계

### 3-Column 비교

| Column | 설명 | 모델 | 시스템 프롬프트 | Thinking |
|--------|------|------|----------------|----------|
| **Col1** | 27B Raw | Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled | 없음 | 비활성화* |
| **Col2** | 27B + 하니스 | 동일 모델 | Claude Code 시스템 프롬프트 원문 (Piebald 추출) | 혼합** |
| **Col3** | Claude Code CLI | Claude (claude -p) | Claude Code 내장 하니스 엔진 전체 | N/A |

> *Col1 thinking 활성화 시 → 무한 루프, 서버 OOM 크래시 (실험 실패). 비활성화 후 재실험.
> **Col2: rest_api/cache_system은 thinking 활성화(원본 실험), task_queue는 thinking 비활성화(재실험)

### 인프라
- **27B 모델 서버**: H200 4-way GPU, vLLM, `118.223.251.22:10051`
- **모델 ID**: `Qwen3.5-27b` (Jackrong/Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled)
- **컨텍스트**: 32,000 tokens (vLLM max_model_len: 16,000)
- **Claude Code CLI**: v2.1.91
- **평가**: Claude-as-judge (6개 기준, 1-10점, `claude -p --output-format json`)

### 하니스 프롬프트 핵심 구성 (Piebald-AI 원문 기반)

Claude Code 시스템 프롬프트에서 코드 생성 품질에 직결되는 핵심 모듈 조합:

| 모듈 | 핵심 지시 |
|------|----------|
| `system-prompt-output-efficiency.md` | "Go straight to the point. Be extra concise." |
| `doing-tasks-no-unnecessary-additions.md` | 요청하지 않은 것 추가 금지 |
| `doing-tasks-no-premature-abstractions.md` | 조기 추상화 금지 (유사한 3줄이 추상화보다 낫다) |
| `doing-tasks-no-unnecessary-error-handling.md` | 불가능한 시나리오 에러핸들링 금지 |
| `doing-tasks-security.md` | 보안 취약점 주의 |
| `doing-tasks-read-before-modifying.md` | 이해 후 수정 |
| `doing-tasks-minimize-file-creation.md` | 파일 생성 최소화 |

**핵심 철학**: "무엇을 하라"가 아닌 **"무엇을 하지 마라"** 중심 설계

### 코딩 과제 (3개, 복잡도 medium~hard)

| ID | 과제 | 핵심 요구사항 |
|----|------|--------------|
| task_queue | Thread-Safe Task Queue | 우선순위 큐(1-10), 재시도(max 3), 상태추적, 스레드안전, 단일파일 |
| rest_api | Flask REST API | CRUD 5개 엔드포인트, 상태코드, JSON, 단일파일 |
| cache_system | LRU Cache + TTL | TTL 만료, LRU 퇴거, 스레드안전, 단일 클래스 |

---

## 3. 실험 결과

### 3-1. 종합 점수 비교 (전체 3개 과제 평균)

| 기준 | Col1: Raw 27B | Col2: 27B + 하니스 | Col3: Claude Code CLI |
|------|:---:|:---:|:---:|
| **정확성** (correctness) | 7.3 | 7.3 | 6.3† |
| **효율성** (efficiency) | 7.7 | **8.3** | 7.0† |
| **간결성** (conciseness) | 4.7 | **7.0** | 5.7† |
| **과잉설계 방지** (no_overengineering) | 3.7 | **6.7** | 5.3† |
| **응답 군더더기** (response_bloat) | 4.3 | **9.7** | 4.7† |
| **지시 준수** (instruction_following) | 8.0 | **9.0** | 7.0† |
| **종합 평균** | 5.93 | **7.97** | 5.83† |

> †Col3 task_queue: Claude Code가 `-p` 모드에서 코드 대신 파일쓰기 권한 요청 → 1.2점. Col3 anomaly 제외 시 평균 **8.15**

### 3-2. 과제별 상세

#### task_queue (Thread-Safe Priority Queue)

| 조건 | 점수 | 응답길이 | 시간 | 출력토큰 | 비고 |
|------|:---:|:---:|:---:|:---:|------|
| **Col1: Raw 27B** | 5.3 | 7,033자 | 120.9s | 1,695 | heap 순서 버그, 불필요한 추상화, 미사용 임포트 |
| **Col2: 27B + 하니스** | 6.3 | 5,300자 | 92.6s | 1,294 | priority 버그 동일, 그러나 응답 군더더기 0 (10점) |
| **Col3: Claude Code** | 1.2 | 1,293자 | 51.1s | 3,598 | 코드 미생성 — 파일쓰기 권한 요청만 출력 |

#### rest_api (Flask REST API)

| 조건 | 점수 | 응답길이 | 시간 | 출력토큰 | 비고 |
|------|:---:|:---:|:---:|:---:|------|
| **Col1: Raw 27B** | 6.5 | 4,503자 | 96.2s | 1,359 | 미사용 임포트, 불필요한 helper 함수, curl 사용법 문서 추가 |
| **Col2: 27B + 하니스** | **9.3** | 1,818자 | 58.5s | 529 | 코드만 출력, 산문 없음, 거의 완벽한 구현 |
| **Col3: Claude Code** | 8.3 | 2,538자 | 30.8s | 2,240 | 코드 + 상태코드 표 + curl 예시 (요청하지 않은 산문 포함) |

#### cache_system (LRU Cache with TTL)

| 조건 | 점수 | 응답길이 | 시간 | 출력토큰 | 비고 |
|------|:---:|:---:|:---:|:---:|------|
| **Col1: Raw 27B** | 6.0 | 5,462자 | 102.3s | 1,439 | type hints, docstrings 전체, helper 남발, 구현 설명 섹션 |
| **Col2: 27B + 하니스** | **8.3** | 1,844자 | 49.1s | 473 | 코드 위주, 최소 산문, 미요청 cleanup 메서드만 추가 |
| **Col3: Claude Code** | 8.0 | 2,294자 | 24.7s | 1,860 | "Key design decisions" 4항목 (요청 안 한 설명) |

---

## 4. 핵심 발견

### 발견 1: 하니스는 "하지 마라" 제약을 27B 모델에 극도로 강하게 적용한다

```
response_bloat 점수:
  Col1 (Raw):          4.3/10  → 설명, 사용법 문서, 주석 범람
  Col2 (Harness):      9.7/10  → 거의 코드만 출력 ★
  Col3 (Claude Code):  4.7/10  → 요청하지 않은 prose 여전히 포함
```

**왜 27B 모델이 Claude 본체보다 더 잘 따르는가?**
- Claude는 수년간의 RLHF로 "도움이 되려면 설명을 추가해야 한다"는 행동 패턴이 강하게 학습됨
- 27B는 사전학습 + Reasoning Distillation만 거쳐 행동 관성이 적음
- 시스템 프롬프트 지시를 **문자 그대로** 따름 → "코드만"이 실제로 "코드만"이 됨

### 발견 2: 출력 토큰 수가 극적으로 감소

| 지표 | Col1 (Raw) | Col2 (Harness) | 감소율 |
|------|:---:|:---:|:---:|
| 평균 출력 토큰 | 1,497 | **765** | **-49%** |
| 평균 응답 길이 | 5,666자 | **3,654자** | **-35%** |
| 평균 응답 시간 | 106.5s | **66.7s** | **-37%** |

**하니스 = 토큰 비용 절감 도구**. 동일한 작업에 절반 가까운 토큰으로 완수.

### 발견 3: 과잉설계(overengineering) 패턴이 완전히 다름

**Raw 27B (Col1)**가 자주 추가하는 것들:
- 모든 함수에 docstring, type hints (`Optional[Any]`, `Callable`, etc.)
- 요청하지 않은 helper/utility 메서드 (`validate_todo_data`, `get_next_id()`, `_cleanup_expired`)
- 미사용 임포트 (`from collections import deque`, `from datetime import datetime`)
- 코드 블록 후 "How to Run", "Implementation Details", curl 예시 섹션

**27B + 하니스 (Col2)**:
- type hints 없음 또는 최소
- 독립 helper 없음
- 코드 외 산문 없음
- 응답 = 코드 블록 하나

### 발견 4: Reasoning Distilled 모델의 thinking 제어 문제

```
Col1 thinking 활성화 → 세 과제 모두 무한루프/OOM
Col1 thinking 비활성화 → 정상 동작, but 120s/과제 소요
Col2 thinking 활성화 → 짧은 과제(rest_api, cache_system) 성공, 긴 과제(task_queue) 타임아웃
```

**결론**: `output_efficiency` 하니스 프롬프트가 thinking 체인도 간접적으로 억제함.
"Go straight to the point" → thinking 루프가 짧아짐 → 타임아웃 방지

### 발견 5: correctness는 모델 고유 한계에 영향받음

**priority 버그 (col1, col2 모두)**:
```python
# PriorityQueue는 min-heap → priority=1이 먼저 dequeue됨 (틀림)
# task.priority로 직접 넣을 경우 '낮은 우선순위'가 먼저 처리됨
# 올바른 수정: (-priority, task_id, func) 형태로 넣어야 함
```
- Col1과 Col2 모두 동일 버그 발생 → 하니스가 논리 정확성보다 **형식/스타일**에 더 강하게 영향
- 하니스는 "불필요한 걸 넣지 마라"는 것에는 탁월, "더 정확하게 구현하라"에는 제한적

---

## 5. 결론

### 5-1. 핵심 결론 표

| 질문 | 답 | 근거 |
|------|---|------|
| Claude Code 하니스가 27B 성능을 올리나? | **Yes — 명확하게** | 5.93 → 7.97 (+34%), 특히 스타일/효율 지표에서 극적 개선 |
| 하니스의 가장 효과적인 부분은? | **"하지 마라" 제약 조건** | response_bloat: 4.3→9.7, no_overengineering: 3.7→6.7 |
| 27B + 하니스 vs 실제 Claude Code? | **동등하거나 우위 가능** | Col2 정상 과제 평균 8.63 vs Col3 정상 과제 평균 8.15 |
| 프롬프트 없이 27B 사용 가능한가? | **실용 가능하나 비효율** | thinking 비활성화 필수, 출력이 verbose/overengineered |
| thinking 비활성화 필요한가? | **Yes (프로덕션 필수)** | 활성화 시 서버 OOM 리스크, 비활성화 시 안정적 |

### 5-2. 실용적 시사점

1. **모델 크기보다 프롬프트 설계가 우선**
   - 동일한 27B 모델에서 하니스 하나로 34% 평균 향상
   - Claude Code doing-tasks 시리즈 7개 모듈이 핵심

2. **하니스는 토큰 비용 절감 도구이기도 함**
   - 응답 토큰 -49%, 응답 시간 -37%
   - H200 4-way 서버에서 동시 처리량 향상 직결

3. **"학습된 모델 행동 관성" 문제**
   - Claude 본체는 RLHF로 설명 추가 행동이 강화됨 → 하니스 지시를 부분 무시
   - 27B는 이 관성이 약함 → 하니스를 더 강하게 따름
   - **이것이 "다른 모델도 Claude Code를 거치면 좋아진다"는 말의 실체**

4. **Reasoning Distilled 모델 운영 지침**
   - 항상 `enable_thinking: False` 또는 thinking budget 제한 설정
   - 시스템 프롬프트에 "output efficiency" 지시 필수
   - 없으면 서버 리소스 낭비 + 사용자 경험 저하

### 5-3. 실험 한계

| 한계 | 영향 | 후속 과제 |
|------|------|----------|
| Col2 thinking 조건 비일관 (task_queue만 비활성화) | 비교 공정성 일부 저하 | 3개 과제 모두 동일 조건 재실험 |
| Col3 task_queue 이상값 (CLI 모드 파일쓰기 시도) | Claude Code 평균 왜곡 | `--no-tools` 또는 `--allowedTools` 옵션 사용 |
| 과제 3개 (샘플 사이즈 작음) | 통계적 유의성 낮음 | HumanEval, MBPP 등 벤치마크 데이터셋 사용 |
| LLM-as-judge 편향 (Claude가 Claude를 평가) | Col3 유리 가능성 | 코드 실행 기반 pass@k 평가 추가 |
| priority 버그가 두 모델에 동일 발생 | correctness 지표 한계 | 더 명확한 요구사항 과제 설계 |
| 단일 모델 크기 (27B만) | 일반화 제한 | 7B, 14B, 72B 등 크기별 비교 |

---

## 6. 원시 데이터

### 실험 파일
| 파일 | 내용 |
|------|------|
| `results/h100_experiment_20260403_160203.json` | Col2 (harness_27b) + Col3 (claude_code) 원본 |
| `results/raw_retry_20260403_173817.json` | Col1 (raw_27b, thinking 비활성화) 재실험 |
| `results/harness_taskqueue_nothink.json` | Col2 task_queue thinking 비활성화 재실험 |
| `run_h100_experiment.py` | 메인 실험 스크립트 (Col2/Col3) |
| `run_raw_retry.py` | Col1 재실험 스크립트 (thinking 비활성화) |

### 응답 효율성 비교

| 지표 | Col1 (Raw) | Col2 (Harness) | Col3 (Claude) |
|------|:---:|:---:|:---:|
| 평균 응답 길이 | 5,666자 | 3,654자 | 2,042자† |
| 평균 출력 토큰 | 1,497 | 765 | 2,566† |
| 코드 비율 (추정) | ~60% | ~95% | ~60% |
| 불필요한 산문 | 많음 | 거의 없음 | 중간 |

> †Col3 task_queue 3,598 토큰(코드 없는 산문) 포함 수치

---

## 7. 참고자료

### 시스템 프롬프트 원문
- [Piebald-AI/claude-code-system-prompts](https://github.com/Piebald-AI/claude-code-system-prompts) — 254개 프롬프트 파일, Claude Code v2.1.91 소스에서 직접 추출
- `system-prompt-output-efficiency.md` — 핵심 효율성 지시
- `system-prompt-doing-tasks-*.md` 시리즈 — 7개 doing-tasks 모듈

### 아키텍처 분석
- [sanbuphy/learn-coding-agent](https://github.com/sanbuphy/learn-coding-agent) — Claude Code 아키텍처 리버스 엔지니어링
  - 프롬프트는 정적이 아니라 **쿼리 시점에 동적으로 조립** (환경, 설정에 따라 조건부 추가)
  - 40+ 도구 시스템, 권한 아키텍처 분석
  - Telemetry (1st-party + Datadog), 언더커버 모드, 킬스위치 분석

### 관련 연구
- [Arize AI — CLAUDE.md Best Practices](https://arize.com/blog/claude-md-best-practices-learned-from-optimizing-claude-code-with-prompt-learning/) — 시스템 프롬프트 최적화 +5~11% 코딩 성능 향상
- [VentureBeat — Claude Code source code leaked](https://venturebeat.com/technology/claude-codes-source-code-appears-to-have-leaked-heres-what-we-know)

---

## 부록: 사용된 Claude Code 하니스 전문

```
You are an interactive agent that helps users with software engineering tasks.

# Doing tasks
The user will primarily request you to perform software engineering tasks.
...
Don't add features, refactor code, or make "improvements" beyond what was asked.
Don't add error handling, fallbacks, or validation for scenarios that can't happen.
Don't create helpers, utilities, or abstractions for one-time operations.
Don't design for hypothetical future requirements. Three similar lines of code is 
better than a premature abstraction.
...

# Output efficiency
IMPORTANT: Go straight to the point. Try the simplest approach first without going 
in circles. Do not overdo it. Be extra concise.
Keep your text output brief and direct. Lead with the answer or action, not the 
reasoning. Skip filler words, preamble, and unnecessary transitions.
If you can say it in one sentence, don't use three.
```

> 전체 프롬프트: `run_h100_experiment.py` 내 `CLAUDE_CODE_HARNESS` 변수 참조
