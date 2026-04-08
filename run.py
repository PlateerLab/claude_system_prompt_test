#!/usr/bin/env python3
"""
harness-bench — Claude Code 하니스 효과 실험 러너

사용법:
  # 기본 (모든 조건, 모든 과제, alibaba qwen3.5-27b)
  python run.py

  # 조건 선택
  python run.py --conditions raw restrictions_only

  # 과제 선택
  python run.py --tasks coding_group_by coding_lru_cache

  # 프로바이더 & 모델 변경
  python run.py --provider openai --model gpt-4o
  python run.py --provider vllm --model Llama-3-8B

  # judge 모델 변경 (기본: claude-opus-4-6)
  python run.py --judge-model claude-sonnet-4-6

  # judge 비활성화 (응답만 수집, 나중에 채점)
  python run.py --no-judge

  # 목록 보기
  python run.py --list-conditions
  python run.py --list-tasks
  python run.py --list-providers

  # 조건/과제 조합 예시
  python run.py --provider alibaba --conditions raw continuous --tasks coding_group_by non_coding_redis_pubsub
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.stdout.reconfigure(line_buffering=True)

from bench.harnesses import CONDITIONS
from bench.tasks import TASKS, TASKS_BY_ID
from bench.providers import PROVIDERS
from bench.judge import evaluate

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="harness-bench: 시스템 프롬프트 형식이 LLM 성능에 미치는 영향 실험",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--conditions", nargs="+", metavar="KEY",
        help="실험할 조건 키 (기본: 모두). bench/harnesses.py에서 추가/제거",
    )
    p.add_argument(
        "--tasks", nargs="+", metavar="ID",
        help="실험할 과제 ID (기본: 모두). bench/tasks.py에서 추가/제거",
    )
    p.add_argument(
        "--provider", default="alibaba",
        choices=list(PROVIDERS.keys()),
        help="사용할 API 프로바이더 (기본: alibaba)",
    )
    p.add_argument(
        "--model", default=None,
        help="모델명. 생략 시 프로바이더 기본값 사용",
    )
    p.add_argument(
        "--judge-model", default="claude-opus-4-6",
        help="LLM judge 모델 (기본: claude-opus-4-6)",
    )
    p.add_argument(
        "--no-judge", action="store_true",
        help="judge 평가 건너뜀 — 응답만 수집",
    )
    p.add_argument(
        "--temperature", type=float, default=0.3,
        help="sampling temperature (기본: 0.3)",
    )
    p.add_argument(
        "--output", default=None,
        help="결과 JSON 저장 경로 (기본: results/run_TIMESTAMP.json)",
    )
    p.add_argument("--list-conditions", action="store_true", help="사용 가능한 조건 목록")
    p.add_argument("--list-tasks", action="store_true", help="사용 가능한 과제 목록")
    p.add_argument("--list-providers", action="store_true", help="사용 가능한 프로바이더 목록")
    return p.parse_args()


def list_conditions():
    print("\n사용 가능한 조건 (bench/harnesses.py에서 수정):\n")
    for key, cond in CONDITIONS.items():
        tok = len(cond["system"].split()) if cond["system"] else 0
        print(f"  {key:<20} — {cond['description']}  (~{tok} words)")
    print()


def list_tasks():
    print("\n사용 가능한 과제 (bench/tasks.py에서 수정):\n")
    for task in TASKS:
        print(f"  {task['id']:<35} [{task['category']}]  {task['name']}")
    print()


def list_providers():
    print("\n사용 가능한 프로바이더 (bench/providers.py에서 수정):\n")
    for key, prov in PROVIDERS.items():
        print(f"  {key:<15} — {prov['description']}  (기본 모델: {prov['default_model']})")
    print()


# ── 실험 루프 ─────────────────────────────────────────────────────────────────

def run(args):
    # 조건 선택
    if args.conditions:
        unknown = [k for k in args.conditions if k not in CONDITIONS]
        if unknown:
            print(f"[오류] 알 수 없는 조건: {unknown}")
            print("  python run.py --list-conditions")
            sys.exit(1)
        selected_conditions = {k: CONDITIONS[k] for k in args.conditions}
    else:
        selected_conditions = CONDITIONS

    # 과제 선택
    if args.tasks:
        unknown = [t for t in args.tasks if t not in TASKS_BY_ID]
        if unknown:
            print(f"[오류] 알 수 없는 과제: {unknown}")
            print("  python run.py --list-tasks")
            sys.exit(1)
        selected_tasks = [TASKS_BY_ID[t] for t in args.tasks]
    else:
        selected_tasks = TASKS

    # 프로바이더
    provider = PROVIDERS[args.provider]
    model = args.model or provider["default_model"]
    caller = provider["caller"]

    # 출력 경로
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(args.output) if args.output else RESULTS_DIR / f"run_{timestamp}.json"

    # ── 헤더 출력 ─────────────────────────────────────────────────────────────
    print("=" * 60)
    print("harness-bench")
    print("=" * 60)
    print(f"  프로바이더 : {args.provider} / {model}")
    print(f"  조건       : {list(selected_conditions.keys())}")
    print(f"  과제       : {[t['id'] for t in selected_tasks]}")
    print(f"  judge      : {'OFF' if args.no_judge else args.judge_model}")
    print(f"  temperature: {args.temperature}")
    print(f"  출력       : {out_path}")
    print()

    results = {
        "meta": {
            "timestamp": timestamp,
            "provider": args.provider,
            "model": model,
            "judge_model": None if args.no_judge else args.judge_model,
            "temperature": args.temperature,
            "conditions": {k: {"name": v["name"], "description": v["description"]}
                           for k, v in selected_conditions.items()},
        },
        "tasks": [],
    }

    # ── 메인 루프 ─────────────────────────────────────────────────────────────
    for task in selected_tasks:
        print(f"\n[과제] {task['name']}  ({task['category']})")
        task_result = {
            "id": task["id"],
            "name": task["name"],
            "category": task["category"],
            "conditions": {},
        }

        for cond_key, cond in selected_conditions.items():
            print(f"  → {cond['name']} ...", end="", flush=True)

            resp = caller(
                system_prompt=cond["system"],
                user_prompt=task["prompt"],
                model=model,
                temperature=args.temperature,
            )

            if "error" in resp:
                print(f"  ERROR: {resp['error']}")
                task_result["conditions"][cond_key] = {"error": resp["error"]}
                continue

            print(f" {resp['elapsed']}s, out:{resp.get('output_tokens', '?')}tok", end="", flush=True)

            cond_result = {
                "response": resp["response"],
                "response_length": resp["response_length"],
                "elapsed": resp["elapsed"],
                "input_tokens": resp.get("input_tokens", 0),
                "output_tokens": resp.get("output_tokens", 0),
            }

            if not args.no_judge:
                eval_result = evaluate(
                    task=task,
                    response=resp["response"],
                    condition_name=cond["name"],
                    judge_model=args.judge_model,
                )
                avg = eval_result.get("average", "ERR")
                print(f" → 점수: {avg}")
                cond_result["evaluation"] = eval_result
            else:
                print()

            task_result["conditions"][cond_key] = cond_result

        results["tasks"].append(task_result)

        # 과제 완료할 때마다 중간 저장
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    # ── 종합 집계 ─────────────────────────────────────────────────────────────
    if not args.no_judge:
        print("\n" + "=" * 60)
        print("종합 결과")
        print("=" * 60)

        summary = {k: {"scores": [], "lengths": [], "times": []} for k in selected_conditions}

        for task_result in results["tasks"]:
            for cond_key in selected_conditions:
                d = task_result["conditions"].get(cond_key, {})
                if "evaluation" in d and "average" in d["evaluation"]:
                    summary[cond_key]["scores"].append(d["evaluation"]["average"])
                    summary[cond_key]["lengths"].append(d.get("response_length", 0))
                    summary[cond_key]["times"].append(d.get("elapsed", 0))

        summary_out = {}
        for cond_key, cond in selected_conditions.items():
            s = summary[cond_key]
            if s["scores"]:
                avg_score = round(sum(s["scores"]) / len(s["scores"]), 2)
                avg_len = round(sum(s["lengths"]) / len(s["lengths"]))
                avg_time = round(sum(s["times"]) / len(s["times"]), 1)
                print(f"  {cond['name']}")
                print(f"    점수: {avg_score}  |  응답길이: {avg_len}자  |  시간: {avg_time}s")
                summary_out[cond_key] = {
                    "avg_score": avg_score, "avg_length": avg_len, "avg_time": avg_time,
                }

        results["summary"] = summary_out
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n결과 저장: {out_path}")
    return out_path


# ── 진입점 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = parse_args()

    if args.list_conditions:
        list_conditions(); sys.exit(0)
    if args.list_tasks:
        list_tasks(); sys.exit(0)
    if args.list_providers:
        list_providers(); sys.exit(0)

    run(args)
