# Claude Code System Prompt Effect Test

Claude Code의 유출된 시스템 프롬프트(하니스)를 다른 모델에 적용했을 때 코드 생성 품질이 향상되는지 검증하는 실험 리포지토리.

## 핵심 결론

- **바닐라 Qwen3.5-27B + 하니스 = +26.5% 향상** (6.83 → 8.64)
- **바닐라+하니스(8.64) ≈ Distilled+하니스(8.53)** → Distillation 무관, 프롬프트 자체의 힘
- **Claude Opus 4.6(9.14)의 94.5%** 달성
- 토큰 74% 절감, 응답 시간 73% 절감

## 실험 구성

| 실험 | 파일 | 핵심 질문 | 결과 |
|------|------|----------|------|
| 1. 3-Column 비교 | `run_h100_experiment.py` | 하니스가 성능을 올리는가? | +34% |
| 2. Inverse Prompt | `run_inverse_experiment.py` | Distillation 때문인가? | 아니다 |
| 3. 5-way Ablation | `run_vllm_ablation.py` | Default template confounding? | 무시 가능 |
| 4. 바닐라 검증 | `run_vanilla_experiment.py` | 바닐라에서도? Claude와 비교? | +26.5%, Claude의 94.5% |

## 파일 구조

```
├── run_h100_experiment.py          # 실험 1: Distilled 3-Column 비교
├── run_inverse_experiment.py       # 실험 2: Inverse Prompt 검증
├── run_supplement.py               # 실험 2: 보충 실험
├── run_vllm_ablation.py            # 실험 3: 5-way Ablation
├── run_vanilla_experiment.py       # 실험 4: 바닐라 Qwen + 알리바바 API
├── run_vanilla_claude_supplement.py # 실험 4: Claude Opus 4.6 보충
├── generate_ablation_report.py     # 실험 3 리포트 생성
├── generate_v3_html.py             # v3 HTML 리포트 생성
└── results/
    ├── FINAL_COMPREHENSIVE_REPORT_v3.md    # 종합 리포트 (최종)
    ├── FINAL_COMPREHENSIVE_REPORT_v3.html  # 종합 리포트 HTML
    ├── REPORT.md                           # 실험 1 리포트
    ├── REPORT_INVERSE.md                   # 실험 2 리포트
    ├── ABLATION_FINAL.md                   # 실험 3 리포트
    ├── h100_experiment_*.json              # 실험 1 데이터
    ├── inverse_experiment_*.json           # 실험 2 데이터
    ├── ablation_*.json                     # 실험 3 데이터
    ├── vanilla_experiment_*.json           # 실험 4 데이터
    └── vanilla_claude_supplement_*.json    # 실험 4 Claude 보충
```

## 실험 환경

- **Distilled 모델**: Jackrong/Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled (vLLM, H200 4-way)
- **바닐라 모델**: Alibaba Cloud qwen3.5-27b (DashScope API)
- **평가**: Claude Opus 4.6 LLM-as-judge (6개 기준, 1-10점)
- **하니스 출처**: [Piebald-AI/claude-code-system-prompts](https://github.com/Piebald-AI/claude-code-system-prompts)

## 참고자료

- [Piebald-AI/claude-code-system-prompts](https://github.com/Piebald-AI/claude-code-system-prompts) — Claude Code 시스템 프롬프트 254개 파일
- [sanbuphy/learn-coding-agent](https://github.com/sanbuphy/learn-coding-agent) — Claude Code 아키텍처 분석
- [Gitlawb/openclaude](https://github.com/Gitlawb/openclaude) — Claude Code 전체 런타임 포크 (다음 실험 예정)
