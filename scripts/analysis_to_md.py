# -*- coding: utf-8 -*-
"""
analysis.json -> draft markdown converter (v4.21 신설)

목적: PDF 생성 전 사용자 검토를 위한 마크다운 초안 생성.
사용: python scripts/analysis_to_md.py {종목명}
출력: output/{종목명}/draft_{종목명}.md

워크플로우:
  STEP 4 (analysis.json Write) -> STEP 4.5 (이 스크립트로 draft.md 생성)
  -> 사용자 검토 -> 수정 필요 시 analysis.json 다시 Write -> draft.md 재생성
  -> 사용자 OK -> STEP 5 generate_all.py로 PDF 1회만 생성
"""
import sys
import io
import json
import os
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 21 섹션 한글 제목 매핑
# v4.21 호환 (21섹션) - 구 종목용
SECTION_TITLES_V4 = {
    "s01_opinion":               "1. 투자의견 & 목표주가",
    "s02_investment_points":     "2. 투자 포인트",
    "s03_company_overview":      "3. 회사 개요",
    "s04_industry":              "4. 산업 / 시장",
    "s05_competition":           "5. 경쟁 구도 + Peer Comparison",
    "s06_moat":                  "6. 경제적 해자",
    "s07_management":            "7. 경영진 + 내부자 매매",
    "s08_financial":             "8. 재무 분석",
    "s09_valuation":             "9. 밸류에이션",
    "s10_macro":                 "10. 매크로 리스크",
    "s11_catalysts":             "11. 카탈리스트 타임라인",
    "s12_scenarios":             "12. Bear / Base / Bull",
    "s13_thesis":                "13. 투자 논문",
    "s14_short_thesis":          "14. 숏 논거 + 반박",
    "s15_beat_miss":             "15. 실적 Beat / Miss",
    "s16_consensus":             "16. 애널리스트 컨센서스",
    "s17_supply":                "17. 수급 분석",
    "s18_shareholder_return":    "18. 주주환원",
    "s19_trust_worry_watch":     "19. Trust / Worry / Watch",
    "s20_action_plan":           "20. 실행 계획",
    "s21_reliability":           "21. 분석 신뢰도 & 한계",
}

# v5.0 (12섹션) - 1티어 애널리스트 방법론, 사용자 강조 ★ 4섹션 독립
# 가독성 순서: 의견 → 핵심 근거 → 회사 → 산업 → 경쟁 → 재무 → 밸류 → 경영진 → ESG → 리스크 → 실적/수급 → 실행
SECTION_TITLES_V5 = {
    "s01_opinion_thesis":        "1. 투자의견과 한 줄 투자 논문",
    "s02_thesis_catalysts":      "2. 투자포인트와 카탈리스트",
    "s03_company_overview":      "3. 회사 개요",
    "s04_industry":              "4. 산업 분석",
    "s05_competitive_moat":      "5. 경쟁 구도와 경제적 해자",
    "s07_financial_analysis":    "6. 재무 분석",
    "s08_valuation":             "7. 밸류에이션",
    "s06_management_fieldcheck": "8. 경영진과 현장 검증",
    "s09_esg":                   "9. ESG 분석",
    "s10_scenarios_risks":       "10. 시나리오와 리스크",
    "s11_earnings_consensus":    "11. 실적과 수급",
    "s12_action_plan":           "12. 실행 계획",
}


def detect_version(sections):
    """v5.0 키가 하나라도 있으면 v5.0 모드, 없으면 v4 모드"""
    v5_unique_keys = ['s01_opinion_thesis', 's02_thesis_catalysts',
                      's05_competitive_moat', 's07_financial_analysis',
                      's09_esg', 's10_scenarios_risks',
                      's11_earnings_consensus', 's12_action_plan']
    has_v5 = any(k in sections for k in v5_unique_keys)
    return 'v5.0' if has_v5 else 'v4.21'


def get_section_titles(sections):
    version = detect_version(sections)
    return (SECTION_TITLES_V5 if version == 'v5.0' else SECTION_TITLES_V4), version


# 호환 보존 (다른 모듈에서 SECTION_TITLES 참조 가능성)
SECTION_TITLES = SECTION_TITLES_V4


def fmt_num(v, unit=""):
    if v is None:
        return "n/a"
    if isinstance(v, (int, float)):
        if abs(v) >= 1e8:
            return f"{v:,.0f}{unit}"
        if abs(v) >= 1:
            return f"{v:,.2f}{unit}".rstrip("0").rstrip(".") + unit if "." in f"{v:,.2f}" else f"{v:,.0f}{unit}"
        return f"{v}{unit}"
    return f"{v}{unit}"


def make_cover(d):
    meta = d.get("meta", {})
    price = d.get("price", {})
    opinion = d.get("opinion", {})

    out = []
    out.append(f"# {meta.get('stock_name', '?')} 리서치 리포트")
    out.append("")
    if meta.get("tagline"):
        out.append(f"> **{meta['tagline']}**")
        out.append("")
    out.append(f"- **종목코드**: {meta.get('stock_code', '?')}")
    out.append(f"- **시장**: {meta.get('market', '?')} / {meta.get('industry', '?')}")
    out.append(f"- **작성일**: {meta.get('date', '?')}")
    out.append(f"- **분석가**: {meta.get('analyst', '?')}")
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 한눈에 보기")
    out.append("")
    out.append("| 항목 | 값 |")
    out.append("|---|---|")
    cur = price.get("current", 0)
    cur_str = f"{cur:,}원" if isinstance(cur, (int, float)) else str(cur)
    out.append(f"| 현재가 | {cur_str} ({price.get('change_pct', 0):+.2f}%) |")
    out.append(f"| 시가총액 | {price.get('market_cap', '?')} |")
    out.append(f"| PER (TTM) | {price.get('per', '?')}배 |")
    out.append(f"| PBR | {price.get('pbr', '?')}배 |")
    out.append(f"| 52주 최고 / 최저 | {price.get('high_52w', '?'):,}원 / {price.get('low_52w', '?'):,}원 |")
    out.append(f"| 1Y 수익률 | {price.get('returns_1y_pct', 0):+.2f}% |")
    out.append(f"| 베타 (52주) | {price.get('beta_52w', '?')} |")
    out.append("")
    out.append("## 투자의견")
    out.append("")
    out.append("| 항목 | 값 |")
    out.append("|---|---|")
    out.append(f"| **레이팅** | **{opinion.get('rating', '?')}** |")
    out.append(f"| 상세 | {opinion.get('type', '')} |")
    out.append(f"| Bear / Base / Bull | {opinion.get('target_bear', '?'):,} / **{opinion.get('target_base', '?'):,}** / {opinion.get('target_bull', '?'):,}원 |")
    out.append(f"| Risk-Reward | {opinion.get('risk_reward', '?')} |")
    out.append(f"| 포지션 권고 | {opinion.get('portfolio_role', '?')} |")
    out.append("")
    return "\n".join(out)


def make_segments(d):
    segs = d.get("segments", []) or []
    if not segs:
        return ""
    out = ["## 사업 부문 구성", "", "| 부문 | 비중 | 전망 |", "|---|---|---|"]
    for s in segs:
        out.append(f"| {s.get('name', '?')} | {s.get('pct', 0)}% | {s.get('outlook', '')} |")
    out.append("")
    return "\n".join(out)


def make_financials(d):
    fin = d.get("financials", {}) or {}
    headers = fin.get("headers", []) or []
    rows = fin.get("rows", {}) or {}
    if not headers or not rows:
        return ""
    out = ["## Forward 6년 재무 테이블", ""]
    out.append("| " + " | ".join(headers) + " |")
    out.append("|" + "---|" * len(headers))
    for k, v in rows.items():
        if isinstance(v, list):
            cells = [k] + [str(x) for x in v]
            # Pad to header length
            while len(cells) < len(headers):
                cells.append("")
            out.append("| " + " | ".join(cells[: len(headers)]) + " |")
    src = fin.get("source", "")
    if src:
        out.append("")
        out.append(f"_출처: {src}_")
    out.append("")
    return "\n".join(out)


def make_quarterly(d):
    q = d.get("quarterly", {}) or {}
    headers = q.get("headers", []) or []
    rows = q.get("rows", {}) or {}
    if not headers or not rows:
        return ""
    # v5.4 패치: rows가 list of list 형식 지원 (대한항공/풍산 v5+)
    if isinstance(rows, list):
        out = ["## 분기별 실적", ""]
        out.append("| " + " | ".join(headers) + " |")
        out.append("|" + "---|" * len(headers))
        for row in rows:
            if isinstance(row, list):
                cells = [str(x) for x in row]
                while len(cells) < len(headers):
                    cells.append("")
                out.append("| " + " | ".join(cells[: len(headers)]) + " |")
        note = q.get("note", "")
        if note:
            out.append("")
            out.append(f"_주: {note}_")
        out.append("")
        return "\n".join(out)
    out = ["## 분기 실적 추이", ""]
    out.append("| " + " | ".join(headers) + " |")
    out.append("|" + "---|" * len(headers))
    for k, v in rows.items():
        if isinstance(v, list):
            cells = [k] + [str(x) for x in v]
            while len(cells) < len(headers):
                cells.append("")
            out.append("| " + " | ".join(cells[: len(headers)]) + " |")
    note = q.get("note", "")
    if note:
        out.append("")
        out.append(f"**주석**: {note}")
    out.append("")
    return "\n".join(out)


def make_supply(d):
    s = d.get("supply", {}) or {}
    if not s:
        return ""
    out = ["## 수급 (20일)", ""]
    out.append("| 투자자 | 순매수 (주) |")
    out.append("|---|---|")
    def _fmt_supply(v):
        if isinstance(v, (int, float)):
            return f'{v:+,}'
        return str(v) if v else '0'
    out.append(f"| 외국인 | {_fmt_supply(s.get('foreign', 0))} |")
    out.append(f"| 기관 | {_fmt_supply(s.get('institution', 0))} |")
    out.append(f"| 개인 | {_fmt_supply(s.get('individual', 0))} |")
    cmt = s.get("comment", "")
    if cmt:
        out.append("")
        out.append(f"**해석**: {cmt}")
    out.append("")
    return "\n".join(out)


def make_peers(d):
    peers = d.get("peers", []) or []
    if not peers:
        return ""
    out = ["## Peer Comparison", "", "| 회사 | 시총 | PER | PBR | 비고 |", "|---|---|---|---|---|"]
    for p in peers:
        mark = "★ " if p.get("highlight") else ""
        out.append(
            f"| {mark}{p.get('name', '?')} | {p.get('market_cap', '?')} | {p.get('per', '?')} | {p.get('pbr', '?')} | {p.get('note', '')} |"
        )
    out.append("")
    return "\n".join(out)


def make_catalysts(d):
    cats = d.get("catalysts", []) or []
    if not cats:
        return ""
    out = ["## 카탈리스트 타임라인", "", "| 시기 | 이벤트 | 영향 |", "|---|---|---|"]
    for c in cats:
        out.append(f"| {c.get('date', '?')} | {c.get('event', '?')} | {c.get('impact', '')} |")
    out.append("")
    return "\n".join(out)


def make_sections(d):
    sections = d.get("sections", {}) or {}
    titles, version = get_section_titles(sections)
    n_sections = len(titles)

    out = []
    out.append("---")
    out.append("")
    out.append(f"# 본문 ({n_sections}섹션, {version})")
    out.append("")

    for key, title in titles.items():
        body = sections.get(key, "")
        if not body:
            # v5.0인데 v5 키 없으면 v4 키로 fallback 시도
            if version == 'v5.0':
                v5_to_v4_fallback = {
                    's01_opinion_thesis': ['s01_opinion', 's13_thesis'],
                    's02_thesis_catalysts': ['s02_investment_points', 's11_catalysts'],
                    's05_competitive_moat': ['s05_competition', 's06_moat'],
                    's06_management_fieldcheck': ['s07_management'],
                    's07_financial_analysis': ['s08_financial'],
                    's08_valuation': ['s09_valuation'],
                    's10_scenarios_risks': ['s12_scenarios', 's10_macro', 's14_short_thesis'],
                    's11_earnings_consensus': ['s15_beat_miss', 's16_consensus', 's17_supply', 's18_shareholder_return'],
                    's12_action_plan': ['s20_action_plan', 's19_trust_worry_watch', 's21_reliability'],
                }
                for fb_key in v5_to_v4_fallback.get(key, []):
                    if sections.get(fb_key):
                        body = sections[fb_key]
                        break

        if not body:
            out.append(f"## {title}")
            out.append("")
            out.append(f"_(섹션 누락 -- {key})_")
            out.append("")
            continue

        # 섹션 제목을 v5 형식으로 명시 (본문 안에 ## 헤더가 있어도 v5 번호 표기 우선)
        out.append(f"## {title}")
        out.append("")
        # 본문 내 첫 ## 헤더는 중복이므로 제거 (v5 번호 헤더와 중복 방지)
        body_lines = body.rstrip().split('\n')
        if body_lines and body_lines[0].startswith('## '):
            body_lines = body_lines[1:]
            # 첫 빈 줄도 제거
            while body_lines and not body_lines[0].strip():
                body_lines = body_lines[1:]
        out.append('\n'.join(body_lines))
        out.append("")
        out.append("---")
        out.append("")
    return "\n".join(out)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/analysis_to_md.py {종목명}")
        sys.exit(1)
    stock_name = sys.argv[1]

    in_path = Path(f"scripts/analysis_{stock_name}.json")
    if not in_path.exists():
        print(f"[ERROR] {in_path} 없음")
        sys.exit(1)

    d = json.load(open(in_path, encoding="utf-8"))

    out_dir = Path(f"output/{stock_name}")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"draft_{stock_name}.md"

    parts = [
        make_cover(d),
        make_segments(d),
        make_financials(d),
        make_quarterly(d),
        make_supply(d),
        make_peers(d),
        make_catalysts(d),
        make_sections(d),
    ]

    md = "\n".join(p for p in parts if p)

    out_path.write_text(md, encoding="utf-8")

    # Stats
    total_chars = sum(len(v) for v in d.get("sections", {}).values() if isinstance(v, str))
    n_tables = md.count("\n| ") - md.count("\n|---")
    n_quotes = md.count("\n> ")

    print(f"[OK] draft md saved: {out_path}")
    print(f"  - 본문 분량: {total_chars:,}자")
    print(f"  - 마크다운 줄 수: {len(md.splitlines()):,}")
    print(f"  - 표 행 수: {n_tables}")
    print(f"  - 인용 박스: {n_quotes}")
    print(f"  - opinion: {d.get('opinion', {}).get('rating')} / Base {d.get('opinion', {}).get('target_base')} / Bull {d.get('opinion', {}).get('target_bull')}")
    print()

    # ========== v5.0 12섹션 자동 검증 ==========
    print("[v5.0 12섹션 검증]")
    sections = d.get('sections', {})
    # v5.0 표준 12섹션 키 (실제 작성 시 v4.21 호환 키도 인정)
    v5_keys = [
        ('s01', ['s01_opinion', 's01_opinion_thesis']),
        ('s02', ['s02_investment_points', 's02_thesis_catalysts']),
        ('s03', ['s03_company_overview']),
        ('s04', ['s04_industry', 's04_industry_competition']),
        ('s05', ['s05_competition', 's05_competitive_moat']),
        ('s06', ['s06_moat', 's06_management_fieldcheck', 's07_management']),
        ('s07', ['s07_financial_analysis', 's08_financial']),
        ('s08', ['s08_valuation', 's09_valuation']),
        ('s09', ['s09_esg', 's10_esg']),
        ('s10', ['s10_scenarios_risks', 's10_macro', 's12_scenarios', 's14_short_thesis']),
        ('s11', ['s11_earnings_consensus', 's15_beat_miss', 's16_consensus', 's17_supply', 's18_shareholder_return']),
        ('s12', ['s12_action_plan', 's19_trust_worry_watch', 's20_action_plan', 's21_reliability']),
    ]
    found = 0
    missing = []
    section_chars = {}
    for label, candidates in v5_keys:
        hit = None
        for c in candidates:
            if c in sections and sections[c]:
                hit = c
                section_chars[label] = len(sections[c])
                found += 1
                break
        if not hit:
            missing.append(label)

    print(f"  - 12섹션 충족: {found}/12")
    if missing:
        print(f"  - 누락: {missing}")

    # 깊이 검증 (사용자 4대 강조 섹션은 깊이 우선)
    depth_warnings = []
    depth_thresholds = {
        's02': 3000,  # 투자포인트 ★
        's03': 2500,  # 회사개요 ★
        's04': 2500,  # 산업분석 ★
        's07': 3000,  # 재무분석 ★
    }
    for label, threshold in depth_thresholds.items():
        n = section_chars.get(label, 0)
        if n < threshold:
            depth_warnings.append(f"{label} {n:,}자 < {threshold:,}자")

    if depth_warnings:
        print(f"  - [WARN] 사용자 강조 섹션 깊이 부족:")
        for w in depth_warnings:
            print(f"      {w}")
        print(f"      → v5.0 핵심 철학: \"섹션 수 축소 = 내용의 질 향상\". 통합된 분량을 깊이로 전환 필수.")
    else:
        print(f"  - [OK] 사용자 강조 4섹션(s02/s03/s04/s07) 모두 깊이 충족")

    # Executive Summary Card (커버 직후 1p) 존재 여부
    cover_text = sections.get('s01_opinion', '') + sections.get('s01_opinion_thesis', '')
    has_exec_card = (
        ('Executive Summary' in cover_text or '한눈에 보기' in cover_text) and
        ('Top 3 Catalysts' in cover_text or '카탈리스트' in cover_text) and
        ('Top 3 Risks' in cover_text or '리스크' in cover_text)
    )
    if not has_exec_card:
        print(f"  - [WARN] Executive Summary Card 누락 -- 첫 페이지 1p 압축 권장 (Goldman/Morgan Stanley 표준)")

    print()
    print(f"[NEXT] 사용자 검토 후 OK 시: python scripts/generate_all.py scripts/analysis_{stock_name}.json")
    print(f"[NEXT] 수정 필요 시: analysis.json 재 Write → 다시 이 스크립트 실행")


if __name__ == "__main__":
    main()
