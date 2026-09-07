"""S6 데모용: YG chart_plan.json 의 [제안] 도표 3종을 본문 근거로 채움 (스킬 STEP4 역할)."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PLAN = 'data/와이지엔터테인먼트/chart_plan.json'
FILL = {
    'c03_activity_matrix': {
        'rows': ['블랙핑크', '베이비몬스터', '트레저', '빅뱅', '신인 보이그룹'],
        'cols': ['26.2Q', '26.3Q', '26.4Q', '27.1Q', '27.2Q'],
        'matrix': [[1, 2, 3, 2, 1],
                   [4, 3, 3, 2, 1],
                   [2, 3, 4, 3, 2],
                   [0, 5, 4, 3, 2],
                   [0, 3, 4, 3, 2]],
    },
    'c05_fact_comparison': {
        'columns': ['항목', 'YG', 'HYBE', 'SM', 'JYP'],
        'rows': [
            ['보유 아티스트', '9팀', '다수', '다수', '다수'],
            ['메가 IP', '블핑·빅뱅·베몬·트레저', 'BTS', 'NCT·에스파', '스키즈·트와이스'],
            ['최근 신인 성공', '베이비몬스터', '아일릿', '라이즈', '엔믹스'],
            ['순현금/시총', '30.5% (최고)', '중', '중', '중'],
        ],
        'highlight_col': 1,
    },
    'c09_waterfall': {
        'labels': ['4사 Median', 'IP 분산 +', '메가IP 양성 +', 'Target PER'],
        'values': [13.5, 5.0, 5.5, 24.0],
        'is_total': [True, False, False, True],
        'ylabel': 'PER (배)',
    },
}

d = json.load(open(PLAN, encoding='utf-8'))
filled = 0
for c in d['charts']:
    if c['name'] in FILL and c.get('data') is None:
        c['data'] = FILL[c['name']]
        filled += 1
        print(f"  채움: {c['caption']}")
json.dump(d, open(PLAN, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(f'{filled}개 제안 도표 데이터 채움 -> {PLAN}')
