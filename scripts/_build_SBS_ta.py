# -*- coding: utf-8 -*-
"""/research-ta SBS 빌더 (idempotent, lite, v5.27 밸류 경량화). 에프에스티 빌더의 render()/won()/pct() 재사용.
SBS 고유: 목표가 = 6/30 실측 BPS(50,080) x P/B 0.25 단일 방법(assumptions.pbr_target). 시나리오·확률가중 없음.
BPS 헤드라인(KIS 69,877)은 2025년 말 값이라 반기 실측(50,080)과 병기한다.
sections/*.md 의 {{이름}} 을 채워 scripts/analysis_SBS_ta.json 을 쓴다.
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
STOCK = 'SBS'
D = os.path.join(ROOT, 'data', STOCK)
TA = os.path.join(D, 'ta')
OUT = os.path.join(ROOT, 'scripts', f'analysis_{STOCK}_ta.json')
SECTIONS = os.path.join(TA, 'sections')

_spec = importlib.util.spec_from_file_location('_fst', os.path.join(ROOT, 'scripts', '_build_에프에스티_ta.py'))
_fst = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fst)
render, won, pct, jload = _fst.render, _fst.won, _fst.pct, _fst.jload
ORDER, TITLES = _fst.ORDER, _fst.TITLES

PEER_NOTE = {'CJ ENM': 'tvN·티빙, 커머스 겸업', '콘텐트리중앙': 'JTBC·SLL, 적자', '스튜디오드래곤': '드라마 제작 1위',
             'KT스카이라이프': '위성·케이블 플랫폼', 'Disney': '글로벌, 선행 PER'}
PEER_ORDER = ['CJ ENM', '콘텐트리중앙', '스튜디오드래곤', 'KT스카이라이프', 'Disney']
GLOBAL_SLUG = {'Disney': 'dis', 'TBS': 'tbs'}

# 연간(연결, 억원). 2022~2025 KIS·신한 7/20 재무표, 2026 상반기 반기보고서 실측. 순이익은 연결(비지배 포함), EPS 는 지배주주
FIN_ROWS = [
    ['매출액(억원)', '11,738', '9,968', '10,467', '10,085', '4,757'],
    ['영업이익(억원)', '1,856', '583', '-192', '182', '-98'],
    ['영업이익률(%)', '15.8', '5.8', '-1.8', '1.8', '-2.1'],
    ['순이익(억원)', '1,566', '472', '338', '79', '-73'],
    ['EPS(원)', '8,357', '2,534', '1,824', '433', '-397'],
    ['BPS(원)', '-', '-', '48,742', '69,866', '{{bps_h1_num}}'],
    ['순현금(억원)', '-', '-', '249', '288', '{{netcash_num}}'],
    ['DPS(원)', '-', '500', '0', '330', '-'],
]
QUARTERLY = {'headers': ['구분', '1Q25', '2Q25', '3Q25', '4Q25', '1Q26', '2Q26'],
             'rows': [['매출액(억원)', '2,063', '2,682', '2,392', '2,947', '1,904', '2,854'],
                      ['영업이익(억원)', '-68', '70', '131', '50', '-176', '78'],
                      ['영업이익률(%)', '-3.3', '2.6', '5.5', '1.7', '-9.3', '2.7'],
                      ['지배순이익(억원)', '-70', '60', '100', '-10', '-140', '70']],
             'year': 2026, 'note': '연결, 당분기 3개월. 매출·영업이익은 DART 분기 실측(2026)과 신한 7/20·하나 8/18 분기표, 지배순이익은 하나 8/18 실적표(십억원 반올림). 2Q26 별도 영업이익은 -43억(WBC·지방선거 비용 50억)이고 스튜디오S 순익 65억·SBS미디어넷 35억이 연결 흑자를 만들었다'}
SEGMENTS = [{'name': '지상파 TV광고', 'pct': 29.0, 'outlook': '1H26 1,381억. 2019 3,889억 → 2025 2,808억, 2026 상반기 -10%. SA 15초 단가 12,929천원(전년 13,329). 10월 시행령(총량 20%·중간광고 30분)'},
            {'name': '라디오 광고', 'pct': 2.5, 'outlook': 'AM 22억·FM 97억. 비중 작고 추세 동일'},
            {'name': '사업수익(판권·협찬·기타)', 'pct': 68.5, 'outlook': '1H26 3,258억. 넷플릭스 6년 계약(2025.1~) 동시방영 11~12편, 구작 분기 100억. 2Q26 +22%. 스튜디오S·미디어넷·프리즘 자회사 포함'}]


def load_global_peers():
    p = os.path.join(D, '_peer_snapshot_global.json')
    if not os.path.exists(p):
        return {}, ''
    g = jload(p)
    return {k: r for k, r in g.items() if isinstance(r, dict) and r.get('ticker') and 'error' not in (r.get('flags') or [])}, (g.get('_collected_at') or '')[:10]


def values():
    L = {i['key']: i for i in jload(os.path.join(TA, 'calc_ledger.json'))['items']}
    lv = lambda k: L[k]['value'] if k in L else None  # noqa: E731
    A = jload(os.path.join(TA, 'assumptions.json'))
    kis = jload(os.path.join(D, 'data_kis.json'))['current_price']
    md = jload(os.path.join(TA, 'market_data.json'))
    fl = jload(os.path.join(TA, 'flow.json'))
    lt = md['latest']
    price = A['price']
    mcap = round(price * A['shares'] / 1e8)
    pt = A['pbr_target']
    tgt = A['pe_target']['rounded']  # critic 1회 반영: P/B 밴드 산식 폐기 -> 2027E EPS x P/E 10
    bear = A['bear_target']['rounded']
    bull = A['bull_target']['rounded']
    bps_adj = A['bps_adj_0916']['value']
    v = {
        'rating': A['opinion']['rating'], 'tagline': A.get('tagline', ''),
        'price': won(price, 1), 'price_date': A.get('price_date', ''), 'mcap': f'{mcap:,}억원',
        'cash': f"{A['cash_h1']:,}억원", 'debt_total': f"{A['debt_total_h1']:,}억원",
        'netcash': f"{A['net_cash']:,}억원", 'netcash_num': f"{A['net_cash']:,}", 'nc_mcap': pct(A['net_cash'] / mcap, 0, False),
        'bps_h1': won(A['bps0'], 1), 'bps_h1_num': f"{A['bps0']:,}", 'bps_fy25': won(A['bps_fy25'], 1), 'bps_kis': won(kis['BPS'], 1),
        'pbr_h1': f"{price / A['bps0']:.2f}배", 'pbr_stale': f"{price / kis['BPS']:.2f}배",
        'pbr_target': f"{pt['multiple']:.2f}배", 'pbr_just': f"{A['pbr_justified']['value']:.2f}배", 'tgt_low': won(bear, 1), 'tgt_high': won(bull, 1),
        'pbr_just_won': won(A['pbr_justified']['per_share'], 1), 'bps_adj': won(bps_adj, 1), 'pbr_adj': f"{price / bps_adj:.2f}배",
        'eps27_ours': f"{A['pe_target']['eps']:,}원", 'pe_mult': f"{A['pe_target']['multiple']}배", 'tgt_raw': won(A['pe_target']['value'], 1),
        'eps_bear': f"{A['bear_target']['eps']:,}원", 'eps_bull': f"{A['bull_target']['eps']:,}원", 'pe_bull': f"{A['bull_target']['multiple']}배",
        'md_loss_at': f"{A['md_loss_after_tax_h1']:,}억원", 'eq_drop_abs': f"{A['equity_drop_h1']:,}억원", 'netcash_ex_pf': f"{abs(A['net_cash_ex_pf']):,}억원",
        'equity_h1': f"{A['equity_h1']:,}억원", 'equity_fy25': f"{A['equity_fy25'] // 10000:.0f}조{A['equity_fy25'] % 10000:,.0f}억원",
        'eq_drop': pct(A['equity_h1'] / A['equity_fy25'] - 1, 0),
        'md_book': f"{A['md_book_h1']:,}억원", 'md_book_fy25': f"{A['md_book_fy25']:,}억원", 'md_loss': f"{A['md_loss_h1']:,}억원",
        'pf_bond': f"{A['taeyoung_pf_bond']:,}억원",
        'per_cons': f"{price / A['per_scenarios']['cons_mean']['eps']:.1f}배", 'eps_cons': f"{A['per_scenarios']['cons_mean']['eps']:,}원",
        'per_cons27': f"{price / A['per_scenarios']['cons_27']['eps']:.1f}배", 'eps_cons27': f"{A['per_scenarios']['cons_27']['eps']:,}원",
        'per_roll': f"{A['per_scenarios']['roll']['per']:.1f}배", 'eps_roll': f"{A['per_scenarios']['roll']['eps']:,}원",
        'per_ours': f"{price / A['eps_12m_fwd']:.1f}배", 'eps_ours': f"{A['eps_12m_fwd']:,}원",
        'cons_target': won(A['cons_target_avg'], 1), 'cons_n': str(A['cons_target_n']),
        'tgt': won(tgt, 1), 'tgtup': pct(tgt / price - 1), 'cons_gap': pct(tgt / A['cons_target_avg'] - 1, 0),
        'rim': won(lv('rim_value_per_share') or 0, 100), 'iroe': pct(lv('price_implied_roe') or 0, 1, False),
        'var1': pct(lv('var95_1d') or 0, 1, False), 'var20': pct(lv('var95_20d') or 0, 1, False),
        'op26': f"{A['op_26_ours']:,}억원", 'op26_cons': f"{A['op_26_cons']:,}억원", 'op27': f"{A['op_27_ours']:,}억원", 'op27_cons': f"{A['op_27_cons']:,}억원",
        'dps': f"{A['dps_ttm']:,}원",
    }
    v.update({
        'close': won(lt['close'], 1), 'sma50': won(lt['close_50_sma'], 1), 'sma200': won(lt['close_200_sma'], 1),
        'rsi': f"{lt['rsi']:.1f}", 'macdh': f"{lt['macdh']:,.0f}", 'boll_ub': won(lt['boll_ub'], 1),
        'boll_lb': won(lt['boll_lb'], 1), 'boll_mid': won(lt['boll'], 1), 'atr': won(lt['atr'], 1),
        'md_date': A.get('price_date', ''),
        'dist200': pct(lt['close'] / lt['close_200_sma'] - 1), 'dist50': pct(lt['close'] / lt['close_50_sma'] - 1),
        'dead_cross': next((c['date'] for c in reversed(md['signals'].get('cross', [])) if c['type'] == 'dead'), '-'),
        'f_days': str(fl['days']),
    })
    w52 = md['signals'].get('w52') or {}
    v.update({'w52_hi': won(kis['52주최고'], 1), 'w52_lo': won(kis['52주최저'], 1),
              'w52_pos': f"{w52['position_pct']:.0f}%" if w52 else f"{(price - kis['52주최저']) / (kis['52주최고'] - kis['52주최저']) * 100:.0f}%"})
    for who, key in (('외국인', 'foreign'), ('기관', 'inst'), ('개인', 'indiv')):
        v[f'f_{key}_sh'] = f"{fl['net_shares'][who]:+,}주"
        v[f'f_{key}_krw'] = f"{fl['net_shares'][who] * price / 1e8:+,.1f}억원"
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
    return v, tgt


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--sections', default=SECTIONS)
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--dump-placeholders')
    args = ap.parse_args(argv)
    v, tgt = values()
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
    peers_snap = jload(os.path.join(D, '_peer_snapshot.json'))
    peers_snap = peers_snap.get('peers', peers_snap)
    gpeers, _ = load_global_peers()
    peers_snap = {**peers_snap, **{k: r for k, r in gpeers.items() if not r.get('flags')}}
    mcap_uk = round(A['price'] * A['shares'] / 1e8)
    low = A['bear_target']['rounded']
    bull = A['bull_target']['rounded']
    d = {
        'meta': {'stock_name': STOCK, 'stock_code': '034120', 'market': 'KOSPI', 'country': 'KR', 'industry': '지상파 방송·콘텐츠',
                 'date': A.get('price_date', ''), 'currency': 'KRW', 'tagline': A.get('tagline', ''),
                 'section_order': ORDER, 'section_titles': TITLES, 'section_labels': {'s08_esg': 'Technical Analysis'},
                 'variant': 'research-ta lite ' + os.path.basename(os.path.normpath(args.sections))},
        'price': {'current': A['price'], 'market_cap': f"{mcap_uk:,}억원", 'market_cap_num': mcap_uk, 'shares_outstanding': A['shares'],
                  'per': round(A['price'] / kis['EPS'], 2), 'pbr': round(A['price'] / kis['BPS'], 2), 'pbr_h1': round(A['price'] / A['bps0'], 2),
                  'eps': kis['EPS'], 'bps': kis['BPS'], 'high_52w': kis['52주최고'], 'low_52w': kis['52주최저'],
                  'var95_1d': L.get('var95_1d'), 'var95_20d': L.get('var95_20d'), 'consensus_eps': A['per_scenarios']['cons_mean']['eps'],
                  'forward_per': round(A['price'] / A['eps_12m_fwd'], 1), 'forward_eps': A['eps_12m_fwd'],
                  'dividend_yield': round(A['dps_ttm'] / A['price'] * 100, 1)},
        'opinion': {**A['opinion'], 'target_bear': low, 'target_base': tgt, 'target_bull': bull,
                    'risk_reward': f"Base 1:{(tgt / A['price'] - 1) / (1 - low / A['price']):.1f} / Bull 1:{(bull / A['price'] - 1) / (1 - low / A['price']):.1f}"},
        'segments': SEGMENTS,
        'financials': {'headers': ['항목', '2022', '2023', '2024', '2025', '2026 상반기'], 'rows': [[render(c, v) if '{{' in c else c for c in r] for r in FIN_ROWS],
                       'source': 'KIS 연간(연결) + 신한 7/20 재무표(BPS·순현금 2024~2025) + 반기보고서 2026.06 실측(BPS 50,080 = 지배자본 9,291억/18,551,238주, 순현금 = 현금·유동금융 - 차입). 순이익은 연결(비지배지분 포함), EPS 는 지배주주 기준. KIS 헤더 BPS 69,877 은 2025년 말 값'},
        'quarterly': QUARTERLY,
        'supply': {'foreign': fl['net_shares']['외국인'], 'institution': fl['net_shares']['기관'], 'individual': fl['net_shares']['개인'],
                   'days': fl['days'], 'comment': f"외국인 {v['f_foreign_sh']}(방송법상 지상파 외국인 소유 금지), 기관 {v['f_inst_sh']}, 개인 {v['f_indiv_sh']} (주식수 기준)"},
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
    print(f'[OK] {args.out} -- 본문 {body:,}자, 기술적 분석 {len(s["s08_esg"]) / body:.1%}, 목표가 {tgt:,} ({v["tgtup"]}), 기준가 {A["price"]:,}')


if __name__ == '__main__':
    main()
