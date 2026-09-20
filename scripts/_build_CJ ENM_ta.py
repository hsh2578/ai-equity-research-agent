# -*- coding: utf-8 -*-
"""/research-ta CJ ENM 빌더 (idempotent, lite). 에프에스티 빌더의 render()/won()/pct() 재사용.
CJ ENM 고유: 목표가 = 장부 sotp_value_per_share_{bear,base,bull} (12M 선행 ex-SD EBIT x 배수 + 상장지분 + 티빙 옵션 - 순차입·우발 - 비지배).
Bear 는 장부가 음수(주주 잔여가치 없음)라 0 으로 표기한다. per_value_* 는 컨센·롤링 비교용.
sections/*.md 의 {{이름}} 을 채워 scripts/analysis_CJ ENM_ta.json 을 쓴다.
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
STOCK = 'CJ ENM'
D = os.path.join(ROOT, 'data', STOCK)
TA = os.path.join(D, 'ta')
OUT = os.path.join(ROOT, 'scripts', f'analysis_{STOCK}_ta.json')
SECTIONS = os.path.join(TA, 'sections')

_spec = importlib.util.spec_from_file_location('_fst', os.path.join(ROOT, 'scripts', '_build_에프에스티_ta.py'))
_fst = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fst)
render, won, pct, jload = _fst.render, _fst.won, _fst.pct, _fst.jload
ORDER, TITLES = _fst.ORDER, _fst.TITLES

PEER_NOTE = {'SBS': '지상파, 11편 동시방영', '콘텐트리중앙': 'JTBC·SLL·메가박스', '에스엠': 'K-POP 레이블',
             'GS리테일': '홈쇼핑·편의점', 'Disney': '글로벌 미디어, 선행 PER'}
PEER_ORDER = ['SBS', '콘텐트리중앙', '에스엠', 'GS리테일', 'Disney']
GLOBAL_SLUG = {'Disney': 'dis', 'WBD': 'wbd', 'Paramount': 'psky'}

# 연간(연결, 억원): KIS 5년 + 반기 실측. 순이익은 연결(비지배 포함). 순차입·OCF 는 증권사 표(삼성 8/7·유진 8/7) 실측 열
FIN_ROWS = [
    ['매출액(억원)', '47,922', '43,684', '52,314', '51,345', '25,329'],
    ['영업이익(억원)', '1,374', '-146', '1,045', '1,329', '349'],
    ['영업이익률(%)', '2.9', '-0.3', '2.0', '2.6', '1.4'],
    ['순이익(억원)', '-1,768', '-3,968', '-5,808', '170', '161'],
    ['EPS(원)', '-5,476', '-14,405', '-22,955', '1,345', '1,358'],
    ['BPS(원)', '-', '147,691', '134,764', '134,460', '130,979'],
    ['영업활동현금흐름(억원)', '-', '12,950', '14,030', '11,660', '-'],
    ['순차입금(억원)', '-', '21,560*', '18,860*', '15,712', '{{h1_netdebt}}'],
    ['순차입금비율(%)', '-', '51.6', '51.3', '50.7', '50.3'],
]
QUARTERLY = {'headers': ['구분', '1Q25', '2Q25', '3Q25', '4Q25', '1Q26', '2Q26'],
             'rows': [['매출액(억원)', '11,383', '13,129', '12,456', '14,378', '13,297', '12,033'],
                      ['영업이익(억원)', '7', '286', '176', '860', '15', '334'],
                      ['영업이익률(%)', '0.1', '2.2', '1.4', '6.0', '0.1', '2.8'],
                      ['순이익(억원)', '-822', '1,146', '798', '-952', '-61', '222']],
             'year': 2026, 'note': '회사 실적발표 덱(연결, 당분기 3개월). 순이익은 비지배 포함. 4Q25 순손실은 기타영업외 -622억·법인세 449억, 2Q25 순이익에는 넷마블 PRS 파생평가이익이 들어 있다'}
SEGMENTS = [{'name': '미디어플랫폼', 'pct': 26.1, 'outlook': 'tvN 등 채널 14개·티빙(48.85%). 2Q26 3,800억(+19%) OP 110억 흑전, 티빙 첫 분기 흑자 60억, TV광고 -21%'},
            {'name': '영화드라마', 'pct': 28.4, 'outlook': '스튜디오드래곤(54.38%)·FIFTH SEASON·영화. 2Q26 1,902억(-54%) OL -105억, FS 시리즈 납품 공백'},
            {'name': '음악', 'pct': 15.9, 'outlook': '라포네(JV 70%)·웨이크원·엠넷플러스. 2Q26 2,302억(+17%) OP 109억(-36%), 신인·플랫폼 투자'},
            {'name': '커머스', 'pct': 29.6, 'outlook': 'CJ온스타일 TV·모바일. 2Q26 4,028억(+4%) OP 260억(+21%), MLC 취급고 +161%'}]


def load_global_peers():
    p = os.path.join(D, '_peer_snapshot_global.json')
    if not os.path.exists(p):
        return {}, ''
    g = jload(p)
    return {k: r for k, r in g.items() if isinstance(r, dict) and r.get('ticker') and 'error' not in (r.get('flags') or [])}, (g.get('_collected_at') or '')[:10]


def values():
    L = {i['key']: i for i in jload(os.path.join(TA, 'calc_ledger.json'))['items']}
    lv = lambda k: L[k]['value']  # noqa: E731
    A = jload(os.path.join(TA, 'assumptions.json'))
    kis = jload(os.path.join(D, 'data_kis.json'))['current_price']
    md = jload(os.path.join(TA, 'market_data.json'))
    fl = jload(os.path.join(TA, 'flow.json'))
    hq = jload(os.path.join(TA, '_holdings_quotes.json'))
    lt = md['latest']
    price = A['price']
    mcap = round(price * A['shares'] / 1e8)
    so = A['sotp']
    nd = -A['net_cash']

    def tgt(sc):  # 장부 SOTP, 천원 단위. Bear 음수는 0
        return max(0, round(lv(f'sotp_value_per_share_{sc}') / 1000) * 1000)
    ev = sum(so['weights'][sc] * tgt(sc) for sc in ('bear', 'base', 'bull'))
    v = {
        'rating': A['opinion']['rating'], 'tagline': A.get('tagline', ''),
        'price': won(price, 1), 'price_date': A.get('price_date', ''), 'mcap': f'{mcap:,}억원',
        'netdebt': f"{nd // 10000:.0f}조{nd % 10000:,.0f}억원", 'nd_mcap': f"{nd / mcap:.1f}배",
        'cash': '7,143억원', 'debt_total': '2조5,619억원',
        'pbr_h1': f"{price / A['bps0']:.2f}배", 'pbr_now': f"{price / kis['BPS']:.2f}배", 'bps_h1': won(A['bps0'], 1),
        'per_cons': f"{price / A['per_scenarios']['cons_mean']['eps']:.1f}배", 'per_roll': f"{A['per_scenarios']['roll']['per']:.1f}배",
        'per_ours': f"{price / A['eps_12m_fwd']:.1f}배",
        'eps_cons': f"{A['per_scenarios']['cons_mean']['eps']:,}원", 'eps_roll': f"{A['per_scenarios']['roll']['eps']:,}원", 'eps_ours': f"{A['eps_12m_fwd']:,}원",
        'cons_target': won(A['cons_target_avg'], 1),
        'listed_value': f"{so['listed_mcap']:,}억원", 'netmarble_val': f"{round(0.18 * hq['넷마블']['시가총액(억원)']):,}억원",
        'sd_val': f"{round(0.5438 * hq['스튜디오드래곤']['시가총액(억원)']):,}억원", 'naver_val': '1,204억원',
        'netmarble_mcap': f"{hq['넷마블']['시가총액(억원)']:,}억원", 'sd_mcap': f"{hq['스튜디오드래곤']['시가총액(억원)']:,}억원",
        'option_ev': f"{so['option_ev_success']:,}억원", 'implied_prob': f"{lv('sotp_implied_option_prob'):.1f}배",
        'ebit_12m': f"{A['ebit_12m_total']:,}억원", 'ebit_cons': f"{A['ebit_12m_cons']:,}억원",
        'ebit_exsd': f"{so['scenarios']['base']['ebitda_annual']:,}억원", 'ebit_sd': f"{A['ebit_12m_sd']:,}억원",
        'ebit_bear': f"{so['scenarios']['bear']['ebitda_annual']:,}억원", 'ebit_bull': f"{so['scenarios']['bull']['ebitda_annual']:,}억원",
        'mult_base': f"{so['scenarios']['base']['multiple']:.1f}배", 'mult_bear': f"{so['scenarios']['bear']['multiple']:.1f}배",
        'mult_bull': f"{so['scenarios']['bull']['multiple']:.1f}배", 'market_mult': f"{A['market_implied_multiple']:.1f}배",
        'deduct': f"{so['net_debt']:,}억원", 'nci': f"{-so['unlisted_book']:,}억원",
        'rim': won(lv('rim_value_per_share'), 1000), 'iroe': pct(lv('price_implied_roe'), 1, False),
        'idcf_g': (pct(lv('reverse_dcf_implied_growth'), 1) if lv('reverse_dcf_implied_growth') is not None else 'n/a'),
        'var1': pct(lv('var95_1d'), 1, False), 'var20': pct(lv('var95_20d'), 1, False),
        'dol': (f"{lv('dol'):.1f}배" if lv('dol') is not None else 'n/a'),
        'w_bear': pct(so['weights']['bear'], 0, False), 'w_base': pct(so['weights']['base'], 0, False), 'w_bull': pct(so['weights']['bull'], 0, False),
        'ev_value': won(round(ev / 100) * 100, 1), 'ev_up': pct(ev / price - 1),
        'kbo_prev': A['kbo_prev_contract'],
        'ebit_27': f"{A['ebit_27_total']:,}억원", 'ebit_27_cons': f"{A['ebit_27_cons']:,}억원",
        'h1_ocf': f"{A['h1_ocf']:,}억원", 'h1_capex': f"{A['h1_capex']:,}억원", 'icr_h1': '0.70배',
    }
    for sc in ('bear', 'base', 'bull'):
        v[f'tgt_{sc}'] = won(tgt(sc), 1); v[f'tgtup_{sc}'] = pct(tgt(sc) / price - 1)
        v[f'raw_{sc}'] = won(round(lv(f'sotp_value_per_share_{sc}') / 100) * 100, 1)
    v['cons_gap'] = pct(tgt('base') / A['cons_target_avg'] - 1, 0)
    v.update({
        'close': won(lt['close'], 1), 'sma50': won(lt['close_50_sma'], 1), 'sma200': won(lt['close_200_sma'], 1),
        'rsi': f"{lt['rsi']:.1f}", 'macdh': f"{lt['macdh']:,.0f}", 'boll_ub': won(lt['boll_ub'], 1),
        'boll_lb': won(lt['boll_lb'], 1), 'boll_mid': won(lt['boll'], 1), 'atr': won(lt['atr'], 1),
        'md_date': A.get('price_date', ''),
        'dist200': pct(lt['close'] / lt['close_200_sma'] - 1), 'dist50': pct(lt['close'] / lt['close_50_sma'] - 1),
        'dead_cross': next((c['date'] for c in reversed(md['signals'].get('cross', [])) if c['type'] == 'dead'), '-'),
        'f_days': str(fl['days']), 'h1_netdebt': f"{A['h1_netdebt']:,}",
    })
    w52 = md['signals'].get('w52') or {}
    v.update({'w52_hi': won(kis['52주최고'], 1), 'w52_lo': won(kis['52주최저'], 1),
              'w52_pos': f"{w52['position_pct']:.0f}%" if w52 else f"{(price - kis['52주최저']) / (kis['52주최고'] - kis['52주최저']) * 100:.0f}%"})
    for who, key in (('외국인', 'foreign'), ('기관', 'inst'), ('개인', 'indiv')):
        v[f'f_{key}_sh'] = f"{fl['net_shares'][who]:+,}주"
        v[f'f_{key}_krw'] = f"{fl['net_shares'][who] * price / 1e8:+,.0f}억원"
        v[f'f_{key}_pct'] = f"{fl['pct_of_shares'][who]:+.2f}%"
    gpeers, gasof = load_global_peers()
    v['gp_asof'] = gasof
    for n, slug in GLOBAL_SLUG.items():
        r = gpeers.get(n) or {}
        fl2 = r.get('flags') or []
        v[f'gp_{slug}_mcap'] = f"{r['market_cap_uk'] / 10000:,.1f}조원" if r.get('market_cap_uk') else 'n/a'
        v[f'gp_{slug}_per'] = f"{r['per']:.1f}배" if r.get('per') else 'n/a'
        v[f'gp_{slug}_fper'] = 'n/a(추정 산포)' if ('forward_pe_suspect' in fl2 or (r.get('per_forward') or 0) > 60) else (f"{r['per_forward']:.1f}배" if r.get('per_forward') else 'n/a')
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
    rnd = lambda x: max(0, int(round(x / 1000) * 1000))  # noqa: E731
    tb, tbase, tbull = rnd(L['sotp_value_per_share_bear']), rnd(L['sotp_value_per_share_base']), rnd(L['sotp_value_per_share_bull'])
    peers_snap = jload(os.path.join(D, '_peer_snapshot.json'))
    peers_snap = peers_snap.get('peers', peers_snap)
    gpeers, _ = load_global_peers()
    peers_snap = {**peers_snap, **{k: r for k, r in gpeers.items() if not r.get('flags')}}
    mcap_uk = round(A['price'] * A['shares'] / 1e8)
    d = {
        'meta': {'stock_name': STOCK, 'stock_code': '035760', 'market': 'KOSDAQ', 'country': 'KR', 'industry': '미디어·콘텐츠·커머스',
                 'date': A.get('price_date', ''), 'currency': 'KRW', 'tagline': A.get('tagline', ''),
                 'section_order': ORDER, 'section_titles': TITLES, 'section_labels': {'s08_esg': 'Technical Analysis'},
                 'variant': 'research-ta lite ' + os.path.basename(os.path.normpath(args.sections))},
        'price': {'current': A['price'], 'market_cap': f"{mcap_uk:,}억원", 'market_cap_num': mcap_uk, 'shares_outstanding': A['shares'],
                  'per': round(A['price'] / kis['EPS'], 2), 'pbr': round(A['price'] / kis['BPS'], 2),
                  'eps': kis['EPS'], 'bps': kis['BPS'], 'high_52w': kis['52주최고'], 'low_52w': kis['52주최저'],
                  'var95_1d': L['var95_1d'], 'var95_20d': L['var95_20d'], 'consensus_eps': A['per_scenarios']['cons_mean']['eps'],
                  'forward_per': round(A['price'] / A['eps_12m_fwd'], 1), 'forward_eps': A['eps_12m_fwd'],
                  'dividend_yield': 0.0},
        'opinion': {**A['opinion'], 'target_bear': tb, 'target_base': tbase, 'target_bull': tbull,
                    'risk_reward': ('목표가 < 현재가' if tbase <= A['price'] else f"1:{(tbase / A['price'] - 1) / (1 - tb / A['price']):.1f}")},
        'segments': SEGMENTS,
        'financials': {'headers': ['항목', '2022', '2023', '2024', '2025', '2026 상반기'], 'rows': [[render(c, v) if '{{' in c else c for c in r] for r in FIN_ROWS],
                       'source': 'KIS 연간(연결) + 회사 실적발표 덱·반기보고서(2026 상반기 실측). OCF 2023~2025 는 증권사 재무표(삼성 8/7·유진 8/7) 실측 열. 순차입금 2025·1H26 은 회사 정의(차입 5종 − 현금 − 단기금융상품, 반기보고서), 2023~2024(*)는 증권사 재무표 정의. 순이익은 연결(비지배지분 포함), EPS 는 지배주주 기준'},
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
