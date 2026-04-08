#!/usr/bin/env python3
"""
실험 6: MD 조각화 하니스 vs 연속 텍스트 하니스 vs 제약만
==========================================================

목적: 하니스의 "형식"이 효과에 영향을 미치는가?
  - 실험 1~5: "무엇을 넣느냐" 검증
  - 실험 6:   "어떻게 구조화하느냐" 검증

실제 유출된 Claude Code 시스템 프롬프트는 254개 MD 파일로 조각화되어 있음.
각 파일은 `# 헤더`로 섹션 구분, 짧고 명확한 규칙 목록.
이 구조가 연속 텍스트 하니스보다 효과적인가?

4-Column 비교 (모두 바닐라 Qwen3.5-27B, 알리바바 API):
  Col1: 바닐라 Raw               — 재사용 (실험 4 결과)
  Col2: 연속 텍스트 하니스        — 재사용 (실험 4 결과, ~500tok)
  Col3: MD 조각화 하니스          — 동일 내용, # 헤더 섹션 구조 (유출 원본 재현)
  Col4: 제약만 (Don't-only)       — "하지 마라" 규칙만, 긍정 문장 없음 (~120tok)
"""

import json
import sys
import time
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import os
import re

load_dotenv()

sys.stdout.reconfigure(line_buffering=True)

OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(exist_ok=True)

# ============================================================
# 엔드포인트 (바닐라 Qwen3.5-27B, 알리바바 클라우드 국제판)
# ============================================================
ALIBABA_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
ALIBABA_API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-2a2c7474fabd4a229f48cd1615d85507")
ALIBABA_MODEL = "qwen3.5-27b"

# ============================================================
# 하니스 정의
# ============================================================

# --- Col2: 연속 텍스트 하니스 (실험 4와 동일) ---
HARNESS_CONTINUOUS = """The user will primarily request you to perform software engineering tasks. These may include solving bugs, adding new functionality, refactoring code, explaining code, and more. When given an unclear or generic instruction, consider it in the context of these software engineering tasks.

You are highly capable and often allow users to complete ambitious tasks that would otherwise be too complex or take too long. You should defer to user judgement about whether a task is too large to attempt.

In general, do not propose changes to code you haven't read. If a user asks about or wants you to modify a file, read it first. Understand existing code before suggesting modifications.

Do not create files unless they're absolutely necessary for achieving your goal. Generally prefer editing an existing file to creating a new one, as this prevents file bloat and builds on existing work more effectively.

Don't add features, refactor code, or make "improvements" beyond what was asked. A bug fix doesn't need surrounding code cleaned up. A simple feature doesn't need extra configurability. Don't add docstrings, comments, or type annotations to code you didn't change. Only add comments where the logic isn't self-evident.

Don't add error handling, fallbacks, or validation for scenarios that can't happen. Trust internal code and framework guarantees. Only validate at system boundaries (user input, external APIs). Don't use feature flags or backwards-compatibility shims when you can just change the code.

Don't create helpers, utilities, or abstractions for one-time operations. Don't design for hypothetical future requirements. The right amount of complexity is what the task actually requires — no speculative abstractions, but no half-finished implementations either. Three similar lines of code is better than a premature abstraction.

Avoid backwards-compatibility hacks like renaming unused _vars, re-exporting types, adding // removed comments for removed code, etc. If you are certain that something is unused, you can delete it completely.

Be careful not to introduce security vulnerabilities such as command injection, XSS, SQL injection, and other OWASP top 10 vulnerabilities. If you notice that you wrote insecure code, immediately fix it. Prioritize writing safe, secure, and correct code.

# Output efficiency

IMPORTANT: Go straight to the point. Try the simplest approach first without going in circles. Do not overdo it. Be extra concise.

Keep your text output brief and direct. Lead with the answer or action, not the reasoning. Skip filler words, preamble, and unnecessary transitions. Do not restate what the user said — just do it. When explaining, include only what is necessary for the user to understand.

Focus text output on:
- Decisions that need the user's input
- High-level status updates at natural milestones
- Errors or blockers that change the plan

If you can say it in one sentence, don't use three. Prefer short, direct sentences over long explanations. This does not apply to code or tool calls."""

# --- Col3: MD 조각화 하니스 (유출 원본 구조 재현) ---
# 동일한 내용이지만 # 헤더로 섹션 구분, 각 섹션 독립 파일처럼 구성
# 출처: Piebald-AI/claude-code-system-prompts 의 실제 파일 구조 참조
HARNESS_FRAGMENTED = """# Doing tasks
The user will primarily request you to perform software engineering tasks. These may include solving bugs, adding new functionality, refactoring code, explaining code, and more. When given an unclear or generic instruction, consider it in the context of these software engineering tasks and the current working directory.

In general, do not propose changes to code you haven't read. If a user asks about or wants you to modify a file, read it first. Understand existing code before suggesting modifications.

Do not create files unless they're absolutely necessary for achieving your goal. Generally prefer editing an existing file to creating a new one.

# Scope discipline
Don't add features, refactor code, or make "improvements" beyond what was asked.
- A bug fix doesn't need surrounding code cleaned up.
- A simple feature doesn't need extra configurability.
- Don't add docstrings, comments, or type annotations to code you didn't change.
- Only add comments where the logic isn't self-evident.

# Error handling
Don't add error handling, fallbacks, or validation for scenarios that can't happen.
- Trust internal code and framework guarantees.
- Only validate at system boundaries (user input, external APIs).
- Don't use feature flags or backwards-compatibility shims when you can just change the code.

# Abstractions
Don't create helpers, utilities, or abstractions for one-time operations.
- Don't design for hypothetical future requirements.
- The right amount of complexity is what the task actually requires.
- Three similar lines of code is better than a premature abstraction.

# Backwards compatibility
Avoid backwards-compatibility hacks like renaming unused _vars, re-exporting types, adding removed comments for removed code.
- If you are certain that something is unused, delete it completely.

# Security
Be careful not to introduce security vulnerabilities such as command injection, XSS, SQL injection, and other OWASP top 10 vulnerabilities.
- Prioritize writing safe, secure, and correct code.

# Output efficiency
IMPORTANT: Go straight to the point. Try the simplest approach first. Do not overdo it. Be extra concise.

Keep your text output brief and direct.
- Lead with the answer or action, not the reasoning.
- Skip filler words, preamble, and unnecessary transitions.
- Do not restate what the user said — just do it.
- When explaining, include only what is necessary.

If you can say it in one sentence, don't use three. Prefer short, direct sentences over long explanations."""

# --- Col4: 제약만 (Don't-only) ---
# 긍정 문장("You are highly capable", "The user will primarily...") 전부 제거
# 순수하게 "하지 마라" 규칙만 남김
HARNESS_RESTRICTIONS_ONLY = """# Rules
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
If you can say it in one sentence, don't use three."""

# ============================================================
# 실험 조건
# ============================================================
CONDITIONS = {
    "raw": {
        "name": "Col1: 바닐라 Raw",
        "system": "",
        "tok_estimate": 0,
        "description": "시스템 프롬프트 없음",
    },
    "continuous": {
        "name": "Col2: 연속 텍스트 하니스",
        "system": HARNESS_CONTINUOUS,
        "tok_estimate": 500,
        "description": "기존 실험 4와 동일한 연속 텍스트 형식",
    },
    "fragmented": {
        "name": "Col3: MD 조각화 하니스",
        "system": HARNESS_FRAGMENTED,
        "tok_estimate": 480,
        "description": "# 헤더로 섹션 구분 — 유출 원본 파일 구조 재현",
    },
    "restrictions_only": {
        "name": "Col4: 제약만 (Don't-only)",
        "system": HARNESS_RESTRICTIONS_ONLY,
        "tok_estimate": 120,
        "description": "긍정 문장 없음, 'Don't X' 규칙만 (~120tok)",
    },
}

# ============================================================
# 과제 6개 (기존 실험과 동일)
# ============================================================
TASKS = [
    # --- 코딩 ---
    {
        "id": "coding_lru_cache",
        "name": "LRU Cache with TTL",
        "category": "coding",
        "prompt": "Write a Python LRU cache with TTL (time-to-live) expiration:\n- get(key) - returns value or None if expired/missing\n- put(key, value, ttl_seconds=60) - stores with expiration\n- Maximum capacity with LRU eviction when full\n- Thread-safe\n\nImplement as a single class LRUCache. Include a brief usage example.",
    },
    {
        "id": "coding_group_by",
        "name": "group_by 함수",
        "category": "coding",
        "prompt": "Write a Python function group_by(items, key_fn) that groups a list of items by the result of key_fn, returning a dict of lists. Do not use itertools.groupby.",
    },
    {
        "id": "coding_merge_intervals",
        "name": "Merge Intervals",
        "category": "coding",
        "prompt": "Write a Python function merge_intervals(intervals) that takes a list of [start, end] intervals and returns a new list with all overlapping intervals merged. Example: [[1,3],[2,6],[8,10],[15,18]] -> [[1,6],[8,10],[15,18]]",
    },
    # --- 비코딩 ---
    {
        "id": "explain_redis_pubsub",
        "name": "Redis Pub/Sub 설명",
        "category": "non-coding",
        "prompt": "Explain how Redis Pub/Sub works, when to use it, and its limitations compared to a dedicated message broker like RabbitMQ or Kafka.",
    },
    {
        "id": "review_code",
        "name": "코드 리뷰",
        "category": "non-coding",
        "prompt": """Review this Python code and identify all issues:

```python
import json
import os
import sys
import re
from typing import Optional, List, Dict, Any, Union

class UserManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.users = {}
        self.db = None

    def get_user(self, user_id):
        try:
            if user_id in self.users:
                return self.users[user_id]
            user = self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
            self.users[user_id] = user
            return user
        except Exception as e:
            print(f"Error: {e}")
            return None

    def delete_user(self, user_id):
        try:
            self.db.query(f"DELETE FROM users WHERE id = {user_id}")
            if user_id in self.users:
                del self.users[user_id]
            return True
        except:
            return False
```""",
    },
    {
        "id": "architecture_decision",
        "name": "아키텍처 의사결정",
        "category": "non-coding",
        "prompt": "We have a monolithic Django app (50k LOC, 10 developers, ~500 RPS). The team wants to break out the payment processing module into a separate service. What are the key considerations, risks, and your recommendation?",
    },
]

# ============================================================
# 평가 기준 (기존과 동일)
# ============================================================
EVAL_PROMPT_CODING = """You are a strict code quality evaluator. Score this coding response on 6 criteria (1-10 each).

## Task
{task_prompt}

## Response (from: {condition_name})
{response}

## Scoring criteria (be STRICT, especially on 3/4/5)
1. correctness: Does the code work correctly? Logic bugs? Missing features? (1=broken, 10=perfect)
2. efficiency: Is the algorithm sound and efficient? (1=poor, 10=optimal)
3. conciseness: Is the code free of unnecessary bloat? Penalize: unused imports, verbose variable names, unnecessary blank lines, redundant code (1=very bloated, 10=minimal)
4. no_overengineering: Did it avoid adding UNNECESSARY things? Penalize heavily: type hints not asked for, docstrings not asked for, error handling for impossible scenarios, unnecessary abstract classes/interfaces (1=heavily overengineered, 10=just what was asked)
5. response_bloat: Is the text response free of unnecessary prose? Penalize: long explanations before code, step-by-step reasoning not asked for, disclaimers, restating the problem (1=very bloated text, 10=mostly just code)
6. instruction_following: Did it follow instructions precisely? All required features implemented? (1=missed requirements, 10=perfect)

Return ONLY this JSON (no other text):
{{"correctness":{{"score":N,"reason":"one line"}}, "efficiency":{{"score":N,"reason":"one line"}}, "conciseness":{{"score":N,"reason":"one line"}}, "no_overengineering":{{"score":N,"reason":"one line"}}, "response_bloat":{{"score":N,"reason":"one line"}}, "instruction_following":{{"score":N,"reason":"one line"}}}}"""

EVAL_PROMPT_NONCODING = """You are a strict response quality evaluator. Score this non-coding response on 6 criteria (1-10 each).

## Task
{task_prompt}

## Response (from: {condition_name})
{response}

## Scoring criteria (be STRICT, especially on 3/4/5)
1. accuracy: Is the information factually correct? Any misleading claims? (1=wrong, 10=perfect)
2. completeness: Does it cover the key points the question asks for? (1=missing most, 10=comprehensive)
3. conciseness: Is it free of unnecessary filler, repetition, and padding? (1=very padded, 10=tight and dense)
4. no_overexplaining: Did it avoid explaining things that weren't asked? Penalize: unsolicited background, basic definitions the questioner clearly knows (1=heavily overexplains, 10=just what was asked)
5. response_bloat: Is it free of unnecessary prose structure? Penalize: excessive headers, bullet-point spam, restating the question, disclaimers (1=very bloated, 10=lean)
6. actionability: Are the insights practical and directly useful? (1=generic fluff, 10=specific and actionable)

Return ONLY this JSON (no other text):
{{"accuracy":{{"score":N,"reason":"one line"}}, "completeness":{{"score":N,"reason":"one line"}}, "conciseness":{{"score":N,"reason":"one line"}}, "no_overexplaining":{{"score":N,"reason":"one line"}}, "response_bloat":{{"score":N,"reason":"one line"}}, "actionability":{{"score":N,"reason":"one line"}}}}"""

METRICS_CODING = ["correctness", "efficiency", "conciseness",
                  "no_overengineering", "response_bloat", "instruction_following"]
METRICS_NONCODING = ["accuracy", "completeness", "conciseness",
                     "no_overexplaining", "response_bloat", "actionability"]

# ============================================================
# API 호출
# ============================================================

def call_alibaba(system_prompt: str, user_prompt: str) -> dict:
    """알리바바 클라우드 API (바닐라 Qwen3.5-27B)"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    start = time.time()
    try:
        resp = requests.post(
            ALIBABA_URL,
            headers={
                "Authorization": f"Bearer {ALIBABA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": ALIBABA_MODEL,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": 0.3,
            },
            timeout=300,
        )
        elapsed = time.time() - start
        data = resp.json()

        if "error" in data:
            return {"error": str(data["error"]), "elapsed": round(elapsed, 2)}

        content = data["choices"][0]["message"]["content"]
        if "<think>" in content:
            content = re.sub(r"<think>.*?</think>\s*", "", content, flags=re.DOTALL).strip()

        usage = data.get("usage", {})
        return {
            "response": content,
            "response_length": len(content),
            "elapsed": round(elapsed, 2),
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "model": f"alibaba/{ALIBABA_MODEL}",
            "cost_usd": 0,
        }
    except Exception as e:
        return {"error": str(e), "elapsed": round(time.time() - start, 2)}


def call_claude_judge(prompt: str) -> str:
    """Claude Opus 4.6 LLM-as-judge"""
    import subprocess
    r = subprocess.run(
        ["claude", "-p", "--output-format", "text"],
        input=prompt, capture_output=True, text=True, timeout=120,
    )
    return r.stdout.strip()


def evaluate_response(task: dict, response: str, condition_name: str) -> dict:
    is_coding = task["category"] == "coding"
    template = EVAL_PROMPT_CODING if is_coding else EVAL_PROMPT_NONCODING
    metrics = METRICS_CODING if is_coding else METRICS_NONCODING

    eval_prompt = template.format(
        task_prompt=task["prompt"],
        condition_name=condition_name,
        response=response[:8000],
    )
    raw = call_claude_judge(eval_prompt)

    try:
        # JSON 추출
        start = raw.find("{")
        end = raw.rfind("}") + 1
        scores_raw = json.loads(raw[start:end])
        scores = {m: scores_raw[m]["score"] for m in metrics if m in scores_raw}
        reasons = {m: scores_raw[m].get("reason", "") for m in metrics if m in scores_raw}
        avg = sum(scores.values()) / len(scores) if scores else 0
        return {"scores": scores, "reasons": reasons, "average": round(avg, 2)}
    except Exception as e:
        return {"error": str(e), "raw": raw[:500]}


# ============================================================
# 메인 실험 루프
# ============================================================

def run_experiment():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"fragmented_experiment_{timestamp}.json"

    print("=" * 60)
    print("실험 6: MD 조각화 하니스 vs 연속 텍스트 vs 제약만")
    print("=" * 60)
    print(f"  모델: 바닐라 Qwen3.5-27B (알리바바 클라우드 국제판)")
    print(f"  과제: 6개 (코딩 3 + 비코딩 3)")
    print(f"  조건: 4개 (Raw / 연속 / MD조각화 / 제약만)")
    print(f"  평가: Claude Opus 4.6 LLM-as-judge")
    print()

    results = {
        "experiment": "fragmented_harness_comparison",
        "timestamp": timestamp,
        "model": ALIBABA_MODEL,
        "conditions": {k: {"name": v["name"], "tok_estimate": v["tok_estimate"],
                           "description": v["description"]}
                       for k, v in CONDITIONS.items()},
        "tasks": [],
    }

    for task in TASKS:
        print(f"\n[과제] {task['name']} ({task['category']})")
        task_result = {
            "id": task["id"],
            "name": task["name"],
            "category": task["category"],
            "conditions": {},
        }

        for cond_key, cond in CONDITIONS.items():
            print(f"  → {cond['name']} ...", end="", flush=True)

            # Col1 Raw는 실험 4 결과 재사용 가능하지만 일관성을 위해 재실행
            resp = call_alibaba(cond["system"], task["prompt"])

            if "error" in resp:
                print(f" ERROR: {resp['error']}")
                task_result["conditions"][cond_key] = {"error": resp["error"]}
                continue

            print(f" {resp['elapsed']}s, {resp['output_tokens']}tok", end="", flush=True)

            eval_result = evaluate_response(task, resp["response"], cond["name"])
            avg = eval_result.get("average", 0)
            print(f" → 점수: {avg}")

            task_result["conditions"][cond_key] = {
                "response": resp["response"],
                "response_length": resp["response_length"],
                "elapsed": resp["elapsed"],
                "input_tokens": resp["input_tokens"],
                "output_tokens": resp["output_tokens"],
                "evaluation": eval_result,
            }

        results["tasks"].append(task_result)

        # 중간 저장
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    # ---- 종합 집계 ----
    print("\n" + "=" * 60)
    print("종합 결과")
    print("=" * 60)

    summary = {k: {"scores": [], "lengths": [], "times": [], "input_toks": [], "output_toks": []}
               for k in CONDITIONS}

    for task_result in results["tasks"]:
        for cond_key in CONDITIONS:
            cond_data = task_result["conditions"].get(cond_key, {})
            if "evaluation" in cond_data and "average" in cond_data["evaluation"]:
                summary[cond_key]["scores"].append(cond_data["evaluation"]["average"])
                summary[cond_key]["lengths"].append(cond_data.get("response_length", 0))
                summary[cond_key]["times"].append(cond_data.get("elapsed", 0))
                summary[cond_key]["input_toks"].append(cond_data.get("input_tokens", 0))
                summary[cond_key]["output_toks"].append(cond_data.get("output_tokens", 0))

    for cond_key, cond in CONDITIONS.items():
        s = summary[cond_key]
        if s["scores"]:
            avg_score = round(sum(s["scores"]) / len(s["scores"]), 2)
            avg_len = round(sum(s["lengths"]) / len(s["lengths"]))
            avg_time = round(sum(s["times"]) / len(s["times"]), 1)
            avg_itok = round(sum(s["input_toks"]) / len(s["input_toks"]))
            avg_otok = round(sum(s["output_toks"]) / len(s["output_toks"]))
            print(f"  {cond['name']}: {avg_score} | {avg_len}자 | {avg_time}s | in:{avg_itok} out:{avg_otok}")

    results["summary"] = {
        cond_key: {
            "avg_score": round(sum(s["scores"]) / len(s["scores"]), 2) if s["scores"] else None,
            "avg_length": round(sum(s["lengths"]) / len(s["lengths"])) if s["lengths"] else None,
            "avg_time": round(sum(s["times"]) / len(s["times"]), 1) if s["times"] else None,
            "avg_input_tokens": round(sum(s["input_toks"]) / len(s["input_toks"])) if s["input_toks"] else None,
            "avg_output_tokens": round(sum(s["output_toks"]) / len(s["output_toks"])) if s["output_toks"] else None,
        }
        for cond_key, s in summary.items()
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n결과 저장: {output_file}")
    return output_file


if __name__ == "__main__":
    run_experiment()
