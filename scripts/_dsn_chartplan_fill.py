# -*- coding: utf-8 -*-
"""덕산네오룩스 chart_plan.json 후처리 (idempotent)
1) [제안] fact_comparison / risk_matrix 데이터 채움
2) SOTP 부문별 가치 분해 워터폴 신규 추가 (밸류에이션 2단계 표와 1:1 대응)
3) 미렌더 섹션(s10/s11/s12) 차트를 호스트(s06/s07)로 재매핑
4) 출처 정정 (FnGuide 무응답 -> 실제 원천 DART/KIS 로 교체)
"""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'data', '덕산네오룩스', 'chart_plan.json')
plan = json.load(open(P, encoding='utf-8'))

FILL = {
    'fact_comparison': {
        "columns": ["항목", "덕산네오룩스", "솔브레인", "동진쎄미켐", "PI첨단소재", "이녹스첨단소재"],
        "rows": [
            ["시가총액 (억원)", "8,765", "25,514", "22,019", "5,873", "4,556"],
            ["후행 PER (배)", "16.48", "32.27", "22.42", "25.13", "7.96"],
            ["PBR (배)", "1.92", "2.38", "2.05", "1.74", "1.09"],
            ["5년 평균 PER (배)", "28.46", "-", "-", "-", "-"],
            ["Forward PER (배)", "10.8", "-", "-", "-", "-"],
            ["시총 대비 순현금 (%)", "20.5", "-", "-", "-", "-"],
        ],
        "highlight_col": 1,
    },
    'risk_matrix': {
        "risks": [
            {"name": "단일 고객\n집중", "prob": 5, "impact": 5},
            {"name": "본업 성장\n재둔화", "prob": 3, "impact": 5},
            {"name": "복합체\n할인 지속", "prob": 4, "impact": 3},
            {"name": "폴더블\n양산 지연", "prob": 3, "impact": 3},
            {"name": "주주환원\n부재", "prob": 5, "impact": 2},
            {"name": "복합금융부채\n희석", "prob": 3, "impact": 1},
            {"name": "부채비율\n상승", "prob": 5, "impact": 1},
        ]
    },
}

SOTP_WATERFALL = {
    "section_key": "s07_valuation",
    "archetype": "waterfall",
    "title": "부문가치 합산 분해 (Base 시나리오)",
    "source": "DART 사업보고서·반기보고서, 위닝펀드 3조 황성혁",
    "data": {
        "labels": ["화학재료 (16.5배)", "터보기계 (10배)", "순현금", "합산 지분가치"],
        "values": [8019, 1996, 424, 10439],
        "is_total": [False, False, False, True],
        "ylabel": "가치 (억원)",
    },
}

RESOURCE = {
    'c03_peer_multiples': 'KIS Open API (2026-08-13 종가 기준)',
    'c04_fact_comparison': 'KIS Open API, FinanceDataReader 5년 밴드, 위닝펀드 3조 황성혁',
    'c05_dupont_roe': 'DART 사업보고서(2022~2025), 2026E 자체 추정, 위닝펀드 3조 황성혁',
    'c06_consensus_gap': 'DART 사업보고서·반기보고서, Wisereport',
    'c07_consensus_gap': 'DART 사업보고서(2022~2025 지배주주 기준), 2026E 자체 추정',
    'c09_consensus_gap': 'DART 분기·반기·사업보고서 (1Q25~2Q26)',
    'c10_consensus_gap': 'KIS Open API (최근 20거래일)',
    'c11_consensus_gap': '위닝펀드 3조 황성혁 (부문가치 합산 시나리오)',
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
    if c['name'] in RESOURCE:
        c['source'] = RESOURCE[c['name']]
    if c['section_key'] in REMAP:
        c['section_key'] = REMAP[c['section_key']]
        n_remap += 1

if not any(c['archetype'] == 'waterfall' for c in plan['charts']):
    plan['charts'].append(dict(SOTP_WATERFALL))

for i, c in enumerate(plan['charts'], 1):
    c['order'] = i
    c['caption'] = f"도표 {i}. {c['title']}"
    c['name'] = f"c{i:02d}_{c['archetype']}"

tmp = P + '.tmp'
json.dump(plan, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
os.replace(tmp, P)

still = [c['caption'] for c in plan['charts'] if c.get('data') is None]
print(f"[OK] {P}")
print(f"  채움 {n_fill} / 재매핑 {n_remap} / SOTP 워터폴 추가 / 총 {len(plan['charts'])}개")
print(f"  data=null 잔여: {still if still else '없음'}")
for c in plan['charts']:
    print(f"   {c['caption'][:42]:45s} | {c['section_key']}")
