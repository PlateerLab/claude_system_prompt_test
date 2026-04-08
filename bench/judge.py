"""
LLM-as-Judge 평가 모듈.

평가 모델: Claude Code CLI (claude -p)
각 응답을 6개 기준 1-10점으로 채점, JSON 반환.
"""

import json
import subprocess

# ── 평가 기준 ─────────────────────────────────────────────────────────────────

METRICS_CODING = [
    "correctness", "efficiency", "conciseness",
    "no_overengineering", "response_bloat", "instruction_following",
]

METRICS_NONCODING = [
    "accuracy", "completeness", "conciseness",
    "no_overexplaining", "response_bloat", "actionability",
]

_PROMPT_CODING = """You are a strict code quality evaluator. Score this coding response on 6 criteria (1-10 each).

## Task
{task_prompt}

## Response (from: {condition_name})
{response}

## Scoring criteria (be STRICT, especially on 3/4/5)
1. correctness: Does the code work correctly? Logic bugs? Missing features? (1=broken, 10=perfect)
2. efficiency: Is the algorithm sound and efficient? (1=poor, 10=optimal)
3. conciseness: Is the code free of unnecessary bloat? Penalize: unused imports, redundant code (1=very bloated, 10=minimal)
4. no_overengineering: Did it avoid adding UNNECESSARY things? Penalize heavily: type hints not asked for, docstrings not asked for, error handling for impossible scenarios (1=heavily overengineered, 10=just what was asked)
5. response_bloat: Is the text response free of unnecessary prose? Penalize: long explanations before code, disclaimers, restating the problem (1=very bloated text, 10=mostly just code)
6. instruction_following: Did it follow instructions precisely? All required features implemented? (1=missed requirements, 10=perfect)

Return ONLY this JSON (no other text):
{{"correctness":{{"score":N,"reason":"one line"}}, "efficiency":{{"score":N,"reason":"one line"}}, "conciseness":{{"score":N,"reason":"one line"}}, "no_overengineering":{{"score":N,"reason":"one line"}}, "response_bloat":{{"score":N,"reason":"one line"}}, "instruction_following":{{"score":N,"reason":"one line"}}}}"""

_PROMPT_NONCODING = """You are a strict response quality evaluator. Score this non-coding response on 6 criteria (1-10 each).

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


def _call_judge(prompt: str, judge_model: str = "claude-opus-4-6") -> str:
    cmd = ["claude", "-p", "--output-format", "text", "--model", judge_model]
    try:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=120)
        return r.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"


def evaluate(task: dict, response: str, condition_name: str, judge_model: str = "claude-opus-4-6") -> dict:
    """
    응답을 judge로 채점해 결과 dict 반환.

    반환:
      {
        "scores":  {"criterion": score, ...},
        "reasons": {"criterion": "one line reason", ...},
        "average": float,
      }
    또는 파싱 실패 시:
      {"error": str, "raw": str}
    """
    is_coding = task["category"] == "coding"
    metrics = METRICS_CODING if is_coding else METRICS_NONCODING
    template = _PROMPT_CODING if is_coding else _PROMPT_NONCODING

    prompt = template.format(
        task_prompt=task["prompt"],
        condition_name=condition_name,
        response=response[:8000],
    )

    raw = _call_judge(prompt, judge_model)

    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        parsed = json.loads(raw[start:end])
        scores = {m: parsed[m]["score"] for m in metrics if m in parsed}
        reasons = {m: parsed[m].get("reason", "") for m in metrics if m in parsed}
        avg = round(sum(scores.values()) / len(scores), 2) if scores else 0.0
        return {"scores": scores, "reasons": reasons, "average": avg}
    except Exception as e:
        return {"error": str(e), "raw": raw[:500]}
