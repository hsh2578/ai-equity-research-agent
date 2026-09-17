# -*- coding: utf-8 -*-
"""/research-ta CJ프레시웨이 빌더 (idempotent). 에프에스티 빌더의 render()/won()/pct() 를 재사용하고
밸류 플레이스홀더만 PER 시나리오(ta/calc_ledger.json per_value_*)로 바꾼다.

sections/*.md 의 {{이름}} 을 장부·시세·수급 값으로 채워 scripts/analysis_CJ프레시웨이_ta.json 을 쓴다.
"""
import importlib.util
import io
import json
import os
import sys

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOCK = 'CJ프레시웨이'
D = os.path.join(ROOT, 'data', STOCK)
TA = os.path.join(D, 'ta')
OUT = os.path.join(ROOT, 'scripts', f'analysis_{STOCK}_ta.json')
SECTIONS = os.path.join(TA, 'sections')

_spec = importlib.util.spec_from_file_location('_fst', os.path.join(ROOT, 'scripts', '_build_에프에스티_ta.py'))
_fst = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fst)
render, won, pct, jload = _fst.render, _fst.won, _fst.pct, _fst.jload
ORDER, TITLES = _fst.ORDER, _fst.TITLES

PEER_NOTE = {'현대그린푸드': '단체급식 비중 큰 경쟁사', '신세계푸드': '급식 매각, 식자재 전업', '풀무원': '식자재+직영급식 겸업',
             '삼성웰스토리': '비상장', '아워홈': '비상장'}
# 요약 재무표 마지막 열: 반기보고서 실측 (financial_summary 2026 블록의 OCF·CAPEX 는 검증 후 사용)
H1 = {'매출액(억원)': '17,571', '영업이익(억원)': '346', '영업이익률(%)': '2.0', '순이익(억원)': '148', 'EPS(원)': '1,248',
      'BPS(원)': '36,444', '부채비율(%)': '319.4', '영업활동현금흐름(억원)': '-363', '설비투자(억원)': '212', '리스부채 원금상환(억원)': '226'}  # 반기보고서 현금흐름표(2026.06) 실측. financial_summary 의 2026 열은 연간 컨센(2026E)이라 쓰지 않는다 (critic 1회차 A1)


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
    v = {
        'price': won(price, 1), 'price_date': A.get('price_date', ''), 'mcap': f'{mcap:,}억원',
        'rim': won(lv('rim_value_per_share'), 1), 'jpbr': f"{lv('justified_pbr'):.2f}배",
        'iroe': pct(lv('price_implied_roe'), 1, False), 'idcf_g': pct(lv('reverse_dcf_implied_growth'), 0),
        'var1': pct(lv('var95_1d'), 1, False), 'var20': pct(lv('var95_20d'), 1, False),
        'netdebt': f"{-A['net_cash']:,.0f}억원", 'nd_mcap': pct(-A['net_cash'] / mcap, 0, False),
        'per_now': f"{price / A['per_scenarios']['bull']['eps']:.1f}배", 'pbr_now': f"{price / kis['BPS']:.2f}배", 'pbr_h1': f"{price / A['bps0']:.2f}배",
        'eps_cons': f"{A['per_scenarios']['bull']['eps']:,}원", 'eps_base': f"{A['per_scenarios']['base']['eps']:,}원",
        'eps_bear': f"{A['per_scenarios']['bear']['eps']:,}원",
        'ev_value': won(lv('per_expected_value')), 'ev_up': pct(lv('per_expected_upside')),
        'w_bear': pct(A['weights']['bear'], 0, False), 'w_base': pct(A['weights']['base'], 0, False), 'w_bull': pct(A['weights']['bull'], 0, False),
        'cons_gap': pct(round(lv('per_value_base') / 100) * 100 / 43000 - 1, 0),
        'tpbr': f"{lv('per_value_base') / A['bps0']:.2f}배",
    }
    for sc, s in A['per_scenarios'].items():
        v[f'per_{sc}'] = won(lv(f'per_value_{sc}'))
        v[f'up_{sc}'] = pct(round(lv(f'per_value_{sc}') / 100) * 100 / price - 1)
        v[f'mult_{sc}'] = f"{s['per']:.1f}배"
        v[f'eps_{sc}'] = f"{s['eps']:,}원"
    v.update({
        'close': won(lt['close'], 1), 'sma50': won(lt['close_50_sma'], 10), 'sma200': won(lt['close_200_sma'], 10),
        'rsi': f"{lt['rsi']:.1f}", 'macdh': f"{lt['macdh']:,.0f}", 'boll_ub': won(lt['boll_ub'], 10),
        'boll_lb': won(lt['boll_lb'], 10), 'boll_mid': won(lt['boll'], 10), 'atr': won(lt['atr'], 10),
        'md_date': md.get('rows_last_date') or md.get('asof', ''),
        'dist200': pct(lt['close'] / lt['close_200_sma'] - 1),
        'dead_cross': next((c['date'] for c in reversed(md['signals'].get('cross', [])) if c['type'] == 'dead'), '-'),
        'f_days': str(fl['days']),
    })
    w52 = md['signals'].get('w52') or {}
    if w52:
        v.update({'w52_hi': won(w52['high'], 1), 'w52_lo': won(w52['low'], 1), 'w52_pos': f"{w52['position_pct']:.0f}%"})
    for who, key in (('외국인', 'foreign'), ('기관', 'inst'), ('개인', 'indiv')):
        v[f'f_{key}_sh'] = f"{fl['net_shares'][who]:+,}주"
        v[f'f_{key}_krw'] = f"{fl['net_krw'][who] / 1e8:+,.1f}억원"
        v[f'f_{key}_pct'] = f"{fl['pct_of_shares'][who]:+.2f}%"
    v['f_price_used'] = won(fl.get('price_used', price), 1)
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
    base = jload(os.path.join(ROOT, 'scripts', f'analysis_{STOCK}.json'))  # 구조 참고용 원본(기존 /research 리포트)
    secs = {}
    for k in ORDER + ['s13_thesis', 's14_short_thesis']:
        with open(os.path.join(args.sections, f'{k}.md'), encoding='utf-8') as f:
            secs[k] = render(f.read().strip() + '\n', v)
    L = {i['key']: i['value'] for i in jload(os.path.join(TA, 'calc_ledger.json'))['items']}
    A = jload(os.path.join(TA, 'assumptions.json'))
    kis = jload(os.path.join(D, 'data_kis.json'))['current_price']
    fl = jload(os.path.join(TA, 'flow.json'))
    rnd = lambda x: int(round(x / 100) * 100)  # noqa: E731
    FIN = {'headers': ['항목', '2022', '2023', '2024', '2025', '2026 상반기'],
           'rows': [[('순이익(연결, 억원)' if r[0] == '순이익(억원)' else r[0])] + r[1:5]
                    + [('133' if r[0] == '순이익(억원)' else H1.get(r[0], '-'))] for r in base['financials']['rows']],  # 순이익 행은 2022~2024 가 연결이라 라벨을 맞춘다(지배 148 은 본문)
           'source': 'FnGuide 연간(순이익은 연결) + 반기보고서 손익·현금흐름표(2026 상반기 실측)'}
    tb, tbase, tbull = rnd(L['per_value_bear']), rnd(L['per_value_base']), rnd(L['per_value_bull'])
    peers_snap = jload(os.path.join(D, '_peer_snapshot.json'))
    d = {
        'meta': {**base['meta'], 'date': A.get('price_date', base['meta']['date']), 'tagline': A.get('tagline', base['meta'].get('tagline', '')),
                 'section_order': ORDER, 'section_titles': TITLES, 'section_labels': {'s08_esg': 'Technical Analysis'},
                 'variant': 'research-ta ' + os.path.basename(os.path.normpath(args.sections))},
        'price': {**base['price'], 'current': A['price'], 'market_cap': f"{round(A['price'] * A['shares'] / 1e8):,}억원",
                  'market_cap_num': round(A['price'] * A['shares'] / 1e8), 'shares_outstanding': A['shares'],
                  'per': round(A['price'] / kis['EPS'], 2) if kis.get('EPS') else kis.get('PER'), 'pbr': round(A['price'] / kis['BPS'], 2),
                  'eps': kis['EPS'], 'bps': kis['BPS'], 'high_52w': kis['52주최고'], 'low_52w': kis['52주최저'],
                  'var95_1d': L['var95_1d'], 'var95_20d': L['var95_20d'], 'consensus_eps': A['per_scenarios']['bull']['eps']},
        'opinion': {**A['opinion'], 'target_bear': tb, 'target_base': tbase, 'target_bull': tbull, 'risk_reward': f"1:{(tbase / A['price'] - 1) / (1 - tb / A['price']):.1f}"},  # 상방/하방 (verify B10 형식)
        'segments': base['segments'], 'financials': FIN, 'quarterly': base.get('quarterly', {}),
        'supply': {'foreign': fl['net_shares']['외국인'], 'institution': fl['net_shares']['기관'], 'individual': fl['net_shares']['개인'],
                   'days': fl['days'], 'comment': f"외국인 {v['f_foreign_sh']}, 기관 {v['f_inst_sh']}, 개인 {v['f_indiv_sh']} (주식수 기준, 금액은 조회 시점 가격 환산)"},
        'peers': [{'name': n, 'market_cap': f"{r['market_cap_uk']:,}억", 'per': r['per'], 'pbr': r['pbr'], 'note': PEER_NOTE.get(n, ''), 'highlight': False}
                  for n, r in peers_snap.items()][:5],
        'catalysts': A.get('catalysts', []),
        'sections': secs,
    }
    for k in ('forward_per', 'forward_eps'):
        d['price'].pop(k, None)
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
    print(f'[OK] {args.out} -- 본문 {body:,}자, 기술적 분석 {len(s["s08_esg"]) / body:.1%}, Base {tbase:,} ({v["up_base"]}), 기준가 {A["price"]:,}')


if __name__ == '__main__':
    main()
