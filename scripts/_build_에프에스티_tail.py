# -*- coding: utf-8 -*-
"""_build_에프에스티.py 에 build() 를 덧붙인다 (idempotent).

heredoc 으로 붙이려다 따옴표에서 깨져, 파일로 쓴다(v5.4 컨벤션).
"""
import io
import pathlib
import sys

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

P = pathlib.Path(__file__).with_name('_build_에프에스티.py')
s = P.read_text(encoding='utf-8')

if 'def build()' in s:
    print('[SKIP] already applied')
    raise SystemExit(0)

TAIL = '''

def build():
    d = {
        'meta': {
            'stock_name': '에프에스티',
            'stock_code': '036810',
            'market': 'KOSDAQ',
            'country': 'KR',
            'industry': '반도체 펠리클·칠러',
            'date': '2026-09-15',
            'currency': 'KRW',
            'tagline': '본업은 돌아왔고 EUV는 경쟁 구간이다',
            'section_order': ORDER,
            'section_titles': TITLES,
        },
        'price': {
            'current': 25300,
            'market_cap': '5,477억원',
            'market_cap_num': 5477,
            'shares_outstanding': 21649789,
            'per': -47.39,
            'pbr': 2.16,
            'eps': -556,
            'bps': 11707,
            'forward_per': 22.8,
            'forward_eps': 1155,
            'consensus_eps': 221.71,
            'consensus_target': 40000,
            'high_52w': 51000,
            'low_52w': 15000,
            'beta': 1.18,
            'volatility_annual': 95.2,
            'dividend_yield': 0.0,
        },
        'opinion': {
            'rating': 'HOLD',
            'type': 'CNT 인증·반복 발주 확인 대기',
            'portfolio_role': '반도체 소재 사이클 노출, 비중 3% 이내',
            'target_bear': 13300,
            'target_base': 27500,
            'target_bull': 43300,
            'risk_reward': '1:0.2 (Base 기준) / 1.49배 (Bull 기준)',
        },
        'segments': [
            {'name': '재료 (펠리클·프레임)', 'pct': 65.9,
             'outlook': '판가 +14.6%, 물량 +15.1% 동반 상승. 국내 점유율 80%'},
            {'name': '장비 (칠러·EUV 인프라)', 'pct': 33.3,
             'outlook': '칠러 수출 단가 2년간 -51.9%. 테일러 EUV 장비 납품'},
            {'name': '기타 (임대 등)', 'pct': 0.7, 'outlook': '영향 미미'},
        ],
        'financials': {
            'headers': ['항목', '2022', '2023', '2024', '2025', '2026E'],
            'rows': [
                ['매출액(억원)', '2,196', '1,976', '2,374', '2,803', '3,200'],
                ['영업이익(억원)', '63', '-108', '23', '-5', '240'],
                ['영업이익률(%)', '2.9', '-5.5', '1.0', '-0.2', '7.5'],
                ['순이익(억원)', '408', '-181', '-16', '-143', '90'],
                ['영업활동현금흐름(억원)', '-16', '81', '-54', '141', '500'],
                ['설비투자(억원)', '341', '305', '685', '483', '1,308'],
                ['잉여현금흐름(억원)', '-357', '-224', '-739', '-342', '-808'],
                ['순차입금(억원)', '887', '1,020', '1,852', '2,125', '2,302'],
            ],
            'source': 'DART 연결 + FnGuide (2026E 는 본 리포트 추정)',
        },
        'quarterly': {
            'headers': ['분기', '3Q25', '4Q25', '1Q26', '2Q26'],
            'rows': [
                ['매출액(억원)', '655', '703', '696', '893'],
                ['매출총이익(억원)', '194', '191', '230', '321'],
                ['매출총이익률(%)', '29.6', '27.1', '33.0', '35.9'],
                ['영업이익(억원)', '-19', '-32', '14', '96'],
                ['순이익(억원)', '-68', '-37', '-28', '70'],
            ],
            'year': '2026',
            'note': 'DART 분기 실측과 FnGuide 1:1 대조 완료 (검산 오차 0.00%)',
        },
        'supply': {
            'foreign': -164497, 'institution': -164498, 'individual': 311855,
            'days': 20,
            'comment': '외국인·기관이 각각 16만주씩 순매도, 개인이 31만주 순매수. '
                       '현재가 환산 약 42억원으로 시가총액 대비 0.8% 수준',
        },
        'peers': [
            {'name': '에스앤에스텍', 'market_cap': '8,385억', 'per': 14.46, 'pbr': 2.70,
             'note': 'EUV 블랭크마스크·펠리클', 'highlight': True},
            {'name': '동진쎄미켐', 'market_cap': '19,853억', 'per': 20.21, 'pbr': 1.85,
             'note': '노광 소재(PR)', 'highlight': False},
            {'name': '티씨케이', 'market_cap': '28,619억', 'per': 41.51, 'pbr': 5.79,
             'note': '반도체 소모성 부품', 'highlight': False},
            {'name': '하나머티리얼즈', 'market_cap': '9,909억', 'per': 25.82, 'pbr': 2.08,
             'note': '반도체 소모성 부품', 'highlight': False},
            {'name': '유니셈', 'market_cap': '2,680억', 'per': 29.83, 'pbr': 1.06,
             'note': '칠러·스크러버', 'highlight': False},
            {'name': '에스티아이', 'market_cap': '2,869억', 'per': 18.99, 'pbr': 0.99,
             'note': '칠러·CDS', 'highlight': False},
        ],
        'catalysts': [
            {'date': '2026-11', 'event': '3분기 보고서 -- CNT 인증 진척과 설비투자 정상화',
             'impact': '연구개발 실적란 문구 변화가 첫 신호'},
            {'date': '2027 상반기', 'event': '카나투 추가 반응기 납품',
             'impact': 'CNT 생산능력 확대의 실물 시점'},
            {'date': '2027 초', 'event': '삼성 테일러 팹1 본양산',
             'impact': 'EUV 펠리클·인프라 장비의 실질 수요 개시'},
            {'date': '상시', 'event': 'CNT 펠리클 반복 발주 확인',
             'impact': '목표주가 27,500 -> 33,300원. 유일한 매수 전환 조건'},
        ],
        'sections': dict(S),
    }

    s = d['sections']
    # v5.0 키 스킴 분열 대응 -- alias 재생성 (generate_all 은 정규 12키만 렌더)
    s['s01_opinion'] = s['s01_opinion_thesis']
    s['s02_investment_points'] = s['s02_thesis_catalysts']
    s['s04_industry'] = s['s04_industry_competition']
    s['s08_financial'] = s['s06_financial']
    s['s09_valuation'] = s['s07_valuation']
    s['s10_scenarios_risks'] = s['s09_scenarios_risks']
    s['s13_thesis'] = (
        '### 본업은 확인됐고 옵션은 아직이다\\n\\n'
        '매출 +9.9%에 영업이익 +146%가 나온 원인은 성장이 아니라 **믹스 교체**다. '
        '재료부문 +32.9%는 펠리클 내수 판가 +14.6%와 물량 +15.1%의 곱(+31.9%)으로 '
        '1%포인트 이내에서 재구성된다.\\n\\n'
        'EUV 는 "일본 독점을 깨는 국산화"가 아니다. 미쓰이화학이 2024년 5월 '
        'CNT 펠리클 연 5,000장 설비를 발표했고 투과율 92% 이상, 1kW 초과 대응을 '
        '제시했다. 동사는 카나투 반응기와 **로열티 구조**로 같은 길을 간다.\\n\\n'
        '**시사점:** 동사의 차별점은 막이 아니라 **막과 장비를 함께 판다**는 것이다. '
        '테일러 팹에 EPMD·EPIS 를 납품했고, 회사가 실적변동 공시에서 '
        '"Taylor 장비납품 준비로 인한 고정비 증가"를 직접 밝혔다.\\n\\n'
        '**시사점:** 자사주 8.20% -> 0.95%. 45만주 매각 목적에 '
        '"EUV펠리클 확장 투자 재원 확보"가 명시돼 있고, 교환사채 200억원의 '
        '용도는 시설자금이다. **설비투자 654억원의 재원이 공시에 다 적혀 있다.**\\n\\n'
        '> 본업은 돌아왔다. 옵션은 아직 인증 전이다.\\n')
    s['s14_short_thesis'] = (
        '### 이 종목을 파는 쪽의 논리\\n\\n'
        '**잉여현금흐름이 5년 연속 적자**로 누적 2,066억원이며 순차입금은 '
        '887억 -> **2,302억원**이다. 최근 3년 설비투자 1,822억원에 늘어난 매출은 '
        '888억원으로 **투자 1원당 매출 0.49원**이다.\\n\\n'
        '**CNT 는 아직 인증 전이다.** 공시 문구는 "Qual 평가 및 HVM Certification '
        '진행 중"이고 완료 시점 언급이 없다. 확률을 0%로 두면 목표주가는 '
        '22,400원(-11.5%)이다.\\n\\n'
        '**시사점:** DRAM 은 EUV 펠리클을 쓰지 않는 것이 관행이다. '
        '"AI·HBM 수요 -> 펠리클 수요" 연결은 성립하지 않으며, 실질 수요처는 '
        '삼성 파운드리 하나다.\\n\\n'
        '**시사점:** 자사주가 0.95%만 남아 같은 방식의 자금 조달은 불가능하다. '
        '교환가 32,413원은 현재가보다 28% 높아 자본 전환도 당장은 아니다. '
        '다음 조달은 차입이거나 신주 발행이다.\\n\\n'
        '> 영업이익은 돌아왔다. 잉여현금흐름은 5년째 돌아오지 않았다.\\n')

    tmp = SRC + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SRC)
    print(f'[OK] {SRC}')


if __name__ == '__main__':
    build()
    body = sum(len(S[k]) for k in ORDER)
    print(f'본문 {body:,}자 (IR협의회 중앙값 27,525자)')
    for k in ORDER:
        print(f'  {TITLES[k]:<18} {len(S[k]):>7,}자 {len(S[k]) / body:>6.1%}')
'''

s = s.rstrip() + '\n' + TAIL
compile(s, str(P), 'exec')
P.write_text(s, encoding='utf-8')
print('[OK] build() 추가')
