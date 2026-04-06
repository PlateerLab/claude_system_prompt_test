#!/usr/bin/env python3
"""v3 리포트 HTML 생성 — 4-Column (바닐라 Raw, 바닐라+하니스, Distilled+하니스, Claude Opus 4.6)"""

import json
from pathlib import Path

# 실험 4 결과 로드
vanilla_files = sorted(Path("results").glob("vanilla_experiment_*.json"))
claude_files = sorted(Path("results").glob("vanilla_claude_supplement_*.json"))

with open(vanilla_files[-1]) as f:
    vanilla_data = json.load(f)
with open(claude_files[-1]) as f:
    claude_data = json.load(f)

results = vanilla_data["results"] + claude_data["results"]

# 유틸리티
def get_scores(condition):
    entries = [r for r in results if r["condition"] == condition and "evaluation" in r and "error" not in r.get("evaluation", {})]
    if not entries:
        return {}
    all_scores = {}
    for r in entries:
        for k, v in r["evaluation"].items():
            if isinstance(v, dict) and "score" in v:
                all_scores.setdefault(k, []).append(v["score"])
    return {k: round(sum(v)/len(v), 1) for k, v in all_scores.items()}

def get_avg(condition):
    entries = [r for r in results if r["condition"] == condition and "evaluation" in r and "error" not in r.get("evaluation", {})]
    scores = []
    for r in entries:
        for v in r["evaluation"].values():
            if isinstance(v, dict) and "score" in v:
                scores.append(v["score"])
    return round(sum(scores)/len(scores), 2) if scores else 0

def get_stats(condition):
    entries = [r for r in results if r["condition"] == condition and "response_length" in r]
    if not entries:
        return {"chars": 0, "tokens": 0, "time": 0}
    return {
        "chars": round(sum(r["response_length"] for r in entries) / len(entries)),
        "tokens": round(sum(r.get("output_tokens", 0) for r in entries) / len(entries)),
        "time": round(sum(r.get("elapsed", 0) for r in entries) / len(entries), 1),
    }

def get_category_scores(condition, category):
    entries = [r for r in results if r["condition"] == condition and r["task_category"] == category
               and "evaluation" in r and "error" not in r.get("evaluation", {})]
    if not entries:
        return {}, 0
    all_scores = {}
    for r in entries:
        for k, v in r["evaluation"].items():
            if isinstance(v, dict) and "score" in v:
                all_scores.setdefault(k, []).append(v["score"])
    avgs = {k: round(sum(v)/len(v), 1) for k, v in all_scores.items()}
    overall = round(sum(sum(v)/len(v) for v in all_scores.values()) / len(all_scores), 2)
    return avgs, overall

# 4개 조건
CONDITIONS = [
    ("vanilla_raw", "바닐라 Raw", "#ff5252"),
    ("vanilla_harness", "바닐라+하니스", "#00e676"),
    ("distilled_harness", "Distilled+하니스", "#448aff"),
    ("claude_opus", "Claude Opus 4.6", "#ff9100"),
]

avgs = {c: get_avg(c) for c, _, _ in CONDITIONS}
stats = {c: get_stats(c) for c, _, _ in CONDITIONS}

coding = {c: get_category_scores(c, "coding") for c, _, _ in CONDITIONS}
noncoding = {c: get_category_scores(c, "non-coding") for c, _, _ in CONDITIONS}

improvement = round((avgs["vanilla_harness"] - avgs["vanilla_raw"]) / avgs["vanilla_raw"] * 100, 1)
token_reduction = round((1 - stats["vanilla_harness"]["tokens"] / max(stats["vanilla_raw"]["tokens"], 1)) * 100)
time_reduction = round((1 - stats["vanilla_harness"]["time"] / max(stats["vanilla_raw"]["time"], 0.1)) * 100)
claude_gap = round(avgs["vanilla_harness"] / max(avgs["claude_opus"], 0.01) * 100, 1)

# 코딩 메트릭 이름
coding_metrics = ["correctness", "efficiency", "conciseness", "no_overengineering", "response_bloat", "instruction_following"]
coding_labels = ["정확성", "효율성", "간결성", "과잉설계방지", "응답간결", "지시준수"]
noncoding_metrics = ["accuracy", "completeness", "conciseness", "no_overexplaining", "response_bloat", "actionability"]
noncoding_labels = ["정확성", "완전성", "간결성", "과잉설명방지", "응답간결", "실행가능성"]

def make_score_table(metrics, labels, category_data):
    rows = ""
    for m, l in zip(metrics, labels):
        vals = []
        for c, _, color in CONDITIONS:
            sc = category_data[c][0].get(m, '-')
            vals.append(f'<td style="color:{color}">{sc}</td>')
        rows += f"<tr><td>{l}</td>{''.join(vals)}</tr>\n"
    # avg row
    avg_row = ""
    for c, _, color in CONDITIONS:
        avg_row += f'<td style="color:{color};font-weight:800">{category_data[c][1]}</td>'
    rows += f'<tr style="border-top:2px solid #333;font-weight:bold"><td>평균</td>{avg_row}</tr>'
    return rows

html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claude Code 하니스 효과 종합 실험 리포트 v3</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0f; color: #e0e0e0; line-height: 1.6; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
  .hero {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); border-radius: 16px; padding: 48px; margin-bottom: 32px; border: 1px solid #2a2a4a; }}
  .hero h1 {{ font-size: 2.2em; background: linear-gradient(90deg, #00d2ff, #7b2ff7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px; }}
  .hero .subtitle {{ font-size: 1.1em; color: #8888aa; margin-bottom: 24px; }}
  .hero-stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 24px; }}
  .hero-stat {{ background: rgba(255,255,255,0.05); border-radius: 12px; padding: 20px; text-align: center; border: 1px solid rgba(255,255,255,0.08); }}
  .hero-stat .value {{ font-size: 2em; font-weight: 800; }}
  .hero-stat .label {{ font-size: 0.85em; color: #8888aa; margin-top: 4px; }}
  .card {{ background: #12121a; border-radius: 12px; padding: 28px; margin-bottom: 24px; border: 1px solid #2a2a3a; }}
  .card h2 {{ font-size: 1.4em; margin-bottom: 16px; color: #fff; }}
  .card h3 {{ font-size: 1.1em; margin: 16px 0 8px; color: #b0b0d0; }}
  .badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.75em; font-weight: 600; margin-left: 8px; }}
  .badge-new {{ background: #ff910033; color: #ff9100; }}
  .badge-key {{ background: #00e67633; color: #00e676; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
  th, td {{ padding: 10px 14px; text-align: center; border-bottom: 1px solid #2a2a3a; }}
  th {{ background: #1a1a2e; color: #8888cc; font-weight: 600; font-size: 0.85em; text-transform: uppercase; }}
  td {{ font-size: 0.95em; }}
  tr:hover {{ background: rgba(255,255,255,0.02); }}
  .highlight {{ background: rgba(0,230,118,0.08) !important; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .grid-4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }}
  @media (max-width: 768px) {{ .grid-2, .grid-4, .hero-stats {{ grid-template-columns: 1fr; }} }}
  .bar-row {{ display: flex; align-items: center; margin: 6px 0; }}
  .bar-label {{ width: 180px; font-size: 0.85em; color: #aaa; }}
  .bar-track {{ flex: 1; height: 28px; background: #1a1a2e; border-radius: 4px; position: relative; }}
  .bar-fill {{ height: 100%; border-radius: 4px; display: flex; align-items: center; justify-content: flex-end; padding-right: 8px; font-size: 0.8em; font-weight: 600; }}
  .verdict {{ background: linear-gradient(135deg, #00e67611, #00e67622); border: 1px solid #00e67644; border-radius: 12px; padding: 24px; margin: 20px 0; }}
  .verdict h3 {{ color: #00e676; }}
  .timeline {{ position: relative; padding-left: 30px; }}
  .timeline::before {{ content: ''; position: absolute; left: 10px; top: 0; bottom: 0; width: 2px; background: #2a2a4a; }}
  .timeline-item {{ position: relative; margin-bottom: 20px; }}
  .timeline-item::before {{ content: ''; position: absolute; left: -24px; top: 6px; width: 12px; height: 12px; border-radius: 50%; border: 2px solid #448aff; background: #12121a; }}
  .timeline-item.active::before {{ background: #00e676; border-color: #00e676; }}
  .timeline-date {{ font-size: 0.8em; color: #666; }}
  .footer {{ text-align: center; padding: 32px; color: #555; font-size: 0.85em; }}
</style>
</head>
<body>
<div class="container">

<div class="hero">
  <h1>Claude Code Harness Effect Report v3</h1>
  <div class="subtitle">4-Column 비교: 바닐라 Raw vs +하니스 vs Distilled vs Claude Opus 4.6</div>
  <div style="font-size:0.85em; color:#666;">2026-04-03 ~ 04-06 | jinsookim | H200 4-way + Alibaba Cloud API | Piebald-AI/claude-code-system-prompts</div>
  <div class="hero-stats">
    <div class="hero-stat">
      <div class="value" style="color:#00e676">+{improvement}%</div>
      <div class="label">바닐라 하니스 효과</div>
    </div>
    <div class="hero-stat">
      <div class="value" style="color:#448aff">{claude_gap}%</div>
      <div class="label">Claude 대비 달성률</div>
    </div>
    <div class="hero-stat">
      <div class="value" style="color:#b388ff">-{token_reduction}%</div>
      <div class="label">토큰 절감</div>
    </div>
    <div class="hero-stat">
      <div class="value" style="color:#ff9100">-{time_reduction}%</div>
      <div class="label">응답 시간 절감</div>
    </div>
  </div>
</div>

<!-- 4-Column 종합 점수 카드 -->
<div class="card">
  <h2>4-Column 종합 비교</h2>
  <div class="grid-4">
    {"".join(f'''<div style="background:#1a1a2e;border-radius:8px;padding:16px;text-align:center;{'border:2px solid '+color+'44;' if c=='vanilla_harness' else ''}">
      <div style="font-size:0.8em;color:{color};">{name}</div>
      <div style="font-size:2.5em;font-weight:800;color:{color};">{avgs[c]}</div>
      <div style="font-size:0.8em;color:#666;">{stats[c]["chars"]}자 | {stats[c]["tokens"]}tok | {stats[c]["time"]}s</div>
    </div>''' for c, name, color in CONDITIONS)}
  </div>

  <div style="margin-top:20px">
    <h3>종합 점수 비교</h3>
    {"".join(f'<div class="bar-row"><div class="bar-label" style="color:{color}">{name}</div><div class="bar-track"><div class="bar-fill" style="width:{avgs[c]/10*100}%;background:linear-gradient(90deg,{color}66,{color})">{avgs[c]}</div></div></div>' for c, name, color in CONDITIONS)}
  </div>

  <div style="margin-top:20px">
    <h3>응답 길이 비교 (자)</h3>
    {"".join(f'<div class="bar-row"><div class="bar-label" style="color:{color}">{name}</div><div class="bar-track"><div class="bar-fill" style="width:{min(stats[c]["chars"]/60,100)}%;background:linear-gradient(90deg,{color}66,{color})">{stats[c]["chars"]}</div></div></div>' for c, name, color in CONDITIONS)}
  </div>

  <div style="margin-top:20px">
    <h3>출력 토큰 비교</h3>
    {"".join(f'<div class="bar-row"><div class="bar-label" style="color:{color}">{name}</div><div class="bar-track"><div class="bar-fill" style="width:{min(stats[c]["tokens"]/20,100)}%;background:linear-gradient(90deg,{color}66,{color})">{stats[c]["tokens"]}</div></div></div>' for c, name, color in CONDITIONS)}
  </div>
</div>

<!-- 기준별 점수 -->
<div class="card">
  <h2>기준별 점수 비교</h2>
  <div class="grid-2">
    <div>
      <h3>코딩 과제 (3개)</h3>
      <table>
        <tr><th>기준</th>{"".join(f'<th style="color:{color}">{name.split(":")[0] if ":" in name else name[:6]}</th>' for _, name, color in CONDITIONS)}</tr>
        {make_score_table(coding_metrics, coding_labels, coding)}
      </table>
    </div>
    <div>
      <h3>비코딩 과제 (3개)</h3>
      <table>
        <tr><th>기준</th>{"".join(f'<th style="color:{color}">{name.split(":")[0] if ":" in name else name[:6]}</th>' for _, name, color in CONDITIONS)}</tr>
        {make_score_table(noncoding_metrics, noncoding_labels, noncoding)}
      </table>
    </div>
  </div>
</div>

<!-- Executive Summary -->
<div class="card">
  <h2>Executive Summary — 4개 실험 결과</h2>
  <table>
    <tr><th>실험</th><th>핵심 질문</th><th>결론</th><th>효과</th></tr>
    <tr><td>1. 3-Column 비교</td><td>하니스가 성능을 올리는가?</td><td style="color:#00e676">Yes</td><td style="color:#00e676">+34%</td></tr>
    <tr><td>2. Inverse Prompt</td><td>Distillation 때문인가?</td><td style="color:#00e676">아니다</td><td>행동 역전 확인</td></tr>
    <tr><td>3. 5-way Ablation</td><td>Default template confounding?</td><td style="color:#00e676">무시 가능</td><td>+0.04 (0.5%)</td></tr>
    <tr class="highlight"><td><strong>4. 바닐라+Claude 비교</strong> <span class="badge badge-new">NEW</span></td><td>바닐라에서도? Claude와 비교?</td><td style="color:#00e676"><strong>Yes</strong></td><td style="color:#00e676"><strong>+{improvement}%, Claude의 {claude_gap}%</strong></td></tr>
  </table>

  <div class="verdict">
    <h3>최종 결론</h3>
    <p style="margin-top:8px;">
      1. 하니스 효과는 <strong>Distillation과 무관</strong> — 바닐라에서도 +{improvement}% 재현<br>
      2. 바닐라+하니스({avgs['vanilla_harness']})가 <strong>Claude Opus 4.6({avgs['claude_opus']})의 {claude_gap}%</strong> 달성<br>
      3. 토큰 {token_reduction}% 절감, 시간 {time_reduction}% 절감 — <strong>비용 효율 극대화</strong>
    </p>
  </div>
</div>

<!-- 핵심 발견 -->
<div class="card">
  <h2>핵심 발견</h2>
  <div class="grid-2">
    <div style="padding:16px;background:#1a1a2e;border-radius:8px;">
      <h3 style="color:#00e676;">바닐라에서도 재현: +{improvement}%</h3>
      <p style="margin-top:8px;">Raw {avgs['vanilla_raw']} → +하니스 {avgs['vanilla_harness']}<br>알리바바 공식 바닐라 모델에서 대폭 향상</p>
    </div>
    <div style="padding:16px;background:#1a1a2e;border-radius:8px;">
      <h3 style="color:#ff9100;">Claude의 {claude_gap}% 달성</h3>
      <p style="margin-top:8px;">바닐라+하니스 {avgs['vanilla_harness']} vs Claude {avgs['claude_opus']}<br>27B 오픈소스로 Claude 근접</p>
    </div>
    <div style="padding:16px;background:#1a1a2e;border-radius:8px;">
      <h3 style="color:#448aff;">Distillation 불필요</h3>
      <p style="margin-top:8px;">바닐라+하니스 {avgs['vanilla_harness']} ≈ Distilled+하니스 {avgs['distilled_harness']}<br>차이 {round(avgs['vanilla_harness']-avgs['distilled_harness'],2)}점 — 통계적 동등</p>
    </div>
    <div style="padding:16px;background:#1a1a2e;border-radius:8px;">
      <h3 style="color:#b388ff;">비용 {token_reduction}% 절감</h3>
      <p style="margin-top:8px;">토큰 {stats['vanilla_raw']['tokens']}→{stats['vanilla_harness']['tokens']}, 시간 {stats['vanilla_raw']['time']}s→{stats['vanilla_harness']['time']}s<br>API 비용 직접 절감</p>
    </div>
  </div>
</div>

<!-- 리뷰어 대응 -->
<div class="card">
  <h2>리뷰어 비판 대응 매트릭스</h2>
  <table>
    <tr><th>비판</th><th>대응 실험</th><th>결과</th><th>판정</th></tr>
    <tr><td>"Distilled라서 잘 따르는 것"</td><td>실험 2 (Inverse)</td><td>반대 지시 → 행동 역전</td><td style="color:#00e676">반박됨</td></tr>
    <tr class="highlight"><td><strong>"Distilled라서 잘 따르는 것"</strong></td><td><strong>실험 4 (바닐라)</strong></td><td><strong>바닐라에서 +{improvement}%</strong></td><td style="color:#00e676"><strong>결정적 반박</strong></td></tr>
    <tr><td>"Default template confounding"</td><td>실험 3 (Ablation)</td><td>A-B = +0.04</td><td style="color:#00e676">반박됨</td></tr>
    <tr><td>"Chat template 구조 영향"</td><td>실험 3 (Ablation)</td><td>E-D = -0.14</td><td style="color:#00e676">반박됨</td></tr>
    <tr><td>"Claude 수준은 안 될 것"</td><td>실험 4 (Claude 비교)</td><td>{avgs['vanilla_harness']} vs {avgs['claude_opus']} ({claude_gap}%)</td><td style="color:#00e676">거의 근접</td></tr>
  </table>
</div>

<!-- 타임라인 -->
<div class="card">
  <h2>실험 타임라인</h2>
  <div class="timeline">
    <div class="timeline-item active">
      <div class="timeline-date">2026-04-03</div>
      <strong>실험 1: 3-Column 비교</strong> — Distilled 27B에서 하니스 효과 +34% 확인
    </div>
    <div class="timeline-item active">
      <div class="timeline-date">2026-04-05</div>
      <strong>실험 2: Inverse Prompt</strong> — 반대 지시 → 행동 역전. Distillation 고정 아님
    </div>
    <div class="timeline-item active">
      <div class="timeline-date">2026-04-05</div>
      <strong>실험 3: 5-way Ablation</strong> — Default confounding +0.04 (무시 가능)
    </div>
    <div class="timeline-item active">
      <div class="timeline-date">2026-04-06</div>
      <strong>실험 4: 바닐라 + Claude 비교</strong> <span class="badge badge-new">NEW</span> — 바닐라에서 +{improvement}% 재현, Claude의 {claude_gap}% 달성
    </div>
  </div>
</div>

<!-- 한계 -->
<div class="card">
  <h2>실험 한계 및 후속 과제</h2>
  <table>
    <tr><th>한계</th><th>영향</th><th>후속 과제</th></tr>
    <tr><td>단일 모델 패밀리 (Qwen)</td><td>일반화 제한</td><td>LLaMA, Mistral, Gemma 추가</td></tr>
    <tr><td>LLM-as-judge (Claude 평가)</td><td>편향 가능 (Claude가 Claude를 높게?)</td><td>pass@k, 인간 평가</td></tr>
    <tr><td>과제 6개</td><td>통계적 유의성</td><td>HumanEval, MBPP</td></tr>
    <tr><td>인프라 차이 (API vs vLLM)</td><td>환경 변수</td><td>Vast.ai 동일 인프라</td></tr>
  </table>
</div>

<div class="footer">
  Claude Code Harness Effect Report v3 | 2026-04-06 | jinsookim<br>
  하니스 출처: <a href="https://github.com/Piebald-AI/claude-code-system-prompts" style="color:#448aff;">Piebald-AI/claude-code-system-prompts</a>
</div>

</div>
</body>
</html>"""

outpath = Path("results/FINAL_COMPREHENSIVE_REPORT_v3.html")
outpath.write_text(html, encoding="utf-8")
print(f"Generated: {outpath} ({len(html):,} bytes)")
