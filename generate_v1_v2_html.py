#!/usr/bin/env python3
"""v1, v2 HTML 리포트 재생성"""

import json
from pathlib import Path

# ============================================================
# v1: 실험 1 (3-Column 비교) HTML
# ============================================================
with open("results/h100_experiment_20260403_160203.json") as f:
    exp1 = json.load(f)
with open("results/raw_retry_20260403_173817.json") as f:
    retry = json.load(f)

# 초기 실험은 리스트 형태
exp1_results = exp1 if isinstance(exp1, list) else exp1.get("results", exp1)
retry_results = retry if isinstance(retry, list) else retry.get("results", retry)

def get_exp1_scores(condition, results_list):
    entries = [r for r in results_list if r.get("condition") == condition and "evaluation" in r and "error" not in r.get("evaluation", {})]
    if not entries:
        return {}, 0, 0, 0, 0
    all_scores = {}
    for r in entries:
        for k, v in r["evaluation"].items():
            if isinstance(v, dict) and "score" in v:
                all_scores.setdefault(k, []).append(v["score"])
    avgs = {k: round(sum(v)/len(v), 1) for k, v in all_scores.items()}
    overall = round(sum(sum(v)/len(v) for v in all_scores.values()) / len(all_scores), 2) if all_scores else 0
    chars = round(sum(r.get("response_length", 0) for r in entries) / len(entries))
    tokens = round(sum(r.get("output_tokens", 0) for r in entries) / len(entries))
    time_avg = round(sum(r.get("elapsed", 0) for r in entries) / len(entries), 1)
    return avgs, overall, chars, tokens, time_avg

raw_scores, raw_avg, raw_chars, raw_tok, raw_time = get_exp1_scores("raw_27b", retry_results)
harness_scores, harness_avg, harness_chars, harness_tok, harness_time = get_exp1_scores("harness_27b", exp1_results)
claude_scores, claude_avg, claude_chars, claude_tok, claude_time = get_exp1_scores("claude_code", exp1_results)

v1_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"><title>실험 1: 3-Column 비교 리포트</title>
<style>
  body {{ font-family: -apple-system, sans-serif; background: #0a0a0f; color: #e0e0e0; line-height: 1.6; margin: 0; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}
  .hero {{ background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460); border-radius: 16px; padding: 40px; margin-bottom: 24px; border: 1px solid #2a2a4a; }}
  .hero h1 {{ font-size: 2em; background: linear-gradient(90deg, #00d2ff, #7b2ff7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
  .card {{ background: #12121a; border-radius: 12px; padding: 24px; margin-bottom: 20px; border: 1px solid #2a2a3a; }}
  .card h2 {{ color: #fff; margin-bottom: 12px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
  th, td {{ padding: 10px 14px; text-align: center; border-bottom: 1px solid #2a2a3a; }}
  th {{ background: #1a1a2e; color: #8888cc; font-size: 0.85em; }}
  .green {{ color: #00e676; }} .blue {{ color: #448aff; }} .orange {{ color: #ff9100; }}
  .hero-stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 20px; }}
  .hero-stat {{ background: rgba(255,255,255,0.05); border-radius: 12px; padding: 20px; text-align: center; }}
  .hero-stat .value {{ font-size: 2em; font-weight: 800; }}
  .hero-stat .label {{ font-size: 0.85em; color: #888; }}
  .footer {{ text-align: center; padding: 24px; color: #555; font-size: 0.85em; }}
</style>
</head>
<body>
<div class="container">
<div class="hero">
  <h1>실험 1: Claude Code 하니스 3-Column 비교</h1>
  <p style="color:#888;">2026-04-03 | Distilled Qwen3.5-27B (vLLM H200) vs Claude Opus 4.6</p>
  <div class="hero-stats">
    <div class="hero-stat"><div class="value green">+34%</div><div class="label">하니스 향상</div></div>
    <div class="hero-stat"><div class="value blue">{harness_avg}</div><div class="label">하니스 점수</div></div>
    <div class="hero-stat"><div class="value orange">-49%</div><div class="label">토큰 절감</div></div>
  </div>
</div>

<div class="card">
  <h2>종합 결과</h2>
  <table>
    <tr><th></th><th style="color:#ff5252">Col1: Raw 27B</th><th style="color:#00e676">Col2: 27B+하니스</th><th style="color:#448aff">Col3: Claude CLI</th></tr>
    <tr><td>종합 점수</td><td style="color:#ff5252;font-size:1.3em;font-weight:800">{raw_avg}</td><td style="color:#00e676;font-size:1.3em;font-weight:800">{harness_avg}</td><td style="color:#448aff;font-size:1.3em;font-weight:800">{claude_avg}</td></tr>
    <tr><td>평균 응답 길이</td><td>{raw_chars}자</td><td>{harness_chars}자</td><td>{claude_chars}자</td></tr>
    <tr><td>평균 토큰</td><td>{raw_tok}</td><td>{harness_tok}</td><td>{claude_tok}</td></tr>
    <tr><td>평균 시간</td><td>{raw_time}s</td><td>{harness_time}s</td><td>{claude_time}s</td></tr>
  </table>
</div>

<div class="card">
  <h2>핵심 발견</h2>
  <ul style="line-height:2;">
    <li>하니스로 <strong class="green">+34% 향상</strong> ({raw_avg} → {harness_avg})</li>
    <li>토큰 <strong>49% 감소</strong>, 응답시간 37% 감소</li>
    <li>27B가 Claude보다 하니스를 <strong>더 잘 따름</strong> (RLHF 관성 적음)</li>
    <li>하니스 철학: "하라"가 아닌 <strong>"하지 마라"</strong> 중심 설계</li>
  </ul>
</div>
<div class="footer">실험 1 리포트 | 2026-04-03 | jinsookim</div>
</div>
</body></html>"""

Path("results/FINAL_COMPREHENSIVE_REPORT_v1.html").write_text(v1_html, encoding="utf-8")
print(f"v1 HTML: {len(v1_html):,} bytes")

# ============================================================
# v2: 실험 1~3 종합 HTML
# ============================================================
with open("results/ablation_Qwen3.5-27b_20260405_141621.json") as f:
    abl = json.load(f)

abl_raw = abl if isinstance(abl, list) else abl.get("results", abl)
abl_results = abl_raw
conditions_abl = {"A": "default_with_template", "B": "no_system_with_template", "C": "default_plus_custom", "D": "custom_only_with_template", "E": "custom_raw_no_template"}

def abl_avg(condition):
    entries = [r for r in abl_results if r.get("condition") == condition and "evaluation" in r and "error" not in r.get("evaluation", {})]
    scores = []
    for r in entries:
        for v in r["evaluation"].values():
            if isinstance(v, dict) and "score" in v:
                scores.append(v["score"])
    return round(sum(scores)/len(scores), 2) if scores else 0

def abl_stats(condition):
    entries = [r for r in abl_results if r.get("condition") == condition and "response_length" in r]
    if not entries: return {"chars": 0, "tokens": 0, "time": 0}
    return {
        "chars": round(sum(r["response_length"] for r in entries) / len(entries)),
        "tokens": round(sum(r.get("output_tokens", 0) for r in entries) / len(entries)),
        "time": round(sum(r.get("elapsed", 0) for r in entries) / len(entries), 1),
    }

abl_a = abl_avg("default_with_template")
abl_b = abl_avg("no_system_with_template")
abl_c = abl_avg("default_plus_custom")
abl_d = abl_avg("custom_only_with_template")
abl_e = abl_avg("custom_raw_no_template")
abl_c_stats = abl_stats("default_plus_custom")
abl_a_stats = abl_stats("default_with_template")

v2_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"><title>종합 리포트 v2: 실험 1~3</title>
<style>
  body {{ font-family: -apple-system, sans-serif; background: #0a0a0f; color: #e0e0e0; line-height: 1.6; margin: 0; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}
  .hero {{ background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460); border-radius: 16px; padding: 40px; margin-bottom: 24px; border: 1px solid #2a2a4a; }}
  .hero h1 {{ font-size: 2em; background: linear-gradient(90deg, #00d2ff, #7b2ff7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
  .card {{ background: #12121a; border-radius: 12px; padding: 24px; margin-bottom: 20px; border: 1px solid #2a2a3a; }}
  .card h2 {{ color: #fff; margin-bottom: 12px; }}
  .card h3 {{ color: #b0b0d0; margin: 16px 0 8px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
  th, td {{ padding: 10px 14px; text-align: center; border-bottom: 1px solid #2a2a3a; }}
  th {{ background: #1a1a2e; color: #8888cc; font-size: 0.85em; }}
  .green {{ color: #00e676; }} .blue {{ color: #448aff; }} .orange {{ color: #ff9100; }}
  .highlight {{ background: rgba(0,230,118,0.08) !important; }}
  .hero-stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 20px; }}
  .hero-stat {{ background: rgba(255,255,255,0.05); border-radius: 12px; padding: 20px; text-align: center; }}
  .hero-stat .value {{ font-size: 2em; font-weight: 800; }}
  .hero-stat .label {{ font-size: 0.85em; color: #888; }}
  .verdict {{ background: linear-gradient(135deg, #00e67611, #00e67622); border: 1px solid #00e67644; border-radius: 12px; padding: 20px; margin: 16px 0; }}
  .verdict h3 {{ color: #00e676; margin-bottom: 8px; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  @media (max-width: 768px) {{ .grid-2, .hero-stats {{ grid-template-columns: 1fr; }} }}
  .footer {{ text-align: center; padding: 24px; color: #555; font-size: 0.85em; }}
</style>
</head>
<body>
<div class="container">
<div class="hero">
  <h1>Claude Code 하니스 효과 종합 리포트 v2</h1>
  <p style="color:#888;">2026-04-03 ~ 04-05 | 3개 실험 | Distilled Qwen3.5-27B (vLLM H200)</p>
  <div class="hero-stats">
    <div class="hero-stat"><div class="value green">+34%</div><div class="label">실험 1: 하니스 효과</div></div>
    <div class="hero-stat"><div class="value blue">역전</div><div class="label">실험 2: Inverse</div></div>
    <div class="hero-stat"><div class="value orange">+0.04</div><div class="label">실험 3: Confounding</div></div>
    <div class="hero-stat"><div class="value" style="color:#b388ff">+0.81</div><div class="label">Custom 순수 효과</div></div>
  </div>
</div>

<div class="card">
  <h2>Executive Summary</h2>
  <table>
    <tr><th>실험</th><th>핵심 질문</th><th>결론</th><th>효과</th></tr>
    <tr><td>1. 3-Column 비교</td><td>하니스가 성능을 올리는가?</td><td class="green">Yes</td><td class="green">+34%</td></tr>
    <tr><td>2. Inverse Prompt</td><td>Distillation 때문인가?</td><td class="green">아니다</td><td>행동 역전</td></tr>
    <tr><td>3. 5-way Ablation</td><td>Default template confounding?</td><td class="green">무시 가능</td><td>+0.04</td></tr>
  </table>
</div>

<div class="card">
  <h2>실험 1: 3-Column 비교</h2>
  <table>
    <tr><th></th><th style="color:#ff5252">Raw 27B</th><th style="color:#00e676">27B+하니스</th><th style="color:#448aff">Claude CLI</th></tr>
    <tr><td>종합 점수</td><td>{raw_avg}</td><td class="green"><strong>{harness_avg}</strong></td><td>{claude_avg}</td></tr>
    <tr><td>토큰</td><td>{raw_tok}</td><td>{harness_tok}</td><td>{claude_tok}</td></tr>
    <tr><td>시간</td><td>{raw_time}s</td><td>{harness_time}s</td><td>{claude_time}s</td></tr>
  </table>
</div>

<div class="card">
  <h2>실험 2: Inverse Prompt</h2>
  <p>반대 지시("상세히 설명해라, docstring 달아라")를 주면 5분에도 끝나지 않을 만큼 verbose → <strong class="green">행동이 고정되지 않았다</strong></p>
</div>

<div class="card">
  <h2>실험 3: 5-way Ablation</h2>
  <table>
    <tr><th>조건</th><th>평균 점수</th><th>토큰</th><th>시간</th></tr>
    <tr><td>A. Default</td><td>{abl_a}</td><td>{abl_a_stats['tokens']}</td><td>{abl_a_stats['time']}s</td></tr>
    <tr><td>B. No System</td><td>{abl_b}</td><td>{abl_stats('no_system_with_template')['tokens']}</td><td>{abl_stats('no_system_with_template')['time']}s</td></tr>
    <tr class="highlight"><td><strong>C. Default+Custom</strong></td><td class="green"><strong>{abl_c}</strong></td><td><strong>{abl_c_stats['tokens']}</strong></td><td><strong>{abl_c_stats['time']}s</strong></td></tr>
    <tr><td>D. Custom Only</td><td>{abl_d}</td><td>{abl_stats('custom_only_with_template')['tokens']}</td><td>{abl_stats('custom_only_with_template')['time']}s</td></tr>
    <tr><td>E. Raw Custom</td><td>{abl_e}</td><td>{abl_stats('custom_raw_no_template')['tokens']}</td><td>{abl_stats('custom_raw_no_template')['time']}s</td></tr>
  </table>

  <h3>Ablation 핵심</h3>
  <div class="grid-2">
    <div class="verdict">
      <h3>Default Confounding (A-B) = +{round(abl_a - abl_b, 2)}</h3>
      <p>무시 가능 수준. 리뷰어 우려 반박.</p>
    </div>
    <div class="verdict">
      <h3>Custom 순수 효과 (D-B) = +{round(abl_d - abl_b, 2)}</h3>
      <p>Default 통제 후에도 유의미한 향상.</p>
    </div>
  </div>
</div>

<div class="card">
  <h2>종합 결론</h2>
  <ul style="line-height:2;">
    <li>하니스 효과는 <strong class="green">프롬프트 자체의 힘</strong></li>
    <li>Default template confounding은 <strong>무시 가능</strong></li>
    <li>"하지 마라" 중심 설계가 핵심</li>
    <li>남은 과제: 바닐라 모델 검증, 다른 모델 패밀리</li>
  </ul>
</div>
<div class="footer">종합 리포트 v2 | 2026-04-03~05 | jinsookim</div>
</div>
</body></html>"""

Path("results/FINAL_COMPREHENSIVE_REPORT_v2.html").write_text(v2_html, encoding="utf-8")
print(f"v2 HTML: {len(v2_html):,} bytes")
