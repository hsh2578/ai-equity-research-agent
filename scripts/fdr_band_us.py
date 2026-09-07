"""
US 종목 5년 PER/PBR 밴드 (KR fdr_band.py 의 미국판, v5.5 신설)

기존에는 이 계산이 /research 실행 중 인라인 임시코드로 이뤄져
  - 재현 불가 (매 실행 코드가 달라짐)
  - generate_all.py 검증 #11 이 형식만 보고 통과
문제가 있었다. 커밋된 스크립트로 고정한다.

KR 과의 차이:
  - 연말 종가: FinanceDataReader -> yfinance history
  - EPS/BPS  : financial_summary.json (SEC EDGAR XBRL 기반) 동일
  - BPS 부재 시 total_equity / shares_outstanding 로 역산

KR 판 대비 개선 (추후 KR 에도 역이식 예정):
  - 밴드 유의성 경고: std/mean > 0.6 이면 "밴드 해석 무의미" 경고.
    AMD 처럼 PER 이 56 -> 278 -> 121 로 튀는 종목은 평균/z-score 가 노이즈다.
  - 표본 3개 미만이면 밴드 산출 자체를 거부 (z-score 날조 차단)

사용법:
    python scripts/fdr_band_us.py NVDA
출력: data/{TICKER}/_per_band.json
"""
import sys
import io
import os
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import numpy as np

try:
    import yfinance as yf
except ImportError:
    print("[ERR] yfinance 미설치. pip install yfinance", file=sys.stderr)
    sys.exit(1)

MIN_SAMPLES = 3
NOISY_CV = 0.6          # 변동계수(std/mean) 이 값을 넘으면 밴드 무의미


def _get_bps(year_data: dict, shares: float):
    """financial_summary.json 연도 블록에서 BPS 추출 또는 역산."""
    for k in ('bps', 'book_value_per_share'):
        v = year_data.get(k)
        if v:
            return float(v)
    equity = year_data.get('total_equity') or year_data.get('stockholders_equity')
    if equity and shares:
        return float(equity) / float(shares)
    return None


def main(ticker: str) -> int:
    ticker = ticker.upper()
    fs_path = f'data/{ticker}/financial_summary.json'
    if not os.path.exists(fs_path):
        print(f"[ERR] {fs_path} 없음. financial_summary_us.py 먼저 실행.")
        return 1

    d = json.load(open(fs_path, encoding='utf-8'))
    fin = d.get('financials', {})
    if not fin:
        print("[ERR] financials 비어있음.")
        return 1

    t = yf.Ticker(ticker)
    info = {}
    try:
        info = t.info or {}
    except Exception as e:
        print(f"  [WARN] info 조회 실패: {type(e).__name__}")

    shares = info.get('sharesOutstanding') or info.get('impliedSharesOutstanding')

    # 연말 종가
    hist = t.history(period='7y', interval='1d', auto_adjust=False)
    if hist is None or hist.empty:
        print("[ERR] 주가 이력 조회 실패.")
        return 1
    year_end = hist.groupby(hist.index.year).tail(1)
    closes = {int(idx.year): float(row['Close']) for idx, row in year_end.iterrows()}

    current_price = float(info.get('currentPrice') or info.get('regularMarketPrice') or 0)
    if not current_price:
        current_price = float(hist['Close'].iloc[-1])
    current_per = float(info.get('trailingPE') or 0)
    current_pbr = float(info.get('priceToBook') or 0)
    current_fwd_per = float(info.get('forwardPE') or 0)

    per_series, pbr_series, detail = [], [], {}
    for y in sorted(closes):
        yd = fin.get(str(y))
        if not yd:
            continue
        close = closes[y]
        eps = yd.get('eps')
        bps = _get_bps(yd, shares)
        row = {'close': round(close, 2), 'eps': eps, 'bps': round(bps, 2) if bps else None}
        if eps and eps > 0:
            per = close / eps
            per_series.append(per)
            row['per'] = round(per, 2)
        if bps and bps > 0:
            pbr = close / bps
            pbr_series.append(pbr)
            row['pbr'] = round(pbr, 2)
        detail[str(y)] = row

    warnings = []

    def _stats(series, label):
        if len(series) < MIN_SAMPLES:
            warnings.append(
                f'{label} 표본 {len(series)}개 (<{MIN_SAMPLES}) - 밴드/z-score 산출 거부. '
                f'리포트에 "5년 평균 대비" 표현 금지.')
            return 0.0, 0.0, False
        mean = float(np.mean(series))
        std = float(np.std(series))
        cv = std / mean if mean else 99
        if cv > NOISY_CV:
            warnings.append(
                f'{label} 변동계수 {cv:.2f} (>{NOISY_CV}) - 밴드 분산이 너무 커서 '
                f'z-score 해석 무의미. "역사적 고평가/저평가" 단정 금지, 연도별 값 직접 제시할 것.')
            return mean, std, False
        return mean, std, True

    per_mean, per_std, per_valid = _stats(per_series, 'PER')
    pbr_mean, pbr_std, pbr_valid = _stats(pbr_series, 'PBR')

    per_z = (current_per - per_mean) / per_std if (per_std and current_per) else 0
    pbr_z = (current_pbr - pbr_mean) / pbr_std if (pbr_std and current_pbr) else 0

    out = {
        '_description': f'{ticker} 5Y PER/PBR 밴드 (yfinance 연말종가 + SEC EPS/BPS)',
        'market': 'US',
        'fiscal_closes': {str(k): round(v, 2) for k, v in closes.items()},
        'detail': detail,
        'per_series': [round(x, 4) for x in per_series],
        'pbr_series': [round(x, 4) for x in pbr_series],
        'per_mean': round(per_mean, 4), 'per_std': round(per_std, 4),
        'pbr_mean': round(pbr_mean, 4), 'pbr_std': round(pbr_std, 4),
        'per_band_valid': per_valid, 'pbr_band_valid': pbr_valid,
        'current_price': round(current_price, 2),
        'current_per': round(current_per, 4),
        'current_per_z': round(per_z, 4),
        'current_pbr': round(current_pbr, 4),
        'current_pbr_z': round(pbr_z, 4),
        'current_forward_per': round(current_fwd_per, 4),
        'warnings': warnings,
    }

    os.makedirs(f'data/{ticker}', exist_ok=True)
    path = f'data/{ticker}/_per_band.json'
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    print(f"\n[{ticker}] 5Y 밸류에이션 밴드")
    print(f"  {'연도':<6} {'종가':>10} {'EPS':>8} {'PER':>8} {'BPS':>10} {'PBR':>8}")
    for y in sorted(detail):
        r = detail[y]
        print(f"  {y:<6} {r['close']:>10.2f} {(r.get('eps') or 0):>8.2f} "
              f"{(r.get('per') or 0):>8.2f} {(r.get('bps') or 0):>10.2f} {(r.get('pbr') or 0):>8.2f}")
    print(f"\n  PER mean={per_mean:.2f} std={per_std:.2f} / current={current_per:.2f} "
          f"(z={per_z:+.2f}) valid={per_valid}")
    print(f"  PBR mean={pbr_mean:.2f} std={pbr_std:.2f} / current={current_pbr:.2f} "
          f"(z={pbr_z:+.2f}) valid={pbr_valid}")
    print(f"  Forward PER = {current_fwd_per:.2f}")
    for w in warnings:
        print(f"  [WARN] {w}")
    print(f"\n[OK] saved: {path}")
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("usage: python scripts/fdr_band_us.py {TICKER}")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
