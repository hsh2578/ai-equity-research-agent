"""ta_calc_ledger.py -- 계산 장부 + 엑셀 모델 + 본문 대조 (Task 10, /research-ta).

리포트에 쓰는 파생 수치는 전부 여기서 계산하고 장부(ta/calc_ledger.json)에 남긴다.
각 항목에는 output/{종목}_ta/model_{종목}.xlsx 의 Calc 시트에 실제로 들어간 수식을 붙인다.

    python scripts/ta_calc_ledger.py compute {종목명}
    python scripts/ta_calc_ledger.py check   {종목명} [--analysis scripts/analysis_{종목명}_ta.json]

단위 규약
  - 재무값은 전부 억원(float). 조회 순서: data_dart_financials.json(원, 반올림 없음)/1e8
    -> _fnguide.json(억원 소수) -> financial_summary.json(정수 억원). EPS/BPS 는 원. (SOURCES)
  - 비율(roe, opm, 성장률, VaR, 내재성장률, upside): 소수 (0.148 = 14.8%), unit "ratio".
  - assumptions.json: fcf0 / net_cash 는 억원, price 는 원, shares 는 주, bps0 는 원.
    시가총액(억원) = price x shares / 1e8.
  - ROE = 지배주주 순이익 / 평균 지배주주지분, ROA = 연결 순이익 / 평균 자산총계 (FnGuide/Wisereport 공표 정의).
    지배주주 분리가 없으면 연결 기준, 기초 잔액이 없으면 기말 기준으로 내리고 item.note 에 적는다.
    나머지 비율(부채·유동비율 등)은 기말 잔액. 각 item 의 definition 이 실제 쓴 식이다.

본문 대조(check) 규칙 -- CJ프레시웨이 실측에서 FAIL 54건 중 진짜 결함이 2건이라 다듬었다
  - 지표 이름 뒤 30자 안의 첫 숫자만 본다. 문장이 끝나면(다. / 문단) 다음 문장의 숫자는 보지 않는다.
  - 표는 이름만 있는 셀의 다음 셀 값을 보고, 다른 글이 섞인 셀은 다음 셀로 넘어가지 않는다.
  - "5개년 / 20일 / 600억 / 6월" 같은 기간·단위, "500% 이하 / 5%대 / 1%포인트" 같은 기준선은 값이 아니다.
  - 순부채비율은 부채비율이 아니다(이름 앞 경계).
  - 장부값과 다른데 주변에 반기·분기·부문·재분류·타사·FnGuide·장부에 없는 연도가 적혀 있으면 FAIL 이 아니라
    WARN(작성자 출처 확인)이다. 올해 값은 반기 누적이라 기간을 'FY{년} YTD' 로 적는다.
  - 비율은 재무요약에 있는 모든 연도를 계산한다(본문 표가 4~5개년을 싣는다).

식 출처(수정하지 않고 일치만 맞춘다)
  - Altman Z: verify_numbers.py B17 -- 1.2(CA-CL)/TA + 1.4 RE/TA + 3.3 EBIT/TA + 0.6 MC/TL + 1.0 Sales/TA
  - 적정 PBR: ggm_check.implied_pbr -- (ROE-g)/(ke-g)
  - DCF: dcf_calculator.calculate_dcf -- FCF_t = FCF0(1+g)^t, TV = FCF_n(1+gT)/(wacc-gT)
"""
import io
import os
import re
import sys
import argparse
import datetime as _dt
from decimal import Decimal, ROUND_HALF_UP

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta_common  # noqa: E402

# 입력 조회 순서 (필드별, 앞 후보 우선). 모든 재무값은 **억원(float)** 으로 통일한다.
#   ('dart', sj_div들, account_id들) -> data_dart_financials.json[YYYY].list thstrm_amount (원, 반올림 없음) / 1e8
#   ('fnguide', 경로)               -> _fnguide.json 경로 끝 dict 의 'YYYY/MM' 키 (억원, 소수 2자리)
#   ('fs', 후보키들)                 -> financial_summary.json financials.YYYY (정수 억원으로 반올림됨 -> 마지막)
# 정밀도가 공표치 대조를 좌우한다(에프에스티 ROA: 정수 억원 -2.73% vs 원 단위 -2.74%). 그래서 DART 가 먼저다.
_BS, _IS = ('BS',), ('CIS', 'IS')
SOURCES = {
    'revenue': [('dart', _IS, ('ifrs-full_Revenue', 'dart_Revenue')),
                ('fnguide', ('financial', 'annual', 'revenue')), ('fs', ('revenue',))],
    'op_income': [('dart', _IS, ('dart_OperatingIncomeLoss', 'ifrs-full_OperatingIncomeLoss')),
                  ('fnguide', ('financial', 'annual', 'operating_income')), ('fs', ('op_income',))],
    'ebit': [('dart', _IS, ('dart_OperatingIncomeLoss', 'ifrs-full_OperatingIncomeLoss')),
             ('fnguide', ('financial', 'annual', 'operating_income')), ('fs', ('ebit', 'op_income'))],
    'net_income': [('dart', _IS, ('ifrs-full_ProfitLoss',)),
                   ('fnguide', ('financial', 'annual', 'net_income')), ('fs', ('net_income',))],
    'net_income_ctrl': [('dart', _IS, ('ifrs-full_ProfitLossAttributableToOwnersOfParent',)),
                        ('fnguide', ('financial', 'annual', 'net_income_controlling')),
                        ('fs', ('net_income_controlling', 'controlling_net_income'))],
    'total_equity': [('dart', _BS, ('ifrs-full_Equity',)),
                     ('fnguide', ('consensus_estimates', '_meta', 'actual', 'total_equity')), ('fs', ('total_equity',))],
    'controlling_equity': [('dart', _BS, ('ifrs-full_EquityAttributableToOwnersOfParent',)),
                           ('fnguide', ('consensus_estimates', '_meta', 'actual', 'controlling_equity')),
                           ('fs', ('controlling_equity',))],
    'total_assets': [('dart', _BS, ('ifrs-full_Assets',)),
                     ('fnguide', ('consensus_estimates', '_meta', 'actual', 'total_assets')), ('fs', ('total_assets',))],
    'total_liabilities': [('dart', _BS, ('ifrs-full_Liabilities',)),
                          ('fnguide', ('consensus_estimates', '_meta', 'actual', 'total_liabilities')),
                          ('fs', ('total_debt',))],   # financial_summary 의 total_debt = 부채총계
    'current_assets': [('dart', _BS, ('ifrs-full_CurrentAssets',)), ('fs', ('current_assets',))],
    'current_liabilities': [('dart', _BS, ('ifrs-full_CurrentLiabilities',)), ('fs', ('current_liabilities',))],
    'retained_earnings': [('dart', _BS, ('ifrs-full_RetainedEarnings',)), ('fs', ('retained_earnings',))],
    'interest_expense': [('dart', _IS, ('ifrs-full_InterestExpense', 'dart_InterestExpense')),
                         ('fs', ('interest_expense',)),
                         ('dart', _IS, ('ifrs-full_FinanceCosts',)),                 # 금융원가 대용
                         ('fnguide', ('financial', 'annual', 'finance_cost'))],      # 금융원가 대용
    # 주당·기타 값: financial_summary 만 (EPS 원/주, 순부채 억원)
    'eps': [('fs', ('eps',))],
    'shares': [('fs', ('shares_outstanding',))],
    'net_debt': [('fs', ('net_debt',))],
}
STATEMENT_UNIT = '억원 (DART 원/1e8 -> FnGuide 억원 -> financial_summary 정수 억원 순으로 조회)'
CONSOLIDATED_MARKERS = ('NoncontrollingInterest', 'AttributableToOwnersOfParent')
MIXED_BASIS_WARNING = '연결/별도 기준 혼재 가능'
CHECKED_FILES = ('financial_summary.json', '_fnguide.json', 'data_dart_financials.json')
MARKET_CAP_KEY = 'market_cap_억'  # financial_summary.json kis 블록 (B17 과 같은 KIS 시총, 억원)

DENOM_MIN = 0.01
NET_CASH_MAG_TOL = 0.20  # assumptions.net_cash 와 financial_summary net_debt 크기 차이 허용 (시점 차이 감안)
NET_CASH_NOTE = '순현금 기업이라 모형 부적합(v5.4 규칙 18)'
ALTMAN_NOTE = ("시총은 현재 시점, 재무는 FY 기말; 원형 Z 는 상장 제조업 모형이라 비제조업이면 Z'' 가 적합 "
               '(식은 verify_numbers B17 과 일치시키려고 원형 유지)')
RIM_DEFINITION = ('V = BPS0 + sum_{t=1..N} (ROE_t - ke) x BPS_{t-1} / (1+ke)^t '
                  '+ [(ROE_N - ke) x BPS_{N-1}] x (1+g) / (ke - g) / (1+ke)^N; '
                  'BPS_t = BPS_{t-1} x (1 + ROE_t x (1 - payout)). '
                  '잔여가치는 N년차 초과이익을 g 로 키운다(BPS 가 ROE(1-payout) 로 커지는 (ROE_N-ke)xBPS_N 기준과 다름)')


# ==================== 순수 계산 ====================

def leverage_ratio(num_prev, num_cur, den_prev, den_cur):
    """(%Δnum)/(%Δden). 반환 (value, reason)."""
    for p, c in ((num_prev, num_cur), (den_prev, den_cur)):
        if p <= 0:
            return None, '부호 전환으로 해석 불가'
        # 브리프는 '전년 음수'만 요구. 흑->적 전환도 %Δ 비율이 의미 없어 같이 막는다 (컨트롤러 승인)
        if c < 0:
            return None, '부호 전환으로 해석 불가(당년 흑자->적자 전환, 확장 가드)'
    d = den_cur / den_prev - 1
    if abs(d) < DENOM_MIN:
        return None, '분모 변화 미미'
    return (num_cur / num_prev - 1) / d, ''


def altman_zone(z):
    if z > 2.99:
        return 'safe'
    if z >= 1.81:
        return 'grey'
    return 'distress'


def _roe_path(roe_list, years):
    return [roe_list[min(t, len(roe_list) - 1)] for t in range(years)]


def rim_value(bps0, roe_list, ke, g, years, payout=0.0):
    """V = BPS0 + sum (ROE_t-ke)BPS_{t-1}/(1+ke)^t + RI_N(1+g)/(ke-g)/(1+ke)^N."""
    v, bps, ri = bps0, bps0, 0.0
    for t, roe in enumerate(_roe_path(roe_list, years), start=1):
        ri = (roe - ke) * bps
        v += ri / (1 + ke) ** t
        bps = bps * (1 + roe * (1 - payout))
    return v + ri * (1 + g) / (ke - g) / (1 + ke) ** years


def dcf_ev(fcf0, g1, wacc, g_t, years):
    ev, fcf = 0.0, fcf0
    for t in range(1, years + 1):
        fcf = fcf * (1 + g1)
        ev += fcf / (1 + wacc) ** t
    return ev + fcf * (1 + g_t) / (wacc - g_t) / (1 + wacc) ** years


EV_RESIDUAL_TOL = 1e-6  # 억원 (= 100원). reverse DCF 해 g 로 재계산한 EV 와 목표 EV 의 허용 차이


def solve_implied_growth(target_ev, fcf0, wacc, g_t, years, lo=-0.5, hi=1.0, tol=1e-6):
    """dcf_ev(g1) = target_ev 인 g1 을 이분법으로. 반환 (g1, reason).
    구간 폭이 tol(g 기준) 아래이고 **동시에** |EV 잔차| < EV_RESIDUAL_TOL(억원) 일 때 멈춘다."""
    f = lambda g: dcf_ev(fcf0, g, wacc, g_t, years) - target_ev  # noqa: E731
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        return None, f'해가 탐색 범위({lo:.0%}~{hi:.0%}) 밖'
    mid = (lo + hi) / 2
    for _ in range(300):
        mid = (lo + hi) / 2
        fm = f(mid)
        if hi - lo < tol and abs(fm) < EV_RESIDUAL_TOL:
            break
        if (flo < 0) == (fm < 0):
            lo, flo = mid, fm
        else:
            hi = mid
    else:
        return None, f'이분법 미수렴 (|EV 잔차| {abs(fm):.2e}억 >= {EV_RESIDUAL_TOL:g}억)'
    return mid, ''


# ==================== 장부 ====================

class _Book:
    """Inputs 행과 Calc 행을 순서대로 쌓아 셀 주소를 확정한다 (헤더 1행, 데이터 2행부터)."""

    def __init__(self):
        self.inputs, self._idx, self.items = [], {}, []

    def inp(self, label, value, source):
        if label not in self._idx:
            self._idx[label] = len(self.inputs) + 2
            self.inputs.append({'label': label, 'value': value, 'source': source})
        return f'Inputs!C{self._idx[label]}'

    def add(self, key, unit, period, value=None, excel='', inputs=None, reason='', **extra):
        row = len(self.items) + 2
        ok = value is not None and not reason
        it = {'key': key, 'value': value if ok else None, 'unit': unit, 'period': period,
              'excel': excel if ok else '', 'cell': f'Calc!C{row}',
              'inputs': inputs or {}, 'status': 'ok' if ok else 'skipped', 'reason': '' if ok else reason}
        it.update(extra)
        self.items.append(it)
        return it


def _period(year):
    """올해 값은 반기·분기 누적이라 FY 와 구분한다 (check 의 연도 판정은 startswith 로 본다)."""
    return f'FY{year} YTD' if str(year) == str(_dt.date.today().year) else f'FY{year}'


def _latest_fy(fs):
    ya = str((fs.get('forward') or {}).get('year_actual') or '')[:4]
    years = sorted(k for k in (fs.get('financials') or {}) if k.isdigit())
    return ya if ya in years else (years[-1] if years else None)


def _num(x):
    if x is None or x == '' or x == '-':
        return None
    try:
        return float(str(x).replace(',', ''))
    except ValueError:
        return None


def _fs(S, year, field):
    """(value 억원 또는 원/주, source). SOURCES 순서대로. 없으면 (None, '')."""
    for spec in SOURCES.get(field, []):
        if spec[0] == 'fs':
            row = ((S.get('fs') or {}).get('financials') or {}).get(year) or {}
            for cand in spec[1]:
                if row.get(cand) is not None:
                    return row[cand], f'financial_summary.json:financials.{year}.{cand}'
        elif spec[0] == 'fnguide':
            node = S.get('fnguide') or {}
            for k in spec[1]:
                node = node.get(k) if isinstance(node, dict) else None
            if isinstance(node, dict):
                for pk, pv in node.items():
                    if str(pk).startswith(f'{year}/') and _num(pv) is not None:
                        return _num(pv), f"_fnguide.json:{'.'.join(spec[1])}.{pk}"
        else:
            _, sj, ids = spec
            rows = ((S.get('dart') or {}).get(year) or {}).get('list') or []
            for aid in ids:
                for r in rows:
                    if (r.get('sj_div') in sj and r.get('account_id') == aid
                            and r.get('account_detail', '-') == '-' and _num(r.get('thstrm_amount')) is not None):
                        return (_num(r['thstrm_amount']) / 1e8,
                                f"data_dart_financials.json:{year}.list[{r['sj_div']}:{aid}].thstrm_amount/1e8")
    return None, ''


def _miss_reason(miss):
    return f'입력 없음: {", ".join(miss)} (확인한 파일: {", ".join(CHECKED_FILES)})'


def _gather(book, pairs):
    """pairs: [(label, value, source)] -> (refs dict, inputs dict, missing list)."""
    refs, inputs, missing = {}, {}, []
    for label, value, source in pairs:
        if value is None:
            missing.append(label)
            continue
        refs[label] = book.inp(label, value, source)
        inputs[label] = {'value': value, 'source': source, 'cell': refs[label]}
    return refs, inputs, missing


def _fs_pairs(S, year, fields):
    out = []
    for f in fields:
        v, src = _fs(S, year, f)
        has_dart = any(spec[0] == 'dart' for spec in SOURCES.get(f, []))
        if v is not None and has_dart and not src.startswith('data_dart_financials.json'):
            why = 'DART 파일 없음' if not S.get('dart') else 'DART 계정 없음'
            S['fallbacks'].setdefault((f, year), f'{f}({year}): {why} -> {src} 사용')
        out.append((f'{f}_{year}', v, src))
    return out


def source_basis(S, source):
    """입력 출처의 연결/별도 기준: 'consolidated' | 'separate' | 'unknown'."""
    file = source.split(':')[0]
    if ':kis.' in source:
        return None  # 시가총액 (시장 데이터)
    if file == 'data_dart_financials.json':
        year = source.split(':')[1].split('.')[0]
        rows = ((S.get('dart') or {}).get(year) or {}).get('list') or []
        divs = {r.get('fs_div') for r in rows if r.get('fs_div')}
        if divs == {'CFS'}:
            return 'consolidated'
        if divs == {'OFS'}:
            return 'separate'
        # fs_div 가 없으면 지배/비지배 분리 계정으로 판단 (별도재무제표에는 없다). 없다고 별도로 단정하지 않는다
        if any(any(m in (r.get('account_id') or '') for m in CONSOLIDATED_MARKERS) for r in rows):
            return 'consolidated'
        return 'unknown'
    if file == '_fnguide.json':
        fn = S.get('fnguide') or {}
        explicit = ((fn.get('financial') or {}).get('_meta') or {}).get('basis')
        if explicit in ('consolidated', 'separate'):
            return explicit
        annual = (fn.get('financial') or {}).get('annual') or {}
        actual = ((fn.get('consensus_estimates') or {}).get('_meta') or {}).get('actual') or {}
        return 'consolidated' if ('net_income_controlling' in annual or 'controlling_equity' in actual) else 'unknown'
    if file == 'financial_summary.json':
        fs = S.get('fs') or {}
        text = ' '.join(str(v) for v in [(fs.get('meta') or {}).get('basis'), fs.get('_description'),
                                          *(fs.get('_sources') or {}).values()] if v)
        if '연결' in text and '별도' not in text:
            return 'consolidated'
        if '별도' in text and '연결' not in text:
            return 'separate'
        return 'unknown'
    return None  # 재무제표 값이 아님 (시가총액·가정·market_data·ledger 참조)


def _ratio(book, S, key, year, num, den, unit='ratio', definition=''):
    refs, inputs, miss = _gather(book, _fs_pairs(S, year, [num, den]))
    period = _period(year)
    if miss:
        return book.add(key, unit, period, inputs=inputs, reason=_miss_reason(miss), definition=definition)
    n, d = inputs[f'{num}_{year}']['value'], inputs[f'{den}_{year}']['value']
    if d == 0:
        return book.add(key, unit, period, inputs=inputs, reason='분모 0', definition=definition)
    return book.add(key, unit, period, n / d, f'={refs[num + "_" + year]}/{refs[den + "_" + year]}', inputs,
                    definition=definition)


def _avg_ratio(book, S, key, year, num, den, definition, fallback_definition, note=None):
    """num_y / ((den_{y-1} + den_y) / 2). 기초 잔액이 없으면 기말 기준으로 내리고 note 에 적는다."""
    py = str(int(year) - 1)
    period = _period(year)
    extra = {'definition': definition}
    notes = [note] if note else []
    if notes:
        extra['note'] = notes[0]
    refs, inputs, miss = _gather(book, _fs_pairs(S, year, [num, den]))
    if miss:
        return book.add(key, 'ratio', period, inputs=inputs, reason=_miss_reason(miss), **extra)
    b_refs, b_inputs, b_miss = _gather(book, _fs_pairs(S, py, [den]))
    n, d1 = inputs[f'{num}_{year}']['value'], inputs[f'{den}_{year}']['value']
    rn, rd1 = refs[f'{num}_{year}'], refs[f'{den}_{year}']
    if b_miss:
        d, excel = d1, f'={rn}/{rd1}'
        extra['definition'] = fallback_definition
        notes.append(f'기초({py}) 잔액 없음 -> 기말 기준으로 계산 (공표치와 다를 수 있음)')
    else:
        inputs.update(b_inputs)
        d = (d1 + b_inputs[f'{den}_{py}']['value']) / 2
        excel = f'={rn}/(({b_refs[den + "_" + py]}+{rd1})/2)'
    if notes:
        extra['note'] = '; '.join(notes)
    if d == 0:
        return book.add(key, 'ratio', period, inputs=inputs, reason='분모 0', **extra)
    return book.add(key, 'ratio', period, n / d, excel, inputs, **extra)


def build_ledger(fs, market=None, assumptions=None, fnguide=None, dart=None):
    """fnguide / dart: _fnguide.json / data_dart_financials.json 원본 dict (financial_summary 에 없는 값의 fallback)."""
    S = {'fs': fs, 'fnguide': fnguide, 'dart': dart, 'fallbacks': {}, 'warnings': []}
    book = _Book()
    fy = _latest_fy(fs)
    py = str(int(fy) - 1) if fy else None

    # ---- 비율 (재무요약에 있는 모든 연도 -- 본문 표가 4~5개년을 싣는다) ----
    for y in sorted((k for k in (fs.get('financials') or {}) if k.isdigit()), reverse=True):
        if _fs(S, y, 'net_income_ctrl')[0] is not None and _fs(S, y, 'controlling_equity')[0] is not None:
            _avg_ratio(book, S, 'roe', y, 'net_income_ctrl', 'controlling_equity',
                       'ROE = 지배주주 순이익 / 평균 지배주주지분((기초+기말)/2)',
                       'ROE = 지배주주 순이익 / 기말 지배주주지분')
        else:
            _avg_ratio(book, S, 'roe', y, 'net_income', 'total_equity',
                       'ROE = 연결 순이익 / 평균 자본총계((기초+기말)/2)',
                       'ROE = 연결 순이익 / 기말 자본총계',
                       note='지배주주 순이익/지분 분리 없음 -> 연결 기준 (공표 ROE 와 다를 수 있음)')
        _avg_ratio(book, S, 'roa', y, 'net_income', 'total_assets',
                   'ROA = 연결 순이익 / 평균 자산총계((기초+기말)/2)', 'ROA = 연결 순이익 / 기말 자산총계')
        _ratio(book, S, 'opm', y, 'op_income', 'revenue', definition='영업이익률 = 영업이익 / 매출액')
        _ratio(book, S, 'npm', y, 'net_income', 'revenue', definition='순이익률 = 연결 순이익 / 매출액')
        _ratio(book, S, 'debt_ratio', y, 'total_liabilities', 'total_equity',
               definition='부채비율 = 기말 부채총계 / 기말 자본총계')
        _ratio(book, S, 'current_ratio', y, 'current_assets', 'current_liabilities',
               definition='유동비율 = 기말 유동자산 / 기말 유동부채')
        it = _ratio(book, S, 'interest_coverage', y, 'op_income', 'interest_expense', unit='x',
                    definition='이자보상배율 = 영업이익 / 이자비용')
        src = (it['inputs'].get(f'interest_expense_{y}') or {}).get('source', '')
        if 'FinanceCosts' in src or 'finance_cost' in src:
            it['definition'] = '이자보상배율 = 영업이익 / 금융원가(이자비용 대용)'
            it['note'] = ('이자비용 계정 없음 -> 금융원가로 대용. 금융원가에는 이자 외 외환·평가손실이 '
                          '섞일 수 있어 배율이 실제보다 낮게 나올 수 있다')

    # ---- 성장 / 레버리지 (fy vs py) ----
    period = f'FY{fy} vs FY{py}'
    fields = {'sales': 'revenue', 'op': 'op_income', 'eps': 'eps'}
    for k, f in fields.items():
        refs, inputs, miss = _gather(book, _fs_pairs(S, py, [f]) + _fs_pairs(S, fy, [f]))
        if miss:
            book.add(f'{k}_growth', 'ratio', period, inputs=inputs, reason=_miss_reason(miss))
            continue
        p, c = inputs[f'{f}_{py}']['value'], inputs[f'{f}_{fy}']['value']
        if p <= 0:
            book.add(f'{k}_growth', 'ratio', period, inputs=inputs, reason='전년 값 0 이하라 성장률 해석 불가')
        else:
            book.add(f'{k}_growth', 'ratio', period, c / p - 1, f'={refs[f + "_" + fy]}/{refs[f + "_" + py]}-1', inputs)

    def lev(key, num, den):
        refs, inputs, miss = _gather(book, _fs_pairs(S, py, [num, den]) + _fs_pairs(S, fy, [num, den]))
        if miss:
            return book.add(key, 'x', period, inputs=inputs, reason=_miss_reason(miss))
        g = lambda f, y: inputs[f'{f}_{y}']['value']  # noqa: E731
        v, why = leverage_ratio(g(num, py), g(num, fy), g(den, py), g(den, fy))
        r = lambda f, y: refs[f'{f}_{y}']  # noqa: E731
        excel = f'=({r(num, fy)}/{r(num, py)}-1)/({r(den, fy)}/{r(den, py)}-1)'
        return book.add(key, 'x', period, v, excel, inputs, reason=why)

    dol = lev('dol', 'op_income', 'revenue')
    dfl = lev('dfl', 'eps', 'op_income')
    if dol['status'] == 'ok' and dfl['status'] == 'ok':
        book.add('dcl', 'x', period, dol['value'] * dfl['value'], f'={dol["cell"]}*{dfl["cell"]}',
                 {'dol': {'value': dol['value'], 'source': 'ledger:dol', 'cell': dol['cell']},
                  'dfl': {'value': dfl['value'], 'source': 'ledger:dfl', 'cell': dfl['cell']}})
    else:
        book.add('dcl', 'x', period, reason='dol/dfl 미산출: ' + (dol['reason'] or dfl['reason']))

    # ---- Altman Z (fy) ----
    zf = ['current_assets', 'current_liabilities', 'total_assets', 'retained_earnings',
          'ebit', 'total_liabilities', 'revenue']
    pairs = _fs_pairs(S, fy, zf) + [('market_cap', (fs.get('kis') or {}).get(MARKET_CAP_KEY),
                                      f'financial_summary.json:kis.{MARKET_CAP_KEY}')]
    refs, inputs, miss = _gather(book, pairs)
    zp = f'FY{fy}'
    if miss:
        book.add('altman_z', 'x', zp, inputs=inputs, reason=_miss_reason(miss))
    else:
        v = {k.rsplit('_' + fy, 1)[0] if k.endswith(fy) else k: d['value'] for k, d in inputs.items()}
        R = {k.rsplit('_' + fy, 1)[0] if k.endswith(fy) else k: c for k, c in refs.items()}
        if v['total_assets'] <= 0 or v['total_liabilities'] <= 0:
            book.add('altman_z', 'x', zp, inputs=inputs, reason='자산 또는 부채총계 0 이하')
        else:
            z = (1.2 * (v['current_assets'] - v['current_liabilities']) / v['total_assets']
                 + 1.4 * v['retained_earnings'] / v['total_assets']
                 + 3.3 * v['ebit'] / v['total_assets']
                 + 0.6 * v['market_cap'] / v['total_liabilities']
                 + 1.0 * v['revenue'] / v['total_assets'])
            excel = (f"=1.2*({R['current_assets']}-{R['current_liabilities']})/{R['total_assets']}"
                     f"+1.4*{R['retained_earnings']}/{R['total_assets']}"
                     f"+3.3*{R['ebit']}/{R['total_assets']}"
                     f"+0.6*{R['market_cap']}/{R['total_liabilities']}"
                     f"+1.0*{R['revenue']}/{R['total_assets']}")
            nd = _fs(S, fy, 'net_debt')[0]
            extra = {'zone': altman_zone(z)}
            notes = [ALTMAN_NOTE]
            if nd is not None and nd < 0:
                notes.insert(0, NET_CASH_NOTE)
            extra['note'] = '; '.join(notes)
            book.add('altman_z', 'x', zp, z, excel, inputs, **extra)

    # ---- VaR (market_data 그대로) ----
    var = (market or {}).get('var') or {}
    for k in ('var95_1d', 'var95_20d'):
        refs, inputs, miss = _gather(book, [(k, var.get(k), f'ta/market_data.json:var.{k}')])
        if miss:
            book.add(k, 'ratio', 'market_data asof', inputs=inputs, reason='market_data.json 없음 또는 값 없음')
        else:
            book.add(k, 'ratio', f"asof {(market or {}).get('asof', '')}", var[k], f'={refs[k]}', inputs,
                     n=var.get('n'))

    # ---- 가정 필요 항목 ----
    A = assumptions or {}
    src = lambda k: f'ta/assumptions.json:{k}' + (f" ({A['sources'][k]})" if k in (A.get('sources') or {}) else '')  # noqa: E731
    pos = lambda x: x if isinstance(x, (int, float)) and x > 0 else None  # noqa: E731
    need = 'assumptions.json 없음 또는 값 없음'

    # RIM
    roe_f = A.get('roe_forecast') or []
    years = int(A.get('rim_years') or 0)
    payout = A.get('payout', 0) or 0
    payout_src = src('payout') if A.get('payout') is not None else '기본값 0 (assumptions 에 없음)'
    pairs = [('ke', A.get('ke'), src('ke')), ('g_terminal', A.get('g_terminal'), src('g_terminal')),
             ('bps0', pos(A.get('bps0')), src('bps0')), ('payout', payout, payout_src)]
    pairs += [(f'roe_forecast_{t + 1}', r, src('roe_forecast')) for t, r in enumerate(_roe_path(roe_f, years))] if roe_f else []
    if roe_f and years > 0:
        refs, inputs, miss = _gather(book, pairs)
    else:
        refs, inputs, miss = {}, {}, ['roe_forecast/rim_years']
    rp = f'{years}년 + 잔여가치'
    if miss:
        book.add('rim_value_per_share', 'KRW', rp, inputs=inputs, reason=f'{need}: {", ".join(miss)}')
    elif A['ke'] <= A['g_terminal']:
        book.add('rim_value_per_share', 'KRW', rp, inputs=inputs, reason='ke <= g_terminal 이라 발산')
    else:
        ke, g, b0, pay = refs['ke'], refs['g_terminal'], refs['bps0'], refs['payout']
        bps_e, terms, ri_e = b0, [], ''
        for t in range(1, years + 1):
            roe = refs[f'roe_forecast_{t}']
            ri_e = f'({roe}-{ke})*{bps_e}'
            terms.append(f'{ri_e}/(1+{ke})^{t}')
            bps_e = f'{bps_e}*(1+{roe}*(1-{pay}))'
        excel = f'={b0}+' + '+'.join(terms) + f'+{ri_e}*(1+{g})/({ke}-{g})/(1+{ke})^{years}'
        book.add('rim_value_per_share', 'KRW', rp,
                 rim_value(A['bps0'], roe_f, A['ke'], A['g_terminal'], years, payout), excel, inputs,
                 definition=RIM_DEFINITION)

    # 컨센서스 ROE (가정 입력 그대로) -- 본문이 '컨센서스 ROE' 를 인용하면 check 가 장부에서 찾게 한다
    if roe_f:
        refs1, inputs1, miss1 = _gather(book, [('roe_forecast_1', roe_f[0], src('roe_forecast'))])
        book.add('roe', 'ratio', 'forecast yr1 (assumptions)', roe_f[0], f"={refs1['roe_forecast_1']}", inputs1,
                 note='assumptions.roe_forecast[0] 그대로 -- 계산값 아님')

    # justified PBR
    refs, inputs, miss = _gather(book, [('roe_forecast_1', roe_f[0] if roe_f else None, src('roe_forecast')),
                                        ('ke', A.get('ke'), src('ke')),
                                        ('g_terminal', A.get('g_terminal'), src('g_terminal'))])
    if miss:
        book.add('justified_pbr', 'x', 'forecast yr1', inputs=inputs, reason=f'{need}: {", ".join(miss)}')
    elif roe_f[0] <= 0 or A['ke'] <= A['g_terminal']:
        book.add('justified_pbr', 'x', 'forecast yr1', inputs=inputs, reason='ROE<=0 또는 ke<=g (ggm_check 와 같은 가드)')
    else:
        book.add('justified_pbr', 'x', 'forecast yr1', (roe_f[0] - A['g_terminal']) / (A['ke'] - A['g_terminal']),
                 f"=({refs['roe_forecast_1']}-{refs['g_terminal']})/({refs['ke']}-{refs['g_terminal']})", inputs)

    # price: assumptions 우선, 없으면 market_data 종가
    price = pos(A.get('price'))
    price_src = src('price')
    if price is None:
        price = pos(((market or {}).get('latest') or {}).get('close'))
        price_src = 'ta/market_data.json:latest.close'

    # 현재가가 내재한 ROE: 적정 PBR 식을 거꾸로 푼다 -- ROE = g + (P/BPS0)*(ke-g). FCF 가 음수라 역DCF 를 못 쓸 때 대안
    refs, inputs, miss = _gather(book, [('price', price, price_src), ('bps0', pos(A.get('bps0')), src('bps0')),
                                        ('ke', A.get('ke'), src('ke')), ('g_terminal', A.get('g_terminal'), src('g_terminal'))])
    if miss:
        book.add('price_implied_roe', 'ratio', 'price vs bps0', inputs=inputs, reason=f'{need}: {", ".join(miss)}')
    elif A['ke'] <= A['g_terminal']:
        book.add('price_implied_roe', 'ratio', 'price vs bps0', inputs=inputs, reason='ke <= g_terminal')
    else:
        book.add('price_implied_roe', 'ratio', 'price vs bps0',
                 A['g_terminal'] + price / A['bps0'] * (A['ke'] - A['g_terminal']),
                 f"={refs['g_terminal']}+{refs['price']}/{refs['bps0']}*({refs['ke']}-{refs['g_terminal']})", inputs)

    # reverse DCF
    n = int(A.get('fcf_growth_years') or 0)
    pairs = [('fcf0', A.get('fcf0'), src('fcf0')), ('wacc', A.get('wacc'), src('wacc')),
             ('g_terminal', A.get('g_terminal'), src('g_terminal')), ('net_cash', A.get('net_cash'), src('net_cash')),
             ('shares', pos(A.get('shares')), src('shares')), ('price', price, price_src)]
    refs, inputs, miss = _gather(book, pairs)
    rkey, rp = 'reverse_dcf_implied_growth', f'{n}년 성장 후 영구성장'
    # net_cash 부호 규약 점검: net_cash(순현금 +) 는 financial_summary net_debt(순부채 +) 와 부호가 반대여야 한다
    nd, nd_src = _fs(S, fy, 'net_debt') if fy else (None, '')
    nc = A.get('net_cash')
    if isinstance(nc, (int, float)) and nd:
        if nc == 0:
            S['warnings'].append(f'net_cash: assumptions 값이 0(템플릿 기본값) 인데 {nd_src} = {nd}억 '
                                 '-- 순현금/순부채를 반영하지 않은 EV 일 수 있음')
        elif nc * nd > 0:
            S['warnings'].append(f'net_cash: 부호 불일치 -- assumptions net_cash {nc}억(순현금 +) 와 {nd_src} {nd}억'
                                 '(순부채 +) 가 같은 부호. net_cash 는 -net_debt 여야 함')
        elif abs(abs(nc) - abs(nd)) > NET_CASH_MAG_TOL * abs(nd):
            S['warnings'].append(f'net_cash: 크기 차이 {NET_CASH_MAG_TOL:.0%} 초과 -- assumptions {nc}억 vs '
                                 f'{nd_src} {nd}억 (FY 기말과 최근 분기 등 시점 차이인지 확인)')
    if miss or n <= 0:
        book.add(rkey, 'ratio', rp, inputs=inputs, reason=f'{need}: {", ".join(miss or ["fcf_growth_years"])}')
    elif A['fcf0'] <= 0:
        book.add(rkey, 'ratio', rp, inputs=inputs, reason='FCF0 <= 0 이라 역산 불가')
    elif A['wacc'] <= A['g_terminal']:
        book.add(rkey, 'ratio', rp, inputs=inputs, reason='wacc <= g_terminal 이라 발산')
    else:
        target = price * A['shares'] / 1e8 - A['net_cash']
        if target <= 0:
            book.add(rkey, 'ratio', rp, inputs=inputs, reason=f'EV(시총-순현금) {target:.1f}억 <= 0 이라 역산 불가')
        else:
            g1, why = solve_implied_growth(target, A['fcf0'], A['wacc'], A['g_terminal'], n)
            tol_txt = f'|잔차| < {EV_RESIDUAL_TOL:g}억원(100원)'
            gref = book.inp('reverse_dcf_g_solved', g1,
                            f'Python 이분법 해 (엑셀 검산: Calc 의 reverse_dcf_ev_residual {tol_txt})') if g1 is not None else ''
            it = book.add(rkey, 'ratio', rp, g1, f'={gref}', inputs, reason=why, target_ev_억=target,
                          note='엑셀은 이분법을 못 하므로 Python 이분법(범위 -50%~+100%, g 허용오차 1e-6, '
                               f'EV 허용오차 {EV_RESIDUAL_TOL:g}억원) 해를 Inputs 에 넣었다. '
                               f'검산: Calc 의 reverse_dcf_ev_residual 값(C열)이 {tol_txt} 이면 통과')
            if it['status'] == 'ok':
                w, gt = refs['wacc'], refs['g_terminal']
                pv = '+'.join(f"{refs['fcf0']}*(1+{gref})^{t}/(1+{w})^{t}" for t in range(1, n + 1))
                resid = (f"={pv}+{refs['fcf0']}*(1+{gref})^{n}*(1+{gt})/({w}-{gt})/(1+{w})^{n}"
                         f"-({refs['price']}*{refs['shares']}/100000000-{refs['net_cash']})")
                book.add('reverse_dcf_ev_residual', '억원', rp,
                         dcf_ev(A['fcf0'], g1, A['wacc'], A['g_terminal'], n) - target, resid, inputs,
                         tolerance_억=EV_RESIDUAL_TOL, note=f'검산 행: {tol_txt} 이면 통과')

    # upside
    refs, inputs, miss = _gather(book, [('target_price', pos(A.get('target_price')), src('target_price')),
                                        ('price', price, price_src)])
    if miss:
        book.add('upside_if_view', 'ratio', 'target vs price', inputs=inputs, reason=f'{need}: {", ".join(miss)}')
    else:
        book.add('upside_if_view', 'ratio', 'target vs price', A['target_price'] / price - 1,
                 f"={refs['target_price']}/{refs['price']}-1", inputs)

    # SOTP (assumptions.sotp): 본업 EV/EBITDA + 상장 관계사 지분 시장가 + 비상장 지분 장부가 + 확률가중 옵션 - 순차입금
    so = A.get('sotp') or {}
    for name, sc in (so.get('scenarios') or {}).items():
        key = f'sotp_value_per_share_{name}'
        if sc.get('ebitda_annual') is not None:
            eb_v, eb_s = sc['ebitda_annual'], src('sotp') + f' scenarios.{name}.ebitda_annual'
        else:
            eb_v = so['ebitda_half'] * 2 if isinstance(so.get('ebitda_half'), (int, float)) else None
            eb_s = src('sotp') + ' ebitda_half x2 (반기 연환산)'
        pairs = [(f'sotp_ebitda_annual_{name}', eb_v, eb_s),
                 (f'sotp_multiple_{name}', sc.get('multiple'), src('sotp') + f' scenarios.{name}.multiple'),
                 ('sotp_listed_stake', so.get('listed_stake'), src('sotp') + ' listed_stake'),
                 ('sotp_listed_mcap', so.get('listed_mcap'), src('sotp') + ' listed_mcap'),
                 (f'sotp_unlisted_{name}', so.get('unlisted_book') if sc.get('unlisted', True) else 0,
                  src('sotp') + (' unlisted_book' if sc.get('unlisted', True) else f' scenarios.{name}.unlisted=false -> 0')),
                 ('sotp_option_ev', so.get('option_ev_success'), src('sotp') + ' option_ev_success'),
                 (f'sotp_option_prob_{name}', sc.get('option_prob'), src('sotp') + f' scenarios.{name}.option_prob'),
                 ('sotp_option_discount', so.get('option_discount'), src('sotp') + ' option_discount'),
                 ('sotp_net_debt', so.get('net_debt'), src('sotp') + ' net_debt'),
                 (f'sotp_adjust_{name}', sc.get('adjust', 0), src('sotp') + f' scenarios.{name}.adjust (상관 조정: 우발·지분 시가 등, 억원, 기본 0)'),
                 ('shares', pos(A.get('shares')), src('shares'))]
        refs, inputs, miss = _gather(book, pairs)
        if miss:
            book.add(key, 'KRW', f'SOTP {name}', inputs=inputs, reason=f'{need}: {", ".join(miss)}')
            continue
        g_ = lambda k: inputs[k]['value']  # noqa: E731
        equity = (g_(f'sotp_ebitda_annual_{name}') * g_(f'sotp_multiple_{name}')
                  + g_('sotp_listed_stake') * g_('sotp_listed_mcap') + g_(f'sotp_unlisted_{name}')
                  + g_('sotp_option_ev') * g_(f'sotp_option_prob_{name}') * g_('sotp_option_discount')
                  - g_('sotp_net_debt') + g_(f'sotp_adjust_{name}'))
        r = refs
        excel = (f"=({r[f'sotp_ebitda_annual_{name}']}*{r[f'sotp_multiple_{name}']}+{r['sotp_listed_stake']}*{r['sotp_listed_mcap']}"
                 f"+{r[f'sotp_unlisted_{name}']}+{r['sotp_option_ev']}*{r[f'sotp_option_prob_{name}']}*{r['sotp_option_discount']}"
                 f"-{r['sotp_net_debt']}+{r[f'sotp_adjust_{name}']})*100000000/{r['shares']}")
        book.add(key, 'KRW', f'SOTP {name}', equity * 1e8 / A['shares'], excel, inputs, equity_억=equity,
                 definition='(반기 EBITDA x2 x 배수 + 상장지분율 x 시총 + 비상장 장부가 + 옵션EV x 확률 x 할인 - 순차입금 + 시나리오 조정) / 주식수. 억원 입력')
        if price and name == 'base':
            # 시장 내재 CNT 확률: 시총에서 옵션 뺀 조각들을 빼고 남은 값을 성공 시 옵션가치(EV x 할인)로 나눈다
            mcap = price * A['shares'] / 1e8
            ex_opt = equity - g_('sotp_option_ev') * g_(f'sotp_option_prob_{name}') * g_('sotp_option_discount')
            pr0 = book.inp('price', price, price_src)
            book.add('sotp_implied_option_prob', 'ratio', 'SOTP base vs price',
                     (mcap - ex_opt) / (g_('sotp_option_ev') * g_('sotp_option_discount')),
                     f"=({pr0}*{r['shares']}/100000000-({r[f'sotp_ebitda_annual_{name}']}*{r[f'sotp_multiple_{name}']}+{r['sotp_listed_stake']}*{r['sotp_listed_mcap']}+{r[f'sotp_unlisted_{name}']}-{r['sotp_net_debt']}))/({r['sotp_option_ev']}*{r['sotp_option_discount']})",
                     inputs, note='현재 시가총액이 Base 배수·지분 가정 아래 CNT 옵션에 매긴 성공 확률')
        if price:
            pr = book.inp('price', price, price_src)
            book.add(f'sotp_upside_{name}', 'ratio', f'SOTP {name} vs price', equity * 1e8 / A['shares'] / price - 1,
                     f'={excel[1:]}/{pr}-1', inputs)

    # SOTP 확률가중 기대가치 (assumptions.sotp.weights)
    wts = so.get('weights') or {}
    vals = {it['key'][len('sotp_value_per_share_'):]: it for it in book.items if it['key'].startswith('sotp_value_per_share_')}
    if wts and all(k in vals and vals[k]['status'] == 'ok' for k in wts):
        winp = {}
        terms = []
        for k, w in wts.items():
            ref = book.inp(f'sotp_weight_{k}', w, src('sotp') + f' weights.{k}')
            winp[f'sotp_weight_{k}'] = {'value': w, 'source': src('sotp') + f' weights.{k}', 'cell': ref}
            terms.append(f"{ref}*{vals[k]['cell']}")
        ev = sum(w * vals[k]['value'] for k, w in wts.items())
        book.add('sotp_expected_value', 'KRW', 'SOTP weighted', ev, '=' + '+'.join(terms), winp,
                 note='시나리오 확률은 판단값(assumptions.sotp.weights)')
        if price:
            book.add('sotp_expected_upside', 'ratio', 'SOTP weighted vs price', ev / price - 1, '', winp)

    # PER 시나리오 (assumptions.per_scenarios): EPS x 배수 -- IR협의회식 밴드+Peer 위치 판단과 판단 블록의 시나리오
    ps = A.get('per_scenarios') or {}
    for name, sc in ps.items():
        eref = book.inp(f'per_eps_{name}', sc.get('eps'), src('per_scenarios') + f' {name}.eps')
        mref = book.inp(f'per_multiple_{name}', sc.get('per'), src('per_scenarios') + f' {name}.per')
        inputs = {f'per_eps_{name}': {'value': sc.get('eps'), 'source': src('per_scenarios'), 'cell': eref},
                  f'per_multiple_{name}': {'value': sc.get('per'), 'source': src('per_scenarios'), 'cell': mref}}
        if sc.get('eps') is None or sc.get('per') is None:
            book.add(f'per_value_{name}', 'KRW', f'PER {name}', inputs=inputs, reason='eps 또는 per 없음')
            continue
        v = sc['eps'] * sc['per']
        book.add(f'per_value_{name}', 'KRW', f'PER {name}', v, f'={eref}*{mref}', inputs, note=sc.get('note', ''))
        if price:
            pr = book.inp('price', price, price_src)
            book.add(f'per_upside_{name}', 'ratio', f'PER {name} vs price', v / price - 1, f'={eref}*{mref}/{pr}-1', inputs)
    wts = A.get('weights') or {}
    pv = {it['key'][len('per_value_'):]: it for it in book.items if it['key'].startswith('per_value_')}
    if wts and all(k in pv and pv[k]['status'] == 'ok' for k in wts):
        winp, terms = {}, []
        for k, w in wts.items():
            ref = book.inp(f'per_weight_{k}', w, src('weights') + f' {k}')
            winp[f'per_weight_{k}'] = {'value': w, 'source': src('weights'), 'cell': ref}
            terms.append(f"{ref}*{pv[k]['cell']}")
        ev = sum(w * pv[k]['value'] for k, w in wts.items())
        book.add('per_expected_value', 'KRW', 'PER weighted', ev, '=' + '+'.join(terms), winp, note='시나리오 확률은 판단값(assumptions.weights)')
        if price:
            book.add('per_expected_upside', 'ratio', 'PER weighted vs price', ev / price - 1, '', winp)

    # 입력 단위를 항목마다 명시한다 (비율 자체는 무단위, 입력이 무엇이었는지 기록)
    input_units = {
        'dfl': 'EPS 원/주, 영업이익 ' + STATEMENT_UNIT, 'dcl': 'dol x dfl',
        'eps_growth': '원/주 (financial_summary.json)',
        'altman_z': STATEMENT_UNIT + '; 시가총액 억원(KIS)',
        'var95_1d': '수익률 소수', 'var95_20d': '수익률 소수',
        'rim_value_per_share': '원/주 (bps0), 비율 소수', 'justified_pbr': '비율 소수', 'price_implied_roe': '원/주 (price, bps0), 비율 소수',
        'reverse_dcf_implied_growth': 'fcf0/net_cash 억원, price 원, shares 주',
        'reverse_dcf_ev_residual': 'fcf0/net_cash 억원, price 원, shares 주', 'upside_if_view': '원',
    }
    warnings = list(S['fallbacks'].values()) + S['warnings']
    for it in book.items:
        it['input_unit'] = input_units.get(it['key'], STATEMENT_UNIT)
        # 연결/별도 기준: 재무제표 입력(시총·가정·market_data 제외)의 출처별 기준을 모은다
        per_file = {}
        for d in it['inputs'].values():
            b = source_basis(S, d['source'])
            if b is not None:
                d['basis'] = b
                per_file.setdefault(d['source'].split(':')[0], set()).add(b)
        if not per_file:
            continue
        bases = set().union(*per_file.values())
        it['basis'] = next(iter(bases)) if len(bases) == 1 else 'unknown'
        # 판단: 출처가 한 파일뿐이면 '혼재'가 아니다(기준 unknown 이어도 경고하지 않음). 두 파일 이상에서
        # 기준이 다르거나 하나라도 unknown 이면 경고. 계산된(ok) 항목만 경고한다.
        if it['status'] == 'ok' and len(per_file) > 1 and (len(bases) > 1 or 'unknown' in bases):
            it.setdefault('warnings', []).append(MIXED_BASIS_WARNING)
            warnings.append(f"{it['key']}({it['period']}): {MIXED_BASIS_WARNING} -- "
                            + ', '.join(f'{f}={"/".join(sorted(b))}' for f, b in sorted(per_file.items())))

    return {'stock': (fs.get('meta') or {}).get('stock_name', ''), 'fy': fy, 'prev_fy': py,
            'method': 'ROE/ROA 는 평균 잔액, 나머지 비율은 기말 잔액. 재무값은 억원(DART 원/1e8 우선, EPS/BPS 원). 항목별 definition/note/input_unit/basis 참조',
            'warnings': warnings,
            'xlsx_note': '엑셀에서 열면 Calc 의 차이 열(E)이 0 이어야 한다 (openpyxl 은 수식을 계산하지 않음)',
            'inputs': book.inputs, 'items': book.items}


# ==================== xlsx ====================

def write_xlsx(ledger, path):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Inputs'
    ws.append(['label', '', 'value', 'source'])
    for i in ledger['inputs']:
        ws.append([i['label'], '', i['value'], i['source']])
    c = wb.create_sheet('Calc')
    c.append(['key', 'period', 'excel', 'python', 'diff', 'status/reason'])
    for r, it in enumerate(ledger['items'], start=2):
        ok = it['status'] == 'ok'
        c.append([it['key'], it['period'], it['excel'] if ok else None, it['value'],
                  f'=C{r}-D{r}' if ok else None, 'ok' if ok else f"skipped: {it['reason']}"])
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    tmp = path + '.tmp'
    wb.save(tmp)
    os.replace(tmp, path)


# ==================== check ====================

# 이름 속 공백은 '없음/여러 칸' 모두 허용한다 ('적정 PBR' == '적정PBR'). 결과 name 은 사전 표기(정규형)로 돌려준다.
CHECK_NAMES = {
    'ROE': ['roe'], 'ROA': ['roa'], '영업 이익률': ['opm'],
    'DOL': ['dol'], '영업 레버리지': ['dol'], 'DFL': ['dfl'], '재무 레버리지': ['dfl'],
    'Altman Z': ['altman_z'], 'Z-score': ['altman_z'], 'Z 스코어': ['altman_z'], 'VaR': ['var95_1d', 'var95_20d'],
    'RIM': ['rim_value_per_share'], '적정 PBR': ['justified_pbr'], '내재 ROE': ['price_implied_roe'],
    '내재 성장률': ['reverse_dcf_implied_growth'], '부채 비율': ['debt_ratio'],
    '유동 비율': ['current_ratio'], '이자 보상 배율': ['interest_coverage'],
}
_CANON = sorted(CHECK_NAMES, key=len, reverse=True)
_NAME_RE = re.compile(r'(?<![가-힣A-Za-z])(?:' + '|'.join(f'(?P<n{i}>' + r'\s*'.join(re.escape(w) for w in n.split(' ')) + ')'
                                                  for i, n in enumerate(_CANON)) + ')')
_NUM_RE = re.compile(r'(?<![\d.])([-\u2212]?)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s*(%?)')
_PERIOD_AFTER = re.compile(r'\s*(개년|년|분기|개월|영업일|거래일|일|억|조|만|명|건|곳|개|kg|톤|회|호|주|월)')   # "5개년", "20일", "600억" 은 지표값이 아니다
_THRESHOLD_AFTER = re.compile(r'\s*(이하|미만|이상|초과|돌파|대(?!비)|포인트|p\b|를 넘|을 넘|넘|밑돌)')  # "500% 이하", "5%대" 는 기준선이지 값이 아니다
_SENTENCE_END = re.compile(r'\.(?=\s|$)|\n\s*\n')   # 문장 끝 / 문단 끝
_CELL_TEXT = re.compile(r'[0-9A-Za-z가-힣%]')
_SCOPE = re.compile(r'상반기|하반기|반기|분기|[1-4]\s*분기|[1-4]Q|[12]H\s*\d\d|누적|연환산|부문|사업부|별도|재분류|IR|타사|경쟁사|vs\.?|대비|컨센|가정|시나리오|요구|영구|역산|잔여가치|수렴|베타|자기자본비용|ke|FnGuide|와이즈')
_YEAR = re.compile(r'(?<!\d)(20\d\d)(?!\d)')
SCOPE_BEFORE = 20
_VAR_HORIZON = re.compile(r'(?<![\d월])(?<!월 )(\d+)\s*(?:영업일|거래일|일)(?!간)')  # '9월 20일' 같은 날짜는 제외
VAR_BEFORE = 8
VAR_LEVELS = ('90', '95', '97.5', '99', '99.9')
WINDOW = 30


def _rounds_equal(ledger_val, text_str):
    d = Decimal(text_str)
    q = Decimal(1).scaleb(d.as_tuple().exponent) if d.as_tuple().exponent < 0 else Decimal(1)
    return Decimal(repr(ledger_val)).quantize(q, rounding=ROUND_HALF_UP) == d


def check_sections(sections, ledger):
    ok_items = [i for i in ledger.get('items', []) if i.get('status') == 'ok']
    results, seen = [], set()
    for sec, text in (sections or {}).items():
        if not isinstance(text, str):
            continue
        for m in _NAME_RE.finditer(text):
            name = _CANON[int(m.lastgroup[1:])]
            win_start = m.end()
            raw = text[win_start:win_start + WINDOW + 12]   # 30자 경계에서 숫자가 잘리지 않게 여유를 두고 읽는다
            cut = _SENTENCE_END.search(raw)
            window = raw[:cut.start()] if cut else raw      # 문장이 끝나면 다음 문장의 숫자는 이 지표의 값이 아니다
            bar = window.find('|')
            if bar >= 0 and _CELL_TEXT.search(window[:bar]):
                window = window[:bar]   # 표: 이름만 있는 셀은 다음 셀의 값을 보고, 다른 글이 섞인 셀은 넘어가지 않는다
            var_level = None
            found = None
            for nm in _NUM_RE.finditer(window):
                if nm.start() >= WINDOW:
                    break
                sign, whole, frac, pct = nm.groups()
                whole = whole.replace(',', '')
                if not frac and not pct and len(whole) == 4 and 1990 <= int(whole) <= 2100:
                    continue  # 연도
                if not pct and _PERIOD_AFTER.match(window, nm.end()):
                    continue  # 기간·단위 표기 (5개년, 3분기, 20일, 600억)
                if _THRESHOLD_AFTER.match(window, nm.end()):
                    continue  # 기준선 (500% 이하, 5%대, 1%포인트)
                if name == 'VaR' and pct and not sign and whole + (frac or '') in VAR_LEVELS and var_level is None:
                    var_level = whole + (frac or '')
                    continue  # 신뢰수준
                found = nm
                break
            if found is None:
                continue
            nm = found
            pos = win_start + nm.start()
            if (sec, pos) in seen:
                continue
            seen.add((sec, pos))
            text_str = ('-' if sign else '') + whole + (frac or '')
            keys = CHECK_NAMES[name]
            var_horizon = None
            if name == 'VaR':
                # 보유기간: 이름 앞 VAR_BEFORE 자 ~ 값 직전. 20(영업/거래)일 -> 20d, 1일/일간/표기 없음 -> 1d
                # pos/endpos 로 자르면 lookbehind 가 구간 밖 글자('9월')까지 본다
                hz = [h.group(1) for h in _VAR_HORIZON.finditer(text, max(0, m.start() - VAR_BEFORE), m.start())]
                hz += [h.group(1) for h in _VAR_HORIZON.finditer(text, win_start, win_start + nm.start())]
                var_horizon = int(hz[-1]) if hz else 1
                keys = {1: ['var95_1d'], 20: ['var95_20d']}.get(var_horizon, [])
            cands = [i for i in ok_items if i['key'] in keys]
            r = {'name': m.group(0), 'metric': name, 'keys': keys, 'section': sec, 'pos': pos, 'text_value': float(text_str),
                 'percent': bool(pct), 'context': text[max(0, m.start() - 10):win_start + WINDOW],
                 'ledger_values': [(i['key'], i['period'], i['value']) for i in cands]}
            if var_level:
                r['var_level'] = var_level
            if var_horizon is not None:
                r['var_horizon_days'] = var_horizon
            if name == 'VaR' and var_level not in (None, '95'):
                r['result'] = 'WARN'  # 다른 신뢰수준을 95% 값과 비교하면 거짓 PASS 가 난다
                r['reason'] = f'장부는 95% VaR 만 있음 (본문 {var_level}%)'
            elif name == 'VaR' and not keys:
                r['result'] = 'WARN'
                r['reason'] = f'장부에 해당 기간 VaR 없음 (본문 {var_horizon}일, 장부는 1일/20일)'
            elif not cands:
                r['result'] = 'WARN'
                r['reason'] = '장부에 없는 지표'
            else:
                hit = False
                for i in cands:
                    v = abs(i['value']) if name == 'VaR' else i['value']
                    ts = text_str.lstrip('-') if name == 'VaR' else text_str
                    scales = [100] if (pct and i['unit'] == 'ratio') else ([1, 100] if i['unit'] == 'ratio' else [1])
                    if any(_rounds_equal(v * s, ts) for s in scales):
                        hit = True
                r['result'] = 'PASS' if hit else 'FAIL'
                if not hit:  # 엄격 비교는 유지하되, 정의 차이가 원인인지 작성자가 보게 한다
                    r['definitions'] = sorted({i.get('definition', '') for i in cands if i.get('definition')})
                    around = text[max(0, m.start() - SCOPE_BEFORE):m.start()] + text[win_start:pos] + text[pos:pos + 14]
                    periods = {i['period'] for i in cands}
                    other_year = any(not any(p.startswith(f'FY{y}') for p in periods) for y in _YEAR.findall(around))
                    if _SCOPE.search(around) or other_year:
                        # 반기·부문·타사·재분류·장부에 없는 연도 -- FY 연결 장부값과 같을 이유가 없다. 작성자가 출처를 확인한다
                        r['result'] = 'WARN'
                        r['reason'] = '장부 밖 기간·범위 표기 (작성자 출처 확인)'
            results.append(r)
    return results


# ==================== CLI ====================


# 규칙 9 -- 이익과 배수의 기간을 맞춘다 (research-ta 절대 규칙 9, HD현대중공업·하이브 critic 실측)
# per_scenarios[name] 에 eps_basis / per_basis 를 적는다. 예: "FY27E", "12M 선행", "후행 12M", "FY26E 컨센".
# 둘의 기간 부류가 다르면 period_note(왜 다른 기간을 곱했는지) 가 없을 때 FAIL. 미표기는 WARN.
_PERIOD_CLASSES = (
    ('ttm', re.compile(r'후행|TTM|trailing|최근\s*12', re.I)),
    ('12m', re.compile(r'12\s*M|12개월|롤링|rolling|NTM', re.I)),
)
_FY_RE = re.compile(r'(?:FY|20)(\d\d)', re.I)


def _period_class(basis):
    if not basis:
        return None
    for name, rx in _PERIOD_CLASSES:
        if rx.search(basis):
            return name
    m = _FY_RE.search(basis)
    return f'fy{m.group(1)}' if m else 'unknown'


def check_period_match(assumptions):
    """per_scenarios 의 eps_basis / per_basis 기간 부류 대조. check_sections 와 같은 결과 모양."""
    out = []
    for name, sc in ((assumptions or {}).get('per_scenarios') or {}).items():
        if not isinstance(sc, dict):
            continue
        eb, pb = sc.get('eps_basis'), sc.get('per_basis')
        base = {'section': 'assumptions.per_scenarios', 'pos': name, 'name': '기간 정합', 'metric': 'period',
                'percent': False, 'text_value': f'eps={eb or "?"} / per={pb or "?"}', 'definitions': []}
        ec, pc = _period_class(eb), _period_class(pb)
        if ec is None or pc is None:
            out.append({**base, 'result': 'WARN', 'ledger_values': [], 'reason': 'eps_basis/per_basis 미표기 (규칙 9)'})
        elif ec == pc and ec != 'unknown':
            out.append({**base, 'result': 'PASS', 'ledger_values': [ec], 'reason': ''})
        elif sc.get('period_note'):
            out.append({**base, 'result': 'PASS', 'ledger_values': [ec, pc], 'reason': f'기간 다름, period_note 있음: {sc["period_note"][:60]}'})
        else:
            out.append({**base, 'result': 'FAIL', 'ledger_values': [ec, pc],
                        'reason': '이익과 배수의 기간이 다른데 period_note 없음 (규칙 9: 선행 이익에는 선행 배수)'})
    return out

def run_compute(stock_name):
    ta = ta_common.ta_dir(stock_name)
    fs = ta_common.read_json(os.path.join(ta_common.data_dir(stock_name), 'financial_summary.json'))
    if fs is None:
        print(f'[ERROR] data/{stock_name}/financial_summary.json 없음')
        ta_common.manifest_update(stock_name, 'calc_ledger', 'failed', reason='financial_summary.json 없음')
        return 1
    market = ta_common.read_json(os.path.join(ta, 'market_data.json'))
    if market is not None and market.get('status') == 'failed':
        market = None
    assumptions = ta_common.read_json(os.path.join(ta, 'assumptions.json'))
    dd = ta_common.data_dir(stock_name)
    ledger = build_ledger(fs, market, assumptions,
                          fnguide=ta_common.read_json(os.path.join(dd, '_fnguide.json')),
                          dart=ta_common.read_json(os.path.join(dd, 'data_dart_financials.json')))
    ledger['asof'] = ta_common.now_kst().isoformat()
    out_name = stock_name.replace(' ', '')  # ta_render/generate_all 과 같은 폴더명 (CJ ENM -> CJENM_ta)
    xlsx = os.path.join(ta_common.PROJECT_ROOT, 'output', f'{out_name}_ta', f'model_{out_name}.xlsx')
    write_xlsx(ledger, xlsx)
    ledger['xlsx'] = xlsx
    ta_common.write_json(os.path.join(ta, 'calc_ledger.json'), ledger)
    ok = sum(1 for i in ledger['items'] if i['status'] == 'ok')
    ta_common.manifest_update(stock_name, 'calc_ledger', 'ok', items_ok=ok, items_total=len(ledger['items']))
    print(f'[calc_ledger] {stock_name} FY{ledger["fy"]}: ok {ok} / {len(ledger["items"])} -> {xlsx}')
    for i in ledger['items']:
        if i['status'] != 'ok':
            print(f'  - skipped {i["key"]} ({i["period"]}): {i["reason"]}')
    for w in ledger['warnings']:
        print(f'  [WARN] {w}')
    return 0


def run_check(stock_name, analysis_path=None):
    ta = ta_common.ta_dir(stock_name)
    ledger = ta_common.read_json(os.path.join(ta, 'calc_ledger.json'))
    if ledger is None:
        print('[ERROR] ta/calc_ledger.json 없음 -- compute 먼저')
        return 1
    analysis_path = analysis_path or os.path.join(ta_common.PROJECT_ROOT, 'scripts', f'analysis_{stock_name}_ta.json')
    A = ta_common.read_json(analysis_path)
    if A is None:
        print(f'[ERROR] {analysis_path} 없음')
        return 1
    res = check_sections(A.get('sections') or {}, ledger)
    res += check_period_match(ta_common.read_json(os.path.join(ta, 'assumptions.json')) or {})
    counts = {k: sum(1 for r in res if r['result'] == k) for k in ('PASS', 'FAIL', 'WARN')}
    ta_common.write_json(os.path.join(ta, 'calc_check.json'),
                         {'status': 'failed' if counts['FAIL'] else 'ok', 'analysis': analysis_path,
                          'counts': counts, 'results': res})
    for r in res:
        if r['result'] != 'PASS':
            print(f"  [{r['result']}] {r['section']}@{r['pos']} {r['name']} 본문 {r['text_value']}"
                  f"{'%' if r['percent'] else ''} / 장부 {r['ledger_values']}"
                  + (f" -- {r['reason']}" if r.get('reason') and r.get('metric') == 'period' else ''))
            for d in r.get('definitions', []):
                print(f'      장부 정의: {d}')
    print(f"[calc_check] PASS {counts['PASS']} / FAIL {counts['FAIL']} / WARN {counts['WARN']}")
    return 1 if counts['FAIL'] else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='계산 장부 + 엑셀 모델 + 본문 대조')
    ap.add_argument('mode', choices=['compute', 'check'])
    ap.add_argument('stock_name')
    ap.add_argument('--analysis')
    a = ap.parse_args(argv)
    if a.mode == 'compute':
        return run_compute(a.stock_name)
    return run_check(a.stock_name, a.analysis)


if __name__ == '__main__':
    sys.exit(main())
