"""
STEP 1.6: 변동성·베타 계산 (100일 회귀)

사용법:
    python scripts/volatility_beta.py {종목명} {종목코드} [시장코드]
    시장코드를 주지 않으면 종목의 상장 시장을 감지해 자동 선택한다.
      069500 = KODEX 200 (코스피)
      229200 = KODEX 코스닥150 (코스닥)

왜 자동 감지인가 (2026-09 에프에스티 사고)
------------------------------------------
에프에스티(036810)는 코스닥인데 기본값 069500 으로 회귀해 Beta=0.76 (R2=0.363) 이
나왔다. FnGuide 실측은 1.837 -- 2.4배 차이다. 에러도 경고도 없었다.
이 베타는 포지션 사이징과 Sharpe 로 그대로 흘러 들어간다.

그래서 이 스크립트는:
  1. 시장을 감지해 맞는 벤치마크를 고르고,
  2. **두 벤치마크 결과를 모두 저장**해 사람이 괴리를 볼 수 있게 하고,
  3. R2 가 낮으면 'UNRELIABLE' 로 표시한다. 조용히 쓰이면 안 된다.
"""
import sys
import os
import json
import time

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from kis_api import get_daily_price

KOSPI200 = '069500'
KOSDAQ150 = '229200'

_LISTING_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              '..', 'data', '_krx_listing.json')
_CACHE_TTL_SEC = 7 * 24 * 3600


def benchmark_for(market):
    """상장 시장 문자열 -> 벤치마크 ETF 코드. 모르면 None (기본값으로 때우지 않는다)."""
    if not market:
        return None
    m = str(market).upper()
    if 'KOSDAQ' in m or '코스닥' in m:
        return KOSDAQ150
    if 'KOSPI' in m or '유가증권' in m or '코스피' in m:
        return KOSPI200
    return None


def regress(stock_closes, mkt_closes):
    """종가 배열 두 개 -> {beta, r2, vol_annual, n}.

    산출 불가(표본 부족 / 분산 0)는 **None** 이다. 0 을 반환하면
    '베타 0인 종목'으로 읽혀 조용히 통과한다.
    """
    s = np.asarray(stock_closes, dtype=float)
    m = np.asarray(mkt_closes, dtype=float)
    s_ret = np.diff(np.log(s))
    m_ret = np.diff(np.log(m))
    n = int(min(len(s_ret), len(m_ret)))
    s_ret, m_ret = s_ret[:n], m_ret[:n]

    out = {'beta': None, 'r2': None, 'vol_annual': None, 'n': n}
    if n < 3:
        return out

    out['vol_annual'] = float(np.std(s_ret) * np.sqrt(252))

    # 공분산과 분산을 **같은 공분산 행렬**에서 뽑는다.
    # np.cov 는 ddof=1, np.var 는 ddof=0 이라 둘을 섞으면 베타가 n/(n-1) 배 부풀려진다.
    cm = np.cov(s_ret, m_ret)
    var_mkt = float(cm[1, 1])
    if var_mkt == 0.0 or float(np.std(s_ret)) == 0.0:
        return out

    out['beta'] = float(cm[0, 1]) / var_mkt
    out['r2'] = float(np.corrcoef(s_ret, m_ret)[0, 1]) ** 2
    return out


def pick_by_r2(results):
    """{벤치마크코드: regress결과} -> R2 가 가장 높은 벤치마크 코드. 전부 불가면 None."""
    best, best_r2 = None, None
    for code, res in results.items():
        r2 = (res or {}).get('r2')
        if r2 is None:
            continue
        if best_r2 is None or r2 > best_r2:
            best, best_r2 = code, r2
    return best


def reliability(r2):
    """R2 -> 'OK' / 'WEAK' / 'UNRELIABLE'."""
    if r2 is None or r2 < 0.2:
        return 'UNRELIABLE'
    if r2 < 0.5:
        return 'WEAK'
    return 'OK'


def detect_market(stock_code):
    """종목코드 -> 'KOSPI' / 'KOSDAQ' / None. FDR 상장목록을 7일 캐시한다."""
    listing = _load_listing_cache()
    if listing is None:
        listing = _fetch_listing()
    if not listing:
        return None
    return listing.get(str(stock_code).zfill(6))


def _load_listing_cache():
    try:
        if time.time() - os.stat(_LISTING_CACHE).st_mtime > _CACHE_TTL_SEC:
            return None
        with open(_LISTING_CACHE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _fetch_listing():
    try:
        import FinanceDataReader as fdr
    except ImportError:
        print("[WARN] FinanceDataReader 없음 -- 시장 자동 감지 불가")
        return None
    out = {}
    # 'KRX-DESC' 는 Market 컬럼을 함께 준다. FDR 0.9.101 에서 'KRX'/'KOSDAQ' 는
    # JSONDecodeError 로 죽고 'KRX' 는 KRX_ID/KRX_PW 로그인을 요구한다.
    try:
        df = fdr.StockListing('KRX-DESC')
        for code, market in zip(df['Code'].astype(str), df['Market'].astype(str)):
            out[code.zfill(6)] = market
    except Exception as e:
        print(f"[WARN] KRX-DESC 상장목록 조회 실패: {type(e).__name__}: {e}")

    if not out:
        try:
            from pykrx import stock as pk
            today = time.strftime('%Y%m%d')
            for market in ('KOSPI', 'KOSDAQ'):
                for code in pk.get_market_ticker_list(today, market=market):
                    out[str(code).zfill(6)] = market
        except Exception as e:
            print(f"[WARN] pykrx 상장목록 조회 실패: {type(e).__name__}: {e}")

    if not out:
        return None
    try:
        os.makedirs(os.path.dirname(_LISTING_CACHE), exist_ok=True)
        tmp = _LISTING_CACHE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(out, f)
        os.replace(tmp, _LISTING_CACHE)
    except OSError as e:
        print(f"[WARN] 상장목록 캐시 저장 실패: {e}")
    return out


def main(stock_name, stock_code, mkt_code=None):
    stock_daily = get_daily_price(stock_code, 100)
    if not stock_daily:
        print("[ERR] 종목 일봉 데이터 없음")
        return 1
    stock_closes = np.array([float(r['종가']) for r in stock_daily[::-1]])

    # 두 벤치마크를 모두 회귀한다 -- 괴리 자체가 정보다.
    results = {}
    for code in (KOSPI200, KOSDAQ150):
        daily = None
        for attempt in range(3):
            try:
                daily = get_daily_price(code, 100)
                break
            except Exception as e:
                # KIS 는 동시 호출이 몰리면 500 을 낸다. 한쪽 벤치마크가 실패해도
                # 나머지로 계속 간다 -- 여기서 죽으면 STEP 1.5 전체가 멈춘다.
                print(f"[WARN] 벤치마크 {code} 조회 실패({attempt + 1}/3): {type(e).__name__}")
                time.sleep(1.5 * (attempt + 1))
        if not daily:
            print(f"[WARN] 벤치마크 {code} 일봉 없음 -- 건너뜀")
            continue
        results[code] = regress(stock_closes,
                                np.array([float(r['종가']) for r in daily[::-1]]))

    if not results:
        print("[ERR] 벤치마크 일봉을 하나도 받지 못했다")
        return 1

    market = None
    if mkt_code:
        chosen, how = mkt_code, 'cli'
    else:
        market = detect_market(stock_code)
        chosen, how = benchmark_for(market), 'listing'
        if chosen is None or chosen not in results:
            chosen, how = pick_by_r2(results), 'r2_fallback'
            print(f"[WARN] 시장 감지 실패(market={market!r}) -- R2 가 높은 벤치마크로 대체")
    if chosen not in results:
        print(f"[ERR] 선택한 벤치마크 {chosen} 결과 없음")
        return 1

    res = results[chosen]
    other = KOSDAQ150 if chosen == KOSPI200 else KOSPI200
    rel = reliability(res['r2'])

    out = {
        'beta': res['beta'],
        'r2': res['r2'],
        'vol_annual': res['vol_annual'],
        'market_code': chosen,
        'market': market,
        'selected_by': how,
        'reliability': rel,
        'n_days': res['n'],
        'alternates': results,
    }
    os.makedirs(f'data/{stock_name}', exist_ok=True)
    path = f'data/{stock_name}/_volatility_beta.json'
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

    b = f"{res['beta']:.2f}" if res['beta'] is not None else "산출불가"
    r2s = f"{res['r2']:.3f}" if res['r2'] is not None else "-"
    vol = f"{res['vol_annual'] * 100:.1f}%" if res['vol_annual'] is not None else "-"
    print(f"[OK] Beta={b} (R2={r2s}, {rel})  sigma_annual={vol}  "
          f"(mkt={chosen}, market={market}, by={how}, n={res['n']})")
    ob = results.get(other) or {}
    if ob.get('beta') is not None:
        print(f"     참고: {other} 기준 Beta={ob['beta']:.2f} (R2={ob['r2']:.3f})")
    if rel != 'OK':
        print("[WARN] R2 가 낮다 -- 베타를 포지션 사이징/Sharpe 에 단정적으로 쓰지 말 것")
    print(f"[OK] saved: {path}")
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("usage: python scripts/volatility_beta.py {종목명} {종목코드} [시장코드]")
        sys.exit(1)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None))
