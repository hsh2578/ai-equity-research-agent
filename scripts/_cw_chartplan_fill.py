# -*- coding: utf-8 -*-
"""씨에스윈드 chart_plan.json 최종 구성 (idempotent).

wf_chart_planner.py 출력을 받아
  1) [제안] 도표(risk_matrix / waterfall / fact_comparison) 데이터를 본문 근거로 채우고
  2) 미렌더 섹션(s10/s11/s12) 도표를 호스트 섹션으로 재매핑하며
  3) 본문 소제목에 맞는 커스텀 도표를 추가한 뒤
  4) 렌더 순서(meta.section_order)대로 번호를 다시 매긴다.
"""
import sys, io, os, json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

STOCK = '씨에스윈드'
AUTHOR = '위닝펀드 18-1기 3조 황성혁'
PLAN = f'data/{STOCK}/chart_plan.json'
ORDER = ['s01_opinion_thesis', 's04_industry_competition', 's03_company_overview',
         's02_thesis_catalysts', 's06_financial', 's09_scenarios_risks', 's07_valuation']

DART = '사업보고서·분기보고서'
SRC_SELF = AUTHOR

# ============================================================
# 최종 도표 정의 (section_key, archetype, title, source, data)
# ============================================================
import FinanceDataReader as fdr

_df = fdr.DataReader('112610', '2026-01-02')
_x = [d.strftime('%m/%d') for d in _df.index]
_y = [int(v) for v in _df['Close']]
_peak = _y.index(max(_y))
_trough = _y.index(min(_y[_peak:])) if _peak < len(_y) - 1 else len(_y) - 1

CHARTS = [
    # ---------- 1. 요약 ----------
    dict(section_key='s01_opinion_thesis', archetype='price_history',
         title='2026년 주가 경로와 변곡점',
         source=f'FinanceDataReader, {SRC_SELF}',
         data={'x': _x, 'y': _y, 'ylabel': '주가 (원)',
               'markers': [{'idx': _peak, 'label': f'4/3 고점 {max(_y):,}원'},
                           {'idx': _trough, 'label': f'7월 저점 {min(_y[_peak:]):,}원'},
                           {'idx': len(_y) - 1, 'label': f'현재 {_y[-1]:,}원'}]}),

    # ---------- 2. 산업 분석 ----------
    dict(section_key='s04_industry_competition', archetype='consensus_gap',
         title='미국 타워 공급능력과 신규 설치 전망',
         source=f'Wood Mackenzie(2026.07), 기업 공시, {SRC_SELF}',
         data={'categories': ['2025년 초 공급', '2026년 현재 공급', '2025년 설치', '2026E 설치'],
               'series': {'용량(GW)': [9.5, 6.5, 7.0, 10.7]}, 'ylabel': '용량 (GW)'}),
    dict(section_key='s04_industry_competition', archetype='peer_multiples',
         title='글로벌 Peer PER·PBR 비교 (12M 선행)',
         source='yfinance 실시간 조회 (2026-08-14)', data=None),   # planner 산출 재사용
    dict(section_key='s04_industry_competition', archetype='fact_comparison',
         title='경쟁 구도 비교',
         source=f'{DART}, 기업 공시, {SRC_SELF}',
         data={'columns': ['항목', '씨에스윈드', 'Arcosa', 'Titan Wind'],
               'rows': [['본사 국가', '한국', '미국', '중국'],
                        ['생산거점', '7개국 8개', '미국 중심', '중국 중심'],
                        ['미국 내 타워 생산', '가동 확대', '4개 중 2개 중단', '없음'],
                        ['주요 고객', 'Vestas·SGRE·GE·Nordex', '북미 OEM', '중국 내수'],
                        ['하부구조물', '보유(축소 중)', '없음', '보유'],
                        ['12M 선행 PER', '11.8배', '28.3배', '11.1배']],
               'highlight_col': 1}),

    # ---------- 3. 기업 분석 ----------
    dict(section_key='s03_company_overview', archetype='quarterly_composition',
         title='2025년 매출 부문 구성',
         source=f'{DART}', data=None),   # planner 산출(segments pie) 재사용
    dict(section_key='s03_company_overview', archetype='consensus_gap',
         title='중국 제외 글로벌 풍력타워 점유율 추이',
         source=f'{DART} (회사 내부 집계)',
         data={'categories': ['2022', '2023', '2024', '2025'],
               'series': {'점유율(%)': [15.2, 17.0, 23.3, 25.3]}, 'ylabel': '점유율 (%)'}),
    dict(section_key='s03_company_overview', archetype='revenue_composition_5y',
         title='사업부문별 매출과 영업이익률 추이',
         source=f'{DART}, 2026F 자체 추정',
         data={'years': ['2023', '2024', '2025', '2026F'],
               'segments': {'풍력타워(제품·상품)': [12359, 18091, 20013, 24410],
                            '보조금수익(AMPC)': [820, 1102, 1129, 1500],
                            '해상풍력 하부구조물': [1624, 11374, 7808, 2900]},
               'opm': [6.9, 8.3, 10.9, 10.4]}),

    # ---------- 4. 투자 포인트 ----------
    dict(section_key='s02_thesis_catalysts', archetype='event_timeline',
         title='카탈리스트 타임라인',
         source=f'공시·언론 종합, {SRC_SELF}', data=None),   # planner 산출 재사용

    # ---------- 5. 재무 분석 ----------
    dict(section_key='s06_financial', archetype='consensus_gap',
         title='분기 매출과 영업이익 추이',
         source='DART 반기보고서(2026-08-14 공시)',
         data={'categories': ['1Q25', '2Q25', '3Q25', '4Q25', '1Q26', '2Q26'],
               'series': {'매출액(억원)': [9019, 6500, 5970, 7827, 7111, 6864],
                          '영업이익(억원)': [1252, 593, 657, 702, 743, 860]},
               'ylabel': '금액 (억원)'}),
    dict(section_key='s06_financial', archetype='consensus_gap',
         title='보조금수익(AMPC) 실측과 영업이익 (실측 공시치)',
         source=f'{DART} 연결주석 부문정보, {SRC_SELF}',
         data={'categories': ['2023', '2024', '2025', '1Q26', '2Q26'],
               'series': {'보조금수익(억원)': [820, 1102, 1129, 387, 363],
                          '영업이익(억원)': [1047, 2555, 3203, 743, 860]},
               'ylabel': '금액 (억원)'}),
    dict(section_key='s06_financial', archetype='dupont_roe',
         title='ROE 5년 추이', source='DART, 자체 추정', data=None),   # planner 산출 재사용
    dict(section_key='s06_financial', archetype='consensus_gap',
         title='투자자별 순매수 (최근 20거래일)',
         source='KIS API', data=None),   # planner 산출 재사용

    # ---------- 6. 리스크 ----------
    dict(section_key='s09_scenarios_risks', archetype='risk_matrix',
         title='리스크 매트릭스 (발생 확률 x 영향도)',
         source=SRC_SELF,
         data={'risks': [{'name': 'AMPC\n일몰', 'prob': 5, 'impact': 5},
                         {'name': '원가·환율', 'prob': 4, 'impact': 3},
                         {'name': '고객\n집중도', 'prob': 3, 'impact': 4},
                         {'name': '하부구조물\n추가손실', 'prob': 3, 'impact': 3},
                         {'name': '교환사채\n오버행', 'prob': 3, 'impact': 2}]}),

    # ---------- 7. 밸류에이션 ----------
    dict(section_key='s07_valuation', archetype='waterfall',
         title='2028년 정상화 영업이익 분해 (Base 시나리오)',
         source=SRC_SELF,
         data={'labels': ['2027E 영업이익', '보조금 소멸', '판가 전가 60%', '2028E 정상화'],
               'values': [3250, -1600, 960, 2610],
               'is_total': [True, False, False, True],
               'ylabel': '영업이익 (억원)'}),
    dict(section_key='s07_valuation', archetype='consensus_gap',
         title='시나리오별 목표주가',
         source=SRC_SELF,
         data={'categories': ['Bear', '현재가', 'Base', 'Bull'],
               'series': {'주가(원)': [32000, 46850, 56000, 82000]}, 'ylabel': '주가 (원)'}),
]


def main():
    plan = json.load(open(PLAN, encoding='utf-8'))
    old = {(c['section_key'], c['archetype'], c['title']): c for c in plan['charts']}
    # planner 가 만든 데이터를 아키타입 기준으로 재활용할 수 있게 인덱싱
    by_arch = {}
    for c in plan['charts']:
        by_arch.setdefault(c['archetype'], []).append(c)

    reuse_pool = {
        'peer_multiples': 0, 'quarterly_composition': 0, 'event_timeline': 0, 'dupont_roe': 0,
    }
    out = []
    for spec in CHARTS:
        data = spec['data']
        if data is None:
            # planner 산출 재사용
            arch = spec['archetype']
            cands = by_arch.get(arch, [])
            if arch == 'consensus_gap':
                cands = [c for c in cands if '순매수' in c['title']]
            if not cands or cands[0].get('data') is None:
                print(f'  [SKIP] {spec["title"]} -- planner 데이터 없음')
                continue
            data = cands[reuse_pool.get(arch, 0)]['data'] if arch in reuse_pool else cands[0]['data']
        out.append({'section_key': spec['section_key'], 'archetype': spec['archetype'],
                    'title': spec['title'], 'source': spec['source'], 'data': data})

    # 렌더 순서대로 정렬 + 번호 재부여
    out.sort(key=lambda e: ORDER.index(e['section_key']))
    for i, e in enumerate(out, 1):
        e['order'] = i
        e['caption'] = f'도표 {i}. {e["title"]}'
        e['name'] = f'c{i:02d}_{e["archetype"]}'

    plan['charts'] = out
    plan['author'] = AUTHOR
    tmp = PLAN + '.tmp'
    json.dump(plan, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    os.replace(tmp, PLAN)

    print(f'[OK] {PLAN}: 도표 {len(out)}개 (전부 데이터 준비)')
    for e in out:
        print(f'  {e["caption"]:52s} <{e["archetype"]}>  [{e["section_key"]}]')


if __name__ == '__main__':
    main()
