# -*- coding: utf-8 -*-
"""YG chart_plan.json 후처리 (idempotent)
1) [제안] 도표 3종(fact_comparison / waterfall / risk_matrix) 데이터를 본문 근거로 채움
2) 병합으로 미렌더되는 섹션(s10/s11/s12) 차트를 호스트 섹션(s06/s07)으로 재매핑
"""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'data', '와이지엔터', 'chart_plan.json')
plan = json.load(open(P, encoding='utf-8'))

FILL = {
    # 앞 페이지 마크다운 '경쟁 구도 비교'(정성)와 중복되지 않도록 밸류에이션·주가 관점으로 구성
    'fact_comparison': {
        "columns": ["항목", "와이지엔터", "하이브", "에스엠", "JYP"],
        "rows": [
            ["시가총액 (억원)", "7,766", "79,748", "17,308", "16,629"],
            ["PER 후행 (배)", "21.05", "적자", "5.00", "10.36"],
            ["PBR (배)", "1.50", "2.41", "1.73", "2.50"],
            ["12M 선행 PER (배)", "16", "25", "15", "16"],
            ["52주 고점 대비", "-61.3%", "-54.4%", "-46.2%", "-41.4%"],
            ["2025 영업이익률", "13.1%", "적자", "-", "-"],
        ],
        "highlight_col": 1,
    },
    'waterfall': {
        "labels": ["현재가", "이익 성장", "멀티플 회복", "목표주가"],
        "values": [41550, 5100, 2350, 49000],
        "is_total": [True, False, False, True],
        "ylabel": "주가 (원)",
    },
    'risk_matrix': {
        "risks": [
            {"name": "2027년\nIP 공백", "prob": 4, "impact": 5},
            {"name": "이익의 질\n(비지배·금융)", "prob": 5, "impact": 3},
            {"name": "섹터\n디레이팅", "prob": 3, "impact": 4},
            {"name": "신인 데뷔\n부진", "prob": 3, "impact": 3},
            {"name": "블랙핑크\n활동 축소", "prob": 2, "impact": 5},
            {"name": "해외 매출\n인식 구조", "prob": 5, "impact": 2},
            {"name": "중국 공연\n재개 지연", "prob": 4, "impact": 2},
        ]
    },
}

RETITLE = {
    'fact_comparison': '엔터 4사 밸류에이션·주가 비교',
}

# 출처 정정: FnGuide(SVD_Main)는 이번 수집에서 응답이 없어 실제 데이터는
# DART 전자공시 + KIS Open API + Wisereport 에서 왔다. 카탈로그 기본 출처 문자열을 실제 원천으로 교체.
RESOURCE = {
    'c03_peer_multiples': 'KIS Open API (2026-08-07 종가 기준)',
    'c04_fact_comparison': 'KIS Open API, 증권사 산업 리포트(2026-05), 위닝펀드 3조 황성혁',
    'c05_dupont_roe': 'DART 사업보고서(2022~2025), 2026E 자체 추정, 위닝펀드 3조 황성혁',
    'c06_consensus_gap': 'DART 사업보고서·분기보고서, Wisereport',
    'c07_consensus_gap': 'DART 사업보고서(2022~2025), 2026E 자체 추정, 위닝펀드 3조 황성혁',
    'c10_consensus_gap': 'DART 분기·반기·사업보고서, 2Q26 잠정실적 공시(2026-08-07)',
    'c11_consensus_gap': 'KIS Open API (최근 20거래일)',
}

REMAP = {
    's10_earnings_consensus': 's06_financial',
    's11_supply_shareholder': 's06_financial',
    's12_action_plan': 's07_valuation',
    's05_management_fieldcheck': 's03_company_overview',
}

n_fill = n_remap = 0
for c in plan['charts']:
    if c.get('data') is None and c['archetype'] in FILL:
        c['data'] = FILL[c['archetype']]
        n_fill += 1
    if c['archetype'] in RETITLE:
        c['title'] = RETITLE[c['archetype']]
        c['caption'] = f"도표 {c['order']}. {c['title']}"
    if c['name'] in RESOURCE:
        c['source'] = RESOURCE[c['name']]
    old = c['section_key']
    if old in REMAP:
        c['section_key'] = REMAP[old]
        n_remap += 1
        print(f"  remap: {c['caption']}  {old} -> {c['section_key']}")

tmp = P + '.tmp'
json.dump(plan, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
os.replace(tmp, P)

still_null = [c['caption'] for c in plan['charts'] if c.get('data') is None]
print(f"[OK] {P}")
print(f"  데이터 채움 {n_fill}건 / 섹션 재매핑 {n_remap}건 / 총 {len(plan['charts'])}개")
print(f"  data=null 잔여: {still_null if still_null else '없음'}")
