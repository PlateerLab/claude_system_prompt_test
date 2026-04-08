# harness-bench 매뉴얼

Claude Code 시스템 프롬프트(하니스)가 다른 모델의 성능에 미치는 영향을 측정하는 실험 프레임워크.

---

## 목차

1. [설치](#1-설치)
2. [빠른 시작](#2-빠른-시작)
3. [대시보드 사용법](#3-대시보드-사용법)
4. [CLI 사용법](#4-cli-사용법)
5. [커스터마이징](#5-커스터마이징)
   - [하니스(조건) 추가](#51-하니스조건-추가)
   - [과제 추가](#52-과제-추가)
   - [프로바이더·모델 추가](#53-프로바이더모델-추가)
6. [결과 파일 형식](#6-결과-파일-형식)
7. [평가 기준](#7-평가-기준)
8. [환경변수 레퍼런스](#8-환경변수-레퍼런스)
9. [트러블슈팅](#9-트러블슈팅)

---

## 1. 설치

### 요구사항

| 항목 | 버전 |
|------|------|
| Python | 3.10+ |
| Claude Code CLI | 최신 (`npm install -g @anthropic-ai/claude-code`) |
| API 키 | Alibaba Cloud DashScope 또는 OpenAI |

### 설치 순서

```bash
# 1. 레포 클론
git clone <repo-url>
cd harness-bench

# 2. Python 의존성 설치
pip install -r requirements.txt

# 3. API 키 설정
cp .env.example .env
# .env 파일을 열어 키 입력

# 4. Claude Code CLI 설치 & 로그인 (judge용)
npm install -g @anthropic-ai/claude-code
claude   # 로그인
```

### .env 예시

```bash
# Alibaba Cloud DashScope (Qwen 모델)
# https://dashscope.console.aliyun.com/apiKey 에서 발급
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# OpenAI (선택)
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 자체 vLLM (선택)
VLLM_BASE_URL=http://localhost:8000/v1
VLLM_MODEL=Qwen3.5-27b
```

---

## 2. 빠른 시작

### 대시보드로 실행 (권장)

```bash
python dashboard.py
```

브라우저가 자동으로 `http://localhost:5000` 열림.

### CLI로 실행

```bash
# 기본 (모든 조건 × 모든 과제)
python run.py

# 특정 조건만
python run.py --conditions raw restrictions_only

# 빠른 확인 (judge 없이)
python run.py --conditions raw continuous --tasks coding_group_by --no-judge
```

---

## 3. 대시보드 사용법

```bash
python dashboard.py
# → http://localhost:5000
```

### 화면 구성

```
┌─────────────────────────────────────────────────────┐
│  헤더: harness-bench               [상태 배지]       │
├──────────────────┬──────────────────────────────────┤
│                  │  탭: [실행 로그] [결과 히스토리]  │
│  사이드바         │                                  │
│  ├ 실험 조건     │  로그 영역                        │
│  ├ 과제          │  (실시간 스트리밍)                │
│  ├ 모델 설정     │                                  │
│  ├ Judge 설정    ├──────────────────────────────────┤
│  └ [실행] [중단] │  종합 점수 바                     │
└──────────────────┴──────────────────────────────────┘
```

### 사용 흐름

**1. 조건 선택** (왼쪽 상단)

실험할 하니스 조건을 체크박스로 선택합니다.

| 조건 | 설명 |
|------|------|
| `raw` | 시스템 프롬프트 없음 (baseline) |
| `continuous` | 연속 텍스트 하니스 (~500 토큰) |
| `fragmented` | `#` 헤더 7섹션 MD 구조 (~480 토큰) |
| `restrictions_only` | Don't 규칙 12줄만 (~120 토큰) |

**2. 과제 선택** (왼쪽 중단)

벤치마크 과제를 체크합니다. 버튼으로 전체선택/해제/코딩만/비코딩만 가능.

**3. 모델 설정**

- **프로바이더**: alibaba / openai / vllm / claude_cli
- **모델**: 비워두면 프로바이더 기본값 사용
- **Temperature**: 0~1 슬라이더 (기본 0.3)

**4. Judge 설정**

- **Judge 모델**: 평가에 사용할 Claude 모델 (기본: claude-opus-4-6)
- **Judge 없이 실행**: 체크하면 응답만 수집, 점수 계산 안 함

**5. ▶ 실험 실행**

- 로그 탭에서 실시간으로 진행 상황 확인
- 각 조건×과제마다 점수 즉시 표시
- 완료 후 하단에 종합 점수 바 표시

**6. 결과 히스토리 탭**

저장된 실험 결과 목록. 클릭하면 상세 모달 오픈:
- 과제별 / 조건별 응답 원문
- 6개 기준 점수 상세
- 응답 길이·시간·토큰 정보

---

## 4. CLI 사용법

```
python run.py [옵션]
```

### 주요 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--conditions KEY ...` | 전체 | 실험할 조건 키 |
| `--tasks ID ...` | 전체 | 실험할 과제 ID |
| `--provider NAME` | `alibaba` | API 프로바이더 |
| `--model NAME` | 프로바이더 기본값 | 모델명 |
| `--judge-model NAME` | `claude-opus-4-6` | judge 모델 |
| `--no-judge` | false | judge 없이 응답만 수집 |
| `--temperature FLOAT` | `0.3` | 샘플링 온도 |
| `--output PATH` | `results/run_TIMESTAMP.json` | 결과 저장 경로 |

### 목록 확인

```bash
python run.py --list-conditions   # 사용 가능한 조건
python run.py --list-tasks        # 사용 가능한 과제
python run.py --list-providers    # 사용 가능한 프로바이더
```

### 사용 예시

```bash
# 기본 전체 실험
python run.py

# 특정 조건 2개, 코딩 과제만, GPT-4o로
python run.py \
  --conditions raw restrictions_only \
  --tasks coding_lru_cache coding_group_by coding_merge_intervals \
  --provider openai \
  --model gpt-4o

# vLLM 자체 호스팅 모델로
python run.py \
  --provider vllm \
  --model Llama-3.1-8B-Instruct \
  --conditions raw continuous

# judge 없이 빠르게 응답만 수집
python run.py --no-judge --conditions restrictions_only

# 결과 파일 직접 지정
python run.py --output results/my_experiment.json
```

---

## 5. 커스터마이징

### 5.1 하니스(조건) 추가

`bench/harnesses.py`의 `CONDITIONS` dict에 항목 추가:

```python
CONDITIONS: dict[str, dict] = {
    # 기존 항목들...

    # 새 하니스 추가
    "my_harness": {
        "name": "My Custom Harness",
        "system": """
당신은 소프트웨어 엔지니어링 과제를 처리하는 AI입니다.

# 규칙
- 요청한 것만 구현하세요.
- 타입 힌트, docstring은 요청하지 않으면 추가하지 마세요.
- 간결하게 답하세요.
        """,
        "description": "한국어로 작성된 커스텀 하니스",
    },
}
```

그러면 바로 사용 가능:

```bash
python run.py --conditions raw my_harness
```

대시보드에서도 자동으로 목록에 표시됩니다.

---

### 5.2 과제 추가

`bench/tasks.py`의 `TASKS` 리스트에 항목 추가:

```python
TASKS: list[dict] = [
    # 기존 항목들...

    # 코딩 과제 추가
    {
        "id": "coding_fibonacci",
        "name": "Fibonacci (memo)",
        "category": "coding",
        "prompt": (
            "Write a Python function fib(n) that returns the nth Fibonacci number. "
            "Use memoization. No imports."
        ),
    },

    # 비코딩 과제 추가
    {
        "id": "non_coding_explain_gc",
        "name": "Garbage Collection 설명",
        "category": "non-coding",
        "prompt": (
            "Explain Python's garbage collection mechanism: "
            "reference counting, cycle detection, and generational GC. "
            "When does it cause performance issues?"
        ),
    },
]
```

- `category`는 반드시 `"coding"` 또는 `"non-coding"` 중 하나
- `id`는 `--tasks` 인자와 결과 JSON 키로 사용되므로 고유해야 함

---

### 5.3 프로바이더·모델 추가

`bench/providers.py`의 `PROVIDERS` dict에 항목 추가:

#### OpenAI 호환 엔드포인트 (가장 간단)

```python
PROVIDERS: dict[str, dict] = {
    # 기존 항목들...

    # Together AI
    "together": {
        "description": "Together AI (Llama, Mistral 등)",
        "default_model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "caller": _make_openai_caller(
            base_url="https://api.together.xyz/v1",
            api_key_env="TOGETHER_API_KEY",
            default_model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        ),
    },

    # Groq
    "groq": {
        "description": "Groq (매우 빠른 추론)",
        "default_model": "llama-3.1-8b-instant",
        "caller": _make_openai_caller(
            base_url="https://api.groq.com/openai/v1",
            api_key_env="GROQ_API_KEY",
            default_model="llama-3.1-8b-instant",
        ),
    },
}
```

`.env`에 키 추가:
```bash
TOGETHER_API_KEY=xxx
GROQ_API_KEY=xxx
```

#### vLLM 로컬 서버

```bash
# 서버 실행
vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000

# .env 설정
VLLM_BASE_URL=http://localhost:8000/v1
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct
```

```bash
python run.py --provider vllm
```

---

## 6. 결과 파일 형식

결과는 `results/run_TIMESTAMP.json`에 저장됩니다.

```json
{
  "meta": {
    "timestamp": "20260408_101912",
    "provider": "alibaba",
    "model": "qwen3.5-27b",
    "judge_model": "claude-opus-4-6",
    "temperature": 0.3,
    "conditions": {
      "raw": { "name": "Raw (no system prompt)", "description": "..." },
      "restrictions_only": { "name": "...", "description": "..." }
    }
  },
  "tasks": [
    {
      "id": "coding_group_by",
      "name": "group_by function",
      "category": "coding",
      "conditions": {
        "raw": {
          "response": "def group_by(items, key_fn):\n    ...",
          "response_length": 1860,
          "elapsed": 9.94,
          "input_tokens": 46,
          "output_tokens": 899,
          "evaluation": {
            "scores": {
              "correctness": 10,
              "efficiency": 10,
              "conciseness": 6,
              "no_overengineering": 4,
              "response_bloat": 4,
              "instruction_following": 10
            },
            "reasons": {
              "correctness": "Logic is correct...",
              "no_overengineering": "Full Google-style docstring not asked for..."
            },
            "average": 7.33
          }
        }
      }
    }
  ],
  "summary": {
    "raw": { "avg_score": 6.7 },
    "restrictions_only": { "avg_score": 8.97 }
  }
}
```

---

## 7. 평가 기준

### 코딩 과제 (6개 기준, 각 1-10점)

| 기준 | 설명 | 낮은 점수 예 |
|------|------|------------|
| `correctness` | 코드가 정확히 동작하는가? 로직 버그, 누락 기능? | 잘못된 알고리즘, 엣지케이스 미처리 |
| `efficiency` | 알고리즘이 효율적인가? | O(n²) 대신 O(n²) 쓸 필요 없는데 씀 |
| `conciseness` | 불필요한 코드가 없는가? | 미사용 import, 중복 변수, 과도한 빈 줄 |
| `no_overengineering` | 미요청 사항 추가가 없는가? | 타입 힌트, docstring, 추상 클래스 미요청 추가 |
| `response_bloat` | 텍스트 응답에 군더더기가 없는가? | 코드 앞 긴 설명, 단계별 추론 산문 |
| `instruction_following` | 지시를 정확히 따랐는가? | 요청한 함수명/시그니처 다름 |

### 비코딩 과제 (6개 기준, 각 1-10점)

| 기준 | 설명 | 낮은 점수 예 |
|------|------|------------|
| `accuracy` | 사실적으로 정확한가? | 틀린 기술 정보 |
| `completeness` | 질문의 핵심을 모두 다뤘는가? | 주요 포인트 누락 |
| `conciseness` | 불필요한 채우기가 없는가? | 반복, 패딩, 결론 재진술 |
| `no_overexplaining` | 묻지 않은 것을 설명하지 않았는가? | 이미 아는 기초 개념 설명 |
| `response_bloat` | 과도한 구조가 없는가? | 헤더 남발, 질문 재진술 |
| `actionability` | 통찰이 직접 활용 가능한가? | 막연한 조언 |

### 점수 해석

| 점수 | 의미 |
|------|------|
| 9-10 | 거의 완벽 |
| 7-8 | 양호, 소소한 문제 |
| 5-6 | 평균, 눈에 띄는 문제 |
| 3-4 | 미흡, 주요 문제 존재 |
| 1-2 | 불합격 수준 |

---

## 8. 환경변수 레퍼런스

| 변수 | 용도 | 필수 여부 |
|------|------|----------|
| `DASHSCOPE_API_KEY` | Alibaba Cloud DashScope (Qwen) | alibaba 프로바이더 사용 시 필수 |
| `OPENAI_API_KEY` | OpenAI API | openai 프로바이더 사용 시 필수 |
| `VLLM_BASE_URL` | vLLM 서버 주소 | vllm 프로바이더 사용 시 필수 |
| `VLLM_MODEL` | vLLM 모델명 | vllm 프로바이더 사용 시 (기본: `Qwen3.5-27b`) |
| `VLLM_API_KEY` | vLLM 인증 토큰 | vLLM에 `--api-key` 설정한 경우 |

---

## 9. 트러블슈팅

### judge가 작동하지 않아요

```
claude: command not found
```

Claude Code CLI가 설치되지 않았습니다:
```bash
npm install -g @anthropic-ai/claude-code
claude   # 로그인
```

또는 judge 없이 실행:
```bash
python run.py --no-judge
```

---

### API 키 오류

```
ERROR: {'message': "You didn't provide an API key..."}
```

`.env` 파일이 없거나 키가 비어 있습니다:
```bash
cp .env.example .env
# .env 열어서 실제 키 입력
```

---

### Alibaba API - "model not found"

모델명 확인:
- 국제판 DashScope: `qwen3.5-27b`, `qwen-plus`, `qwen-max`
- 중국판 DashScope: `qwen3.5-72b-instruct` 등 (다른 이름)

```bash
python run.py --provider alibaba --model qwen-plus
```

---

### vLLM thinking 토큰이 너무 많아요 (latency 증가)

Qwen3.5 계열은 thinking 모드가 활성화되면 출력 토큰이 폭증합니다. 비활성화하려면:

```python
# bench/providers.py의 call_openai_compat에서
json={
    ...,
    "extra_body": {"enable_thinking": False},  # Qwen3.5 thinking 비활성화
}
```

또는 모델을 thinking 비활성화 버전으로 교체.

---

### 대시보드가 안 열려요

```bash
# 포트 충돌 확인
lsof -i :5000

# 다른 포트로 실행
# dashboard.py 맨 마지막 줄 수정:
app.run(host="0.0.0.0", port=5001, ...)
```

---

### 결과 JSON 파싱 오류 (judge 0점)

judge가 JSON 대신 마크다운을 반환할 때 발생합니다. 재실행하거나 judge 모델을 변경:

```bash
python run.py --judge-model claude-sonnet-4-6
```

---

## 파일 구조 요약

```
harness-bench/
├── run.py                    진입점 (CLI)
├── dashboard.py              웹 대시보드
├── bench/
│   ├── harnesses.py          ★ 하니스 추가/제거
│   ├── tasks.py              ★ 과제 추가/제거
│   ├── providers.py          ★ 프로바이더 추가
│   └── judge.py              평가 로직 (건드릴 필요 없음)
├── templates/
│   └── index.html            대시보드 UI
├── results/                  실험 결과 JSON (자동 저장)
├── .env                      API 키 (git에 포함 안 됨)
├── .env.example              API 키 템플릿
├── requirements.txt
├── README.md
└── MANUAL.md                 이 파일
```

★ 표시된 파일만 수정하면 대부분의 커스터마이징이 가능합니다.
