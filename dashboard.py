#!/usr/bin/env python3
"""
harness-bench 대시보드

브라우저에서 실험 설정, 실행, 결과 확인.

실행:
  python dashboard.py
  → http://localhost:5000 접속
"""

import json
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_from_directory
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from bench.harnesses import CONDITIONS
from bench.tasks import TASKS, TASKS_BY_ID
from bench.providers import PROVIDERS
from bench.judge import evaluate

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

app = Flask(__name__)

# 실행 중인 실험 상태
_run_state: dict = {"running": False, "queue": queue.Queue()}


# ── API ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config")
def api_config():
    """대시보드 초기 설정값 반환."""
    return jsonify({
        "conditions": [
            {"key": k, "name": v["name"], "description": v["description"],
             "tok_approx": len(v["system"].split()) if v["system"] else 0}
            for k, v in CONDITIONS.items()
        ],
        "tasks": [
            {"id": t["id"], "name": t["name"], "category": t["category"]}
            for t in TASKS
        ],
        "providers": [
            {"key": k, "description": v["description"], "default_model": v["default_model"]}
            for k, v in PROVIDERS.items()
        ],
    })


@app.route("/api/run", methods=["POST"])
def api_run():
    """실험 시작."""
    if _run_state["running"]:
        return jsonify({"error": "이미 실험이 실행 중입니다."}), 409

    body = request.get_json()
    selected_conditions = body.get("conditions", list(CONDITIONS.keys()))
    selected_task_ids = body.get("tasks", [t["id"] for t in TASKS])
    provider_key = body.get("provider", "alibaba")
    model = body.get("model") or PROVIDERS[provider_key]["default_model"]
    judge_model = body.get("judge_model", "claude-opus-4-6")
    no_judge = body.get("no_judge", False)
    temperature = float(body.get("temperature", 0.3))

    # 검증
    bad_conds = [k for k in selected_conditions if k not in CONDITIONS]
    bad_tasks = [t for t in selected_task_ids if t not in TASKS_BY_ID]
    if bad_conds or bad_tasks:
        return jsonify({"error": f"unknown conditions={bad_conds} tasks={bad_tasks}"}), 400

    # 백그라운드 실행
    q = queue.Queue()
    _run_state["running"] = True
    _run_state["queue"] = q

    def _run():
        try:
            _execute(
                condition_keys=selected_conditions,
                task_ids=selected_task_ids,
                provider_key=provider_key,
                model=model,
                judge_model=judge_model,
                no_judge=no_judge,
                temperature=temperature,
                q=q,
            )
        finally:
            _run_state["running"] = False
            q.put(None)  # sentinel

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/stream")
def api_stream():
    """SSE 스트림 — 실험 로그 실시간 전송."""
    q = _run_state["queue"]

    def generate():
        while True:
            try:
                msg = q.get(timeout=30)
            except queue.Empty:
                yield "data: \n\n"  # keepalive
                continue
            if msg is None:
                yield "data: [DONE]\n\n"
                break
            yield f"data: {json.dumps(msg)}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/results")
def api_results():
    """저장된 결과 파일 목록."""
    files = sorted(RESULTS_DIR.glob("run_*.json"), reverse=True)
    out = []
    for f in files[:30]:
        try:
            data = json.loads(f.read_text())
            meta = data.get("meta", {})
            summary = data.get("summary", {})
            out.append({
                "filename": f.name,
                "timestamp": meta.get("timestamp", f.stem),
                "provider": meta.get("provider"),
                "model": meta.get("model"),
                "conditions": list(meta.get("conditions", {}).keys()),
                "summary": {k: v.get("avg_score") for k, v in summary.items()},
            })
        except Exception:
            pass
    return jsonify(out)


@app.route("/api/results/<filename>")
def api_result_detail(filename: str):
    """특정 결과 파일 상세 반환."""
    path = RESULTS_DIR / filename
    if not path.exists() or not filename.endswith(".json"):
        return jsonify({"error": "not found"}), 404
    return jsonify(json.loads(path.read_text()))


@app.route("/api/stop", methods=["POST"])
def api_stop():
    """실험 중단 신호 (현재 과제 완료 후 종료)."""
    _run_state["stop_requested"] = True
    return jsonify({"status": "stop requested"})


# ── 실험 실행 로직 ────────────────────────────────────────────────────────────

def _emit(q: queue.Queue, type: str, **kwargs):
    q.put({"type": type, "ts": datetime.now().strftime("%H:%M:%S"), **kwargs})


def _execute(
    condition_keys, task_ids, provider_key, model,
    judge_model, no_judge, temperature, q: queue.Queue,
):
    _run_state["stop_requested"] = False
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"run_{timestamp}.json"

    selected_conditions = {k: CONDITIONS[k] for k in condition_keys}
    selected_tasks = [TASKS_BY_ID[t] for t in task_ids]
    caller = PROVIDERS[provider_key]["caller"]

    _emit(q, "start",
          provider=provider_key, model=model,
          conditions=condition_keys, tasks=task_ids,
          judge=("off" if no_judge else judge_model),
          output=str(out_path))

    results = {
        "meta": {
            "timestamp": timestamp,
            "provider": provider_key,
            "model": model,
            "judge_model": None if no_judge else judge_model,
            "temperature": temperature,
            "conditions": {k: {"name": v["name"], "description": v["description"]}
                           for k, v in selected_conditions.items()},
        },
        "tasks": [],
    }

    for task in selected_tasks:
        if _run_state.get("stop_requested"):
            _emit(q, "log", msg="⏹ 중단 요청으로 실험 종료")
            break

        _emit(q, "task_start", task_id=task["id"], task_name=task["name"],
              category=task["category"])

        task_result = {
            "id": task["id"], "name": task["name"],
            "category": task["category"], "conditions": {},
        }

        for cond_key, cond in selected_conditions.items():
            _emit(q, "cond_start", cond_key=cond_key, cond_name=cond["name"])

            resp = caller(
                system_prompt=cond["system"],
                user_prompt=task["prompt"],
                model=model,
                temperature=temperature,
            )

            if "error" in resp:
                _emit(q, "cond_error", cond_key=cond_key, error=resp["error"])
                task_result["conditions"][cond_key] = {"error": resp["error"]}
                continue

            cond_result = {
                "response": resp["response"],
                "response_length": resp["response_length"],
                "elapsed": resp["elapsed"],
                "input_tokens": resp.get("input_tokens", 0),
                "output_tokens": resp.get("output_tokens", 0),
            }

            if not no_judge:
                eval_result = evaluate(
                    task=task, response=resp["response"],
                    condition_name=cond["name"], judge_model=judge_model,
                )
                cond_result["evaluation"] = eval_result
                _emit(q, "cond_done",
                      cond_key=cond_key,
                      elapsed=resp["elapsed"],
                      output_tokens=resp.get("output_tokens", 0),
                      response_length=resp["response_length"],
                      avg_score=eval_result.get("average"),
                      scores=eval_result.get("scores", {}))
            else:
                _emit(q, "cond_done",
                      cond_key=cond_key,
                      elapsed=resp["elapsed"],
                      output_tokens=resp.get("output_tokens", 0),
                      response_length=resp["response_length"])

            task_result["conditions"][cond_key] = cond_result

        results["tasks"].append(task_result)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    # 종합 집계
    if not no_judge:
        summary = {k: [] for k in condition_keys}
        for tr in results["tasks"]:
            for ck in condition_keys:
                d = tr["conditions"].get(ck, {})
                if "evaluation" in d and "average" in d["evaluation"]:
                    summary[ck].append(d["evaluation"]["average"])

        results["summary"] = {
            k: {"avg_score": round(sum(v) / len(v), 2) if v else None}
            for k, v in summary.items()
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        _emit(q, "summary",
              summary=results["summary"],
              condition_names={k: CONDITIONS[k]["name"] for k in condition_keys})

    _emit(q, "done", output=str(out_path))


# ── 진입점 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import webbrowser
    print("harness-bench 대시보드 시작 중...")
    print("→ http://localhost:5000")
    # 브라우저 자동 열기 (1초 딜레이)
    threading.Timer(1.0, lambda: webbrowser.open("http://localhost:5000")).start()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
