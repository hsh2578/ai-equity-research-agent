# -*- coding: utf-8 -*-
"""OCI홀딩스 chart_plan.json 후처리 v2 (idempotent)
1) [제안] fact_comparison / risk_matrix 데이터를 본문 근거로 채움
2) SOTP 워터폴 도표 신규 추가 (밸류에이션 섹션의 핵심 시각화)
3) 수급 도표 유지 (2026-08-14 KIS 수급 데이터 확보로 복원)
4) 미렌더 섹션(s10/s11/s12) 차트를 호스트(s06/s07)로 재매핑
5) 출처 정정 (FnGuide 무응답 -> 실제 원천 DART/KIS 로 교체)
"""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'data', 'OCI홀딩스', 'chart_plan.json')
plan = json.load(open(P, encoding='utf-8'))

FILL = {
    'fact_comparison': {
        "columns": ["항목", "OCI홀딩스", "한화솔루션", "OCI(자회사)", "HD현대에너지솔루션"],
        "rows": [
            ["시가총액 (억원)", "51,903", "80,736", "7,153", "13,709"],
            ["PBR (배)", "1.32", "0.75", "0.63", "3.28"],
            ["PBR 5년 평균 (배)", "0.61", "-", "-", "-"],
            ["2025 영업이익률 (%)", "-1.7", "적자", "-0.6", "-"],
            ["최근 1년 주가 (%)", "+174.7", "-", "-", "-"],
            ["순차입/자기자본 (%)", "22.4", "-", "-", "-"],
        ],
        "highlight_col": 1,
    },
    'risk_matrix': {
        "risks": [
            {"name": "밸류에이션\n선반영", "prob": 5, "impact": 5},
            {"name": "증설 지연", "prob": 4, "impact": 4},
            {"name": "스페이스X\n무산", "prob": 3, "impact": 5},
            {"name": "MIP 예외\n협상", "prob": 3, "impact": 4},
            {"name": "극심한\n변동성", "prob": 5, "impact": 3},
            {"name": "순차입\n증가", "prob": 4, "impact": 2},
            {"name": "중국\n우회수출", "prob": 3, "impact": 2},
        ]
    },
}

# 신규 SOTP 워터폴 (밸류에이션 본문 2~3단계와 1:1 대응)
SOTP_WATERFALL = {
    "section_key": "s07_valuation",
    "archetype": "waterfall",
    "title": "SOTP 부문별 가치 분해 (Base 시나리오)",
    "source": "DART 사업보고서·분기보고서, KIS Open API, 위닝펀드 3조 황성혁",
    "data": {
        "labels": ["화학소재 지분", "에너지솔루션", "도시개발", "기타·투자", "폴리실리콘", "순차입", "SOTP 지분가치"],
        "values": [2252, 6000, 6000, 3000, 46800, -10966, 53086],
        "is_total": [False, False, False, False, False, False, True],
        "ylabel": "가치 (억원)",
    },
}

RESOURCE_BY_TITLE = {
    'Peer PER': 'KIS Open API (2026-08-13 종가 기준)',
    '경쟁사 비교표': 'KIS Open API, FinanceDataReader 5년 밴드, 위닝펀드 3조 황성혁',
    'ROE 5년': 'DART 사업보고서(2022~2025), 2026E 자체 추정, 위닝펀드 3조 황성혁',
    'EPS 5년': 'DART 사업보고서(2022~2025), 2026E 컨센서스 기반 자체 추정',
    '분기 매출': 'DART 분기·사업보고서, 2Q26 실적공시(2026-07-23)',
    '투자자별 순매수': 'KIS Open API (최근 20거래일, 2026-08-13 기준)',
    'Bear/Base/Bull': '위닝펀드 3조 황성혁 (SOTP 시나리오)',
}

REMAP = {
    's10_earnings_consensus': 's06_financial',
    's11_supply_shareholder': 's06_financial',
    's12_action_plan': 's07_valuation',
    's05_management_fieldcheck': 's03_company_overview',
}

# (2026-08-14) KIS 수급 데이터가 채워져 수급 도표를 복원 -- 더 이상 제거하지 않는다
dropped = 0

n_fill = n_remap = 0
for c in plan['charts']:
    if c.get('data') is None and c['archetype'] in FILL:
        c['data'] = FILL[c['archetype']]
        n_fill += 1
    for key, src in RESOURCE_BY_TITLE.items():
        if key in c['title']:
            c['source'] = src
            break
    if c['section_key'] in REMAP:
        c['section_key'] = REMAP[c['section_key']]
        n_remap += 1

# SOTP 워터폴 추가 (중복 방지)
if not any(c['archetype'] == 'waterfall' for c in plan['charts']):
    plan['charts'].append(dict(SOTP_WATERFALL))

# order / caption / name 재부여
for i, c in enumerate(plan['charts'], 1):
    c['order'] = i
    c['caption'] = f"도표 {i}. {c['title']}"
    c['name'] = f"c{i:02d}_{c['archetype']}"

tmp = P + '.tmp'
json.dump(plan, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
os.replace(tmp, P)

still_null = [c['caption'] for c in plan['charts'] if c.get('data') is None]
print(f"[OK] {P}")
print(f"  채움 {n_fill} / 재매핑 {n_remap} / SOTP 워터폴 추가")
print(f"  총 {len(plan['charts'])}개, data=null 잔여: {still_null if still_null else '없음'}")
for c in plan['charts']:
    print(f"   {c['caption'][:44]:47s} | {c['section_key']}")
