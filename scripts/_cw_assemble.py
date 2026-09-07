# -*- coding: utf-8 -*-
"""씨에스윈드 analysis.json 조립부: 병합 -> alias 재생성 -> 원자 dump.

_build_씨에스윈드.py 하단에서 import 해 build(...) 를 호출한다.
"""
import os
import re
import json

# 위닝펀드 7섹션 렌더 순서
SECTION_ORDER = [
    's01_opinion_thesis',        # 1. 요약
    's04_industry_competition',  # 2. 산업 분석
    's03_company_overview',      # 3. 기업 분석 (+ s05 병합)
    's02_thesis_catalysts',      # 4. 투자 포인트
    's06_financial',             # 5. 재무 분석
    's09_scenarios_risks',       # 6. 리스크
    's07_valuation',             # 7. 밸류에이션
]


def _demote(md):
    """맨 위 '## ' 만 '### ' 로 강등. 내부 ### 소제목은 유지(차트 매칭 보존)."""
    return re.sub(r'^##\s', '### ', md.strip(), count=1)


def build(out_path, meta, price, opinion, segments, financials, quarterly,
          supply, peers, catalysts, S):
    # --- 1) 보조 섹션 병합 (alias 재생성 전에 수행) ---
    # s05(지배구조·주주환원) -> 기업 분석 호스트
    S['s03_company_overview'] = S['s03_company_overview'] + '\n\n' + _demote(S['s05_management_fieldcheck'])
    # s07 은 s12 를 이미 본문에 통합했으므로 추가 병합하지 않는다.
    # s06 은 실적/컨센/수급을 이미 본문에 통합했으므로 s10/s11 을 병합하지 않는다(중복 방지).

    # --- 2) alias 키 재생성 (CLAUDE.md v5.0 키 스킴 분열 대응) ---
    S['s08_financial'] = S['s06_financial']
    S['s09_valuation'] = S['s07_valuation']
    S['s10_scenarios_risks'] = S['s09_scenarios_risks']
    S['s11_earnings_consensus'] = S['s10_earnings_consensus'] + '\n\n' + S['s11_supply_shareholder']
    S['s02_investment_points'] = S['s02_thesis_catalysts']
    S['s04_industry'] = S['s04_industry_competition']
    S['s01_opinion'] = S['s01_opinion_thesis']
    S['s07_financial_analysis'] = S['s06_financial']

    meta = dict(meta)
    meta['section_order'] = SECTION_ORDER

    doc = {
        'meta': meta,
        'price': price,
        'opinion': opinion,
        'segments': segments,
        'financials': financials,
        'quarterly': quarterly,
        'supply': supply,
        'peers': peers,
        'catalysts': catalysts,
        'sections': S,
    }

    tmp = out_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    os.replace(tmp, out_path)

    total = sum(len(v) for v in S.values())
    rendered = sum(len(S[k]) for k in SECTION_ORDER)
    return {'sections': len(S), 'rendered': len(SECTION_ORDER),
            'chars_total': total, 'chars_rendered': rendered}
