#!/usr/bin/env python3
"""
실험: Claude Code 시스템 프롬프트(하니스)가 27B 모델 성능을 끌어올리는가?
==========================================================================

3-Column 비교:
  Col 1: Qwen3.5-27B Raw (시스템 프롬프트 없음)
  Col 2: Qwen3.5-27B + Claude Code 하니스 (유출된 시스템 프롬프트)
  Col 3: Claude Opus 4.6 CLI (claude -p --model claude-opus-4-6)

과제: 코딩 3개 + 비코딩 3개 = 6개 (혼합)

모델: Jackrong/Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled
서버: H200 @ 118.223.251.22:10051 (vLLM)
평가: Claude Opus 4.6을 LLM-as-judge로 사용
"""

import json
import sys
import time
import subprocess
import requests
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)

OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(exist_ok=True)

# ============================================================
# 엔드포인트 설정
# ============================================================
VLLM_URL = "http://118.223.251.22:10051/v1/chat/completions"
VLLM_MODEL = "Qwen3.5-27b"

# ============================================================
# 시스템 프롬프트
# ============================================================

# 유출된 시스템 프롬프트 원문 그대로 조합 (변형 없음)
# 출처: Piebald-AI/claude-code-system-prompts/system-prompts/
CLAUDE_CODE_HARNESS = """The user will primarily request you to perform software engineering tasks. These may include solving bugs, adding new functionality, refactoring code, explaining code, and more. When given an unclear or generic instruction, consider it in the context of these software engineering tasks.

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

# ============================================================
# 실험 조건
# ============================================================
CONDITIONS = {
    "raw_27b": {
        "name": "Col1: Qwen3.5-27B Raw",
        "type": "vllm",
        "system": "",
    },
    "harness_27b": {
        "name": "Col2: Qwen3.5-27B + Claude Code 하니스",
        "type": "vllm",
        "system": CLAUDE_CODE_HARNESS,
    },
    "claude_code": {
        "name": "Col3: Claude Opus 4.6 CLI",
        "type": "claude_cli",
        "system": None,
    },
}

# ============================================================
# 과제 6개: 코딩 3개 + 비코딩 3개
# ============================================================
TASKS = [
    # --- 코딩 과제 ---
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
    # --- 비코딩 과제 ---
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
# 평가 기준 (코딩 / 비코딩 분리)
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
4. no_overengineering: Did it avoid adding UNNECESSARY things? Penalize heavily: type hints not asked for, docstrings not asked for, error handling for impossible scenarios, unnecessary abstract classes/interfaces, design patterns that add complexity without value (1=heavily overengineered, 10=just what was asked)
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
4. no_overexplaining: Did it avoid explaining things that weren't asked? Penalize: unsolicited background, basic definitions of terms the questioner clearly knows, tangential topics (1=heavily overexplains, 10=just what was asked)
5. response_bloat: Is it free of unnecessary prose structure? Penalize: excessive headers, bullet-point spam, restating the question, "let me explain", disclaimers, conclusions that repeat the intro (1=very bloated, 10=lean)
6. actionability: Are the insights practical and directly useful? Not vague platitudes? (1=generic fluff, 10=specific and actionable)

Return ONLY this JSON (no other text):
{{"accuracy":{{"score":N,"reason":"one line"}}, "completeness":{{"score":N,"reason":"one line"}}, "conciseness":{{"score":N,"reason":"one line"}}, "no_overexplaining":{{"score":N,"reason":"one line"}}, "response_bloat":{{"score":N,"reason":"one line"}}, "actionability":{{"score":N,"reason":"one line"}}}}"""

METRICS_CODING = ["correctness", "efficiency", "conciseness",
                  "no_overengineering", "response_bloat", "instruction_following"]
METRICS_NONCODING = ["accuracy", "completeness", "conciseness",
                     "no_overexplaining", "response_bloat", "actionability"]

# ============================================================
# API 호출 함수
# ============================================================

def call_vllm(system_prompt: str, user_prompt: str) -> dict:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    start = time.time()
    try:
        resp = requests.post(
            VLLM_URL,
            json={
                "model": VLLM_MODEL,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": 0.3,
                "chat_template_kwargs": {"enable_thinking": False},
            },
            timeout=300,
        )
        elapsed = time.time() - start
        data = resp.json()

        if "error" in data:
            return {"error": data["error"], "elapsed": round(elapsed, 2)}

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return {
            "response": content,
            "response_length": len(content),
            "elapsed": round(elapsed, 2),
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "model": VLLM_MODEL,
        }
    except Exception as e:
        return {"error": str(e), "elapsed": round(time.time() - start, 2)}


def call_claude_cli(user_prompt: str) -> dict:
    cmd = ["claude", "-p", "--model", "claude-opus-4-6", "--output-format", "json"]
    start = time.time()
    try:
        r = subprocess.run(cmd, input=user_prompt, capture_output=True, text=True, timeout=180)
        elapsed = time.time() - start

        if r.returncode != 0:
            return {"error": r.stderr.strip()[:300], "elapsed": round(elapsed, 2)}

        try:
            out = json.loads(r.stdout)
            return {
                "response": out.get("result", r.stdout),
                "response_length": len(out.get("result", r.stdout)),
                "elapsed": round(elapsed, 2),
                "input_tokens": out.get("usage", {}).get("input_tokens", 0),
                "output_tokens": out.get("usage", {}).get("output_tokens", 0),
                "model": out.get("model", "claude-opus-4-6"),
                "cost_usd": out.get("cost_usd", 0),
            }
        except json.JSONDecodeError:
            return {
                "response": r.stdout.strip(),
                "response_length": len(r.stdout.strip()),
                "elapsed": round(elapsed, 2),
                "input_tokens": 0, "output_tokens": 0, "model": "claude-opus-4-6", "cost_usd": 0,
            }
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "elapsed": 180}


def evaluate_with_claude(task: dict, response: str, condition_name: str) -> dict:
    is_coding = task["category"] == "coding"
    template = EVAL_PROMPT_CODING if is_coding else EVAL_PROMPT_NONCODING
    eval_prompt = template.format(
        task_prompt=task["prompt"],
        condition_name=condition_name,
        response=response[:8000],
    )

    cmd = ["claude", "-p", "--model", "claude-opus-4-6", "--output-format", "json",
           "--system-prompt", "You are a response evaluator. Return ONLY valid JSON."]
    try:
        r = subprocess.run(cmd, input=eval_prompt, capture_output=True, text=True, timeout=90)
        if r.returncode != 0:
            return {"error": r.stderr[:200]}

        try:
            out = json.loads(r.stdout)
            text = out.get("result", r.stdout)
        except json.JSONDecodeError:
            text = r.stdout.strip()

        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return {"error": "no_json", "raw": text[:300]}
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# 메인 실험
# ============================================================

def main():
    total = len(CONDITIONS) * len(TASKS)
    coding_count = sum(1 for t in TASKS if t["category"] == "coding")
    noncoding_count = len(TASKS) - coding_count

    print("=" * 70)
    print("  Claude Code 하니스 효과 실험 (코딩 + 비코딩 혼합)")
    print(f"  조건 3개 × 과제 {len(TASKS)}개 (코딩 {coding_count} + 비코딩 {noncoding_count}) = {total}회")
    print(f"  Col1: Qwen3.5-27B Raw | Col2: +하니스 | Col3: Claude Opus 4.6")
    print(f"  시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 메타데이터에 시스템 프롬프트 전문 기록
    experiment_meta = {
        "experiment": "h100_3column_mixed",
        "timestamp": datetime.now().isoformat(),
        "vllm_url": VLLM_URL,
        "vllm_model": VLLM_MODEL,
        "claude_model": "claude-opus-4-6",
        "temperature": 0.3,
        "max_tokens": 4096,
        "system_prompts": {
            "raw_27b": "(없음)",
            "harness_27b": CLAUDE_CODE_HARNESS,
            "claude_code": "(Claude Code CLI 내장 하니스 — claude -p --model claude-opus-4-6)",
        },
        "eval_prompt_coding": EVAL_PROMPT_CODING,
        "eval_prompt_noncoding": EVAL_PROMPT_NONCODING,
        "tasks": TASKS,
    }

    all_results = []
    count = 0

    for task in TASKS:
        print(f"\n{'━' * 70}")
        print(f"  📋 [{task['category'].upper()}] {task['name']}")
        print(f"{'━' * 70}")

        for ck, cv in CONDITIONS.items():
            count += 1
            print(f"\n  [{count}/{total}] {cv['name']}")

            if cv["type"] == "vllm":
                gen = call_vllm(cv["system"], task["prompt"])
            else:
                gen = call_claude_cli(task["prompt"])

            entry = {
                "task_id": task["id"],
                "task_name": task["name"],
                "task_category": task["category"],
                "task_prompt": task["prompt"],
                "condition": ck,
                "condition_name": cv["name"],
                "system_prompt_used": cv["system"] if cv["system"] is not None else "(claude cli built-in)",
                "timestamp": datetime.now().isoformat(),
            }

            if "error" in gen:
                entry["error"] = gen["error"]
                print(f"    ✗ ERROR: {gen['error'][:100]}")
                all_results.append(entry)
                continue

            entry.update({
                "response": gen["response"],
                "response_length": gen["response_length"],
                "elapsed": gen["elapsed"],
                "input_tokens": gen.get("input_tokens", 0),
                "output_tokens": gen.get("output_tokens", 0),
                "model": gen.get("model", "unknown"),
                "cost_usd": gen.get("cost_usd", 0),
            })
            print(f"    ✓ GEN: {gen['response_length']} chars, {gen['elapsed']}s, "
                  f"{gen.get('output_tokens',0)} tokens, model={gen.get('model','?')}")

            print(f"    ⏳ Evaluating (Claude Opus judge)...")
            ev = evaluate_with_claude(task, gen["response"], cv["name"])
            entry["evaluation"] = ev

            if "error" not in ev:
                scores = {k: v["score"] for k, v in ev.items() if isinstance(v, dict)}
                avg = round(sum(scores.values()) / len(scores), 1)
                print(f"    ✓ SCORES: {scores}")
                print(f"    ✓ AVG: {avg}/10")
            else:
                print(f"    ✗ EVAL ERROR: {ev.get('error','')[:100]}")

            all_results.append(entry)
            time.sleep(0.3)

    # 저장 (메타데이터 + 결과)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = OUTPUT_DIR / f"h100_experiment_{ts}.json"
    output_data = {
        "meta": experiment_meta,
        "results": all_results,
    }
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    # ============================================================
    # 결과 요약
    # ============================================================
    print(f"\n\n{'=' * 70}")
    print("  RESULTS SUMMARY")
    print(f"{'=' * 70}")

    for category in ["coding", "non-coding"]:
        cat_tasks = [t for t in TASKS if t["category"] == category]
        if not cat_tasks:
            continue

        metrics = METRICS_CODING if category == "coding" else METRICS_NONCODING
        cat_ids = {t["id"] for t in cat_tasks}

        print(f"\n  --- {category.upper()} ({len(cat_tasks)} tasks) ---")
        header = f"{'Condition':<44} | " + " | ".join(f"{m[:7]:>7}" for m in metrics) + f" | {'AVG':>5} | {'Chars':>6}"
        print(f"\n  {header}")
        print(f"  {'─' * len(header)}")

        for ck in ["raw_27b", "harness_27b", "claude_code"]:
            valid = [r for r in all_results
                     if r["condition"] == ck
                     and r["task_id"] in cat_ids
                     and "evaluation" in r
                     and "error" not in r.get("evaluation", {})]
            if not valid:
                print(f"  {CONDITIONS[ck]['name']:<44} | (no valid results)")
                continue

            metric_avgs = {}
            for m in metrics:
                scores = [r["evaluation"][m]["score"] for r in valid
                          if m in r["evaluation"] and isinstance(r["evaluation"][m], dict)]
                metric_avgs[m] = round(sum(scores) / len(scores), 1) if scores else 0

            all_s = list(metric_avgs.values())
            overall = round(sum(all_s) / len(all_s), 2) if all_s else 0
            avg_chars = round(sum(r.get("response_length", 0) for r in valid) / len(valid))

            row = (f"  {CONDITIONS[ck]['name']:<44} | "
                   + " | ".join(f"{metric_avgs.get(m,0):>7}" for m in metrics)
                   + f" | {overall:>5} | {avg_chars:>6}")
            print(row)

    # 전체 평균
    print(f"\n  --- OVERALL (all {len(TASKS)} tasks) ---")
    for ck in ["raw_27b", "harness_27b", "claude_code"]:
        valid = [r for r in all_results
                 if r["condition"] == ck
                 and "evaluation" in r
                 and "error" not in r.get("evaluation", {})]
        if not valid:
            continue
        all_scores = []
        for r in valid:
            ev = r["evaluation"]
            for v in ev.values():
                if isinstance(v, dict) and "score" in v:
                    all_scores.append(v["score"])
        overall = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0
        avg_chars = round(sum(r.get("response_length", 0) for r in valid) / len(valid))
        print(f"  {CONDITIONS[ck]['name']:<44} | AVG: {overall:>5} | Chars: {avg_chars:>6}")

    print(f"\n  결과 저장: {outfile}")
    return str(outfile)


if __name__ == "__main__":
    main()
