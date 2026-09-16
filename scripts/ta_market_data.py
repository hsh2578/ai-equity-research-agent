"""ta_market_data.py -- 기술지표 + 검증 스냅샷 + VaR + KIS 현재가 교차검증 (Task 4).

리포트 '기술적 분석' 섹션의 유일한 수치 원천. FinanceDataReader 로 받은
OHLCV 에서 TradingAgents(stockstats 기반) 13개 지표를 stockstats 소스
(https://github.com/jealous/stockstats/blob/master/stockstats.py) 와
동일한 정의로 pandas 만 써서 재구현한다 (stockstats 미설치, 설치 금지).

CLI: python scripts/ta_market_data.py {종목명} [--code ...] [--days 700]
출력: data/{종목명}/ta/market_data.json

기본 `--days` 는 700 (fix round 2, 컨트롤러 지적). 400 일이면 거래일로 약
270행 밖에 안 들어와, SMA200 워밍업(200행)을 빼고 나면 골든/데드크로스가
유효한 구간이 3개월 남짓밖에 안 남는다. 700 캘린더일 ~= 470 거래일 정도가
들어와야 워밍업 200행을 빼고도 signals.warmup_excluded_before 이후로 약
250거래일(1년)의 크로스/RSI/볼린저 판정 구간이 남는다.
"""
import io
import sys

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import argparse
import os
from datetime import timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta_common as tc  # noqa: E402

MIN_ROWS = 250
STALE_DAYS = 10
SIGNAL_WINDOW = 250
W52_WINDOW = 252

INDICATOR_KEYS = (
    'close_10_ema', 'close_50_sma', 'close_200_sma',
    'macd', 'macds', 'macdh', 'rsi',
    'boll', 'boll_ub', 'boll_lb', 'atr', 'vwma', 'mfi',
)

# stockstats 소스(위 URL) 를 그대로 옮긴 정의. adjust=True 는 pandas ewm 의
# "지수가중, 시작점부터 감쇠 가중합/가중합" 방식 (재귀 근사가 아님).
# 각 문자열 끝의 "워밍업 N행" 은 stockstats 원본이 min_periods=1 로 그 구간도
# 값을 채운다는 뜻이지, "믿을 만하다"는 뜻이 아니다 -- 예를 들어 close_200_sma
# 는 실제 데이터가 5개뿐이어도 그 5개 평균을 낸다. latest/series_tail 은
# stockstats 값과 맞추기 위해 이 구간도 그대로 보여주지만, signals(신호)
# 목록은 워밍업 구간의 크로스/과열/돌파를 진짜 신호로 세지 않는다
# (compute_signals 의 CROSS_MIN_IDX/BOLL_MIN_IDX/RSI_MIN_IDX, signals.warmup_excluded_before 참고).
DEFINITIONS = {
    'close_10_ema': 'EMA(Close, span=10): pandas ewm(span=10, adjust=True, min_periods=1).mean(). 워밍업 10행(그 전엔 관측치가 창보다 적음).',
    'close_50_sma': 'SMA(Close, 50): rolling(50, min_periods=1).mean(). 워밍업 50행.',
    'close_200_sma': 'SMA(Close, 200): rolling(200, min_periods=1).mean(). 워밍업 200행 -- signals.cross 는 이 구간을 신호에서 제외한다(row index < 199).',
    'macd': 'EMA(Close,12,span,adjust=True) - EMA(Close,26,span,adjust=True). 워밍업 26행(더 긴 EMA 기준).',
    'macds': 'EMA(macd, 9, span, adjust=True) -- macd 라인 자체의 9기간 EMA. 워밍업 약 35행(macd 26 + signal 9).',
    'macdh': 'macd - macds. 워밍업 약 35행(macds 와 동일).',
    'rsi': ("Wilder SMMA(RSI, 14): up=diff.clip(>=0), down=(-diff).clip(>=0), "
            "smma=ewm(alpha=1/14, adjust=True, min_periods=0).mean(); "
            "rsi=100*up_smma/(up_smma+down_smma), 분모 0 또는 첫 행은 50. "
            "워밍업 14행 -- signals.rsi_extremes 는 이 구간을 제외한다(row index < 13)."),
    'boll': 'SMA(Close, 20) -- 볼린저 중심선. 워밍업 20행.',
    'boll_ub': 'boll + 2*STD(Close,20, rolling(20,min_periods=1).std(), ddof=1). 워밍업 20행 -- signals.boll_breaks 는 이 구간을 제외한다(row index < 19).',
    'boll_lb': 'boll - 2*STD(Close,20, ddof=1). 워밍업 20행(boll_ub 와 동일).',
    'atr': ('SMMA(TR,14): TR=max(High-Low, |High-PrevClose|, |Low-PrevClose|), '
            'PrevClose 는 Close 를 1행 shift, 첫 행은 자기 자신으로 채움; '
            'SMMA=ewm(alpha=1/14, adjust=True, min_periods=0).mean(). 워밍업 14행.'),
    'vwma': 'sum(Volume*TypicalPrice,20)/sum(Volume,20), TypicalPrice=(Close+High+Low)/3. 워밍업 20행.',
    'mfi': ('sum(양의 자금흐름,14) / sum(전체 자금흐름,14) -- 0~1 소수 (x100 아님). '
            '자금흐름=TypicalPrice*Volume, 부호는 TypicalPrice 전일대비. '
            '분모 0 이거나 처음 14행은 0.5 고정 (stockstats 원본 동작 -- 이 자체가 워밍업 14행 표시).'),
}

_TAIL_KEYS = ('close_50_sma', 'close_200_sma', 'rsi', 'macd', 'macds', 'macdh', 'boll_ub', 'boll_lb')


# ==================== 지표 계산 (순수 함수, 네트워크 없음) ====================

def _ewm_span(series, window):
    return series.ewm(span=window, min_periods=1, adjust=True).mean()


def _ewm_smma(series, window):
    return series.ewm(alpha=1.0 / window, min_periods=0, adjust=True).mean()


def _sma(series, window):
    return series.rolling(window, min_periods=1).mean()


def compute_indicators(df):
    """OHLCV(df: Open/High/Low/Close/Volume, 오름차순) -> 13개 지표 컬럼을 더한 복사본."""
    out = df.copy()
    close = out['Close'].astype(float)
    high = out['High'].astype(float)
    low = out['Low'].astype(float)
    volume = out['Volume'].astype(float)

    out['close_10_ema'] = _ewm_span(close, 10)
    out['close_50_sma'] = _sma(close, 50)
    out['close_200_sma'] = _sma(close, 200)

    ema12 = _ewm_span(close, 12)
    ema26 = _ewm_span(close, 26)
    macd = ema12 - ema26
    macds = _ewm_span(macd, 9)
    out['macd'] = macd
    out['macds'] = macds
    out['macdh'] = macd - macds

    diff = close.diff().fillna(0.0)
    up = diff.clip(lower=0.0)
    down = (-diff).clip(lower=0.0)
    up_smma = _ewm_smma(up, 14).to_numpy()
    down_smma = _ewm_smma(down, 14).to_numpy()
    total = up_smma + down_smma
    with np.errstate(divide='ignore', invalid='ignore'):
        rsi = np.where(total != 0, 100 * (up_smma / np.where(total != 0, total, 1.0)), 50.0)
    rsi[0] = 50.0
    out['rsi'] = rsi

    boll = _sma(close, 20)
    std20 = close.rolling(20, min_periods=1).std()  # pandas 기본 ddof=1
    out['boll'] = boll
    out['boll_ub'] = boll + 2 * std20
    out['boll_lb'] = boll - 2 * std20

    prev_close = close.shift(1)
    prev_close.iloc[0] = close.iloc[0]
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    out['atr'] = _ewm_smma(tr, 14)

    tp = (close + high + low) / 3.0
    tpv = tp * volume
    out['vwma'] = tpv.rolling(20, min_periods=1).sum() / volume.rolling(20, min_periods=1).sum()

    tp_diff = tp.diff().fillna(0.0)
    raw_flow = tp * volume
    pos_flow = raw_flow.where(tp_diff > 0, 0.0)
    neg_flow = raw_flow.where(tp_diff < 0, 0.0)
    pos_sum = pos_flow.rolling(14, min_periods=1).sum().to_numpy()
    neg_sum = neg_flow.rolling(14, min_periods=1).sum().to_numpy()
    tot_flow = pos_sum + neg_sum
    with np.errstate(divide='ignore', invalid='ignore'):
        mfi = np.where(tot_flow > 0, pos_sum / np.where(tot_flow > 0, tot_flow, 1.0), 0.5)
    mfi[:14] = 0.5
    out['mfi'] = mfi

    return out


def _fmt_date(d):
    return pd.Timestamp(d).strftime('%Y-%m-%d')


def _row_indicators(row):
    d = {'close': round(float(row['Close']), 2)}
    for k in INDICATOR_KEYS:
        v = row[k]
        d[k] = None if pd.isna(v) else round(float(v), 4)
    return d


CROSS_MIN_IDX = 199  # SMA200 이 200행을 다 채운 첫 행(0-based) -- 그 전은 워밍업
BOLL_MIN_IDX = 19    # 20행 볼린저 윈도가 다 채워진 첫 행
RSI_MIN_IDX = 13     # 14행 RSI(SMMA) 윈도가 다 채워진 첫 행


def compute_signals(ind):
    """골든/데드크로스, RSI 상태, 볼린저 돌파, 52주 위치, ATR 밴드.

    `latest`/`series_tail` 는 stockstats 원본과 값을 맞추려고 min_periods=1 을
    그대로 쓰지만(워밍업 구간도 값이 나온다), 신호 목록은 그 워밍업 구간에서
    나온 값을 근거로 "크로스/과열/돌파"를 보고하면 안 된다 -- SMA200 이 아직
    20~30개 관측치로만 채워진 시점의 교차는 진짜 골든/데드크로스가 아니다.
    그래서 절대 행 위치(`ind` 전체 기준, 최근 250행으로 자르기 전)가
    각 지표의 완전한 윈도 길이에 못 미치면 그 행은 신호 판정에서 아예 제외한다."""
    n = len(ind)
    d = ind.tail(SIGNAL_WINDOW)
    start_pos = n - len(d)  # d.iloc[k] 는 ind 전체 기준 절대 위치 (start_pos + k)
    dates = list(d.index)

    sign = np.sign((d['close_50_sma'] - d['close_200_sma']).to_numpy())
    cross = []
    prev_sign = None
    for k, s in enumerate(sign):
        if start_pos + k < CROSS_MIN_IDX or s == 0:
            continue
        if prev_sign is not None and s != prev_sign:
            cross.append({'date': _fmt_date(dates[k]), 'type': 'golden' if s > 0 else 'dead'})
        prev_sign = s

    rsi = d['rsi']
    rsi_extremes = []
    for k, (date, v) in enumerate(zip(dates, rsi)):
        if start_pos + k < RSI_MIN_IDX or pd.isna(v):
            continue
        if v > 70:
            rsi_extremes.append({'date': _fmt_date(date), 'rsi': round(float(v), 2), 'state': 'overbought'})
        elif v < 30:
            rsi_extremes.append({'date': _fmt_date(date), 'rsi': round(float(v), 2), 'state': 'oversold'})
    latest_rsi = float(rsi.iloc[-1])
    rsi_state = 'overbought' if latest_rsi > 70 else ('oversold' if latest_rsi < 30 else 'neutral')

    close = d['Close']
    boll_breaks = []
    for k, (date, c, ub, lb) in enumerate(zip(dates, close, d['boll_ub'], d['boll_lb'])):
        if start_pos + k < BOLL_MIN_IDX or pd.isna(ub) or pd.isna(lb):
            continue
        if c > ub:
            boll_breaks.append({'date': _fmt_date(date), 'type': 'upper_break'})
        elif c < lb:
            boll_breaks.append({'date': _fmt_date(date), 'type': 'lower_break'})

    w = ind.tail(W52_WINDOW)
    w52_high = float(w['High'].max())
    w52_low = float(w['Low'].min())
    last_close = float(ind['Close'].iloc[-1])
    position_pct = ((last_close - w52_low) / (w52_high - w52_low) * 100) if w52_high > w52_low else 50.0

    last_atr = float(ind['atr'].iloc[-1])
    atr_bands = {
        'm2': round(last_close - 2 * last_atr, 2), 'm1': round(last_close - last_atr, 2),
        'p1': round(last_close + last_atr, 2), 'p2': round(last_close + 2 * last_atr, 2),
    }

    # 전체 신호 중 가장 긴 워밍업(SMA200, 200행)을 단일 경계로 보고한다 --
    # 이 날짜 이전 행은 cross 판정에서 제외됐다는 뜻(boll/rsi 는 더 짧은
    # 윈도라 이 날짜 이전에도 이미 유효할 수 있지만, "가장 보수적인 경계"
    # 하나만 노출해 리포트 작성자가 매번 3개 임계값을 따로 기억하지 않게 한다.
    if n > CROSS_MIN_IDX:
        warmup_excluded_before = _fmt_date(ind.index[CROSS_MIN_IDX])
    else:
        warmup_excluded_before = _fmt_date(ind.index[-1])

    return {
        'cross': cross,
        'rsi_state': rsi_state,
        'rsi_extremes': rsi_extremes,
        'boll_breaks': boll_breaks,
        'w52': {'high': round(w52_high, 2), 'low': round(w52_low, 2), 'position_pct': round(position_pct, 2)},
        'atr_bands': atr_bands,
        'warmup_excluded_before': warmup_excluded_before,
    }


def compute_var(df, window=SIGNAL_WINDOW):
    """역사적 방식 VaR. var95_1d = 최근 일수익률 5% 분위수, var95_20d = 20일 겹침
    누적수익률(pct_change(20), sqrt(20) 스케일링 아님) 의 5% 분위수. 둘 다 음수/소수."""
    close = df['Close'].astype(float)
    ret1 = close.pct_change().dropna().tail(window)
    ret20 = close.pct_change(20).dropna().tail(window)
    return {
        'var95_1d': round(float(ret1.quantile(0.05)), 6) if len(ret1) else None,
        'var95_20d': round(float(ret20.quantile(0.05)), 6) if len(ret20) else None,
        'n': int(len(ret1)),
    }


# ==================== 가격 로딩 (네트워크, 주입 가능) ====================

def load_prices(code, days=700, reader=None):
    """FDR DataReader(code, start) -- reader 주입 가능(테스트용). 오름차순 정렬 반환."""
    if reader is None:
        import FinanceDataReader as fdr
        reader = fdr.DataReader
    start = (tc.now_kst().date() - timedelta(days=days)).strftime('%Y-%m-%d')
    df = reader(code, start)
    if df is None or len(df) == 0:
        raise ValueError('FDR 이 빈 데이터를 반환함')
    return df.sort_index()


def kis_cross_check(code, fdr_last_close, get_price=None):
    """kis_api.get_current_price 로 현재가/PER/PBR/시가총액 교차검증.
    실패해도 예외를 올리지 않고 status failed 로 구조화한다."""
    if get_price is None:
        import kis_api
        get_price = kis_api.get_current_price
    try:
        px = get_price(code)
    except Exception as e:
        return {'status': 'failed', 'reason': f'{type(e).__name__}: {e}'}

    if not isinstance(px, dict) or px.get('error'):
        reason = px.get('error') if isinstance(px, dict) else f'응답 형식 오류: {type(px).__name__}'
        return {'status': 'failed', 'reason': str(reason)}

    cur = px.get('현재가')
    if not cur:
        return {'status': 'failed', 'reason': '현재가 없음(0 또는 누락)'}

    diff_pct = round((cur - fdr_last_close) / fdr_last_close * 100, 3) if fdr_last_close else None
    return {
        'status': 'ok', 'reason': '',
        '현재가': cur, 'diff_pct_vs_fdr': diff_pct,
        'PER': px.get('PER'), 'PBR': px.get('PBR'), '시가총액': px.get('시가총액'),
    }


# ==================== 조립 ====================

def build_market_data(stock_name, code=None, days=700, reader=None, get_price=None):
    """순수 조립 함수 (파일 I/O 없음). code 를 직접 받으면 종목코드/시장 조회
    네트워크 호출(tc.resolve_stock)을 타지 않는다 -- 이 스크립트는 market(상장시장)
    을 쓰지 않으므로 --code 가 있을 때 굳이 그 조회를 태울 이유가 없다(판단)."""
    asof = tc.now_kst().strftime('%Y-%m-%d')
    try:
        code6 = str(code).zfill(6) if code else tc.resolve_stock(stock_name)['code']
    except Exception as e:
        return {'stock': stock_name, 'code': code or '', 'asof': asof, 'rows': 0,
                'status': 'failed', 'reason': f'종목코드 확인 실패: {type(e).__name__}: {e}'}

    try:
        raw = load_prices(code6, days=days, reader=reader)
    except Exception as e:
        return {'stock': stock_name, 'code': code6, 'asof': asof, 'rows': 0,
                'status': 'failed', 'reason': f'{type(e).__name__}: {e}'}

    rows = len(raw)
    if rows < MIN_ROWS:
        return {'stock': stock_name, 'code': code6, 'asof': asof, 'rows': rows,
                'status': 'failed', 'reason': '표본 부족'}

    last_date = pd.Timestamp(raw.index[-1]).date()
    stale_days = (tc.now_kst().date() - last_date).days
    if stale_days > STALE_DAYS:
        return {'stock': stock_name, 'code': code6, 'asof': asof, 'rows': rows,
                'status': 'failed', 'reason': f'stale ({last_date}, {stale_days}일 경과)'}

    ind = compute_indicators(raw)
    signals = compute_signals(ind)
    var = compute_var(raw)
    fdr_last_close = float(raw['Close'].iloc[-1])
    kis = kis_cross_check(code6, fdr_last_close, get_price=get_price)

    return {
        'stock': stock_name, 'code': code6, 'asof': asof, 'rows': rows,
        'definitions': DEFINITIONS,
        'latest': _row_indicators(ind.iloc[-1]),
        'series_tail': [
            {'date': _fmt_date(date), 'close': round(float(row['Close']), 2),
             **{k: (None if pd.isna(row[k]) else round(float(row[k]), 4)) for k in _TAIL_KEYS}}
            for date, row in ind.tail(60).iterrows()
        ],
        'signals': signals,
        'var': var,
        'kis': kis,
        'status': 'ok', 'reason': '',
    }


def run(stock_name, code=None, days=700, reader=None, get_price=None):
    """build_market_data 실행 + ta/market_data.json 원자적 저장 + manifest 갱신."""
    result = build_market_data(stock_name, code=code, days=days, reader=reader, get_price=get_price)
    out_path = os.path.join(tc.ta_dir(stock_name), 'market_data.json')
    tc.write_json(out_path, result)
    tc.manifest_update(stock_name, 'market_data', result['status'],
                        reason=result.get('reason', ''), rows=result.get('rows', 0))
    return result, out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stock_name')
    ap.add_argument('--code')
    ap.add_argument('--days', type=int, default=700,
                     help='FDR 조회 기간(캘린더일). 기본 700 -- SMA200 워밍업(200행)을 빼고도 '
                          '약 250거래일(1년)의 신호 판정 구간이 남도록 잡은 값')
    args = ap.parse_args()

    result, out_path = run(args.stock_name, code=args.code, days=args.days)

    if result['status'] != 'ok':
        print(f"[FAIL] {args.stock_name}: {result.get('reason')}")
        sys.exit(1)

    print(f"[OK] {args.stock_name} ({result['code']}) rows={result['rows']} -> {out_path}")
    print(f"  RSI={result['latest']['rsi']} state={result['signals']['rsi_state']} "
          f"w52_pos={result['signals']['w52']['position_pct']}% "
          f"kis={result['kis']['status']}")
    sys.exit(0)


if __name__ == '__main__':
    main()
