# harness-bench

> **Claude Code 시스템 프롬프트가 다른 모델 성능을 올릴 수 있을까?**
>
> 2026년 3월 Claude Code npm 소스맵 유출로 공개된 시스템 프롬프트(하니스)를
> 바닐라 Qwen3.5-27B에 적용했더니 코드 품질이 **+26.5%** 향상됐습니다.
> 이 레포는 그 실험을 누구나 재현하고, 자기 모델/프롬프트로 확장할 수 있게 만든 벤치마크 프레임워크입니다.

---

## 실험으로 밝혀진 것들

6개 실험, 총 수백 회의 LLM-as-judge 평가를 통해 확인한 결과입니다.

| 발견 | 수치 |
|------|------|
| 하니스를 적용하면 바닐라 Qwen 성능이 오른다 | 6.83 → 8.64 **(+26.5%)** |
| Distillation(파인튜닝) 때문이 아니다 | 바닐라 ≈ Distilled (차이 0.11) |
| 하니스 형식도 성능에 영향을 준다 | 제약만(8.97) > MD조각화(8.5) > 연속텍스트(8.33) |
| 더 길다고 더 좋은 건 아니다 | 21K 토큰 < 500 토큰 (−11%) |
| 코딩에서는 Claude를 넘어서기도 한다 | 바닐라 27B + 제약만: 9.83 vs Claude Opus: 9.14 |

**핵심 인사이트**: Claude Code의 경쟁력은 모델 크기가 아니라 **"하지 마라"는 제약 12줄**에 있다.

---

## 설치

### 1. 레포 클론 & 패키지 설치

```bash
git clone <repo-url>
cd harness-bench

pip install -r requirements.txt
```

### 2. API 키 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어서 키를 입력하세요:

```bash
# Alibaba Cloud DashScope (Qwen 모델 사용 시 필수)
# 발급: https://dashscope.console.aliyun.com/apiKey
DASHSCOPE_API_KEY=sk-여기에입력

# OpenAI (GPT 모델 사용 시)
OPENAI_API_KEY=sk-여기에입력
```

### 3. Claude Code CLI 설치 (평가 judge용)

```bash
npm install -g @anthropic-ai/claude-code
claude   # 로그인
```

> judge는 각 응답을 6개 기준으로 채점하는 역할입니다.
> Claude Code CLI가 없으면 `--no-judge` 옵션으로 응답만 수집할 수 있어요.

---

## 실행 방법

### 방법 A — 대시보드 (추천)

```bash
python dashboard.py
```

브라우저에서 `http://localhost:5000` 접속.
조건·과제를 체크박스로 고르고 실행 버튼 하나면 됩니다.

![대시보드 구성]
```
┌──────────────────────────────────────────────────────────┐
│  harness-bench                              [상태 배지]   │
├─────────────────┬────────────────────────────────────────┤
│                 │  탭: [실행 로그]  [결과 히스토리]       │
│  ✅ 조건 선택   │                                         │
│  ✅ 과제 선택   │  실험 진행 상황 실시간 스트리밍          │
│  모델/API 설정  │  과제·조건별 점수 즉시 표시             │
│  Judge 설정     │                                         │
│                 ├────────────────────────────────────────┤
│  [▶ 실험 실행]  │  종합 점수 비교 바                      │
│  [⏹ 중단]      │                                         │
└─────────────────┴────────────────────────────────────────┘
```

### 방법 B — CLI

```bash
# 기본 전체 실행
python run.py

# 조건 지정
python run.py --conditions raw restrictions_only

# 과제 지정
python run.py --tasks coding_group_by coding_lru_cache

# 다른 모델로
python run.py --provider openai --model gpt-4o
python run.py --provider vllm --model Llama-3.1-8B-Instruct

# 빠른 확인 (judge 없이 응답만 수집)
python run.py --conditions restrictions_only --tasks coding_group_by --no-judge
```

---

## 기본 제공 조건 (하니스)

| 키 | 설명 | 토큰 | 코딩 점수 |
|----|------|:----:|:---------:|
| `raw` | 시스템 프롬프트 없음 (baseline) | 0 | 7.39 |
| `continuous` | 연속 텍스트 하니스 (실험 1~4 기본) | ~500 | 9.0 |
| `fragmented` | `#` 헤더 7섹션 — 유출 원본 구조 재현 | ~480 | 9.22 |
| `restrictions_only` | "Don't X" 규칙 12줄만 | ~120 | **9.83** |

> 점수는 바닐라 Qwen3.5-27B + Claude Opus 4.6 judge 기준입니다.

---

## 커스터마이징

### 내 하니스 추가하기 → `bench/harnesses.py`

`CONDITIONS` dict에 항목을 추가하면 CLI와 대시보드에 바로 반영됩니다.

```python
CONDITIONS: dict[str, dict] = {
    # 기존 항목...

    # 내 하니스 추가
    "my_harness": {
        "name": "My Custom Harness",
        "system": """
# 규칙
요청한 것만 구현하세요.
타입 힌트나 docstring은 요청하지 않으면 추가하지 마세요.
간결하게 답하세요.
        """,
        "description": "내가 만든 커스텀 하니스",
    },
}
```

```bash
python run.py --conditions raw my_harness
```

### 내 과제 추가하기 → `bench/tasks.py`

```python
TASKS: list[dict] = [
    # 기존 항목...

    {
        "id": "coding_fibonacci",           # 고유 ID (CLI와 결과 JSON에서 사용)
        "name": "Fibonacci with memoization",
        "category": "coding",               # "coding" 또는 "non-coding"
        "prompt": "Write fib(n) using memoization. No imports.",
    },
]
```

```bash
python run.py --tasks coding_fibonacci
```

### 다른 모델/서비스 연결하기 → `bench/providers.py`

OpenAI 호환 엔드포인트라면 몇 줄이면 됩니다:

```python
PROVIDERS: dict[str, dict] = {
    # 기존 항목...

    # Together AI
    "together": {
        "description": "Together AI",
        "default_model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "caller": _make_openai_caller(
            base_url="https://api.together.xyz/v1",
            api_key_env="TOGETHER_API_KEY",
            default_model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        ),
    },
}
```

`.env`에 키 추가 후:
```bash
python run.py --provider together --model meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo
```

**자체 vLLM 서버 연결:**
```bash
# .env에 추가
VLLM_BASE_URL=http://내서버:8000/v1
VLLM_MODEL=Qwen3.5-27b

python run.py --provider vllm
```

---

## CLI 전체 옵션

```
python run.py [옵션]

  --conditions KEY [...]     실험할 조건 키 목록 (기본: 모두)
  --tasks ID [...]           실험할 과제 ID 목록 (기본: 모두)
  --provider NAME            프로바이더 선택: alibaba | openai | vllm | claude_cli
  --model NAME               모델명 (생략하면 프로바이더 기본값)
  --judge-model NAME         judge에 쓸 Claude 모델 (기본: claude-opus-4-6)
  --no-judge                 평가 없이 응답만 수집
  --temperature FLOAT        샘플링 온도 (기본: 0.3)
  --output PATH              결과 JSON 저장 경로

  --list-conditions          사용 가능한 조건 목록 보기
  --list-tasks               사용 가능한 과제 목록 보기
  --list-providers           사용 가능한 프로바이더 목록 보기
```

---

## 파일 구조

```
harness-bench/
│
├── run.py                   CLI 진입점
├── dashboard.py             웹 대시보드 (Flask)
│
├── bench/                   ← 커스터마이징은 여기서만
│   ├── harnesses.py         하니스(조건) 추가·제거
│   ├── tasks.py             벤치마크 과제 추가·제거
│   ├── providers.py         모델·API 엔드포인트 추가
│   └── judge.py             LLM-as-judge 로직 (건드릴 일 없음)
│
├── templates/
│   └── index.html           대시보드 UI
│
├── results/                 실험 결과 자동 저장
│   ├── run_TIMESTAMP.json
│   └── FINAL_COMPREHENSIVE_REPORT_v4.md
│
├── .env                     API 키 (git 제외)
├── .env.example             API 키 템플릿
├── requirements.txt
├── README.md                이 파일
└── MANUAL.md                상세 매뉴얼
```

> 세 파일(`harnesses.py`, `tasks.py`, `providers.py`)만 수정하면
> 대부분의 커스터마이징이 가능합니다.

---

## 평가 기준

모든 응답은 Claude Opus 4.6이 6개 기준 각 1-10점으로 채점합니다.

**코딩 과제**

| 기준 | 높은 점수 조건 |
|------|--------------|
| `correctness` | 코드가 정확히 동작한다 |
| `efficiency` | 알고리즘이 효율적이다 |
| `conciseness` | 군더더기 코드가 없다 |
| `no_overengineering` | 요청하지 않은 타입힌트·docstring·추상화를 추가하지 않았다 |
| `response_bloat` | 코드 앞 설명 산문이 없다, 바로 코드만 준다 |
| `instruction_following` | 지시한 시그니처·요건을 정확히 따랐다 |

**비코딩 과제**

| 기준 | 높은 점수 조건 |
|------|--------------|
| `accuracy` | 사실이 정확하다 |
| `completeness` | 질문의 핵심을 빠짐없이 다뤘다 |
| `conciseness` | 반복·패딩이 없다 |
| `no_overexplaining` | 묻지 않은 배경 설명을 늘어놓지 않았다 |
| `response_bloat` | 헤더 남발, 질문 재진술이 없다 |
| `actionability` | 추상적 조언이 아닌 실제로 쓸 수 있는 답이다 |

---

## 실험 이력

이 레포에서 진행된 6개 실험의 흐름입니다.

```
실험 1 (2026-04-03)  하니스가 작동하는가?
  → Distilled Qwen 27B에 적용  →  +34% (5.93 → 7.97)  ✅

실험 2 (2026-04-05)  파인튜닝 때문이 아닌가? (Inverse Prompt)
  → 반대 지시를 줬더니 행동이 역전됨  →  프롬프트 자체의 힘  ✅

실험 3 (2026-04-05)  기본 템플릿이 결과를 오염시키나? (5-way Ablation)
  → Default system 효과 = +0.04점  →  무시 가능  ✅

실험 4 (2026-04-06)  파인튜닝 안 된 바닐라 모델에서도 되나?
  → 알리바바 공식 Qwen3.5-27B 사용  →  +26.5% (6.83 → 8.64)  ✅

실험 5 (2026-04-06)  Claude Code 전체 런타임(~21K 토큰)이 더 좋을까?
  → 추출 하니스(8.64) > 전체 하니스(7.67)  →  길수록 좋은 건 아님  ✅

실험 6 (2026-04-08)  형식이 달라지면 결과가 달라지나?
  → 제약만(8.97) > MD조각화(8.5) > 연속텍스트(8.33)  →  형식도 중요  ✅
```

상세 결과 → [`results/FINAL_COMPREHENSIVE_REPORT_v4.md`](results/FINAL_COMPREHENSIVE_REPORT_v4.md)

---

## 자주 묻는 것들

**Q. Alibaba Cloud 계정이 없어요. OpenAI로 해도 되나요?**

됩니다. `.env`에 `OPENAI_API_KEY` 넣고 `--provider openai --model gpt-4o`로 실행하면 됩니다.

**Q. 로컬 모델로 실험하고 싶어요.**

vLLM 등으로 OpenAI 호환 서버를 띄우면 됩니다:
```bash
vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000
# .env에 VLLM_BASE_URL=http://localhost:8000/v1 설정
python run.py --provider vllm
```

**Q. Claude Code CLI 없이도 실험할 수 있나요?**

판단(judge) 없이 응답만 수집할 수 있습니다:
```bash
python run.py --no-judge
```

**Q. 내가 만든 시스템 프롬프트를 테스트하고 싶어요.**

`bench/harnesses.py`에 항목 추가 후 바로 사용 가능합니다. 대시보드를 재시작하면 자동 반영됩니다.

---

## 참고자료

- [Piebald-AI/claude-code-system-prompts](https://github.com/Piebald-AI/claude-code-system-prompts) — 유출된 Claude Code 시스템 프롬프트 254개 파일 정리
- [Gitlawb/openclaude](https://github.com/Gitlawb/openclaude) — Claude Code 전체 런타임 오픈소스 포크
- 상세 매뉴얼: [`MANUAL.md`](MANUAL.md)
- 종합 리포트: [`results/FINAL_COMPREHENSIVE_REPORT_v4.md`](results/FINAL_COMPREHENSIVE_REPORT_v4.md)
