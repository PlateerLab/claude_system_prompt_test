#!/usr/bin/env python3
"""
실험 4 보충: Claude Opus 4.6 CLI 추가 (Col4)
기존 vanilla_experiment 결과에 합산
"""

import json
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)

OUTPUT_DIR = Path(__file__).parent / "results"

TASKS = [
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


def main():
    print("=" * 70)
    print("  실험 4 보충: Claude Opus 4.6 CLI (Col4)")
    print(f"  과제 {len(TASKS)}개, 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    all_results = []

    for i, task in enumerate(TASKS):
        print(f"\n  [{i+1}/{len(TASKS)}] [{task['category'].upper()}] {task['name']}")

        gen = call_claude_cli(task["prompt"])

        entry = {
            "task_id": task["id"],
            "task_name": task["name"],
            "task_category": task["category"],
            "task_prompt": task["prompt"],
            "condition": "claude_opus",
            "condition_name": "Col4: Claude Opus 4.6 CLI",
            "system_prompt_used": "(claude cli built-in harness)",
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
            "model": gen.get("model", "claude-opus-4-6"),
            "cost_usd": gen.get("cost_usd", 0),
        })
        print(f"    ✓ GEN: {gen['response_length']} chars, {gen['elapsed']}s, "
              f"{gen.get('output_tokens',0)} tok, ${gen.get('cost_usd',0)}")

        print(f"    ⏳ Evaluating...")
        ev = evaluate_with_claude(task, gen["response"], "Col4: Claude Opus 4.6 CLI")
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

    # 저장
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = OUTPUT_DIR / f"vanilla_claude_supplement_{ts}.json"
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump({"meta": {"experiment": "vanilla_claude_supplement", "timestamp": datetime.now().isoformat()}, "results": all_results}, f, ensure_ascii=False, indent=2)

    # 요약
    valid = [r for r in all_results if "evaluation" in r and "error" not in r.get("evaluation", {})]
    if valid:
        all_scores = []
        for r in valid:
            for v in r["evaluation"].values():
                if isinstance(v, dict) and "score" in v:
                    all_scores.append(v["score"])
        avg = round(sum(all_scores) / len(all_scores), 2)
        avg_chars = round(sum(r.get("response_length", 0) for r in valid) / len(valid))
        avg_tokens = round(sum(r.get("output_tokens", 0) for r in valid) / len(valid))
        avg_time = round(sum(r.get("elapsed", 0) for r in valid) / len(valid), 1)
        avg_cost = round(sum(r.get("cost_usd", 0) for r in valid) / len(valid), 4)
        print(f"\n{'=' * 70}")
        print(f"  Col4: Claude Opus 4.6 CLI")
        print(f"  AVG: {avg} | Chars: {avg_chars} | Tok: {avg_tokens} | Time: {avg_time}s | Cost: ${avg_cost}")
        print(f"{'=' * 70}")

    print(f"\n  저장: {outfile}")
    return str(outfile)


if __name__ == "__main__":
    main()
