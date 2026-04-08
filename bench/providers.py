"""
API 프로바이더 래퍼 — 모델 엔드포인트 추가/변경은 여기서만.

지원하는 프로바이더:
  openai      — OpenAI API (GPT-4o 등)
  alibaba     — Alibaba Cloud DashScope (Qwen 모델)
  vllm        — 자체 호스팅 vLLM (OpenAI 호환)
  claude_cli  — Claude Code CLI (claude -p)

새 프로바이더 추가하려면:
  1. call_* 함수 하나 추가
  2. PROVIDER_REGISTRY에 등록
"""

import os
import re
import time
import subprocess
import requests


def _strip_think(text: str) -> str:
    """Qwen3.5 등 thinking 모드 모델의 <think>...</think> 제거."""
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()


def call_openai_compat(
    system_prompt: str,
    user_prompt: str,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    timeout: int = 300,
) -> dict:
    """OpenAI 호환 엔드포인트 범용 호출 (OpenAI / Alibaba / vLLM 모두 사용)."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    start = time.time()
    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
            timeout=timeout,
        )
        elapsed = round(time.time() - start, 2)
        data = resp.json()

        if "error" in data:
            return {"error": str(data["error"]), "elapsed": elapsed}

        content = _strip_think(data["choices"][0]["message"]["content"])
        usage = data.get("usage", {})
        return {
            "response": content,
            "response_length": len(content),
            "elapsed": elapsed,
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "model": model,
        }
    except Exception as e:
        return {"error": str(e), "elapsed": round(time.time() - start, 2)}


def call_claude_cli(
    system_prompt: str,
    user_prompt: str,
    model: str = "claude-opus-4-6",
    timeout: int = 120,
) -> dict:
    """Claude Code CLI 호출 (claude -p)."""
    cmd = ["claude", "-p", "--output-format", "json"]
    if model:
        cmd += ["--model", model]

    full_input = user_prompt
    if system_prompt:
        # Claude CLI는 시스템 프롬프트를 직접 주입할 수 없으므로 앞에 붙임
        full_input = f"<system>\n{system_prompt}\n</system>\n\n{user_prompt}"

    start = time.time()
    try:
        r = subprocess.run(cmd, input=full_input, capture_output=True, text=True, timeout=timeout)
        elapsed = round(time.time() - start, 2)

        if r.returncode != 0:
            return {"error": r.stderr.strip()[:300], "elapsed": elapsed}

        import json
        try:
            out = json.loads(r.stdout)
            content = out.get("result", r.stdout.strip())
        except Exception:
            content = r.stdout.strip()

        return {
            "response": content,
            "response_length": len(content),
            "elapsed": elapsed,
            "input_tokens": 0,
            "output_tokens": 0,
            "model": model,
        }
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "elapsed": timeout}
    except Exception as e:
        return {"error": str(e), "elapsed": round(time.time() - start, 2)}


# ── 프로바이더 레지스트리 ────────────────────────────────────────────────────
# run.py가 이 테이블을 읽어서 적절한 call_* 함수를 선택합니다.
# 새 프로바이더를 추가하려면 함수 하나 만들고 여기에 등록하면 됩니다.

def _make_openai_caller(base_url: str, api_key_env: str, default_model: str):
    """OpenAI 호환 프로바이더 팩토리."""
    def caller(system_prompt, user_prompt, model=None, **kw):
        return call_openai_compat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            base_url=base_url,
            api_key=os.getenv(api_key_env, ""),
            model=model or default_model,
            **kw,
        )
    return caller


PROVIDERS: dict[str, dict] = {
    "alibaba": {
        "description": "Alibaba Cloud DashScope (Qwen 모델 권장)",
        "default_model": "qwen3.5-27b",
        "caller": _make_openai_caller(
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            api_key_env="DASHSCOPE_API_KEY",
            default_model="qwen3.5-27b",
        ),
    },
    "openai": {
        "description": "OpenAI API (GPT-4o 등)",
        "default_model": "gpt-4o",
        "caller": _make_openai_caller(
            base_url="https://api.openai.com/v1",
            api_key_env="OPENAI_API_KEY",
            default_model="gpt-4o",
        ),
    },
    "vllm": {
        "description": "자체 호스팅 vLLM (VLLM_BASE_URL 환경변수 필요)",
        "default_model": os.getenv("VLLM_MODEL", "Qwen3.5-27b"),
        "caller": _make_openai_caller(
            base_url=os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1"),
            api_key_env="VLLM_API_KEY",
            default_model=os.getenv("VLLM_MODEL", "Qwen3.5-27b"),
        ),
    },
    "claude_cli": {
        "description": "Claude Code CLI (claude -p, 로컬 설치 필요)",
        "default_model": "claude-opus-4-6",
        "caller": lambda system_prompt, user_prompt, model=None, **kw: call_claude_cli(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model or "claude-opus-4-6",
        ),
    },
    # ── 여기에 자신만의 프로바이더를 추가하세요 ──────────────────────────────
    # "my_provider": {
    #     "description": "My custom endpoint",
    #     "default_model": "my-model",
    #     "caller": _make_openai_caller(
    #         base_url="http://my-host:8000/v1",
    #         api_key_env="MY_API_KEY",
    #         default_model="my-model",
    #     ),
    # },
}
