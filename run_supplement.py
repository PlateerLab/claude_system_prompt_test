#!/usr/bin/env python3
"""C, D 조건 보충 실험 (max_tokens=800)"""
import requests, time, json, subprocess, sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)
VLLM_URL = "http://118.223.251.22:10051/v1/chat/completions"
OUTPUT_DIR = Path(__file__).parent / "results"

INVERSE_PROMPT = """You are a highly detailed and thorough software engineering assistant.
When writing code, ALWAYS follow these practices:
- Add comprehensive docstrings to EVERY function and class
- Add type hints to ALL function parameters and return values
- Add inline comments explaining non-trivial logic
- Add error handling for ALL possible edge cases
- Create helper functions to keep code DRY
- Include a "How to Use" section after the code with usage examples
Be as verbose and detailed as possible."""

IRRELEVANT_PROMPT = """You are a data science specialist. You MUST use pandas for ALL data operations.
- Use pandas DataFrames as the primary data structure, even for simple key-value storage
- Import numpy and pandas at the top of every file
- Use pd.DataFrame() instead of dict or list for storing data
Always prefer pandas operations over native Python data structures."""

CONDITIONS = {
    "C_inverse": {"name": "C: Inverse Prompt (verbose)", "system": INVERSE_PROMPT},
    "D_irrelevant": {"name": "D: Irrelevant (pandas)", "system": IRRELEVANT_PROMPT},
}

TASKS = [
    {"id": "cache_system", "name": "LRU Cache with TTL",
     "prompt": "Write a Python LRU cache with TTL. get/put methods. Thread-safe. Single class. Brief example."},
    {"id": "rest_api", "name": "Flask REST API",
     "prompt": "Write a Python Flask REST API for a todo app. GET/POST/PUT/DELETE /todos. In-memory dict. Single file."},
]

def call_vllm(system_prompt, user_prompt):
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": "/nothink\n" + user_prompt})
    start = time.time()
    try:
        r = requests.post(VLLM_URL, json={
            "model": "Qwen3.5-27b", "messages": messages,
            "max_tokens": 800, "temperature": 0.3,
            "chat_template_kwargs": {"enable_thinking": False}
        }, timeout=120)
        elapsed = time.time() - start
        d = r.json()
        if "error" in d:
            return {"error": d["error"], "elapsed": round(elapsed, 2)}
        content = d["choices"][0]["message"]["content"]
        usage = d.get("usage", {})
        return {"response": content, "response_length": len(content), "elapsed": round(elapsed, 2),
                "input_tokens": usage.get("prompt_tokens", 0), "output_tokens": usage.get("completion_tokens", 0)}
    except Exception as e:
        return {"error": str(e), "elapsed": round(time.time() - start, 2)}

def evaluate_with_claude(task_prompt, response, condition_name):
    eval_prompt = f"""You are a strict code quality evaluator. Score this coding response on 6 criteria (1-10 each).
## Task
{task_prompt}
## Response (from: {condition_name})
{response[:8000]}
## Scoring criteria (be STRICT)
1. correctness: Does the code work correctly? (1=broken, 10=perfect)
2. efficiency: Is the algorithm efficient? (1=poor, 10=optimal)
3. conciseness: Free of unnecessary bloat? (1=very bloated, 10=minimal)
4. no_overengineering: Avoided unnecessary additions? (1=heavily overengineered, 10=just what was asked)
5. response_bloat: Free of unnecessary prose? (1=very bloated text, 10=mostly just code)
6. instruction_following: Followed instructions precisely? (1=missed requirements, 10=perfect)
Return ONLY this JSON:
{{"correctness":{{"score":N,"reason":"one line"}}, "efficiency":{{"score":N,"reason":"one line"}}, "conciseness":{{"score":N,"reason":"one line"}}, "no_overengineering":{{"score":N,"reason":"one line"}}, "response_bloat":{{"score":N,"reason":"one line"}}, "instruction_following":{{"score":N,"reason":"one line"}}}}"""
    cmd = ["claude", "-p", "--model", "claude-opus-4-6", "--output-format", "json", "--system-prompt", "You are a code evaluator. Return ONLY valid JSON."]
    try:
        r = subprocess.run(cmd, input=eval_prompt, capture_output=True, text=True, timeout=90)
        if r.returncode != 0: return {"error": r.stderr[:200]}
        try:
            out = json.loads(r.stdout)
            text = out.get("result", r.stdout)
        except json.JSONDecodeError:
            text = r.stdout.strip()
        start = text.find("{"); end = text.rfind("}") + 1
        if start >= 0 and end > start: return json.loads(text[start:end])
        return {"error": "no_json", "raw": text[:300]}
    except Exception as e:
        return {"error": str(e)}

results = []
total = len(CONDITIONS) * len(TASKS)
count = 0
print(f"Supplement experiment: C, D conditions, max_tokens=800")

for task in TASKS:
    print(f"\n  Task: {task['name']}")
    for ck, cv in CONDITIONS.items():
        count += 1
        print(f"  [{count}/{total}] {cv['name']}")
        gen = call_vllm(cv["system"], task["prompt"])
        entry = {"task_id": task["id"], "task_name": task["name"], "condition": ck,
                 "condition_name": cv["name"], "timestamp": datetime.now().isoformat()}
        if "error" in gen:
            entry["error"] = gen["error"]
            print(f"    ERROR: {gen['error'][:80]}")
            results.append(entry)
            time.sleep(10)
            continue
        entry.update({"response": gen["response"], "response_length": gen["response_length"],
                      "elapsed": gen["elapsed"], "input_tokens": gen.get("input_tokens", 0),
                      "output_tokens": gen.get("output_tokens", 0)})
        print(f"    GEN: {gen['response_length']} chars, {gen['elapsed']}s, {gen.get('output_tokens',0)} tok")
        print(f"    Evaluating...")
        ev = evaluate_with_claude(task["prompt"], gen["response"], cv["name"])
        entry["evaluation"] = ev
        if "error" not in ev:
            scores = {k: v["score"] for k, v in ev.items() if isinstance(v, dict)}
            avg = round(sum(scores.values()) / len(scores), 1)
            print(f"    SCORES: {scores}")
            print(f"    AVG: {avg}/10")
        results.append(entry)
        time.sleep(10)

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
outfile = OUTPUT_DIR / f"inverse_supplement_{ts}.json"
with open(outfile, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nSaved: {outfile}")
