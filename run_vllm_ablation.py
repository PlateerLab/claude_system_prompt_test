#!/usr/bin/env python3
"""
Ablation 실험: Default Chat Template의 Confounding Effect 분리
================================================================
리뷰어 피드백 대응:
  "Qwen 같은 vLLM 모델은 이미 먹고 들어가는 context가 있는데,
   이것을 바탕으로 시스템 프롬프트 실험하는 게 맞냐"

핵심 실험 설계:
  조건 A: default_template   — 모델 기본 chat template (Qwen default system)
  조건 B: no_system          — system 필드를 빈 문자열로 (template은 유지)
  조건 C: custom_on_default  — default system + custom system prompt 추가 (append)
  조건 D: custom_replace     — default 제거, custom system prompt만 (replace)
  조건 E: raw_custom         — chat template 완전 우회, raw prompt로 직접 제어

핵심 비교:
  D - B = custom system prompt의 순수 효과 (default template 통제)
  C - A = custom system prompt의 추가 효과 (default 위에 쌓기)
  E - D = chat template 자체의 효과 (같은 system prompt, template 유무 차이)
  A - B = default system prompt의 효과

사용법:
  # vLLM 서버가 localhost:8000에서 실행 중이어야 함
  # vllm serve Qwen/Qwen2.5-Coder-7B-Instruct --port 8000

  python run_vllm_ablation.py                              # 기본: localhost:8000
  python run_vllm_ablation.py --base-url http://host:8000  # 커스텀 URL
  python run_vllm_ablation.py --use-ollama                 # Ollama 사용
  python run_vllm_ablation.py --models qwen2.5-coder:7b,qwen2.5-coder:14b  # 여러 모델
  python run_vllm_ablation.py --use-ollama --no-eval  # 평가 없이 생성만 (빠른 테스트)
"""

import json
import time
import sys
import argparse
import requests
from datetime import datetime
from pathlib import Path
from textwrap import dedent

_builtin_print = __builtins__["print"] if isinstance(__builtins__, dict) else __builtins__.print
def log(msg=""):
    _builtin_print(msg, flush=True)

OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(exist_ok=True)

# ============================================================
# Custom System Prompt (Claude Code 스타일)
# ============================================================

CUSTOM_SYSTEM_PROMPT = dedent("""\
You are an interactive agent that helps users with software engineering tasks.

# Doing tasks
The user will primarily request you to perform software engineering tasks.
You are highly capable and often allow users to complete ambitious tasks.

Don't add features, refactor code, or make "improvements" beyond what was asked.
A bug fix doesn't need surrounding code cleaned up.
Don't add docstrings, comments, or type annotations to code you didn't change.
Only add comments where the logic isn't self-evident.

Don't add error handling, fallbacks, or validation for scenarios that can't happen.
Trust internal code and framework guarantees.
Only validate at system boundaries (user input, external APIs).

Don't create helpers, utilities, or abstractions for one-time operations.
Three similar lines of code is better than a premature abstraction.

# Output efficiency
IMPORTANT: Go straight to the point. Be extra concise.
Lead with the answer or action, not the reasoning.
If you can say it in one sentence, don't use three.""")


# ============================================================
# 5개 실험 조건 정의
# ============================================================

def build_conditions(default_system_prompt: str):
    """모델의 default system prompt를 받아 5개 조건 생성"""
    return {
        "A_default_template": {
            "name": "A. Default Template (모델 기본)",
            "description": "모델의 기본 chat template 그대로 사용",
            "system": default_system_prompt,
            "use_raw": False,
        },
        "B_no_system": {
            "name": "B. No System Prompt",
            "description": "system 필드를 빈 문자열로 설정 (template 구조는 유지)",
            "system": "",
            "use_raw": False,
        },
        "C_custom_on_default": {
            "name": "C. Default + Custom (Append)",
            "description": "기본 system prompt 뒤에 custom prompt 추가",
            "system": f"{default_system_prompt}\n\n{CUSTOM_SYSTEM_PROMPT}",
            "use_raw": False,
        },
        "D_custom_replace": {
            "name": "D. Custom Only (Replace)",
            "description": "default 제거, custom system prompt만 사용",
            "system": CUSTOM_SYSTEM_PROMPT,
            "use_raw": False,
        },
        "E_raw_custom": {
            "name": "E. Raw Prompt (Template 우회)",
            "description": "chat template 완전 우회, raw text로 직접 제어",
            "system": CUSTOM_SYSTEM_PROMPT,
            "use_raw": True,
        },
    }


# ============================================================
# 테스트 과제 (기존 실험과 동일 + 추가)
# ============================================================

TEST_CASES = [
    {
        "id": "algo_1",
        "category": "algorithm",
        "difficulty": "easy",
        "prompt": "Write a Python function `two_sum(nums, target)` that returns indices of two numbers that add up to target. Must be O(n) time complexity.",
    },
    {
        "id": "algo_2",
        "category": "algorithm",
        "difficulty": "medium",
        "prompt": "Write a Python function `merge_intervals(intervals)` that merges overlapping intervals. Input: list of [start, end] pairs. Return merged list.",
    },
    {
        "id": "bugfix_1",
        "category": "bugfix",
        "difficulty": "easy",
        "prompt": dedent("""\
            Fix the bug in this Python code. Only fix the bug, don't refactor or add features:

            ```python
            def flatten(nested_list):
                result = []
                for item in nested_list:
                    if type(item) == list:
                        result.extend(flatten(item))
                    else:
                        result.append(item)
                return result

            # Bug: flatten([1, [2, [3]], (4, 5)]) should return [1, 2, 3, (4, 5)]
            # But it fails with nested tuples and other iterables
            ```"""),
    },
    {
        "id": "bugfix_2",
        "category": "bugfix",
        "difficulty": "medium",
        "prompt": dedent("""\
            Fix the race condition in this Python code. Only fix the race condition, don't add features:

            ```python
            import threading

            class Counter:
                def __init__(self):
                    self.count = 0

                def increment(self):
                    current = self.count
                    self.count = current + 1

                def get_count(self):
                    return self.count
            ```"""),
    },
    {
        "id": "web_1",
        "category": "web",
        "difficulty": "medium",
        "prompt": "Write a Python FastAPI endpoint `POST /users` that creates a user with fields: name (str, required), email (str, required, must be valid email), age (int, optional). Return 201 with the created user. Use Pydantic for validation.",
    },
    {
        "id": "data_1",
        "category": "data",
        "difficulty": "easy",
        "prompt": "Write a Python function `group_by(items, key_fn)` that groups a list of items by the result of key_fn. Return a dict mapping keys to lists of items. Similar to itertools.groupby but doesn't require sorted input.",
    },
    {
        "id": "refactor_1",
        "category": "refactor",
        "difficulty": "medium",
        "prompt": dedent("""\
            Refactor this Python code to remove duplication. Keep the same behavior:

            ```python
            def get_active_users(db):
                users = db.query("SELECT * FROM users WHERE active = 1")
                result = []
                for user in users:
                    result.append({
                        'id': user['id'],
                        'name': user['name'],
                        'email': user['email'],
                        'display': f"{user['name']} <{user['email']}>"
                    })
                return result

            def get_admin_users(db):
                users = db.query("SELECT * FROM users WHERE role = 'admin'")
                result = []
                for user in users:
                    result.append({
                        'id': user['id'],
                        'name': user['name'],
                        'email': user['email'],
                        'display': f"{user['name']} <{user['email']}>"
                    })
                return result
            ```"""),
    },
    {
        "id": "refactor_2",
        "category": "refactor",
        "difficulty": "hard",
        "prompt": dedent("""\
            Simplify this Python code while keeping the same behavior:

            ```python
            def process_order(order):
                if order is not None:
                    if order.get('items') is not None:
                        if len(order['items']) > 0:
                            total = 0
                            for item in order['items']:
                                if item.get('price') is not None:
                                    if item.get('quantity') is not None:
                                        total += item['price'] * item['quantity']
                                    else:
                                        total += item['price'] * 1
                                else:
                                    pass
                            if order.get('discount') is not None:
                                total = total - (total * order['discount'] / 100)
                            return total
                        else:
                            return 0
                    else:
                        return 0
                else:
                    return 0
            ```"""),
    },
]


# ============================================================
# 알려진 모델의 Default System Prompt 목록
# ============================================================

KNOWN_DEFAULT_SYSTEM_PROMPTS = {
    "qwen": "You are Qwen, created by Alibaba Cloud. You are a helpful assistant.",
    "llama": "You are a helpful, respectful and honest assistant. Always answer as helpfully as possible, while being safe. Your answers should not include any harmful, unethical, racist, sexist, toxic, dangerous, or illegal content. Please ensure that your responses are socially unbiased and positive in nature.\n\nIf a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct. If you don't know the answer to a question, please don't share false information.",
    "mistral": "",
    "codestral": "",
    "deepseek": "You are a helpful assistant.",
    "yi": "You are a helpful assistant.",
    "gemma": "",
    "phi": "You are a helpful AI assistant.",
}


def detect_default_system_prompt(model_name: str) -> str:
    """모델 이름으로 default system prompt 추정"""
    model_lower = model_name.lower()
    for key, prompt in KNOWN_DEFAULT_SYSTEM_PROMPTS.items():
        if key in model_lower:
            return prompt
    return "You are a helpful assistant."


# ============================================================
# Chat Template 감지 및 Raw Prompt 생성
# ============================================================

CHAT_TEMPLATES = {
    "qwen": {
        "system_prefix": "<|im_start|>system\n",
        "system_suffix": "<|im_end|>\n",
        "user_prefix": "<|im_start|>user\n",
        "user_suffix": "<|im_end|>\n",
        "assistant_prefix": "<|im_start|>assistant\n",
        "stop_token": "<|im_end|>",
    },
    "llama": {
        "system_prefix": "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n",
        "system_suffix": "<|eot_id|>",
        "user_prefix": "<|start_header_id|>user<|end_header_id|>\n\n",
        "user_suffix": "<|eot_id|>",
        "assistant_prefix": "<|start_header_id|>assistant<|end_header_id|>\n\n",
        "stop_token": "<|eot_id|>",
    },
    "mistral": {
        "system_prefix": "[INST] ",
        "system_suffix": "\n",
        "user_prefix": "",
        "user_suffix": " [/INST]",
        "assistant_prefix": "",
        "stop_token": "</s>",
    },
    "deepseek": {
        "system_prefix": "<|begin_of_sentence|>",
        "system_suffix": "\n\n",
        "user_prefix": "User: ",
        "user_suffix": "\n\n",
        "assistant_prefix": "Assistant: ",
        "stop_token": "<|end_of_sentence|>",
    },
}


def detect_template(model_name: str) -> dict:
    """모델 이름으로 chat template 감지"""
    model_lower = model_name.lower()
    for key, tmpl in CHAT_TEMPLATES.items():
        if key in model_lower:
            return tmpl
    # fallback: ChatML (Qwen style)
    return CHAT_TEMPLATES["qwen"]


def build_raw_prompt(template: dict, system: str, user: str) -> str:
    """Chat template을 사용해 raw text prompt 직접 구성"""
    parts = []
    if system:
        parts.append(f"{template['system_prefix']}{system}{template['system_suffix']}")
    parts.append(f"{template['user_prefix']}{user}{template['user_suffix']}")
    parts.append(template["assistant_prefix"])
    return "".join(parts)


# ============================================================
# API 호출 (vLLM OpenAI-compatible / Ollama)
# ============================================================

def call_vllm_chat(base_url: str, model: str, system: str, user: str,
                   temperature: float = 0.3, max_tokens: int = 4096,
                   timeout: int = 300) -> dict:
    """vLLM OpenAI-compatible chat API 호출"""
    url = f"{base_url}/v1/chat/completions"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    start = time.time()
    try:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # Reasoning/thinking 모델의 경우 thinking 비활성화 (OOM 방지)
        if any(kw in model.lower() for kw in ["qwen3", "reasoning", "distill"]):
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        resp = requests.post(url, json=payload, timeout=timeout)
        elapsed = time.time() - start

        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}", "elapsed": elapsed}

        data = resp.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})
        content = choice["message"]["content"]
        return {
            "response": content,
            "response_length": len(content),
            "elapsed": round(elapsed, 2),
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "finish_reason": choice.get("finish_reason", "unknown"),
        }
    except Exception as e:
        return {"error": str(e), "elapsed": round(time.time() - start, 2)}


def call_vllm_raw(base_url: str, model: str, raw_prompt: str, stop_token: str,
                  temperature: float = 0.3, max_tokens: int = 4096,
                  timeout: int = 300) -> dict:
    """vLLM OpenAI-compatible completions API (raw text, template 우회)"""
    url = f"{base_url}/v1/completions"
    start = time.time()
    try:
        resp = requests.post(url, json={
            "model": model,
            "prompt": raw_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stop": [stop_token],
        }, timeout=timeout)
        elapsed = time.time() - start

        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}", "elapsed": elapsed}

        data = resp.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})
        content = choice["text"]
        return {
            "response": content,
            "response_length": len(content),
            "elapsed": round(elapsed, 2),
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "finish_reason": choice.get("finish_reason", "unknown"),
        }
    except Exception as e:
        return {"error": str(e), "elapsed": round(time.time() - start, 2)}


def call_ollama_chat(model: str, system: str, user: str,
                     temperature: float = 0.3, timeout: int = 600) -> dict:
    """Ollama chat API 호출"""
    url = "http://localhost:11434/api/chat"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    start = time.time()
    try:
        resp = requests.post(url, json={
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": 2048},
        }, timeout=timeout)
        elapsed = time.time() - start
        data = resp.json()
        content = data.get("message", {}).get("content", "")
        return {
            "response": content,
            "response_length": len(content),
            "elapsed": round(elapsed, 2),
            "input_tokens": data.get("prompt_eval_count", 0),
            "output_tokens": data.get("eval_count", 0),
            "finish_reason": "stop",
        }
    except Exception as e:
        return {"error": str(e), "elapsed": round(time.time() - start, 2)}


def call_ollama_raw(model: str, raw_prompt: str,
                    temperature: float = 0.3, timeout: int = 300) -> dict:
    """Ollama generate API (raw text, template 우회)"""
    url = "http://localhost:11434/api/generate"
    start = time.time()
    try:
        resp = requests.post(url, json={
            "model": model,
            "prompt": raw_prompt,
            "raw": True,  # template 우회
            "stream": False,
            "options": {"temperature": temperature, "num_predict": 2048},
        }, timeout=timeout)
        elapsed = time.time() - start
        data = resp.json()
        content = data.get("response", "")
        return {
            "response": content,
            "response_length": len(content),
            "elapsed": round(elapsed, 2),
            "input_tokens": data.get("prompt_eval_count", 0),
            "output_tokens": data.get("eval_count", 0),
            "finish_reason": "stop",
        }
    except Exception as e:
        return {"error": str(e), "elapsed": round(time.time() - start, 2)}


# ============================================================
# Rendered Prompt 로깅 (투명성)
# ============================================================

def log_rendered_prompt(condition_key: str, system: str, user: str,
                        model: str, template: dict, use_raw: bool) -> str:
    """실제 모델에 전달되는 prompt를 재구성하여 반환 (투명성 확보)"""
    if use_raw:
        return build_raw_prompt(template, system, user)
    else:
        # chat API 사용 시 template 적용된 형태 재구성
        return build_raw_prompt(template, system, user)


# ============================================================
# Claude를 judge로 사용
# ============================================================

import subprocess

EVAL_SYSTEM = "You are a strict code quality evaluator. Return ONLY valid JSON, no other text."

EVAL_TEMPLATE = """\
Evaluate this coding response on 6 criteria, each scored 1-10.

## Problem
{problem}

## Response to evaluate
{response}

## Scoring criteria
1. correctness: Does the code work correctly? (1=broken, 10=perfect)
2. efficiency: Is the algorithm/approach efficient? (1=very slow, 10=optimal)
3. conciseness: Is the response free of unnecessary code/explanations? (1=very bloated, 10=minimal and clean)
4. no_overengineering: Did it avoid adding things not asked for? (type hints, docstrings, error handling for impossible cases, extra classes/patterns) (1=heavily overengineered, 10=exactly what was asked)
5. response_bloat: Is the response free of unnecessary prose, preamble, disclaimers? (1=very bloated text, 10=code-focused and clean)
6. instruction_following: Did it follow the specific instructions precisely? (1=ignored instructions, 10=perfect adherence)

Return ONLY this JSON:
{{"correctness":{{"score":N,"reason":"..."}}, "efficiency":{{"score":N,"reason":"..."}}, "conciseness":{{"score":N,"reason":"..."}}, "no_overengineering":{{"score":N,"reason":"..."}}, "response_bloat":{{"score":N,"reason":"..."}}, "instruction_following":{{"score":N,"reason":"..."}}}}"""


def evaluate_with_claude(problem: str, response: str) -> dict:
    """Claude CLI로 코드 품질 평가"""
    prompt = EVAL_TEMPLATE.format(problem=problem, response=response[:5000])
    cmd = ["claude", "-p", "--model", "claude-opus-4-6", "--output-format", "json",
           "--system-prompt", EVAL_SYSTEM]
    try:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=90)
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

def run_experiment(args):
    models = [m.strip() for m in args.models.split(",")]

    for model in models:
        default_system = detect_default_system_prompt(model)
        conditions = build_conditions(default_system)
        template = detect_template(model)

        total = len(conditions) * len(TEST_CASES)
        log("=" * 70)
        log(f"  Ablation 실험: Default Chat Template Confounding 분리")
        log(f"  모델: {model}")
        log(f"  백엔드: {'Ollama' if args.use_ollama else 'vLLM'}")
        log(f"  Default System Prompt: {repr(default_system[:60])}...")
        log(f"  조건: {len(conditions)}개 | 문제: {len(TEST_CASES)}개 | 총: {total}회")
        log(f"  시작: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        log("=" * 70)

        # rendered prompt 샘플 로깅
        log("\n--- Rendered Prompt 샘플 (조건별 첫 번째 문제) ---")
        for ck, cv in conditions.items():
            rendered = log_rendered_prompt(
                ck, cv["system"], TEST_CASES[0]["prompt"],
                model, template, cv["use_raw"]
            )
            log(f"\n[{ck}] (처음 200자):")
            log(rendered[:200])
            log("...")
        log("-" * 70)

        all_results = []
        count = 0

        # 실험에 사용된 메타데이터 기록
        experiment_meta = {
            "model": model,
            "backend": "ollama" if args.use_ollama else "vllm",
            "base_url": args.base_url,
            "default_system_prompt": default_system,
            "custom_system_prompt": CUSTOM_SYSTEM_PROMPT,
            "chat_template": template,
            "temperature": 0.3,
            "max_tokens": 4096,
            "started_at": datetime.now().isoformat(),
            "conditions": {k: {"name": v["name"], "description": v["description"]}
                           for k, v in conditions.items()},
        }

        for tc in TEST_CASES:
            for ck, cv in conditions.items():
                count += 1
                label = f"[{count}/{total}] {ck:25s} | {tc['id']}"
                log(f"\n{label}")

                # API 호출
                if cv["use_raw"]:
                    raw_prompt = build_raw_prompt(template, cv["system"], tc["prompt"])
                    if args.use_ollama:
                        gen = call_ollama_raw(model, raw_prompt)
                    else:
                        gen = call_vllm_raw(args.base_url, model, raw_prompt,
                                            template["stop_token"])
                else:
                    if args.use_ollama:
                        gen = call_ollama_chat(model, cv["system"], tc["prompt"])
                    else:
                        gen = call_vllm_chat(args.base_url, model,
                                             cv["system"], tc["prompt"])

                entry = {
                    "model": model,
                    "condition": ck,
                    "condition_name": cv["name"],
                    "condition_description": cv["description"],
                    "use_raw": cv["use_raw"],
                    "system_prompt_length": len(cv["system"]),
                    "test_id": tc["id"],
                    "category": tc["category"],
                    "difficulty": tc["difficulty"],
                    "timestamp": datetime.now().isoformat(),
                    "rendered_prompt": log_rendered_prompt(
                        ck, cv["system"], tc["prompt"], model, template, cv["use_raw"]
                    ),
                }

                if "error" in gen:
                    entry["error"] = gen["error"]
                    log(f"  ERR: {gen['error'][:80]}")
                    all_results.append(entry)
                    continue

                entry.update({
                    "response": gen["response"],
                    "response_length": gen["response_length"],
                    "elapsed": gen["elapsed"],
                    "input_tokens": gen["input_tokens"],
                    "output_tokens": gen["output_tokens"],
                })
                log(f"  GEN: {gen['response_length']} chars, {gen['elapsed']}s, "
                      f"{gen['input_tokens']}+{gen['output_tokens']} tokens")

                # 평가
                if not args.no_eval:
                    ev = evaluate_with_claude(tc["prompt"], gen["response"])
                    entry["evaluation"] = ev
                    if "error" not in ev:
                        scores = {k: v["score"] for k, v in ev.items() if isinstance(v, dict)}
                        avg_score = round(sum(scores.values()) / len(scores), 1) if scores else 0
                        log(f"  EVAL: {scores} -> avg={avg_score}")
                    else:
                        log(f"  EVAL ERR: {ev.get('error', '')[:80]}")
                else:
                    log(f"  EVAL: skipped (--no-eval)")

                all_results.append(entry)
                time.sleep(0.3)

        experiment_meta["finished_at"] = datetime.now().isoformat()

        # 저장
        model_slug = model.replace("/", "_").replace(":", "_")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        outfile = OUTPUT_DIR / f"ablation_{model_slug}_{ts}.json"
        output_data = {
            "experiment_meta": experiment_meta,
            "results": all_results,
        }
        with open(outfile, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        log(f"\n저장 완료: {outfile}")

        # 요약 출력
        print_summary(conditions, all_results)


def print_summary(conditions, results):
    """실험 결과 요약 출력"""
    log("\n" + "=" * 70)
    log("  ABLATION RESULTS SUMMARY")
    log("=" * 70)

    cond_stats = {}
    for ck in conditions:
        cond_results = [r for r in results
                        if r["condition"] == ck
                        and "evaluation" in r
                        and "error" not in r.get("evaluation", {})]
        if not cond_results:
            cond_stats[ck] = None
            continue

        all_scores = []
        metric_scores = {}
        for r in cond_results:
            for metric, val in r["evaluation"].items():
                if isinstance(val, dict) and "score" in val:
                    all_scores.append(val["score"])
                    metric_scores.setdefault(metric, []).append(val["score"])

        avg_score = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0
        avg_chars = round(sum(r["response_length"] for r in cond_results) / len(cond_results))
        avg_tokens = round(sum(r["output_tokens"] for r in cond_results) / len(cond_results))

        cond_stats[ck] = {
            "avg_score": avg_score,
            "avg_chars": avg_chars,
            "avg_tokens": avg_tokens,
            "metrics": {k: round(sum(v)/len(v), 1) for k, v in metric_scores.items()},
            "n": len(cond_results),
        }
        log(f"\n  {conditions[ck]['name']}")
        log(f"    평균 점수: {avg_score}/10 (n={len(cond_results)})")
        log(f"    평균 응답: {avg_chars} chars / {avg_tokens} tokens")
        for m, scores in metric_scores.items():
            log(f"    {m}: {round(sum(scores)/len(scores), 1)}/10")

    # 핵심 비교
    log("\n" + "-" * 70)
    log("  KEY COMPARISONS (Ablation)")
    log("-" * 70)

    def safe_diff(a_key, b_key, label):
        a = cond_stats.get(a_key)
        b = cond_stats.get(b_key)
        if a and b and a["avg_score"] and b["avg_score"]:
            diff = round(a["avg_score"] - b["avg_score"], 2)
            pct = round((diff / b["avg_score"]) * 100, 1) if b["avg_score"] else 0
            log(f"  {label}")
            log(f"    점수 차이: {'+' if diff > 0 else ''}{diff} ({'+' if pct > 0 else ''}{pct}%)")
            char_diff = a["avg_chars"] - b["avg_chars"]
            log(f"    응답 길이 차이: {'+' if char_diff > 0 else ''}{char_diff} chars")

    safe_diff("D_custom_replace", "B_no_system",
              "D - B = Custom System Prompt의 순수 효과:")
    safe_diff("C_custom_on_default", "A_default_template",
              "C - A = Default 위에 Custom 추가 효과:")
    safe_diff("A_default_template", "B_no_system",
              "A - B = Default System Prompt의 효과:")
    safe_diff("E_raw_custom", "D_custom_replace",
              "E - D = Chat Template 자체의 효과:")


def main():
    parser = argparse.ArgumentParser(
        description="Ablation: Default Chat Template Confounding 분리 실험")
    parser.add_argument("--base-url", default="http://localhost:8000",
                        help="vLLM 서버 URL (default: http://localhost:8000)")
    parser.add_argument("--models", default="qwen2.5-coder:7b",
                        help="모델 이름 (쉼표로 구분, default: qwen2.5-coder:7b)")
    parser.add_argument("--use-ollama", action="store_true",
                        help="vLLM 대신 Ollama 사용")
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--no-eval", action="store_true",
                        help="평가 없이 생성만 (빠른 테스트)")
    args = parser.parse_args()

    run_experiment(args)


if __name__ == "__main__":
    main()
