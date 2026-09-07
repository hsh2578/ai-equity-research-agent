# -*- coding: utf-8 -*-
"""한국콜마 chart_plan.json 보정 (idempotent)
1) 위닝펀드 7섹션 병합으로 미렌더되는 섹션의 차트를 호스트 섹션으로 재매핑
2) [제안] fact_comparison 데이터를 본문 근거로 채움
"""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

P = 'data/한국콜마/chart_plan.json'
plan = json.load(open(P, encoding='utf-8'))

REMAP = {
    's10_earnings_consensus': 's06_financial',
    's11_supply_shareholder': 's06_financial',
    's12_action_plan': 's07_valuation',
    's05_management_fieldcheck': 's03_company_overview',
}

FACT = {
    "columns": ["비교 항목", "한국콜마", "코스맥스", "코스메카코리아"],
    "rows": [
        ["연간 생산능력", "10억개", "24억개", "7.6억개"],
        ["카테고리 강점", "기초·자외선차단", "색조·겔마스크", "기초·미국현지"],
        ["2024년 영업이익률", "7.9%", "8.1%", "11.5%"],
        ["2Q26 영업이익률", "12.8%", "-", "-"],
        ["계열 용기사", "연우 보유", "없음", "없음"],
        ["미국 법인 손익", "적자 지속", "2Q26 첫 흑자", "흑자"],
    ],
    "highlight_col": 1,
}

n_remap = 0
for c in plan.get('charts', []):
    sk = c.get('section_key')
    if sk in REMAP:
        c['section_key'] = REMAP[sk]
        n_remap += 1
    if c.get('archetype') == 'fact_comparison' and not c.get('data'):
        c['data'] = FACT

# 3) 도표 제목을 해당 섹션 소제목 토큰과 겹치게 조정 -> 섹션 끝 밀림 방지
RETITLE = {
    'c01_event_timeline': '촉매 타임라인: 다음 단계를 여는 이벤트',
    'c02_quarterly_composition': '화장품 회사가 아니다: 매출 부문 구성',
    'c03_peer_multiples': '한국 ODM 4사와 브랜드사 밸류에이션 비교',
    'c04_fact_comparison': '경쟁 구도 점검: ODM 3사 비교',
}
for c in plan.get('charts', []):
    if c['name'] in RETITLE:
        c['title'] = RETITLE[c['name']]
# caption 은 planner 가 title 로 만들므로 재생성 필요
for i, c in enumerate(plan.get('charts', []), 1):
    c['caption'] = f'도표 {i}. {c["title"]}'

tmp = P + '.tmp'
with open(tmp, 'w', encoding='utf-8') as f:
    json.dump(plan, f, ensure_ascii=False, indent=2)
os.replace(tmp, P)

print(f"[OK] {P}")
print(f"  - 재매핑 {n_remap}건")
for c in plan['charts']:
    print(f"  {c['name']} -> {c['section_key']} | data {'OK' if c.get('data') else 'NULL'}")
