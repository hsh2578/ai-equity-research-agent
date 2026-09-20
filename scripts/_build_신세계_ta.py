# -*- coding: utf-8 -*-
"""/research-ta 신세계 빌더 (하이브 빌더 복사, 상수 교체) (idempotent, lite 실행).
에프에스티 빌더의 render()/won()/pct() 를 재사용하고 밸류 플레이스홀더는 PER 시나리오(ta/calc_ledger.json per_value_*)로 채운다.
신세계 고유: 목표가 = 본업 PER 값 + 상장 지분(삼성생명·광주신세계·SI) 30% 할인 가산(assumptions.asset_add). 장부의 per_value_* 는 본업만이다.

sections/*.md 의 {{이름}} 을 장부·시세·수급 값으로 채워 scripts/analysis_신세계_ta.json 을 쓴다.
"""
import importlib.util
import io
import json
import os
import sys

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
STOCK = '신세계'
D = os.path.join(ROOT, 'data', STOCK)
TA = os.path.join(D, 'ta')
OUT = os.path.join(ROOT, 'scripts', f'analysis_{STOCK}_ta.json')
SECTIONS = os.path.join(TA, 'sections')

_spec = importlib.util.spec_from_file_location('_fst', os.path.join(ROOT, 'scripts', '_build_에프에스티_ta.py'))
_fst = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fst)
render, won, pct, jload = _fst.render, _fst.won, _fst.pct, _fst.jload
ORDER, TITLES = _fst.ORDER, _fst.TITLES

PEER_NOTE = {'현대백화점': '백화점 13점·면세 DF2', '롯데쇼핑': '백화점 30점·마트·하이마트', '호텔신라': '면세·호텔',
             '이세탄미쓰코시': '일본 1위 백화점', 'J프론트리테일링': '다이마루·마츠자카야'}
# peers 배열(커버·요약 표) = 배수 산정 대상 5사: 국내 3 + 해외 2. 해외 값은 _peer_snapshot_global.json(yfinance, 억원 환산·후행 PER)
PEER_ORDER = ['현대백화점', '롯데쇼핑', '호텔신라', '이세탄미쓰코시', 'J프론트리테일링']
GLOBAL_SLUG = {'이세탄미쓰코시': 'isetan', '다카시마야': 'taka', 'J프론트리테일링': 'jfront', '메이시스': 'macys', '중국중면': 'ctg'}


def load_global_peers():
    """flags(forward_pe_suspect·fx_missing)·error 가 있는 레코드는 리포트에 쓰지 않는다."""
    p = os.path.join(D, '_peer_snapshot_global.json')
    if not os.path.exists(p):
        return {}, ''
    g = jload(p)
    return {k: r for k, r in g.items() if isinstance(r, dict) and 'error' not in r}, (g.get('_collected_at') or '')[:10]


# 연간 실적 (KIS 5년 + Wisereport 비율) + 2026 상반기 실측 (반기보고서 연결, IR 덱). 2025 순이익은 연결 646억(지배 139억)
FIN_ROWS = [
    ['순매출액(억원)', '78,128', '63,571', '65,704', '69,295', '36,275'],
    ['영업이익(억원)', '6,454', '6,398', '4,770', '4,800', '3,650'],
    ['영업이익률(%)', '8.3', '10.1', '7.3', '6.9', '10.1'],
    ['지배순이익(억원)', '4,060', '2,250', '1,080', '139', '2,104'],
    ['EPS(원)', '41,245', '22,865', '10,948', '1,440', '22,042'],
    ['BPS(원)', '418,209', '445,995', '486,461', '508,154', '571,970'],
    ['ROE(%)', '10.3', '5.4', '2.5', '0.3', '-'],
    ['부채비율(%)', '129.5', '132.7', '136.4', '140.9', '121.2'],
    ['영업활동현금흐름(억원)', '9,031', '7,914', '7,758', '9,906', '{{h1_ocf}}'],
    ['설비투자(억원)', '3,814', '6,006', '8,954', '4,909', '{{h1_capex}}'],
    ['순차입금(억원)', '34,664', '38,417', '44,840', '37,144', '{{h1_netdebt}}'],
]
QUARTERLY = {'headers': ['구분', '1Q25', '2Q25', '3Q25', '4Q25', '1Q26', '2Q26'],
             'rows': [['순매출액(억원)', '16,658', '16,938', '16,361', '19,337', '18,471', '17,804'],
                      ['영업이익(억원)', '1,323', '753', '998', '1,725', '1,978', '1,671'],
                      ['영업이익률(%)', '7.9', '4.4', '6.1', '8.9', '10.7', '9.4'],
                      ['순이익(억원)', '771', '83', '483', '-691', '1,454', '1,070']],
             'year': 2026, 'note': 'DART 분기·반기보고서 연결(당분기 3개월, 4Q25 는 연간-3Q누적 역산). 순이익은 비지배 포함, 지배 기준은 1Q26 1,202억·2Q26 901억. 백화점 총매출 기준 신장률은 IR 덱 참고'}
SEGMENTS = [{'name': '백화점', 'pct': 40.1, 'outlook': '1H26 순매출 1조4,794억(+15%), 외국인 매출 비중 8.2%, 본점·강남·센텀'},
            {'name': '면세점(디에프)', 'pct': 31.9, 'outlook': '1H26 1조1,324억(-3%), DF2 철수(4/28) 뒤 명동+DF4, OP 흑자 전환'},
            {'name': '신세계인터내셔날', 'pct': 16.0, 'outlook': '1H26 5,872억(+15%), 해외패션·수입코스메틱, 39.7% 연결 종속'},
            {'name': '센트럴시티', 'pct': 5.3, 'outlook': '1H26 2,075억(+12%), 강남점 임대·JW메리어트 OCC 86%'},
            {'name': '까사·라이브쇼핑', 'pct': 6.7, 'outlook': '1H26 까사 2,305억(+91%, JAJU 양수)·라이브쇼핑 1,766억'}]


def values():
    L = {i['key']: i for i in jload(os.path.join(TA, 'calc_ledger.json'))['items']}
    lv = lambda k: L[k]['value']  # noqa: E731
    A = jload(os.path.join(TA, 'assumptions.json'))
    kis = jload(os.path.join(D, 'data_kis.json'))['current_price']
    md = jload(os.path.join(TA, 'market_data.json'))
    fl = jload(os.path.join(TA, 'flow.json'))
    lt = md['latest']
    price = A['price']
    mcap = round(price * A['shares'] / 1e8)
    add = A['asset_add']
    def tgt(sc):   # 본업 PER 값 + 상장 지분 가산, 천원 단위 (opinion 과 본문이 같은 숫자여야 verify B24 통과)
        return round((lv(f'per_value_{sc}') + add.get(sc, 0)) / 1000) * 1000
    v = {
        'price': won(price, 1), 'price_date': A.get('price_date', ''), 'mcap': f'{mcap:,}억원',
        'rim': won(lv('rim_value_per_share'), 1), 'jpbr': f"{lv('justified_pbr'):.2f}배",
        'jpbr_value': won(lv('justified_pbr') * A['bps0'], 100),
        'iroe': pct(lv('price_implied_roe'), 1, False), 'idcf_g': (pct(lv('reverse_dcf_implied_growth'), 1) if lv('reverse_dcf_implied_growth') is not None else 'n/a(해 없음)'),
        'var1': pct(lv('var95_1d'), 1, False), 'var20': pct(lv('var95_20d'), 1, False),
        'netdebt': f"{(-A['net_cash'])//10000:.0f}조{(-A['net_cash'])%10000:,.0f}억원", 'nd_mcap': pct(-A['net_cash'] / mcap, 0, False),
        'per_now': f"{price / A['per_scenarios']['cons_mean']['eps']:.1f}배", 'pbr_now': f"{price / kis['BPS']:.2f}배", 'pbr_h1': f"{price / A['bps0']:.2f}배",
        'per_ttm': f"{price / kis['EPS']:.1f}배",
        'eps_cons': f"{A['per_scenarios']['cons_mean']['eps']:,}원", 'eps_base': f"{A['per_scenarios']['base']['eps']:,}원",
        'eps_bear': f"{A['per_scenarios']['bear']['eps']:,}원", 'eps_bull': f"{A['per_scenarios']['bull']['eps']:,}원",
        'w_bear': pct(A['weights']['bear'], 0, False), 'w_base': pct(A['weights']['base'], 0, False), 'w_bull': pct(A['weights']['bull'], 0, False),
        'cons_target': won(A['cons_target_avg'], 1000),
        'dol': (f"{lv('dol'):.1f}배" if lv('dol') is not None else 'n/a'), 'dfl': (f"{lv('dfl'):.2f}배" if lv('dfl') is not None else 'n/a(부호 전환)'),
    }
    for sc, s in A['per_scenarios'].items():
        r1k = round(lv(f'per_value_{sc}') / 1000) * 1000
        v[f'per_{sc}'] = won(r1k)                      # 본업 PER 값(장부)
        v[f'up_{sc}'] = pct(r1k / price - 1)
        v[f'mult_{sc}'] = f"{s['per']:.1f}배"
        v[f'eps_{sc}'] = f"{s['eps']:,}원"
    for sc in ('bear', 'base', 'bull'):               # 목표가 = 본업 + 상장 지분 가산
        v[f'tgt_{sc}'] = won(tgt(sc)); v[f'tgtup_{sc}'] = pct(tgt(sc) / price - 1); v[f'add_{sc}'] = won(add[sc], 1000)
    ev = sum(A['weights'][sc] * tgt(sc) for sc in ('bear', 'base', 'bull'))
    v.update({'ev_value': won(ev, 1000), 'ev_up': pct(ev / price - 1),
              'cons_gap': pct(tgt('base') / A['cons_target_avg'] - 1, 0),
              'sl_shares': f"{add['samsung_life_shares'] / 1e4:,.1f}만주", 'sl_price': won(add['samsung_life_price'], 1),
              'sl_value': f"{add['samsung_life_shares'] * add['samsung_life_price'] / 1e8:,.0f}억원",
              'sl_value_h1': f"{add['samsung_life_book_h1']:,}억원", 'sl_value_fy25': f"{add['samsung_life_book_fy25']:,}억원",
              'sl_mcap_pct': pct(add['samsung_life_shares'] * add['samsung_life_price'] / 1e8 / mcap, 0, False),
              'sl_ps': won(add['samsung_life_shares'] * add['samsung_life_price'] / A['shares'], 1000),
              'other_listed': f"{add['other_listed_value']:,}억원", 'disc': pct(add['discount'], 0, False)})
    # 재토론 변형 앵커 -- 장부 함수로 계산해 본문 표에 공개 (점 추정 금지)
    import ta_calc_ledger as tl
    b0, ke, g, roe, po, n = A['bps0'], A['ke'], A['g_terminal'], A['roe_forecast'], A['payout'], A['rim_years']
    def _rim_notv():
        b, pv = b0, 0.0
        for t, r in enumerate(roe, 1):
            pv += (r - ke) * b / (1 + ke) ** t
            b += r * b * (1 - po)
        return b0 + pv
    ggm = lambda ke_, bps: bps * (roe[0] - g) / (ke_ - g)  # noqa: E731
    req = lambda px: (px / b0) * (ke - g) + g  # noqa: E731
    v.update({
        'rim_g0': won(tl.rim_value(b0, roe, ke, 0.0, n, po), 1000), 'rim_notv': won(_rim_notv(), 1000),
        'rim_ke_alt': won(tl.rim_value(b0, roe, A['ke_alt'], g, n, po), 1000),
        'jpbr_ke_alt': f"{ggm(A['ke_alt'], b0) / b0:.2f}배", 'jpbr_ke_alt_value': won(ggm(A['ke_alt'], b0), 100),
        'jpbr_fwd_value': won(ggm(ke, A['bps_forward']), 100), 'pbr_fwd': f"{A['price'] / A['bps_forward']:.2f}배",
        'ke_alt': pct(A['ke_alt'], 1, False), 'ke': pct(ke, 1, False),
        'idcf_g_ex': (lambda r: pct(r, 1) if r is not None else 'n/a(해 없음)')(tl.solve_implied_growth(mcap, A['fcf0'], A['wacc'], g, A['fcf_growth_years'])[0]),
        'per_ttm_ni': f"{mcap / A['ni_ttm']:.1f}배", 'per_fy25_cur': f"{mcap / A['ni_fy25']:.1f}배",
        'eps_12m': f"{A['eps_12m_fwd']:,}원", 'per_roll_mult': f"{A['per_scenarios']['roll']['per']:.2f}배",
        'req_bear': pct(req(tgt('bear')), 1, False), 'req_base': pct(req(tgt('base')), 1, False),
        'req_bull': pct(req(tgt('bull')), 1, False), 'req_now': pct(req(price), 1, False),
        'h1_ocf': f"{A['h1_ocf']:,}", 'h1_capex': f"{A['h1_capex']:,}", 'h1_netdebt': f"{A['h1_netdebt']:,}",
        'exsl_mult': f"{(mcap - add['samsung_life_shares'] * add['samsung_life_price'] / 1e8) / (A['eps_12m_fwd'] * A['shares'] / 1e8):.1f}배",
    })
    v.update({
        'close': won(lt['close'], 1), 'sma50': won(lt['close_50_sma'], 10), 'sma200': won(lt['close_200_sma'], 10),
        'rsi': f"{lt['rsi']:.1f}", 'macdh': f"{lt['macdh']:,.0f}", 'boll_ub': won(lt['boll_ub'], 10),
        'boll_lb': won(lt['boll_lb'], 10), 'boll_mid': won(lt['boll'], 10), 'atr': won(lt['atr'], 10),
        'md_date': A.get('price_date', '') or md.get('rows_last_date') or md.get('asof', ''),
        'dist200': pct(lt['close'] / lt['close_200_sma'] - 1),
        'dist50': pct(lt['close'] / lt['close_50_sma'] - 1),
        'dead_cross': next((c['date'] for c in reversed(md['signals'].get('cross', [])) if c['type'] == 'dead'), '-'),
        'f_days': str(fl['days']),
    })
    w52 = md['signals'].get('w52') or {}
    if w52:
        v.update({'w52_hi': won(w52['high'], 1), 'w52_lo': '170,200원', 'w52_pos': f"{w52['position_pct']:.0f}%"})  # 저가는 FDR 일봉 실측(2025-11-04), KIS 226,500·market_data 168,800 과 달라 통일
    for who, key in (('외국인', 'foreign'), ('기관', 'inst'), ('개인', 'indiv')):
        v[f'f_{key}_sh'] = f"{fl['net_shares'][who]:+,}주"
        v[f'f_{key}_krw'] = f"{fl['net_shares'][who] * price / 1e8:+,.0f}억원"
    gpeers, gasof = load_global_peers()   # s07 해외 비교기업 표 (flags 있는 값은 n/a)
    v['gp_asof'] = gasof
    for n, slug in GLOBAL_SLUG.items():
        r = gpeers.get(n) or {}
        fl2 = r.get('flags') or []
        v[f'gp_{slug}_mcap'] = f"{r['market_cap_uk']:,}억원" if r.get('market_cap_uk') else 'n/a'
        v[f'gp_{slug}_per'] = f"{r['per']:.1f}배" if r.get('per') else 'n/a'
        v[f'gp_{slug}_fper'] = 'n/a(추정 산포)' if 'forward_pe_suspect' in fl2 else (f"{r['per_forward']:.1f}배" if r.get('per_forward') else 'n/a')
        v[f'gp_{slug}_pbr'] = f"{r['pbr']:.2f}배" if r.get('pbr') else 'n/a'
    return v


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--sections', default=SECTIONS)
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--dump-placeholders')
    args = ap.parse_args(argv)
    v = values()
    if args.dump_placeholders:
        with open(args.dump_placeholders, 'w', encoding='utf-8') as f:
            json.dump(v, f, ensure_ascii=False, indent=1)
        print(f'[OK] placeholders {len(v)}개 -> {args.dump_placeholders}')
        return
    secs = {}
    for k in ORDER + ['s13_thesis', 's14_short_thesis']:
        with open(os.path.join(args.sections, f'{k}.md'), encoding='utf-8') as f:
            secs[k] = render(f.read().strip() + '\n', v)
    L = {i['key']: i['value'] for i in jload(os.path.join(TA, 'calc_ledger.json'))['items']}
    A = jload(os.path.join(TA, 'assumptions.json'))
    kis = jload(os.path.join(D, 'data_kis.json'))['current_price']
    fl = jload(os.path.join(TA, 'flow.json'))
    add = A['asset_add']
    rnd = lambda x: int(round(x / 1000) * 1000)  # noqa: E731  # 목표가는 천원 단위
    tb, tbase, tbull = rnd(L['per_value_bear'] + add['bear']), rnd(L['per_value_base'] + add['base']), rnd(L['per_value_bull'] + add['bull'])
    peers_snap = jload(os.path.join(D, '_peer_snapshot.json'))
    peers_snap = peers_snap.get('peers', peers_snap)
    gpeers, _ = load_global_peers()
    peers_snap = {**peers_snap, **{k: r for k, r in gpeers.items() if not r.get('flags')}}
    mcap_uk = round(A['price'] * A['shares'] / 1e8)
    d = {
        'meta': {'stock_name': STOCK, 'stock_code': '004170', 'market': 'KOSPI', 'country': 'KR', 'industry': '백화점·유통',
                 'date': A.get('price_date', ''), 'currency': 'KRW', 'tagline': A.get('tagline', ''),
                 'section_order': ORDER, 'section_titles': TITLES, 'section_labels': {'s08_esg': 'Technical Analysis'},
                 'variant': 'research-ta lite ' + os.path.basename(os.path.normpath(args.sections))},
        'price': {'current': A['price'], 'market_cap': f"{mcap_uk:,}억원", 'market_cap_num': mcap_uk, 'shares_outstanding': A['shares'],
                  'per': round(A['price'] / kis['EPS'], 2), 'pbr': round(A['price'] / kis['BPS'], 2),
                  'eps': kis['EPS'], 'bps': kis['BPS'], 'high_52w': kis['52주최고'], 'low_52w': kis['52주최저'],  # KIS 표시(B4 대조용). FDR 실측 170,200(2025-11-04)은 s08 에 병기
                  'var95_1d': L['var95_1d'], 'var95_20d': L['var95_20d'], 'consensus_eps': A['per_scenarios']['cons_mean']['eps'],
                  'forward_per': round(A['price'] / A['eps_12m_fwd'], 1), 'forward_eps': A['eps_12m_fwd'],
                  'dividend_yield': round(A['dps_ttm'] / A['price'] * 100, 2)},
        'opinion': {**A['opinion'], 'target_bear': tb, 'target_base': tbase, 'target_bull': tbull,
                    'risk_reward': (f"1:{(tbase / A['price'] - 1) / (1 - tb / A['price']):.1f}" if tbase > A['price'] and tb < A['price'] else ('목표가 < 현재가' if tbase <= A['price'] else '하방 0'))},
        'segments': SEGMENTS,
        'financials': {'headers': ['항목', '2022', '2023', '2024', '2025', '2026 상반기'], 'rows': [[render(c, v) if '{{' in c else c for c in r] for r in FIN_ROWS],
                       'source': 'KIS·Wisereport 연간(연결) + 반기보고서 손익·현금흐름표(2026 상반기 실측). 순차입금은 2022~2024 Wisereport(리스 포함), 2025·1H26 차입금·사채-현금성자산(리스 제외, 회사 2분기 자료)'},
        'quarterly': QUARTERLY,
        'supply': {'foreign': fl['net_shares']['외국인'], 'institution': fl['net_shares']['기관'], 'individual': fl['net_shares']['개인'],
                   'days': fl['days'], 'comment': f"외국인 {v['f_foreign_sh']}, 기관 {v['f_inst_sh']}, 개인 {v['f_indiv_sh']} (주식수 기준, 금액은 조회 시점 가격 환산)"},
        'peers': [{'name': n, 'market_cap': f"{peers_snap[n]['market_cap_uk']:,}억", 'per': peers_snap[n]['per'], 'pbr': peers_snap[n]['pbr'],
                   'note': PEER_NOTE.get(n, ''), 'highlight': False}
                  for n in PEER_ORDER if n in peers_snap and peers_snap[n].get('market_cap_uk')][:5],
        'catalysts': A.get('catalysts', []),
        'sections': secs,
    }
    s = d['sections']
    s['s01_opinion'] = s['s01_opinion_thesis']; s['s02_investment_points'] = s['s02_thesis_catalysts']
    s['s04_industry'] = s['s04_industry_competition']; s['s08_financial'] = s['s06_financial']
    s['s09_valuation'] = s['s07_valuation']; s['s10_scenarios_risks'] = s['s09_scenarios_risks']
    s['s11_earnings_consensus'] = s['s10_earnings_consensus'] + '\n\n' + s['s11_supply_shareholder']
    tmp = args.out + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, args.out)
    body = sum(len(s[k]) for k in ORDER)
    print(f'[OK] {args.out} -- 본문 {body:,}자, 기술적 분석 {len(s["s08_esg"]) / body:.1%}, Base {tbase:,} ({v["tgtup_base"]}), 기준가 {A["price"]:,}')


if __name__ == '__main__':
    main()
