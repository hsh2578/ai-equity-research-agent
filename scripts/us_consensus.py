"""
US 종목 컨센서스 + 추정치 리비전 추이 수집 (v5.5 신설)

KR 종목의 Wisereport 컨센 추이 / FnGuide 3년 추정에 대응하는 미국판.
yfinance 가 이미 제공하는 데이터를 쓰므로 추가 API 키가 필요 없다.

수집 항목:
  - earnings_estimate  : 0q/+1q/0y/+1y EPS 컨센 (평균/최저/최고/애널리스트 수/성장률)
  - revenue_estimate   : 동일 기간 매출 컨센
  - eps_trend          : current / 7d / 30d / 60d / 90d 전 EPS 컨센 (= 리비전 추이)
  - eps_revisions      : 최근 7일/30일 상향-하향 건수
  - growth_estimates   : 종목 vs 산업/섹터/지수 성장률
  - analyst_price_targets : 목표가 low/high/mean/median + 현재가
  - recommendations_summary : strongBuy/buy/hold/sell/strongSell 분포
  - upgrades_downgrades: 최근 90일 등급 변경 이력

파생 지표 (리포트 s10 컨센서스 섹션에 직접 인용):
  - revision_momentum_90d : 0y / +1y EPS 컨센이 90일간 몇 % 변했나
  - net_revisions_30d     : 상향 건수 - 하향 건수 (30일)
  - consensus_direction   : UP / DOWN / FLAT 자동 판정

사용법:
    python scripts/us_consensus.py NVDA
    python scripts/us_consensus.py AMD --dir data/AMD

출력: data/{TICKER}/_us_consensus.json
"""
import sys
import io
import os
import json
from datetime import datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    import yfinance as yf
except ImportError:
    print("[ERR] yfinance 미설치. pip install yfinance", file=sys.stderr)
    sys.exit(1)

import pandas as pd


# eps_trend / eps_revisions 인덱스 라벨 -> 한글 설명
PERIOD_LABEL = {
    '0q': '당분기',
    '+1q': '다음분기',
    '0y': '당해년도',
    '+1y': '내년',
    '+5y': '5년',
    '-5y': '과거5년',
}


def _num(v):
    """NaN / None / numpy 타입을 JSON 안전한 float 또는 None 으로."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _df_to_records(df):
    """DataFrame -> {index: {col: value}} (NaN 제거)."""
    if df is None or not hasattr(df, 'empty') or df.empty:
        return {}
    out = {}
    for idx, row in df.iterrows():
        key = str(idx)
        out[key] = {str(c): _num(row[c]) for c in df.columns}
    return out


def _pct_change(new, old):
    if new is None or old is None or old == 0:
        return None
    return (new - old) / abs(old) * 100


def collect(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    out = {
        '_description': f'{ticker} 컨센서스 + 리비전 추이 (yfinance)',
        '_collected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'ticker': ticker.upper(),
        'warnings': [],
    }

    # --- 1. EPS / 매출 컨센 ---
    for attr, key in (('earnings_estimate', 'eps_estimate'),
                      ('revenue_estimate', 'revenue_estimate')):
        try:
            out[key] = _df_to_records(getattr(t, attr))
        except Exception as e:
            out[key] = {}
            out['warnings'].append(f'{attr} 조회 실패: {type(e).__name__}')

    # --- 2. 리비전 추이 (핵심) ---
    try:
        out['eps_trend'] = _df_to_records(t.eps_trend)
    except Exception as e:
        out['eps_trend'] = {}
        out['warnings'].append(f'eps_trend 조회 실패: {type(e).__name__}')

    try:
        out['eps_revisions'] = _df_to_records(t.eps_revisions)
    except Exception as e:
        out['eps_revisions'] = {}
        out['warnings'].append(f'eps_revisions 조회 실패: {type(e).__name__}')

    try:
        out['growth_estimates'] = _df_to_records(t.growth_estimates)
    except Exception as e:
        out['growth_estimates'] = {}

    # --- 3. 목표가 / 투자의견 분포 ---
    try:
        pt = t.analyst_price_targets
        out['price_targets'] = {k: _num(v) for k, v in dict(pt).items()} if pt is not None else {}
    except Exception as e:
        out['price_targets'] = {}
        out['warnings'].append(f'analyst_price_targets 조회 실패: {type(e).__name__}')

    try:
        out['recommendations'] = _df_to_records(t.recommendations_summary)
    except Exception:
        out['recommendations'] = {}

    # --- 4. 최근 90일 등급 변경 ---
    try:
        ud = t.upgrades_downgrades
        if ud is not None and not ud.empty:
            cutoff = pd.Timestamp(datetime.now() - timedelta(days=90))
            idx = ud.index
            if idx.tz is not None:
                cutoff = cutoff.tz_localize(idx.tz)
            recent = ud[idx >= cutoff]
            out['upgrades_downgrades_90d'] = [
                {
                    'date': str(i.date()) if hasattr(i, 'date') else str(i),
                    'firm': str(r.get('Firm', '')),
                    'from': str(r.get('FromGrade', '')),
                    'to': str(r.get('ToGrade', '')),
                    'action': str(r.get('Action', '')),
                }
                for i, r in recent.iterrows()
            ][:40]
        else:
            out['upgrades_downgrades_90d'] = []
    except Exception as e:
        out['upgrades_downgrades_90d'] = []
        out['warnings'].append(f'upgrades_downgrades 조회 실패: {type(e).__name__}')

    # --- 5. 파생 지표 ---
    derived = {}
    trend = out.get('eps_trend', {})
    for period in ('0y', '+1y'):
        row = trend.get(period)
        if not row:
            continue
        cur = row.get('current')
        d90 = row.get('90daysAgo')
        d30 = row.get('30daysAgo')
        derived[f'revision_{period}_90d_pct'] = _pct_change(cur, d90)
        derived[f'revision_{period}_30d_pct'] = _pct_change(cur, d30)
        derived[f'eps_{period}_current'] = cur

    rev = out.get('eps_revisions', {})
    for period in ('0y', '+1y'):
        row = rev.get(period)
        if not row:
            continue
        up = row.get('upLast30days') or 0
        # yfinance 컬럼명이 대소문자 혼용(downLast30days) 이라 양쪽 모두 시도
        down = row.get('downLast30days')
        if down is None:
            down = row.get('downLast30Days') or 0
        derived[f'net_revisions_{period}_30d'] = up - down
        derived[f'up_revisions_{period}_30d'] = up
        derived[f'down_revisions_{period}_30d'] = down

    # 컨센 방향 자동 판정: +1y 90일 변화 기준
    mom = derived.get('revision_+1y_90d_pct')
    if mom is None:
        derived['consensus_direction'] = 'UNKNOWN'
    elif mom >= 3:
        derived['consensus_direction'] = 'UP'
    elif mom <= -3:
        derived['consensus_direction'] = 'DOWN'
    else:
        derived['consensus_direction'] = 'FLAT'

    out['derived'] = derived

    # --- 6. 데이터 신선도 경고 ---
    if not trend:
        out['warnings'].append('eps_trend 비어있음 - 컨센 추이 인용 금지')
    n_analysts = None
    est0y = out.get('eps_estimate', {}).get('0y', {})
    if est0y:
        n_analysts = est0y.get('numberOfAnalysts')
    if n_analysts is not None and n_analysts < 5:
        out['warnings'].append(
            f'당해년도 애널리스트 {int(n_analysts)}명 - 컨센 신뢰도 낮음, 단일 추정 취급')

    return out


def print_summary(d: dict):
    print(f"\n{'=' * 62}")
    print(f"  {d['ticker']} 컨센서스 스냅샷")
    print(f"{'=' * 62}")

    est = d.get('eps_estimate', {})
    if est:
        print("\n[EPS 컨센]")
        print(f"  {'기간':<10} {'평균':>10} {'최저':>10} {'최고':>10} {'분석가':>7}")
        for k in ('0q', '+1q', '0y', '+1y'):
            r = est.get(k)
            if not r:
                continue
            lab = PERIOD_LABEL.get(k, k)
            print(f"  {lab:<10} {r.get('avg') or 0:>10.2f} {r.get('low') or 0:>10.2f} "
                  f"{r.get('high') or 0:>10.2f} {int(r.get('numberOfAnalysts') or 0):>7}")

    trend = d.get('eps_trend', {})
    if trend:
        print("\n[EPS 컨센 리비전 추이] (Wisereport 컨센 추이 대응)")
        print(f"  {'기간':<10} {'현재':>10} {'30일전':>10} {'90일전':>10} {'90일변화':>10}")
        for k in ('0y', '+1y'):
            r = trend.get(k)
            if not r:
                continue
            lab = PERIOD_LABEL.get(k, k)
            chg = _pct_change(r.get('current'), r.get('90daysAgo'))
            chg_s = f"{chg:+.1f}%" if chg is not None else "N/A"
            print(f"  {lab:<10} {r.get('current') or 0:>10.2f} {r.get('30daysAgo') or 0:>10.2f} "
                  f"{r.get('90daysAgo') or 0:>10.2f} {chg_s:>10}")

    dv = d.get('derived', {})
    if dv:
        print(f"\n[방향 판정] {dv.get('consensus_direction')}")
        for k in ('0y', '+1y'):
            net = dv.get(f'net_revisions_{k}_30d')
            if net is None:
                continue
            print(f"  {PERIOD_LABEL.get(k, k)} 30일 순리비전: {net:+.0f}건 "
                  f"(상향 {int(dv.get(f'up_revisions_{k}_30d') or 0)} / "
                  f"하향 {int(dv.get(f'down_revisions_{k}_30d') or 0)})")

    pt = d.get('price_targets', {})
    if pt:
        print("\n[목표가]")
        print(f"  현재 {pt.get('current') or 0:.2f} / 평균 {pt.get('mean') or 0:.2f} "
              f"/ 최저 {pt.get('low') or 0:.2f} / 최고 {pt.get('high') or 0:.2f}")

    ud = d.get('upgrades_downgrades_90d', [])
    if ud:
        print(f"\n[최근 90일 등급 변경] {len(ud)}건 (최신 5건)")
        for r in ud[:5]:
            print(f"  {r['date']}  {r['firm']:<22} {r['from']} -> {r['to']} ({r['action']})")

    for w in d.get('warnings', []):
        print(f"\n  [WARN] {w}")


def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/us_consensus.py {TICKER} [--dir data/{TICKER}]")
        return 1

    ticker = sys.argv[1].upper()
    out_dir = f'data/{ticker}'
    if '--dir' in sys.argv:
        out_dir = sys.argv[sys.argv.index('--dir') + 1]

    print(f"[1/1] {ticker} 컨센서스 수집 (yfinance)...")
    d = collect(ticker)
    print_summary(d)

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, '_us_consensus.json')
    json.dump(d, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"\n[OK] saved: {path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
