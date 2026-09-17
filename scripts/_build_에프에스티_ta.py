# -*- coding: utf-8 -*-
"""/research-ta 에프에스티 빌더 (idempotent).

sections/*.md 의 {{이름}} 을 장부(ta/calc_ledger.json)·시세(data_kis.json, ta/market_data.json)·
수급(ta/flow.json) 값으로 채워 scripts/analysis_에프에스티_ta.json 을 쓴다.
본문 수치를 손으로 쓰지 않는 이유: 종가·장부가 바뀌면 다시 돌리기만 하면 된다.
"""
import io
import json
import os
import re
import sys

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOCK = '에프에스티'
D = os.path.join(ROOT, 'data', STOCK)
TA = os.path.join(D, 'ta')
OUT = os.path.join(ROOT, 'scripts', f'analysis_{STOCK}_ta.json')
SECTIONS = os.path.join(TA, 'sections')

ORDER = ['s01_opinion_thesis', 's03_company_overview', 's11_supply_shareholder', 's05_management_fieldcheck',
         's04_industry_competition', 's02_thesis_catalysts', 's10_earnings_consensus', 's07_valuation',
         's08_esg', 's09_scenarios_risks', 's06_financial']
TITLES = {'s01_opinion_thesis': '요약', 's03_company_overview': '기업 개요 및 연혁',
          's11_supply_shareholder': '주주구성 및 자회사', 's05_management_fieldcheck': '주요 제품 및 기술력',
          's04_industry_competition': '산업 현황', 's02_thesis_catalysts': '투자포인트',
          's10_earnings_consensus': '실적 추이 및 전망', 's07_valuation': '밸류에이션',
          's08_esg': '기술적 분석', 's09_scenarios_risks': '리스크 요인', 's06_financial': '재무 분석'}


def jload(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def won(v, step=100):
    return f'{int(round(v / step) * step):,}원'


def pct(v, d=1, sign=True):
    s = f'{v * 100:+.{d}f}%' if sign else f'{v * 100:.{d}f}%'
    return s


def values():
    L = {i['key']: i for i in jload(os.path.join(TA, 'calc_ledger.json'))['items']}
    lv = lambda k: L[k]['value']  # noqa: E731
    A = jload(os.path.join(TA, 'assumptions.json'))
    so = A['sotp']
    kis = jload(os.path.join(D, 'data_kis.json'))['current_price']
    md = jload(os.path.join(TA, 'market_data.json'))
    fl = jload(os.path.join(TA, 'flow.json'))
    lt = md['latest']
    price = A['price']
    v = {
        'price': won(price, 1), 'price_date': A.get('price_date', ''), 'mcap': f"{kis['시가총액']:,}억원",
        'rim': won(lv('rim_value_per_share'), 1), 'jpbr': f"{lv('justified_pbr'):.2f}배",
        'iroe': pct(lv('price_implied_roe'), 1, False), 'var1': pct(lv('var95_1d'), 1, False),
        'var20': pct(lv('var95_20d'), 1, False), 'altz': f"{lv('altman_z'):.2f}",
        'ebitda_half': f"{so['ebitda_half']:,}억원", 'ebitda_ann': f"{so['ebitda_half'] * 2:,.0f}억원",
        'oros_mcap': f"{so['listed_mcap']:,}억원", 'oros_value': f"{so['listed_stake'] * so['listed_mcap']:,.0f}억원",
        'isol': f"{so['unlisted_book']:,.0f}억원", 'netdebt': f"{so['net_debt']:,.0f}억원",
        'netdebt_ps': won(so['net_debt'] * 1e8 / A['shares'], 10),
        'nd_mcap': pct(so['net_debt'] / kis['시가총액'], 0, False),
        'iprob': pct(lv('sotp_implied_option_prob'), 0, False),
        'ev_value': won(lv('sotp_expected_value')), 'ev_up': pct(lv('sotp_expected_upside')),
        'w_bear': pct(so['weights']['bear'], 0, False), 'w_base': pct(so['weights']['base'], 0, False), 'w_bull': pct(so['weights']['bull'], 0, False),
        'iprob_ttm': pct((price * A['shares'] / 1e8 - (so['scenarios']['base_ttm']['ebitda_annual'] * so['scenarios']['base_ttm']['multiple']
                          + so['listed_stake'] * so['listed_mcap'] + so['unlisted_book'] - so['net_debt']))
                         / (so['option_ev_success'] * so['option_discount']), 0, False),
        'iopt_share': pct(lv('sotp_implied_option_prob') * so['option_ev_success'] * so['option_discount'] / (price * A['shares'] / 1e8), 0, False),
        'iopt_value': f"{lv('sotp_implied_option_prob') * so['option_ev_success'] * so['option_discount']:,.0f}억원",
        'gift_value': f"{874167 * price / 1e8:,.0f}억원",
        'tpbr': f"{lv('sotp_value_per_share_base') / A['bps0']:.2f}배",
        'cons_gap_ss': pct(lv('sotp_value_per_share_base') / 40000 - 1, 0),
        'cons_gap_yt': pct(lv('sotp_value_per_share_base') / 48000 - 1, 0),
    }
    fw = jload(os.path.join(TA, 'peer_fwd_ev_ebitda.json'))['peers']
    v.update({
        'hana_ttm': f"{fw['하나머티리얼즈']['ev_ebitda_ttm_0917']:.2f}배", 'hana_fwd': f"{fw['하나머티리얼즈']['ev_ebitda_ntm']:.2f}배",
        'unisem_ttm': f"{fw['유니셈']['ev_ebitda_ttm_0917']:.2f}배", 'unisem_fwd': f"{fw['유니셈']['ev_ebitda_ntm']:.2f}배",
        'fst_fwd': f"{fw['에프에스티']['ev_ebitda_ntm']:.2f}배", 'fst_ttm': f"{fw['에프에스티']['ev_ebitda_ttm_0917']:.2f}배",
        'da_ttm': f"{fw['에프에스티']['da_ttm']:,.1f}억원", 'ntm_op': f"{0.25 * fw['에프에스티']['op26e'] + 0.75 * fw['에프에스티']['op27e']:,.1f}억원",
        'gift_tax_lo': f"{((874167 * price / 1e8) * 0.5 - 4.6) * 0.97 * 2:,.0f}억원",           # 할증 0%, 2인 합계
        'gift_tax_hi': f"{((874167 * price * 1.2 / 1e8) * 0.5 - 4.6) * 0.97 * 2:,.0f}억원",     # 최대주주 할증 20%
        'gift_tax_mcap': pct(((874167 * price * 1.2 / 1e8) * 0.5 - 4.6) * 0.97 * 2 / kis['시가총액'], 0, False),
    })
    for sc in so['scenarios']:
        s = so['scenarios'][sc]
        v[f'sotp_{sc}'] = won(lv(f'sotp_value_per_share_{sc}'))
        v[f'up_{sc}'] = pct(round(lv(f'sotp_value_per_share_{sc}') / 100) * 100 / price - 1)  # 표시 목표가(100원 반올림) 기준 -- 커버와 일치
        v[f'eq_{sc}'] = f"{L[f'sotp_value_per_share_{sc}']['equity_억']:,.0f}억원"
        v[f'mult_{sc}'] = f"{s['multiple']:.1f}배" if round(s['multiple'], 1) == s['multiple'] else f"{s['multiple']:.2f}배"
        v[f'ebitda_{sc}'] = f"{(s.get('ebitda_annual') or so['ebitda_half'] * 2):,.0f}억원"
        v[f'core_{sc}'] = f"{(s.get('ebitda_annual') or so['ebitda_half'] * 2) * s['multiple']:,.0f}억원"
        v[f'cnt_{sc}'] = f"{so['option_ev_success'] * s['option_prob'] * so['option_discount']:,.0f}억원"
    base_v = lv('sotp_value_per_share_base')
    for nm, key in (('p0', 'base_p0'), ('p80', 'base_p80'), ('bear', 'bear'), ('bull', 'bull')):
        r100 = lambda x: int(round(x / 100) * 100)  # noqa: E731  표에 보이는 반올림 값끼리 뺀다
        dv = r100(lv(f'sotp_value_per_share_{key}')) - r100(base_v)
        v[f'd_{nm}'] = f"{dv:+,}원 ({dv / r100(base_v) * 100:+.0f}%)"
    v.update({
        'close': won(lt['close'], 1), 'sma50': won(lt['close_50_sma'], 10), 'sma200': won(lt['close_200_sma'], 10),
        'rsi': f"{lt['rsi']:.1f}", 'macdh': f"{lt['macdh']:,.0f}", 'boll_ub': won(lt['boll_ub'], 10),
        'boll_lb': won(lt['boll_lb'], 10), 'boll_mid': won(lt['boll'], 10), 'atr': won(lt['atr'], 10),
        'md_date': md.get('rows_last_date') or (md.get('series_tail') or [{}])[-1].get('date', md['asof']),
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
    return v


_JOSA = {'은': ('은', '는'), '는': ('은', '는'), '이': ('이', '가'), '가': ('이', '가'),
         '을': ('을', '를'), '를': ('을', '를'), '으로': ('으로', '로'), '로': ('으로', '로'),
         '이다': ('이다', '다'), '다': ('이다', '다')}
_DIGIT_BATCHIM = set('0136780')  # 영 일 삼 육 칠 팔 십 (0 은 '십/백/천/만' 자리 끝이라도 받침 있음)


def _final(value):
    """(받침 있음, 받침이 ㄹ) -- 괄호 부기는 건너뛰고 앞 단어 기준으로 읽는다."""
    s = re.sub(r'\([^()]*\)\s*$', '', value).rstrip()
    ch = s[-1] if s else ''
    if '가' <= ch <= '힣':
        jong = (ord(ch) - 0xAC00) % 28
        return jong != 0, jong == 8
    if ch == '%':
        return False, False  # 퍼센트
    return ch in _DIGIT_BATCHIM, ch in '178'


def render(text, v):
    """placeholder 치환 + 바로 뒤 조사를 값의 받침에 맞춘다 (예: 29,600원를 -> 29,600원을).
    괄호 부기 `{{a}}({{b}})가` 는 괄호 앞 값(a)의 받침으로 고른다."""
    def val(k):
        if k not in v:
            raise KeyError(f'placeholder 없음: {k}')
        return v[k]

    def sub(m):
        k, paren, josa = m.group(1), m.group(2), m.group(3)
        out = val(k)
        if paren is not None:
            out += '(' + re.sub(r'\{\{([a-z0-9_]+)\}\}', lambda mm: val(mm.group(1)), paren) + ')'
        if not josa:
            return out
        batchim, rieul = _final(val(k))
        pair = _JOSA[josa]
        pick = pair[0] if batchim and not (pair[0] == '으로' and rieul) else pair[1]
        return out + pick
    return re.sub(r'\{\{([a-z0-9_]+)\}\}(?:\(([^()]*\{\{[a-z0-9_]+\}\}[^()]*)\))?(?:(이다|으로|은|는|이|가|을|를|로|다)(?![가-힣]))?', sub, text)


PEER_NOTE = {'동진쎄미켐': '노광 소재(PR), 배수 산정', '하나머티리얼즈': '반도체 소모성 부품, 선행 배수',
             '유니셈': '칠러·스크러버, 선행 배수', '에스티아이': '칠러·장비, 배수 산정', '에스앤에스텍': 'EUV 블랭크마스크(참고)'}

H1 = {'매출액(억원)': '1,589', '영업이익(억원)': '110', '영업이익률(%)': '6.9', '순이익(억원)': '42',
      '영업활동현금흐름(억원)': '39', '설비투자(억원)': '439', '잉여현금흐름(억원)': '-401', '순차입금(억원)': '2,269'}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--sections', default=SECTIONS, help='섹션 md 폴더 (A/B 실험: ta/sections_agent)')
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--dump-placeholders', help='플레이스홀더 이름과 현재 값을 이 json 경로로 쓰고 종료')
    ap.add_argument('--opinion', help='등급·목표가 override json (lite 대조군: ta/lite_opinion.json)')
    args = ap.parse_args(argv)
    v = values()
    if args.dump_placeholders:
        with open(args.dump_placeholders, 'w', encoding='utf-8') as f:
            json.dump(v, f, ensure_ascii=False, indent=1)
        print(f'[OK] placeholders {len(v)}개 -> {args.dump_placeholders}')
        return
    base = jload(os.path.join(ROOT, 'scripts', f'analysis_{STOCK}.json'))  # price/peers 등 구조 참고용 원본
    secs = {}
    for k in ORDER + ['s13_thesis', 's14_short_thesis']:
        p = os.path.join(args.sections, f'{k}.md')
        with open(p, encoding='utf-8') as f:
            secs[k] = render(f.read().strip() + '\n', v)
    L = {i['key']: i['value'] for i in jload(os.path.join(TA, 'calc_ledger.json'))['items']}
    A = jload(os.path.join(TA, 'assumptions.json'))
    kis = jload(os.path.join(D, 'data_kis.json'))['current_price']
    md = jload(os.path.join(TA, 'market_data.json'))
    fl = jload(os.path.join(TA, 'flow.json'))
    rnd = lambda x: int(round(x / 100) * 100)  # noqa: E731
    # 요약 재무표: 마지막 열은 추정 대신 반기보고서 실측(2026 상반기). financial_summary 2026 블록은 OCF·CAPEX 가 DART 와 달라 쓰지 않는다
    FIN = {'headers': ['항목', '2022', '2023', '2024', '2025', '2026 상반기'],
           'rows': [[r[0]] + r[1:5] + [H1[r[0]]] for r in base['financials']['rows']],
           'source': 'DART 연결(2026 상반기: 반기보고서 손익·현금흐름표, 순차입금은 회사 공시 순부채) + FnGuide'}
    tb, tbase, tbull = rnd(L['sotp_value_per_share_bear']), rnd(L['sotp_value_per_share_base']), rnd(L['sotp_value_per_share_bull'])
    op_over = jload(args.opinion) if args.opinion else None
    if op_over:  # lite 대조군: 작성자가 정한 등급·목표가를 그대로 쓴다 (장부 SOTP 무시)
        tb, tbase, tbull = op_over['target_bear'], op_over['target_base'], op_over['target_bull']
    d = {
        'meta': {**base['meta'], 'date': A.get('price_date', base['meta']['date']),
                 'tagline': A.get('tagline', '이익은 돌아왔고 EUV는 아직 확인 전이다'),
                 'section_order': ORDER, 'section_titles': TITLES,
                 'section_labels': {'s08_esg': 'Technical Analysis'},
                 'variant': 'research-ta pilot ' + os.path.basename(os.path.normpath(args.sections))},
        'price': {**base['price'], 'current': A['price'], 'market_cap': f"{kis['시가총액']:,}억원",
                  'market_cap_num': kis['시가총액'], 'shares_outstanding': round(kis['시가총액'] * 1e8 / A['price']), 'shares_float_for_sotp': A['shares'],
                  'per': kis['PER'], 'pbr': kis['PBR'], 'eps': kis['EPS'], 'bps': kis['BPS'],
                  'high_52w': kis['52주최고'], 'low_52w': kis['52주최저'], 'forward_per': None, 'forward_eps': None,
                  'var95_1d': L['var95_1d'], 'var95_20d': L['var95_20d'], 'consensus_eps': 611.22},
        'opinion': ({'rating': op_over['rating'], 'type': op_over.get('method', ''), 'portfolio_role': '',
                     'target_bear': tb, 'target_base': tbase, 'target_bull': tbull,
                     'risk_reward': f"Base {(tbase / A['price'] - 1) * 100:+.1f}%"} if op_over else
                    {**A['opinion'], 'target_bear': tb, 'target_base': tbase, 'target_bull': tbull,
                     'risk_reward': f"기대 {v['ev_up']}"}),  # 커버 레일 폭 제한 -- 긴 문자열이면 3-시나리오 값이 잘린다
        'segments': base['segments'], 'financials': FIN, 'quarterly': base['quarterly'],
        'supply': {'foreign': fl['net_shares']['외국인'], 'institution': fl['net_shares']['기관'],
                   'individual': fl['net_shares']['개인'], 'days': fl['days'],
                   'comment': f"외국인 {v['f_foreign_sh']}, 기관 {v['f_inst_sh']}, 개인 {v['f_indiv_sh']} (주식수 기준, 금액은 조회 시점 가격 환산)"},
        'peers': [{'name': n, 'market_cap': f"{r['market_cap_uk']:,}억", 'per': r['per'], 'pbr': r['pbr'],
                   'note': PEER_NOTE.get(n, ''), 'highlight': False}
                  for n, r in jload(os.path.join(D, '_peer_snapshot.json')).items()],  # 밸류 산정 대상과 동일 5사, KIS 실시간
        'catalysts': [
            {'date': '2026-10-01', 'event': '최대주주 지분 증여(16.15% -> 8.08%, 두 자녀 각 874,167주)', 'impact': '특수관계인 합계 불변. 증여세 2인 합계 약 ' + v['gift_tax_lo'] + '~' + v['gift_tax_hi'] + ' 재원 미공시'},
            {'date': '2026-11-14', 'event': '3분기보고서 제출기한', 'impact': '2분기 이익 지속·OCF·차입 방향 확인'},
            {'date': '2027 상반기', 'event': '카나투 추가 반응기 납품', 'impact': 'CNT 생산능력 확대의 실물 시점'},
            {'date': '2027 초', 'event': '삼성 테일러 팹 EUV 펠리클 납품 예정(보도)', 'impact': 'EUV 매출 인식 여부'}],
        'sections': secs,
    }
    if 'forward_per' in d['price'] and d['price']['forward_per'] is None:
        d['price'].pop('forward_per'); d['price'].pop('forward_eps')
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
    print(f'[OK] {args.out} -- 본문 {body:,}자, 기술적 분석 {len(s["s08_esg"]) / body:.1%}, '
          f'Base {tbase:,} ({v["up_base"]}), 기준가 {A["price"]:,}')


if __name__ == '__main__':
    main()
