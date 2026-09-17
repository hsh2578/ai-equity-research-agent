"""ta_market_data 테스트 -- 기술지표/신호/VaR/KIS 교차검증 (Task 4).

네트워크 금지. 지표는 stockstats 원본 정의(ewm adjust=True 재귀식, ddof=1
표준편차, SMMA alpha=1/window)를 이 테스트 안에서 **독립적으로 재구현**해
대조한다(허용오차 1e-6). load_prices/kis_cross_check 는 reader/get_price
주입으로 네트워크를 차단한다.

실행: python tests/test_ta_market_data.py
"""
import inspect
import io
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import pandas as pd                                     # noqa: E402
import ta_common as tc                                  # noqa: E402
import ta_market_data as tm                              # noqa: E402

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_passed = 0
_failed = []


def eq(got, want, label):
    global _passed
    if got == want:
        _passed += 1
    else:
        _failed.append((label, want, got))


def close_enough(got, want, label, tol=1e-6):
    global _passed
    if got is None or want is None:
        eq(got, want, label)
        return
    if abs(got - want) <= tol:
        _passed += 1
    else:
        _failed.append((label, want, got))


# ==================== 합성 OHLCV (결정론적, 90행) ====================

N = 90
_DATES = pd.bdate_range(end='2025-06-30', periods=N)
_CLOSE = [100 + 10 * math.sin(i / 7.0) + i * 0.05 for i in range(N)]
_HIGH = [c * 1.01 for c in _CLOSE]
_LOW = [c * 0.99 for c in _CLOSE]
_VOLUME = [1000 + (i % 7) * 37 for i in range(N)]

SYNTH = pd.DataFrame(
    {'Open': _CLOSE, 'High': _HIGH, 'Low': _LOW, 'Close': _CLOSE, 'Volume': _VOLUME},
    index=_DATES,
)

IND = tm.compute_indicators(SYNTH)


# ---------- 독립 재구현 (production 코드 호출 없이 직접 계산) ----------

def indep_ewm_series(values, alpha):
    """pandas ewm(span/alpha, adjust=True, min_periods<=1).mean() 과 동일한
    재귀식(num_t = x_t + (1-a)*num_{t-1}, den_t = 1 + (1-a)*den_{t-1})."""
    out = []
    num = den = 0.0
    for x in values:
        num = x + (1 - alpha) * num
        den = 1 + (1 - alpha) * den
        out.append(num / den)
    return out


def indep_sma(values, window, i):
    lo = max(0, i - window + 1)
    seg = values[lo:i + 1]
    return sum(seg) / len(seg)


def indep_std_ddof1(values, window, i):
    lo = max(0, i - window + 1)
    seg = values[lo:i + 1]
    if len(seg) < 2:
        return None
    m = sum(seg) / len(seg)
    var = sum((x - m) ** 2 for x in seg) / (len(seg) - 1)
    return var ** 0.5


# 지표 전 구간 독립 계산
_alpha10 = 2 / 11.0
_ema10_indep = indep_ewm_series(_CLOSE, _alpha10)

_alpha12 = 2 / 13.0
_alpha26 = 2 / 27.0
_ema12_indep = indep_ewm_series(_CLOSE, _alpha12)
_ema26_indep = indep_ewm_series(_CLOSE, _alpha26)
_macd_indep = [a - b for a, b in zip(_ema12_indep, _ema26_indep)]
_macds_indep = indep_ewm_series(_macd_indep, 2 / 10.0)
_macdh_indep = [a - b for a, b in zip(_macd_indep, _macds_indep)]

_diff = [0.0] + [_CLOSE[i] - _CLOSE[i - 1] for i in range(1, N)]
_up = [max(d, 0.0) for d in _diff]
_down = [max(-d, 0.0) for d in _diff]
_up_smma_indep = indep_ewm_series(_up, 1 / 14.0)
_down_smma_indep = indep_ewm_series(_down, 1 / 14.0)
_rsi_indep = [50.0]
for i in range(1, N):
    t = _up_smma_indep[i] + _down_smma_indep[i]
    _rsi_indep.append(100 * _up_smma_indep[i] / t if t != 0 else 50.0)

_prev_close = [_CLOSE[0]] + _CLOSE[:-1]
_tr_indep = [
    max(_HIGH[i] - _LOW[i], abs(_HIGH[i] - _prev_close[i]), abs(_LOW[i] - _prev_close[i]))
    for i in range(N)
]
_atr_indep = indep_ewm_series(_tr_indep, 1 / 14.0)

_tp = [(_CLOSE[i] + _HIGH[i] + _LOW[i]) / 3.0 for i in range(N)]
_tpv = [_tp[i] * _VOLUME[i] for i in range(N)]


def _vwma_indep(i, window=20):
    lo = max(0, i - window + 1)
    return sum(_tpv[lo:i + 1]) / sum(_VOLUME[lo:i + 1])


_tp_diff = [0.0] + [_tp[i] - _tp[i - 1] for i in range(1, N)]
_raw_flow = [_tp[i] * _VOLUME[i] for i in range(N)]
_pos_flow = [_raw_flow[i] if _tp_diff[i] > 0 else 0.0 for i in range(N)]
_neg_flow = [_raw_flow[i] if _tp_diff[i] < 0 else 0.0 for i in range(N)]


def _mfi_indep(i, window=14):
    if i < window:
        return 0.5
    lo = max(0, i - window + 1)
    pos = sum(_pos_flow[lo:i + 1])
    neg = sum(_neg_flow[lo:i + 1])
    tot = pos + neg
    return pos / tot if tot > 0 else 0.5


for idx in (5, 25, 50, 89):
    row = IND.iloc[idx]
    close_enough(float(row['close_10_ema']), _ema10_indep[idx], f'close_10_ema[{idx}]')
    close_enough(float(row['close_50_sma']), indep_sma(_CLOSE, 50, idx), f'close_50_sma[{idx}]')
    close_enough(float(row['close_200_sma']), indep_sma(_CLOSE, 200, idx), f'close_200_sma[{idx}]')
    close_enough(float(row['macd']), _macd_indep[idx], f'macd[{idx}]')
    close_enough(float(row['macds']), _macds_indep[idx], f'macds[{idx}]')
    close_enough(float(row['macdh']), _macdh_indep[idx], f'macdh[{idx}]')
    close_enough(float(row['rsi']), _rsi_indep[idx], f'rsi[{idx}]')
    close_enough(float(row['boll']), indep_sma(_CLOSE, 20, idx), f'boll[{idx}]')
    std_i = indep_std_ddof1(_CLOSE, 20, idx)
    if std_i is not None:
        close_enough(float(row['boll_ub']), indep_sma(_CLOSE, 20, idx) + 2 * std_i, f'boll_ub[{idx}]')
        close_enough(float(row['boll_lb']), indep_sma(_CLOSE, 20, idx) - 2 * std_i, f'boll_lb[{idx}]')
    close_enough(float(row['atr']), _atr_indep[idx], f'atr[{idx}]')
    close_enough(float(row['vwma']), _vwma_indep(idx), f'vwma[{idx}]')
    close_enough(float(row['mfi']), _mfi_indep(idx), f'mfi[{idx}]')

# mfi 처음 14행은 무조건 0.5 (stockstats 원본 동작 -- 분모>0 이어도 덮어씀)
eq(all(IND.iloc[i]['mfi'] == 0.5 for i in range(14)), True, 'mfi 처음 14행은 전부 0.5 고정')
eq(float(IND.iloc[0]['rsi']), 50.0, 'rsi 첫 행은 50 고정')


# ==================== compute_signals -- 워밍업 제외 (fix round 1) ====================
# RSI(14)/Boll(20) 은 각각 행 위치 13/19 미만이면 워밍업이라 신호에서 제외한다.
# 30행 중 idx5(rsi 과열), idx10(볼린저 상단 돌파) 는 워밍업 구간 -> 제외돼야 하고,
# idx15/idx25(rsi), idx20/idx27(볼린저) 는 워밍업을 지났으니 포함돼야 한다.

N30 = 30
_sig_dates = pd.bdate_range('2025-01-06', periods=N30)
_rsi30 = [50] * N30
_rsi30[5] = 80    # idx5 < RSI_MIN_IDX(13) -> 워밍업, 제외돼야 함
_rsi30[15] = 75   # idx15 >= 13 -> 포함
_rsi30[25] = 20   # idx25 >= 13 -> 포함
_close30 = [100] * N30
_close30[10] = 115  # idx10 < BOLL_MIN_IDX(19) -> 워밍업, 제외돼야 함 (boll_ub=110)
_close30[20] = 115  # idx20 >= 19 -> 포함 (상단 돌파)
_close30[27] = 80   # idx27 >= 19 -> 포함 (하단 돌파, boll_lb=90)

sig_df = pd.DataFrame({
    'Close': _close30,
    'High': [105] * N30,
    'Low': [95] * N30,
    'close_50_sma': [10] * N30,   # sign 항상 -1 (크로스 없음 -- 크로스는 250행 시나리오에서 따로 검증)
    'close_200_sma': [11] * N30,
    'rsi': _rsi30,
    'boll_ub': [110] * N30,
    'boll_lb': [90] * N30,
    'atr': [5] * N30,
}, index=_sig_dates)

sig = tm.compute_signals(sig_df)
d = [tm._fmt_date(x) for x in _sig_dates]

eq(sig['cross'], [], '부호가 항상 -1 이면 크로스 없음')
eq(sig['rsi_state'], 'neutral', '마지막 행(idx29) rsi=50 -> neutral')
eq(sig['rsi_extremes'], [
    {'date': d[15], 'rsi': 75.0, 'state': 'overbought'},
    {'date': d[25], 'rsi': 20.0, 'state': 'oversold'},
], 'RSI 극값: idx5 는 워밍업(<13)이라 제외, idx15/25 만 채택')
eq(sig['boll_breaks'], [
    {'date': d[20], 'type': 'upper_break'},
    {'date': d[27], 'type': 'lower_break'},
], '볼린저 돌파: idx10 은 워밍업(<19)이라 제외, idx20/27 만 채택')
eq(sig['w52'], {'high': 105.0, 'low': 95.0, 'position_pct': 50.0}, '52주 고저 + 현재가 위치(%) -- 워밍업 제외 대상 아님')
eq(sig['atr_bands'], {'m2': 90.0, 'm1': 95.0, 'p1': 105.0, 'p2': 110.0}, 'ATR 밴드 -- 워밍업 제외 대상 아님')
eq(sig['warmup_excluded_before'], d[-1], 'n(30) <= CROSS_MIN_IDX(199) 이면 전체가 크로스 워밍업 -> 마지막 날짜')


# ---------- 골든/데드크로스: 워밍업 구간의 가짜 크로스는 반드시 제외된다 ----------
# 250행: idx0-49 sign=-1, idx50-149 sign=+1(워밍업 중 가짜 골든), idx150-199 sign=-1
# (워밍업 중 가짜 데드), idx200-249 sign=+1(진짜 골든, row index>=199 라 채택).
# rsi/boll/atr 은 전부 중립값으로 고정해 크로스만 격리해 본다.
N250 = 250
_cross_dates = pd.bdate_range('2024-01-02', periods=N250)


def _sma_pair(i):
    if i < 50:
        return 10, 11   # sign -1
    if i < 150:
        return 12, 11   # sign +1 (워밍업 구간의 가짜 골든크로스, idx50 에서 발생)
    if i < 200:
        return 10, 11   # sign -1 (워밍업 구간의 가짜 데드크로스, idx150 에서 발생)
    return 12, 11        # sign +1 (idx200 에서 발생 -- row index >= 199 라 진짜 신호)


_sma50s, _sma200s = zip(*[_sma_pair(i) for i in range(N250)])
cross_df = pd.DataFrame({
    'Close': [100] * N250, 'High': [105] * N250, 'Low': [95] * N250,
    'close_50_sma': list(_sma50s), 'close_200_sma': list(_sma200s),
    'rsi': [50] * N250, 'boll_ub': [110] * N250, 'boll_lb': [90] * N250,
    'atr': [5] * N250,
}, index=_cross_dates)

cross_sig = tm.compute_signals(cross_df)
dc = [tm._fmt_date(x) for x in _cross_dates]
eq(cross_sig['cross'], [{'date': dc[200], 'type': 'golden'}],
   '워밍업(idx50/idx150) 중 가짜 크로스 2건은 제외되고 idx200 진짜 골든크로스 1건만 남는다')
eq(cross_sig['warmup_excluded_before'], dc[199], 'n(250) > CROSS_MIN_IDX(199) -> 200번째 행 날짜가 경계')


# ==================== compute_var ====================

# (a) var95_1d -- 알려진 10개 수익률, 5% 분위수(선형보간) 를 손으로 계산해 대조
_returns10 = [-0.05, -0.03, -0.01, 0.0, 0.02, 0.04, 0.06, 0.08, 0.10, -0.02]
_closes10 = [100.0]
for r in _returns10:
    _closes10.append(_closes10[-1] * (1 + r))
var_dates = pd.bdate_range('2025-01-06', periods=len(_closes10))
var_df10 = pd.DataFrame({'Close': _closes10}, index=var_dates)

_sorted = sorted(_returns10)
_pos = 0.05 * (len(_sorted) - 1)
_lo_i, _frac = int(_pos), _pos - int(_pos)
_expected_var1d = _sorted[_lo_i] + _frac * (_sorted[_lo_i + 1] - _sorted[_lo_i])

var_out10 = tm.compute_var(var_df10)
close_enough(var_out10['var95_1d'], _expected_var1d, 'var95_1d 선형보간 5% 분위수', tol=1e-4)
eq(var_out10['n'], 10, 'var95_1d 표본 수(n)')

# (b) var95_20d -- 일정 1% 일수익률이면 20일 누적수익률은 상수 (1.01**20 - 1),
#     sqrt(20) 스케일링([X] 잘못 구현하면 0.01*sqrt(20)=0.0447 이 나온다) 이 아님을 구분
_closes40 = [100.0 * (1.01 ** i) for i in range(40)]
var_df40 = pd.DataFrame({'Close': _closes40}, index=pd.bdate_range('2025-01-06', periods=40))
var_out40 = tm.compute_var(var_df40)
_expected_var20d = 1.01 ** 20 - 1
close_enough(var_out40['var95_20d'], _expected_var20d, 'var95_20d = 20일 누적수익률 분위수(스케일링 아님)', tol=1e-6)
_not_sqrt_scaled = abs(var_out40['var95_20d'] - 0.01 * math.sqrt(20)) > 0.05
eq(_not_sqrt_scaled, True, 'var95_20d 는 sqrt(20) 스케일링이 아니다')


# ==================== --days 기본값 (fix round 2) ====================
# 400 캘린더일이면 거래일 ~270행 -- SMA200 워밍업(200행) 을 빼면 신호 판정
# 구간이 3개월 남짓뿐이다. 700 캘린더일(~470 거래일)로 올려 워밍업 이후에도
# 약 1년치 크로스/RSI/볼린저 판정 구간이 남도록 한다.
for _fn in (tm.load_prices, tm.build_market_data, tm.run):
    eq(inspect.signature(_fn).parameters['days'].default, 700, f'{_fn.__name__} days 기본값 700')


# ==================== build_market_data ====================

def _make_ok_df(n=260, last_date=None):
    if last_date is None:
        last_date = tc.now_kst().date()
    dates = pd.date_range(end=last_date, periods=n, freq='D')
    close = [100 + 5 * math.sin(i / 11.0) + i * 0.03 for i in range(n)]
    high = [c * 1.01 for c in close]
    low = [c * 0.99 for c in close]
    volume = [1000 + (i % 5) * 20 for i in range(n)]
    return pd.DataFrame({'Open': close, 'High': high, 'Low': low, 'Close': close, 'Volume': volume}, index=dates)


_OK_DF = _make_ok_df()


def _reader_ok(code, start):
    return _OK_DF


def _reader_thin(code, start):
    return _OK_DF.tail(100)


def _reader_stale(code, start):
    from datetime import timedelta
    return _make_ok_df(last_date=tc.now_kst().date() - timedelta(days=30))


def _get_price_ok(code):
    return {'현재가': int(_OK_DF['Close'].iloc[-1] * 1.01), 'PER': 12.3, 'PBR': 1.5, '시가총액': 543210}


def _get_price_fail(code):
    raise RuntimeError('KIS 모의서버 HTTP 500')


# ---------- KRX 일별매매 교차검증 (Task 14, fix round 1) 고정 fixture ----------
# krx_call 기본값은 None -> tc.krx_http_call(실 네트워크) 이므로, build_market_data 가
# krx_cross_check 까지 도달하는 모든 호출에는 반드시 가짜 krx_call 을 주입한다(네트워크 금지).
# fix round 1: krx_cross_check 는 이제 FDR "마지막" 종가가 아니라 KRX 확정거래일(trade_date)
# **그 날짜**의 FDR 종가를 찾아 비교한다 -- 그래서 기대값도 trade_date 행에서 뽑는다
# (_OK_DF 는 freq='D' 전체 달력일이라 trade_date 가 항상 인덱스에 있다).


def _first_krx_basdd():
    """krx_call_with_fallback 의 첫 basDd 후보 계산을 그대로 복제(테스트 기대값 산출용,
    벽시계 시각에 따라 값이 달라지므로 하드코딩하지 않는다)."""
    from datetime import timedelta as _td
    n = tc.now_kst()
    d = n.date()
    if d.weekday() < 5 and n.hour < 17:
        d -= _td(days=1)
    while d.weekday() >= 5:
        d -= _td(days=1)
    return d.strftime('%Y%m%d')


_KRX_BASDD_TODAY = _first_krx_basdd()
_KRX_TRADE_DATE = f'{_KRX_BASDD_TODAY[:4]}-{_KRX_BASDD_TODAY[4:6]}-{_KRX_BASDD_TODAY[6:]}'
_KRX_TRADE_TS = pd.Timestamp(_KRX_TRADE_DATE)
_FDR_CLOSE_ON_TRADE = float(_OK_DF.loc[_KRX_TRADE_TS, 'Close'])
_KRX_CLOSE = round(_FDR_CLOSE_ON_TRADE * 1.002, 2)


def _krx_call_ok(path, basDd):
    if path == 'sto/ksq_bydd_trd':
        return [{'ISU_SRT_CD': '036810', 'TDD_CLSPRC': str(_KRX_CLOSE)}]
    return []


def _krx_call_fail(path, basDd):
    return []


# ---------- krx_cross_check 직접 테스트 (fix round 1) ----------

def _krx_row_ok(path, basDd):
    if path == 'sto/ksq_bydd_trd':
        return [{'ISU_SRT_CD': '036810', 'TDD_CLSPRC': '10500'}]
    return []


# (a) 같은 날짜(trade_date) 에 FDR 값이 있으면 "마지막 행"이 아니라 그 날짜 종가로 비교한다.
_fdr_two_rows = pd.DataFrame(
    {'Close': [10000.0, 10600.0]},
    index=[_KRX_TRADE_TS, _KRX_TRADE_TS + pd.Timedelta(days=1)],  # [trade_date 행, 그 다음날(마지막 행, 다른 값)]
)
r_same = tm.krx_cross_check('036810', _fdr_two_rows, krx_call=_krx_row_ok)
eq(r_same['status'], 'ok', '같은 날짜 FDR 값이 있으면 ok')
eq(r_same['trade_date'], _KRX_TRADE_DATE, 'trade_date 는 KRX 확정 거래일')
eq(r_same['fdr_date'], _KRX_TRADE_DATE, 'fdr_date 는 trade_date 와 같아야 한다(다른 날 비교 금지, fix round 1)')
eq(r_same['fdr_close'], 10000.0, 'fdr_close 는 trade_date 행의 종가(마지막 행 10600 이 아니다)')
eq(r_same['krx_close'], 10500.0, 'krx_close')
eq(r_same['diff_pct'], round((10500.0 - 10000.0) / 10000.0 * 100, 3), 'diff_pct = (KRX-FDR)/FDR*100')

# (b) FDR 에 trade_date 행이 없으면 failed + 사유에 날짜 명시
_fdr_no_match = pd.DataFrame({'Close': [9999.0]}, index=[_KRX_TRADE_TS + pd.Timedelta(days=30)])
r_missing_date = tm.krx_cross_check('036810', _fdr_no_match, krx_call=_krx_row_ok)
eq(r_missing_date['status'], 'failed', 'FDR 에 trade_date 행이 없으면 failed')
eq(r_missing_date['reason'], f'FDR 에 {_KRX_TRADE_DATE} 행 없음', '사유에 날짜가 명시된다')

# (c) KRX 응답에 기대 필드(TDD_CLSPRC)가 없으면(스키마 변경 가정) failed + 필드명 명시
def _krx_row_missing_field(path, basDd):
    if path == 'sto/ksq_bydd_trd':
        return [{'ISU_SRT_CD': '036810'}]  # TDD_CLSPRC 없음
    return []


r_missing_field = tm.krx_cross_check('036810', _fdr_two_rows, krx_call=_krx_row_missing_field)
eq(r_missing_field['status'], 'failed', 'KRX 응답에 기대 필드가 없으면 failed')
eq('TDD_CLSPRC' in r_missing_field['reason'], True, '사유에 빠진 필드명이 들어간다')


r1 = tm.build_market_data('테스트종목', code='036810', reader=_reader_thin, get_price=_get_price_ok)
eq(r1['status'], 'failed', '250행 미만 -> failed')
eq(r1['reason'], '표본 부족', '250행 미만 사유')

r2 = tm.build_market_data('테스트종목', code='036810', reader=_reader_stale, get_price=_get_price_ok)
eq(r2['status'], 'failed', '마지막 행이 10일+ 과거 -> failed')
eq('stale' in r2['reason'], True, 'stale 사유 문자열 포함')

r3 = tm.build_market_data('테스트종목', code='036810', reader=_reader_ok, get_price=_get_price_fail,
                           krx_call=_krx_call_ok)
eq(r3['status'], 'ok', 'KIS 실패해도 전체 status 는 ok (가격/지표는 정상)')
eq(r3['kis']['status'], 'failed', 'KIS 로더 예외 -> kis.status failed')
eq('RuntimeError' in r3['kis']['reason'], True, 'kis.reason 에 예외타입 포함')

r3b = tm.build_market_data('테스트종목', code='036810', reader=_reader_ok, get_price=_get_price_ok,
                            krx_call=_krx_call_fail)
eq(r3b['status'], 'ok', 'KRX 실패해도 전체 status 는 ok (KIS 와 독립)')
eq(r3b['krx']['status'], 'failed', 'KRX 응답에 종목코드 없음 -> krx.status failed')
eq(r3b['krx']['reason'] != '', True, 'krx.reason 에 사유가 남는다')

r4 = tm.build_market_data('테스트종목', code='036810', reader=_reader_ok, get_price=_get_price_ok,
                           krx_call=_krx_call_ok)
eq(r4['status'], 'ok', '정상 경로 -> ok')
eq(r4['code'], '036810', '코드는 6자리로 zfill')
eq(r4['rows'], 260, '행 수 기록')
eq(r4['kis']['status'], 'ok', 'KIS 정상 -> ok')
eq(r4['krx']['status'], 'ok', 'KRX 정상 -> ok')
eq(r4['krx']['trade_date'], _KRX_TRADE_DATE, 'krx.trade_date 는 조회에 성공한 basDd 를 YYYY-MM-DD 로 표기')
eq(r4['krx']['fdr_date'], _KRX_TRADE_DATE, 'krx.fdr_date 는 trade_date 와 같다(fix round 1 -- 다른 날 비교 금지)')
eq(r4['krx']['krx_close'], _KRX_CLOSE, 'krx.krx_close 는 KRX 응답 종가')
eq(r4['krx']['fdr_close'], _FDR_CLOSE_ON_TRADE, 'krx.fdr_close 는 trade_date **그 날짜**의 FDR 종가(마지막 행 아님)')
_expected_diff = round((_KRX_CLOSE - _FDR_CLOSE_ON_TRADE) / _FDR_CLOSE_ON_TRADE * 100, 3)
eq(r4['krx']['diff_pct'], _expected_diff, 'krx.diff_pct = (KRX-FDR)/FDR*100, 반올림 3자리')
eq(set(tm.INDICATOR_KEYS) <= set(r4['latest'].keys()), True, 'latest 에 13개 지표 키가 모두 있다')
eq(len(r4['series_tail']), 60, 'series_tail 은 최근 60행')
eq(set(r4['definitions'].keys()), set(tm.INDICATOR_KEYS), 'definitions 는 13개 지표를 모두 설명한다')
eq(r4['signals']['warmup_excluded_before'], tm._fmt_date(_OK_DF.index[199]),
   '실제 파이프라인(260행)에서도 warmup_excluded_before 가 200번째 행 날짜로 채워진다')
eq(all('워밍업' in v for v in r4['definitions'].values()), True, 'definitions 는 13개 지표 전부에 워밍업 구간을 명시한다')

# ---------- run() -- 파일 저장 + manifest ----------
import json  # noqa: E402
import tempfile  # noqa: E402

with tempfile.TemporaryDirectory() as td:
    orig_root = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        result, out_path = tm.run('테스트종목', code='036810', reader=_reader_ok, get_price=_get_price_ok,
                                   krx_call=_krx_call_ok)
        eq(os.path.exists(out_path), True, 'run() 이 market_data.json 을 저장한다')
        on_disk = json.load(open(out_path, encoding='utf-8'))
        eq(on_disk['status'], 'ok', '저장된 JSON 의 status')
        eq(on_disk['krx']['status'], 'ok', '저장된 JSON 에도 krx 블록이 포함된다')
        manifest_path = os.path.join(tc.ta_dir('테스트종목'), 'manifest.json')
        manifest = json.load(open(manifest_path, encoding='utf-8'))
        eq(manifest['steps']['market_data']['status'], 'ok', 'manifest_update 로 진행 기록')
    finally:
        tc.PROJECT_ROOT = orig_root


print('=' * 66)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  ta_market_data 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
