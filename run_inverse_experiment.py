#!/usr/bin/env python3
"""
실험: Distilled 모델에서 하니스 효과가 Distillation 의존인지 프롬프트 자체의 힘인지 검증
=================================================================================

핵심 논리:
  - Distillation으로 행동이 고정됐다면 → 반대 지시를 줘도 여전히 간결해야 함
  - 프롬프트를 따르는 거라면 → 반대 지시를 주면 verbose해져야 함

설계: 4개 조건
  A: Raw (시스템 프롬프트 없음) — baseline
  B: Claude Code 하니스 — "하지 마라" 제약
  C: 반대 지시 (Inverse Prompt) — "상세히 해라" 지시 (핵심 대조군)
  D: 무관한 지시 — "pandas를 써라" (프롬프트 반응성 확인)

모델: Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled (vLLM)
평가: Claude-as-judge (6개 기준, 1-10점)
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

VLLM_URL = "http://118.223.251.22:10051/v1/chat/completions"
VLLM_MODEL = "Qwen3.5-27b"

# ============================================================
# 4개 시스템 프롬프트
# ============================================================

HARNESS_PROMPT = """You are an interactive agent that helps users with software engineering tasks.

# Doing tasks
The user will primarily request you to perform software engineering tasks. These may include solving bugs, adding new functionality, refactoring code, explaining code, and more. When given an unclear or generic instruction, consider it in the context of these software engineering tasks.

You are highly capable and often allow users to complete ambitious tasks that would otherwise be too complex or take too long. You should defer to user judgement about whether a task is too large to attempt.

In general, do not propose changes to code you haven't read. If a user asks about or wants you to modify a file, read it first. Understand existing code before suggesting modifications.

Do not create files unless they're absolutely necessary for achieving your goal. Generally prefer editing an existing file to creating a new one, as this prevents file bloat and builds on existing work more effectively.

Don't add features, refactor code, or make "improvements" beyond what was asked. A bug fix doesn't need surrounding code cleaned up. A simple feature doesn't need extra configurability. Don't add docstrings, comments, or type annotations to code you didn't change. Only add comments where the logic isn't self-evident.

Don't add error handling, fallbacks, or validation for scenarios that can't happen. Trust internal code and framework guarantees. Only validate at system boundaries (user input, external APIs). Don't use feature flags or backwards-compatibility shims when you can just change the code.

Don't create helpers, utilities, or abstractions for one-time operations. Don't design for hypothetical future requirements. The right amount of complexity is what the task actually requires — no speculative abstractions, but no half-finished implementations either. Three similar lines of code is better than a premature abstraction.

Be careful not to introduce security vulnerabilities such as command injection, XSS, SQL injection, and other OWASP top 10 vulnerabilities. If you notice that you wrote insecure code, immediately fix it. Prioritize writing safe, secure, and correct code.

# Output efficiency
IMPORTANT: Go straight to the point. Try the simplest approach first without going in circles. Do not overdo it. Be extra concise.

Keep your text output brief and direct. Lead with the answer or action, not the reasoning. Skip filler words, preamble, and unnecessary transitions. Do not restate what the user said — just do it. When explaining, include only what is necessary for the user to understand.

If you can say it in one sentence, don't use three. Prefer short, direct sentences over long explanations."""

INVERSE_PROMPT = """You are a highly detailed and thorough software engineering assistant.

# Coding standards
When writing code, ALWAYS follow these practices:
- Add comprehensive docstrings to EVERY function and class explaining purpose, parameters, return values, and examples
- Add type hints to ALL function parameters and return values (use typing module: Optional, List, Dict, Union, etc.)
- Add inline comments explaining the reasoning behind non-trivial logic
- Add error handling for ALL possible edge cases, even unlikely ones
- Create helper functions and utility methods to keep code DRY and modular
- Add input validation for all parameters
- Include a "How to Use" section after the code with usage examples and curl commands if applicable

# Output format
- Before the code, explain your design decisions and architecture choices
- After the code, provide:
  1. Implementation details explaining each component
  2. Usage examples with expected output
  3. Potential improvements and future considerations
  4. Error handling strategy explanation

Be as verbose and detailed as possible. The user benefits from thorough explanations."""

IRRELEVANT_PROMPT = """You are a data science specialist. You MUST use pandas for ALL data operations.

# Strict rules
- Use pandas DataFrames as the primary data structure, even for simple key-value storage
- Import numpy and pandas at the top of every file
- Use pd.DataFrame() instead of dict or list for storing data
- Use df.iterrows() for iteration instead of regular loops
- Add matplotlib/seaborn visualization code when relevant
- Structure code as a Jupyter notebook style with markdown explanations in comments

Always prefer pandas operations over native Python data structures."""

CONDITIONS = {
    "A_raw": {
        "name": "A: Raw (no system prompt)",
        "system": "",
    },
    "B_harness": {
        "name": "B: Claude Code Harness",
        "system": HARNESS_PROMPT,
    },
    "C_inverse": {
        "name": "C: Inverse Prompt (verbose)",
        "system": INVERSE_PROMPT,
    },
    "D_irrelevant": {
        "name": "D: Irrelevant (pandas)",
        "system": IRRELEVANT_PROMPT,
    },
}

TASKS = [
    {
        "id": "cache_system",
        "name": "LRU Cache with TTL",
        "prompt": """Write a Python LRU cache with TTL (time-to-live) expiration:
- get(key) - returns value or None if expired/missing
- put(key, value, ttl_seconds=60) - stores with expiration
- Maximum capacity with LRU eviction when full
- Thread-safe

Implement as a single class LRUCache. Include a brief usage example.""",
    },
    {
        "id": "rest_api",
        "name": "Flask REST API",
        "prompt": """Write a Python Flask REST API for a simple todo app:
- GET /todos - list all todos
- POST /todos - create a todo (title required, optional: description, due_date)
- GET /todos/<id> - get single todo
- PUT /todos/<id> - update a todo
- DELETE /todos/<id> - delete a todo

Use in-memory storage (dict). Return proper HTTP status codes and JSON responses. Single file.""",
    },
    {
        "id": "task_queue",
        "name": "Thread-Safe Task Queue",
        "prompt": """Write a Python thread-safe task queue with priority (1-10), retry on failure (max 3), and task status tracking. Classes: TaskQueue, Task, Worker. Single file, brief example.""",
    },
]


def call_vllm(system_prompt, user_prompt):
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": "/nothink\n" + user_prompt})

    start = time.time()
    try:
        resp = requests.post(
            VLLM_URL,
            json={
                "model": VLLM_MODEL,
                "messages": messages,
                "max_tokens": 1500,
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
        }
    except Exception as e:
        return {"error": str(e), "elapsed": round(time.time() - start, 2)}


def evaluate_with_claude(task_prompt, response, condition_name):
    eval_prompt = f"""You are a strict code quality evaluator. Score this coding response on 6 criteria (1-10 each).

## Task
{task_prompt}

## Response (from: {condition_name})
{response[:8000]}

## Scoring criteria (be STRICT, especially on 3/4/5)
1. correctness: Does the code work correctly? Logic bugs? Missing features? (1=broken, 10=perfect)
2. efficiency: Is the algorithm sound and efficient? (1=poor, 10=optimal)
3. conciseness: Is the code free of unnecessary bloat? Penalize: unused imports, verbose variable names, unnecessary blank lines, redundant code (1=very bloated, 10=minimal)
4. no_overengineering: Did it avoid adding UNNECESSARY things? Penalize heavily: type hints not asked for, docstrings not asked for, error handling for impossible scenarios, unnecessary abstract classes/interfaces, design patterns that add complexity without value (1=heavily overengineered, 10=just what was asked)
5. response_bloat: Is the text response free of unnecessary prose? Penalize: long explanations before code, step-by-step reasoning not asked for, disclaimers, restating the problem (1=very bloated text, 10=mostly just code)
6. instruction_following: Did it follow instructions precisely? All required features implemented? (1=missed requirements, 10=perfect)

Return ONLY this JSON (no other text):
{{"correctness":{{"score":N,"reason":"one line"}}, "efficiency":{{"score":N,"reason":"one line"}}, "conciseness":{{"score":N,"reason":"one line"}}, "no_overengineering":{{"score":N,"reason":"one line"}}, "response_bloat":{{"score":N,"reason":"one line"}}, "instruction_following":{{"score":N,"reason":"one line"}}}}"""

    cmd = ["claude", "-p", "--model", "claude-opus-4-6", "--output-format", "json",
           "--system-prompt", "You are a code evaluator. Return ONLY valid JSON."]
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


def main():
    total = len(CONDITIONS) * len(TASKS)
    print("=" * 70)
    print("  Inverse Prompt Experiment")
    print("  Distilled 모델의 프롬프트 반응성 검증")
    print(f"  모델: {VLLM_MODEL}")
    print(f"  조건 {len(CONDITIONS)}개 x 과제 {len(TASKS)}개 = {total}회")
    print(f"  시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    all_results = []
    count = 0

    for task in TASKS:
        print(f"\n{'━' * 70}")
        print(f"  과제: {task['name']}")
        print(f"{'━' * 70}")

        for ck, cv in CONDITIONS.items():
            count += 1
            print(f"\n  [{count}/{total}] {cv['name']}")

            gen = call_vllm(cv["system"], task["prompt"])

            entry = {
                "task_id": task["id"],
                "task_name": task["name"],
                "condition": ck,
                "condition_name": cv["name"],
                "system_prompt_length": len(cv["system"]),
                "timestamp": datetime.now().isoformat(),
            }

            if "error" in gen:
                entry["error"] = gen["error"]
                print(f"    ERROR: {gen['error'][:100]}")
                all_results.append(entry)
                continue

            entry.update({
                "response": gen["response"],
                "response_length": gen["response_length"],
                "elapsed": gen["elapsed"],
                "input_tokens": gen.get("input_tokens", 0),
                "output_tokens": gen.get("output_tokens", 0),
            })
            print(f"    GEN: {gen['response_length']} chars, {gen['elapsed']}s, "
                  f"{gen.get('output_tokens',0)} tok")

            print(f"    Evaluating...")
            ev = evaluate_with_claude(task["prompt"], gen["response"], cv["name"])
            entry["evaluation"] = ev

            if "error" not in ev:
                scores = {k: v["score"] for k, v in ev.items() if isinstance(v, dict)}
                avg = round(sum(scores.values()) / len(scores), 1)
                print(f"    SCORES: {scores}")
                print(f"    AVG: {avg}/10")
            else:
                print(f"    EVAL ERROR: {ev.get('error','')[:100]}")

            all_results.append(entry)
            time.sleep(5)

    # 저장
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = OUTPUT_DIR / f"inverse_experiment_{ts}.json"
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    # ============================================================
    # 결과 요약
    # ============================================================
    print(f"\n\n{'=' * 70}")
    print("  RESULTS")
    print(f"{'=' * 70}")

    metrics_order = ["correctness", "efficiency", "conciseness",
                     "no_overengineering", "response_bloat", "instruction_following"]

    summary = {}
    for ck in CONDITIONS:
        valid = [r for r in all_results
                 if r["condition"] == ck
                 and "evaluation" in r
                 and "error" not in r.get("evaluation", {})]
        if not valid:
            continue

        metric_avgs = {}
        for m in metrics_order:
            scores = [r["evaluation"][m]["score"] for r in valid
                      if m in r["evaluation"] and isinstance(r["evaluation"][m], dict)]
            metric_avgs[m] = round(sum(scores) / len(scores), 1) if scores else 0

        all_s = [s for m in metrics_order for r in valid
                 if m in r.get("evaluation", {}) and isinstance(r["evaluation"].get(m), dict)
                 for s in [r["evaluation"][m]["score"]]]
        overall = round(sum(all_s) / len(all_s), 2) if all_s else 0

        avg_chars = round(sum(r["response_length"] for r in valid) / len(valid))
        avg_tokens = round(sum(r.get("output_tokens", 0) for r in valid) / len(valid))

        summary[ck] = {
            "metrics": metric_avgs,
            "overall": overall,
            "avg_chars": avg_chars,
            "avg_tokens": avg_tokens,
        }

    header = f"{'Condition':<35} | {'Correct':>7} | {'Effic':>5} | {'Concise':>7} | {'NoOver':>6} | {'Bloat':>5} | {'Follow':>6} | {'AVG':>5} | {'Chars':>6} | {'Tokens':>6}"
    print(f"\n  {header}")
    print(f"  {'─' * len(header)}")

    for ck in ["A_raw", "B_harness", "C_inverse", "D_irrelevant"]:
        if ck not in summary:
            continue
        s = summary[ck]
        m = s["metrics"]
        print(f"  {CONDITIONS[ck]['name']:<35} | "
              f"{m.get('correctness',0):>7} | "
              f"{m.get('efficiency',0):>5} | "
              f"{m.get('conciseness',0):>7} | "
              f"{m.get('no_overengineering',0):>6} | "
              f"{m.get('response_bloat',0):>5} | "
              f"{m.get('instruction_following',0):>6} | "
              f"{s['overall']:>5} | "
              f"{s['avg_chars']:>6} | "
              f"{s['avg_tokens']:>6}")

    # 핵심 분석
    print(f"\n  {'─' * 60}")
    print(f"  DISTILLATION vs PROMPT EFFECT ANALYSIS")
    print(f"  {'─' * 60}")

    if "A_raw" in summary and "C_inverse" in summary:
        raw_bloat = summary["A_raw"]["metrics"].get("response_bloat", 0)
        inv_bloat = summary["C_inverse"]["metrics"].get("response_bloat", 0)
        raw_over = summary["A_raw"]["metrics"].get("no_overengineering", 0)
        inv_over = summary["C_inverse"]["metrics"].get("no_overengineering", 0)
        raw_chars = summary["A_raw"]["avg_chars"]
        inv_chars = summary["C_inverse"]["avg_chars"]

        print(f"\n  [Test 1] Inverse prompt makes model MORE verbose?")
        print(f"    Raw response_bloat:     {raw_bloat}")
        print(f"    Inverse response_bloat: {inv_bloat}")
        print(f"    Raw avg chars:          {raw_chars}")
        print(f"    Inverse avg chars:      {inv_chars}")
        if inv_chars > raw_chars * 1.1:
            print(f"    --> YES: Model follows inverse prompt (+{round((inv_chars/raw_chars-1)*100)}% chars)")
            print(f"    --> CONCLUSION: Prompt effect, NOT distillation lock-in")
        else:
            print(f"    --> NO: Model ignores inverse prompt")
            print(f"    --> CONCLUSION: Possible distillation lock-in")

    if "B_harness" in summary and "C_inverse" in summary:
        har_bloat = summary["B_harness"]["metrics"].get("response_bloat", 0)
        inv_bloat = summary["C_inverse"]["metrics"].get("response_bloat", 0)
        har_over = summary["B_harness"]["metrics"].get("no_overengineering", 0)
        inv_over = summary["C_inverse"]["metrics"].get("no_overengineering", 0)

        print(f"\n  [Test 2] Harness vs Inverse: opposite behavior?")
        print(f"    Harness response_bloat:     {har_bloat} (higher=less bloat)")
        print(f"    Inverse response_bloat:     {inv_bloat}")
        print(f"    Harness no_overengineering: {har_over}")
        print(f"    Inverse no_overengineering: {inv_over}")
        gap = round(har_bloat - inv_bloat, 1)
        if gap > 2:
            print(f"    --> Gap: {gap} points — STRONG opposite behavior")
            print(f"    --> CONFIRMS: Model responds to prompt content, not distillation")
        elif gap > 0:
            print(f"    --> Gap: {gap} points — Moderate difference")
        else:
            print(f"    --> Gap: {gap} points — No meaningful difference")

    if "D_irrelevant" in summary:
        print(f"\n  [Test 3] Irrelevant prompt (pandas) compliance?")
        print(f"    Check responses manually for pandas/DataFrame usage")

    print(f"\n  Results saved: {outfile}")
    return str(outfile)


if __name__ == "__main__":
    main()
