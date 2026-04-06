#!/usr/bin/env python3
"""
Ablation 실험 결과 보고서 생성
================================
run_vllm_ablation.py의 결과를 분석하여 학술 보고서 스타일의 HTML+MD 생성

핵심: 리뷰어가 "default template confounding"을 지적했으므로,
      ablation을 통해 각 요소의 순수 효과를 분리하여 보여줌
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

RESULTS_DIR = Path(__file__).parent / "results"


def load_ablation_results(filepath=None):
    """ablation 결과 파일 로드"""
    if filepath:
        p = Path(filepath)
    else:
        files = sorted(RESULTS_DIR.glob("ablation_*.json"))
        if not files:
            print("ablation 결과 파일이 없습니다. run_vllm_ablation.py를 먼저 실행하세요.")
            sys.exit(1)
        p = files[-1]

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data, p.name


def avg(lst):
    return round(sum(lst) / len(lst), 2) if lst else 0


def compute_stats(results):
    """조건별 통계 계산"""
    cond_scores = defaultdict(lambda: defaultdict(list))
    cond_meta = defaultdict(lambda: {
        "chars": [], "tokens": [], "times": [],
        "input_tokens": [], "output_tokens": [],
    })
    cat_scores = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for r in results:
        if "error" in r or "evaluation" not in r:
            continue
        ev = r["evaluation"]
        if "error" in ev:
            continue

        cond = r["condition"]
        cat = r["category"]

        for metric, val in ev.items():
            if isinstance(val, dict) and "score" in val:
                cond_scores[cond][metric].append(val["score"])
                cat_scores[cond][cat][metric].append(val["score"])

        cond_meta[cond]["chars"].append(r.get("response_length", 0))
        cond_meta[cond]["output_tokens"].append(r.get("output_tokens", 0))
        cond_meta[cond]["input_tokens"].append(r.get("input_tokens", 0))
        cond_meta[cond]["times"].append(r.get("elapsed", 0))

    return cond_scores, cond_meta, cat_scores


def compute_ablation_effects(cond_scores):
    """Ablation 효과 계산"""
    def overall_avg(cond):
        all_vals = []
        for metric_vals in cond_scores.get(cond, {}).values():
            all_vals.extend(metric_vals)
        return avg(all_vals) if all_vals else None

    scores = {k: overall_avg(k) for k in [
        "A_default_template", "B_no_system",
        "C_custom_on_default", "D_custom_replace", "E_raw_custom"
    ]}

    effects = {}

    # D - B: custom system prompt의 순수 효과
    if scores["D_custom_replace"] is not None and scores["B_no_system"] is not None:
        diff = round(scores["D_custom_replace"] - scores["B_no_system"], 2)
        effects["custom_pure_effect"] = {
            "label": "Custom System Prompt의 순수 효과 (D - B)",
            "description": "Default template을 통제한 상태에서 custom prompt의 순수 기여",
            "formula": "D_custom_replace - B_no_system",
            "value": diff,
            "D": scores["D_custom_replace"],
            "B": scores["B_no_system"],
        }

    # C - A: default 위에 custom 추가 효과
    if scores["C_custom_on_default"] is not None and scores["A_default_template"] is not None:
        diff = round(scores["C_custom_on_default"] - scores["A_default_template"], 2)
        effects["custom_additive_effect"] = {
            "label": "Default 위 Custom 추가 효과 (C - A)",
            "description": "기존 default prompt 위에 custom을 추가했을 때의 증분 효과",
            "formula": "C_custom_on_default - A_default_template",
            "value": diff,
            "C": scores["C_custom_on_default"],
            "A": scores["A_default_template"],
        }

    # A - B: default system prompt 자체의 효과
    if scores["A_default_template"] is not None and scores["B_no_system"] is not None:
        diff = round(scores["A_default_template"] - scores["B_no_system"], 2)
        effects["default_prompt_effect"] = {
            "label": "Default System Prompt의 효과 (A - B)",
            "description": "모델에 내장된 default system prompt가 성능에 미치는 영향",
            "formula": "A_default_template - B_no_system",
            "value": diff,
            "A": scores["A_default_template"],
            "B": scores["B_no_system"],
        }

    # E - D: chat template 구조 자체의 효과
    if scores["E_raw_custom"] is not None and scores["D_custom_replace"] is not None:
        diff = round(scores["E_raw_custom"] - scores["D_custom_replace"], 2)
        effects["template_structure_effect"] = {
            "label": "Chat Template 구조의 효과 (E - D)",
            "description": "동일 system prompt에서 chat template 유무에 따른 차이",
            "formula": "E_raw_custom - D_custom_replace",
            "value": diff,
            "E": scores["E_raw_custom"],
            "D": scores["D_custom_replace"],
        }

    return effects, scores


def generate_markdown_report(data, filename):
    """학술 보고서 스타일 마크다운 생성"""
    meta = data["experiment_meta"]
    results = data["results"]
    cond_scores, cond_meta, cat_scores = compute_stats(results)
    effects, overall_scores = compute_ablation_effects(cond_scores)

    lines = []

    # ============================================================
    # 제목
    # ============================================================
    lines.append("# Ablation Study: Default Chat Template의 Confounding Effect 분리")
    lines.append("")
    lines.append(f"> **모델**: {meta['model']}")
    lines.append(f"> **백엔드**: {meta['backend']}")
    lines.append(f"> **실험 일시**: {meta.get('started_at', 'N/A')[:19]}")
    lines.append(f"> **데이터 소스**: `{filename}`")
    lines.append("")

    # ============================================================
    # 1. 실험 동기 및 설계
    # ============================================================
    lines.append("## 1. 실험 동기 (Motivation)")
    lines.append("")
    lines.append("**리뷰어 피드백**: Qwen 등 오픈소스 모델은 chat template에 default system prompt가")
    lines.append("내장되어 있으므로, 시스템 프롬프트 실험에서 이 confounding variable을 통제하지 않으면")
    lines.append("관찰된 효과가 custom prompt 때문인지, default prompt과의 상호작용 때문인지 구분할 수 없다.")
    lines.append("")
    lines.append("**대응**: Ablation study를 통해 각 요소의 순수 효과를 분리한다.")
    lines.append("")

    # ============================================================
    # 2. 실험 설계
    # ============================================================
    lines.append("## 2. 실험 설계 (Experimental Design)")
    lines.append("")
    lines.append("### 2.1 실험 조건 (5-way Ablation)")
    lines.append("")
    lines.append("| 조건 | Default System | Custom System | Chat Template | 목적 |")
    lines.append("|------|:---:|:---:|:---:|------|")
    lines.append("| **A** Default Template | O | X | O | Baseline: 모델 기본 상태 |")
    lines.append("| **B** No System | X | X | O | Default prompt 제거 |")
    lines.append("| **C** Default + Custom | O | O (append) | O | 누적 효과 측정 |")
    lines.append("| **D** Custom Replace | X | O (replace) | O | Custom의 순수 효과 |")
    lines.append("| **E** Raw Custom | X | O | X (우회) | Template 자체 효과 분리 |")
    lines.append("")

    lines.append("### 2.2 핵심 비교 (Key Contrasts)")
    lines.append("")
    lines.append("| 비교 | 수식 | 측정 대상 |")
    lines.append("|------|------|----------|")
    lines.append("| Custom 순수 효과 | D - B | Default를 통제한 custom prompt 효과 |")
    lines.append("| Custom 추가 효과 | C - A | Default 위에 custom을 쌓았을 때 증분 |")
    lines.append("| Default Prompt 효과 | A - B | 내장 default system prompt의 영향 |")
    lines.append("| Template 구조 효과 | E - D | Chat template 형식 자체의 영향 |")
    lines.append("")

    lines.append("### 2.3 투명성: 실제 Rendered Prompt")
    lines.append("")
    lines.append(f"**모델 Default System Prompt**:")
    lines.append(f"```")
    lines.append(meta.get("default_system_prompt", "N/A"))
    lines.append(f"```")
    lines.append("")
    lines.append(f"**Chat Template** ({meta['model']}):")
    tmpl = meta.get("chat_template", {})
    lines.append(f"```")
    lines.append(f"system_prefix: {repr(tmpl.get('system_prefix', ''))}")
    lines.append(f"system_suffix: {repr(tmpl.get('system_suffix', ''))}")
    lines.append(f"user_prefix:   {repr(tmpl.get('user_prefix', ''))}")
    lines.append(f"user_suffix:   {repr(tmpl.get('user_suffix', ''))}")
    lines.append(f"assistant_prefix: {repr(tmpl.get('assistant_prefix', ''))}")
    lines.append(f"```")
    lines.append("")

    # ============================================================
    # 3. 결과: 조건별 종합 점수
    # ============================================================
    lines.append("## 3. 결과 (Results)")
    lines.append("")
    lines.append("### 3.1 조건별 종합 점수")
    lines.append("")

    metrics = ["correctness", "efficiency", "conciseness",
               "no_overengineering", "response_bloat", "instruction_following"]
    metric_labels = {
        "correctness": "정확성",
        "efficiency": "효율성",
        "conciseness": "간결성",
        "no_overengineering": "과잉설계방지",
        "response_bloat": "응답간결",
        "instruction_following": "지시준수",
    }

    cond_order = ["A_default_template", "B_no_system", "C_custom_on_default",
                  "D_custom_replace", "E_raw_custom"]
    cond_labels = {
        "A_default_template": "A. Default",
        "B_no_system": "B. No System",
        "C_custom_on_default": "C. Default+Custom",
        "D_custom_replace": "D. Custom Only",
        "E_raw_custom": "E. Raw Custom",
    }

    header = "| 조건 | " + " | ".join(metric_labels[m] for m in metrics) + " | **평균** |"
    sep = "|------|" + "|".join(["------"] * len(metrics)) + "|---------|"
    lines.append(header)
    lines.append(sep)

    for cond in cond_order:
        scores = cond_scores.get(cond, {})
        vals = [avg(scores.get(m, [])) for m in metrics]
        overall = round(sum(vals) / len(vals), 2) if any(vals) else 0
        vals_str = " | ".join(f"{v}" for v in vals)
        lines.append(f"| {cond_labels[cond]} | {vals_str} | **{overall}** |")

    lines.append("")

    # ============================================================
    # 3.2 효율성 비교
    # ============================================================
    lines.append("### 3.2 효율성 비교")
    lines.append("")
    lines.append("| 조건 | 평균 응답 길이(chars) | 평균 출력 토큰 | 평균 응답 시간(s) |")
    lines.append("|------|---------------------|---------------|------------------|")
    for cond in cond_order:
        m = cond_meta.get(cond, {})
        lines.append(f"| {cond_labels[cond]} | {avg(m.get('chars', []))} | "
                     f"{avg(m.get('output_tokens', []))} | {avg(m.get('times', []))} |")
    lines.append("")

    # ============================================================
    # 4. Ablation 분석 (핵심)
    # ============================================================
    lines.append("## 4. Ablation 분석 (핵심 결과)")
    lines.append("")
    lines.append("이 섹션이 리뷰어 피드백에 대한 직접적 대응입니다.")
    lines.append("")

    for key, effect in effects.items():
        sign = "+" if effect["value"] > 0 else ""
        significance = ""
        if abs(effect["value"]) < 0.3:
            significance = " (미미)"
        elif abs(effect["value"]) < 0.7:
            significance = " (소폭)"
        elif abs(effect["value"]) < 1.5:
            significance = " (유의미)"
        else:
            significance = " (큰 차이)"

        lines.append(f"### {effect['label']}")
        lines.append(f"- **수식**: `{effect['formula']}`")
        lines.append(f"- **결과**: {sign}{effect['value']}{significance}")
        lines.append(f"- **해석**: {effect['description']}")

        # 상세 값 표시
        for k, v in effect.items():
            if k in ("label", "description", "formula", "value"):
                continue
            lines.append(f"- {k} 평균 점수: {v}")
        lines.append("")

    # ============================================================
    # 5. 카테고리별 분석
    # ============================================================
    lines.append("## 5. 카테고리별 분석")
    lines.append("")

    categories = ["algorithm", "bugfix", "web", "data", "refactor"]
    cat_labels_kr = {
        "algorithm": "알고리즘", "bugfix": "버그 수정",
        "web": "웹/API", "data": "데이터 처리", "refactor": "리팩토링",
    }

    for cat in categories:
        lines.append(f"### {cat_labels_kr.get(cat, cat)}")
        lines.append("")
        lines.append("| 조건 | 정확성 | 간결성 | 과잉설계방지 | 평균 |")
        lines.append("|------|--------|--------|------------|------|")
        for cond in cond_order:
            cs = cat_scores.get(cond, {}).get(cat, {})
            c = avg(cs.get("correctness", []))
            co = avg(cs.get("conciseness", []))
            no = avg(cs.get("no_overengineering", []))
            overall = round((c + co + no) / 3, 2) if (c + co + no) else 0
            lines.append(f"| {cond_labels[cond]} | {c} | {co} | {no} | **{overall}** |")
        lines.append("")

    # ============================================================
    # 6. 결론
    # ============================================================
    lines.append("## 6. 결론 (Discussion)")
    lines.append("")

    # 자동 결론 생성
    custom_pure = effects.get("custom_pure_effect", {}).get("value", 0)
    default_effect = effects.get("default_prompt_effect", {}).get("value", 0)
    template_effect = effects.get("template_structure_effect", {}).get("value", 0)

    lines.append("### 리뷰어 피드백 대응")
    lines.append("")
    lines.append(f"1. **Default system prompt의 confounding effect**: "
                 f"A-B 비교에서 {'+' if default_effect > 0 else ''}{default_effect}점 차이 관찰. "
                 f"{'이는 default prompt가 실험에 유의미한 영향을 미침을 확인.' if abs(default_effect) > 0.5 else '이는 default prompt의 영향이 제한적임을 시사.'}")
    lines.append("")
    lines.append(f"2. **Custom system prompt의 순수 효과 (D-B)**: "
                 f"{'+' if custom_pure > 0 else ''}{custom_pure}점. "
                 f"{'Default prompt를 통제한 후에도 custom prompt가 독립적으로 성능을 개선함을 확인.' if custom_pure > 0 else 'Default prompt를 통제하면 custom prompt의 효과가 감소/소멸.'}")
    lines.append("")
    lines.append(f"3. **Chat template 구조의 효과 (E-D)**: "
                 f"{'+' if template_effect > 0 else ''}{template_effect}점. "
                 f"{'Chat template 형식 자체가 성능에 영향을 미침.' if abs(template_effect) > 0.5 else 'Chat template 형식 자체의 영향은 제한적.'}")
    lines.append("")
    lines.append("### 방법론적 의의")
    lines.append("")
    lines.append("- 본 실험은 5-way ablation을 통해 system prompt 효과를 default prompt, custom prompt,")
    lines.append("  chat template 구조의 세 가지 요소로 분해하여 각각의 기여를 독립적으로 측정함")
    lines.append("- 모든 조건에서 실제 rendered prompt를 기록하여 실험의 투명성을 확보함")
    lines.append("- Raw completion API를 활용한 조건 E를 통해 chat template 자체의 효과를 분리함")
    lines.append("")

    # ============================================================
    # 7. 개별 결과 상세 (접기)
    # ============================================================
    lines.append("## 7. 개별 결과 상세")
    lines.append("")

    for r in results:
        if "error" in r or "evaluation" not in r:
            continue
        ev = r["evaluation"]
        if "error" in ev:
            continue

        lines.append(f"### {r['test_id']} | {cond_labels.get(r['condition'], r['condition'])}")
        lines.append("")
        for metric, val in ev.items():
            if isinstance(val, dict) and "score" in val:
                lines.append(f"- **{metric}**: {val['score']}/10 — {val.get('reason', '')}")

        resp_preview = r.get("response", "")[:2000]
        lines.append(f"\n<details><summary>응답 ({r.get('response_length', 0)} chars)</summary>\n")
        lines.append(f"```\n{resp_preview}\n```\n</details>\n")

    # ============================================================
    # Appendix: Rendered Prompts 샘플
    # ============================================================
    lines.append("## Appendix: Rendered Prompt 샘플")
    lines.append("")
    lines.append("실험 투명성을 위해 각 조건에서 실제 모델에 전달된 prompt의 처음 500자를 기록합니다.")
    lines.append("")

    seen_conds = set()
    for r in results:
        cond = r["condition"]
        if cond in seen_conds:
            continue
        seen_conds.add(cond)
        rendered = r.get("rendered_prompt", "N/A")
        lines.append(f"### {cond_labels.get(cond, cond)}")
        lines.append(f"```")
        lines.append(rendered[:500])
        lines.append(f"```")
        lines.append("")

    return "\n".join(lines)


def generate_html_report(md_content: str, filename: str) -> str:
    """마크다운을 간단한 HTML로 변환"""
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Ablation Study Report - {filename}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       max-width: 960px; margin: 40px auto; padding: 0 20px;
       color: #333; line-height: 1.6; }}
h1 {{ border-bottom: 2px solid #2563eb; padding-bottom: 10px; }}
h2 {{ border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; margin-top: 2em; }}
h3 {{ color: #1e40af; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
th, td {{ border: 1px solid #d1d5db; padding: 8px 12px; text-align: center; }}
th {{ background: #f3f4f6; font-weight: 600; }}
tr:nth-child(even) {{ background: #f9fafb; }}
blockquote {{ border-left: 4px solid #2563eb; padding-left: 16px;
             margin-left: 0; color: #4b5563; background: #f0f9ff; padding: 12px 16px; }}
code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }}
pre {{ background: #1e293b; color: #e2e8f0; padding: 16px; border-radius: 8px;
       overflow-x: auto; }}
pre code {{ background: none; color: inherit; }}
details {{ margin: 1em 0; }}
summary {{ cursor: pointer; font-weight: 500; color: #2563eb; }}
.positive {{ color: #059669; font-weight: 600; }}
.negative {{ color: #dc2626; font-weight: 600; }}
.neutral {{ color: #6b7280; }}
</style>
</head>
<body>
<div id="content">
"""
    # 간단한 마크다운 -> HTML 변환 (외부 라이브러리 없이)
    in_code_block = False
    in_table = False
    in_list = False

    for line in md_content.split("\n"):
        if line.startswith("```"):
            if in_code_block:
                html += "</code></pre>\n"
                in_code_block = False
            else:
                html += "<pre><code>"
                in_code_block = True
            continue

        if in_code_block:
            html += line.replace("<", "&lt;").replace(">", "&gt;") + "\n"
            continue

        # 테이블
        if line.startswith("|"):
            if not in_table:
                html += "<table>\n"
                in_table = True
            if line.replace("|", "").replace("-", "").strip() == "":
                continue  # separator row
            cells = [c.strip() for c in line.split("|")[1:-1]]
            tag = "th" if not any("**" in c for c in cells) and in_table else "td"
            row = "".join(f"<{tag}>{c.replace('**', '')}</{tag}>" for c in cells)
            html += f"<tr>{row}</tr>\n"
            continue
        elif in_table:
            html += "</table>\n"
            in_table = False

        # 리스트
        if line.startswith("- "):
            if not in_list:
                html += "<ul>\n"
                in_list = True
            content = line[2:]
            # bold
            while "**" in content:
                content = content.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
            html += f"<li>{content}</li>\n"
            continue
        elif in_list and not line.startswith("  "):
            html += "</ul>\n"
            in_list = False

        # 헤더
        if line.startswith("### "):
            html += f"<h3>{line[4:]}</h3>\n"
        elif line.startswith("## "):
            html += f"<h2>{line[3:]}</h2>\n"
        elif line.startswith("# "):
            html += f"<h1>{line[2:]}</h1>\n"
        elif line.startswith("> "):
            html += f"<blockquote>{line[2:]}</blockquote>\n"
        elif line.startswith("<details"):
            html += line + "\n"
        elif line.startswith("</details"):
            html += line + "\n"
        elif line.startswith("<summary"):
            html += line + "\n"
        elif line.strip() == "":
            html += "<br>\n"
        else:
            # inline code
            while "`" in line:
                line = line.replace("`", "<code>", 1).replace("`", "</code>", 1)
            html += f"<p>{line}</p>\n"

    if in_table:
        html += "</table>\n"
    if in_list:
        html += "</ul>\n"

    html += """
</div>
</body>
</html>"""
    return html


def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else None
    data, filename = load_ablation_results(filepath)

    # 마크다운 보고서
    md_report = generate_markdown_report(data, filename)
    md_file = RESULTS_DIR / "ABLATION_REPORT.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"마크다운 보고서: {md_file}")

    # HTML 보고서
    html_report = generate_html_report(md_report, filename)
    html_file = RESULTS_DIR / "ablation_report.html"
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_report)
    print(f"HTML 보고서: {html_file}")

    # 미리보기
    print("\n" + "=" * 70)
    print(md_report[:3000])
    print("...\n(전체 보고서는 파일 참조)")


if __name__ == "__main__":
    main()
