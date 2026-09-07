"""
US 종목 5년 PER/PBR 밴드 (KR fdr_band.py 의 미국판, v5.5 신설)

기존에는 이 계산이 /research 실행 중 인라인 임시코드로 이뤄져
  - 재현 불가 (매 실행 코드가 달라짐)
  - generate_all.py 검증 #11 이 형식만 보고 통과
문제가 있었다. 커밋된 스크립트로 고정한다.

KR 과의 차이:
  - 연말 종가: FinanceDataReader -> yfinance history
  - EPS/BPS  : financial_summary.json (SEC EDGAR XBRL 기반) 동일

KR 판 대비 개선 (추후 KR 에도 역이식 예정):
  - 밴드 유의성 경고: std/mean > 0.6 이면 "밴드 해석 무의미" 경고.
    AMD 처럼 PER 이 56 -> 278 -> 121 로 튀는 종목은 평균/z-score 가 노이즈다.
  - 표본 3개 미만이면 밴드 산출 자체를 거부 (z-score 날조 차단)

v5.6 데이터 정확성 수정 (코드리뷰 지적 2건)
-------------------------------------------
(a) **진행 중인 당해년도를 밴드에서 뺀다.**
    hist.groupby(year).tail(1) 은 오늘 종가를 그 해의 '연말 종가'로 만든다.
    financial_summary 에 그 해 부분 실적(예: 3분기 누적 EPS)이 있으면
    close/eps 가 4배쯤 부풀려진 가짜 배수가 되고, 그 오염된 시계열로
    per_mean 과 변동계수(NOISY_CV)를 재게 된다. 달력연도가 끝난 해만 쓴다.

(b) **BPS 는 그 연도의 발행주식수로 나눈다.**
    이전 코드는 오늘의 yfinance sharesOutstanding 으로 과거 각 연도의
    total_equity 를 나눴다. 자사주 매입/증자/액면분할이 있었던 기업은
    역사 BPS 와 PBR 밴드 전체가 체계적으로 틀린다 (AMD 2021 BPS 4.59 vs 실제 6.21).
    financial_summary 의 연도별 shares_outstanding 을 쓰고, 없으면
    **BPS/PBR 밴드를 산출하지 않고 warnings 에 명시**한다.
    틀린 숫자를 내놓는 것보다 없다고 말하는 편이 낫다.

(b-2) 주당 기준(share basis) 혼재 차단.
    yfinance 종가는 액면분할이 이미 반영돼 **오늘 주식수 기준**이다. 반면 SEC
    XBRL 은 연도마다 분할 전/후 기준이 섞여 들어온다(NFLX 실측: 2021~2023 은
    분할 전 EPS·주식수, 2024~ 는 10:1 분할 후). 기준이 다른 연도를 그대로
    나누면 PER 이 10배 틀린다. 두 가지로 거른다:
      - 그 해 주식수가 최신 기준 대비 BASIS_RANGE 배를 벗어나면 연도 통째 제외
      - NI/EPS 로 역산한 주식수가 보고 주식수와 BASIS_TOL 이상 다르면 PER 만 제외

사용법:
    python scripts/fdr_band_us.py NVDA
출력: data/{TICKER}/_per_band.json
"""
import sys
import io
import os
import json
from datetime import date

# 이미 UTF-8 로 감싸져 있으면 다시 감싸지 않는다 (두 번 감싸면 먼저 만든 래퍼가
# GC 될 때 buffer 를 닫아 이 모듈을 import 한 쪽의 stdout 이 죽는다).
if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import numpy as np

MIN_SAMPLES = 3
NOISY_CV = 0.6          # 변동계수(std/mean) 이 값을 넘으면 밴드 무의미
BASIS_RANGE = 3.0       # 최신 기준 주식수 대비 허용 배수 (넘으면 분할 등 기준 혼재)
BASIS_TOL = 0.25        # NI/EPS 역산 주식수와 보고 주식수의 허용 괴리


def confirmed_year_closes(year_rows, current_year):
    """[(연도, 종가)] -> ({연도: 종가}, [제외 연도]).

    달력연도가 끝나야 '연말 종가'가 존재한다. 진행 중인 당해년도의 마지막
    거래일 종가는 연말 종가가 아니므로 밴드에서 뺀다 (수정 (a)).
    """
    closes, excluded = {}, []
    for y, close in year_rows:
        y = int(y)
        if y >= current_year:
            excluded.append(y)
            continue
        closes[y] = float(close)
    return closes, sorted(set(excluded))


def year_shares(year_data):
    """그 연도의 발행주식수. 없거나 0 이면 None."""
    v = (year_data or {}).get('shares_outstanding')
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def year_bps(year_data):
    """그 연도의 BPS. bps 필드 우선, 없으면 자기자본 / **그 연도** 주식수.

    오늘 주식수로 과거 자기자본을 나누지 않는다 (수정 (b)).
    주식수를 못 구하면 None -- 추정하지 않는다.
    """
    yd = year_data or {}
    for k in ('bps', 'book_value_per_share'):
        v = yd.get(k)
        if v:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    equity = yd.get('total_equity') or yd.get('stockholders_equity')
    shares = year_shares(yd)
    if equity and shares:
        return float(equity) / shares
    return None


def basis_problem(year_data, ref_shares):
    """연도 전체를 버려야 하는 주당 기준 불일치인가. 사유 문자열 또는 None."""
    shares = year_shares(year_data)
    if not shares or not ref_shares:
        return None
    ratio = shares / float(ref_shares)
    if ratio > BASIS_RANGE or ratio < 1.0 / BASIS_RANGE:
        return (f'주식수 {shares:,.0f} 가 최신 기준 {ref_shares:,.0f} 의 {ratio:.2f}배 - '
                f'주당 기준 불일치(액면분할 미반영 추정)')
    return None


def eps_basis_problem(year_data, ref_shares):
    """EPS 만 버려야 하는 불일치인가 (NI/EPS 역산 주식수 대조). 사유 또는 None."""
    yd = year_data or {}
    eps, ni = yd.get('eps'), yd.get('net_income')
    base = year_shares(yd) or (float(ref_shares) if ref_shares else None)
    if not eps or not ni or not base:
        return None
    implied = float(ni) / float(eps)
    if implied <= 0:
        return None
    ratio = implied / base
    if ratio > 1 + BASIS_TOL or ratio < 1 / (1 + BASIS_TOL):
        return (f'NI/EPS 역산 주식수 {implied:,.0f} 가 보고 주식수 {base:,.0f} 의 '
                f'{ratio:.2f}배 - EPS 주당 기준 불일치')
    return None


def build_series(closes, fin, ref_shares=None):
    """확정 연도 종가 + 연도별 재무로 PER/PBR 시계열을 만든다.

    반환: {per_series, pbr_series, detail, notes, skipped}
      - skipped : {연도: 제외 사유}
      - notes   : 산출 거부/부분 제외 사유 (그대로 warnings 로 나간다)
    """
    per_series, pbr_series, detail, notes = [], [], {}, []
    skipped, no_shares = {}, []

    for y in sorted(closes):
        yd = fin.get(str(y))
        if not yd:
            continue
        prob = basis_problem(yd, ref_shares)
        if prob:
            skipped[str(y)] = prob
            continue

        close = closes[y]
        eps = yd.get('eps')
        bps = year_bps(yd)
        if bps is None and (yd.get('total_equity') or yd.get('stockholders_equity')):
            no_shares.append(str(y))

        row = {'close': round(close, 2), 'eps': eps,
               'bps': round(bps, 2) if bps else None}

        eps_prob = eps_basis_problem(yd, ref_shares)
        if eps and eps > 0 and not eps_prob:
            per = close / float(eps)
            per_series.append(per)
            row['per'] = round(per, 2)
        elif eps_prob:
            notes.append(f'{y} PER 제외 - {eps_prob}')

        if bps and bps > 0:
            pbr = close / bps
            pbr_series.append(pbr)
            row['pbr'] = round(pbr, 2)

        detail[str(y)] = row

    if no_shares:
        notes.append(
            f'{", ".join(no_shares)}년 발행주식수 없음 - BPS/PBR 산출 거부. '
            f'오늘 주식수로 과거 자기자본을 나누면 자사주매입/증자 기업이 전부 틀린다.')
    if skipped:
        notes.append(
            f'{", ".join(sorted(skipped))}년 제외 - 주당 기준 불일치. '
            f'종가는 분할 반영(오늘 기준)인데 재무는 분할 전 기준이면 배수가 10배 틀린다.')
    return {'per_series': per_series, 'pbr_series': pbr_series,
            'detail': detail, 'notes': notes, 'skipped': skipped}


def _load_yfinance():
    try:
        import yfinance as yf
    except ImportError:
        print("[ERR] yfinance 미설치. pip install yfinance", file=sys.stderr)
        return None
    return yf


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

    yf = _load_yfinance()
    if yf is None:
        return 1

    t = yf.Ticker(ticker)
    info = {}
    try:
        info = t.info or {}
    except Exception as e:
        print(f"  [WARN] info 조회 실패: {type(e).__name__}")

    # 주당 기준 대조용 최신 주식수. yfinance 가 없으면 가장 최근 회계연도(최신 공시
    # 기준으로 재작성된 값)를 대용으로 쓴다.
    ref_shares = info.get('sharesOutstanding') or info.get('impliedSharesOutstanding')
    if not ref_shares and fin:
        ref_shares = year_shares(fin[max(fin, key=lambda k: str(k))])

    # 연말 종가
    hist = t.history(period='7y', interval='1d', auto_adjust=False)
    if hist is None or hist.empty:
        print("[ERR] 주가 이력 조회 실패.")
        return 1
    year_end = hist.groupby(hist.index.year).tail(1)
    rows = [(int(idx.year), float(row['Close'])) for idx, row in year_end.iterrows()]
    closes, excluded_years = confirmed_year_closes(rows, date.today().year)

    current_price = float(info.get('currentPrice') or info.get('regularMarketPrice') or 0)
    if not current_price:
        current_price = float(hist['Close'].iloc[-1])
    current_per = float(info.get('trailingPE') or 0)
    current_pbr = float(info.get('priceToBook') or 0)
    current_fwd_per = float(info.get('forwardPE') or 0)

    built = build_series(closes, fin, ref_shares)
    per_series = built['per_series']
    pbr_series = built['pbr_series']
    detail = built['detail']
    warnings = list(built['notes'])

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
        'excluded_years': excluded_years,
        'skipped_years': built['skipped'],
        'ref_shares': float(ref_shares) if ref_shares else None,
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
    if excluded_years:
        print(f"  진행 중인 당해년도 제외: {excluded_years} (연말 종가가 아직 없다)")
    print(f"  {'연도':<6} {'종가':>10} {'EPS':>8} {'PER':>8} {'BPS':>10} {'PBR':>8}")
    for y in sorted(detail):
        r = detail[y]
        print(f"  {y:<6} {r['close']:>10.2f} {(r.get('eps') or 0):>8.2f} "
              f"{(r.get('per') or 0):>8.2f} {(r.get('bps') or 0):>10.2f} {(r.get('pbr') or 0):>8.2f}")
    for y, why in sorted(built['skipped'].items()):
        print(f"  {y:<6} [제외] {why}")
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
