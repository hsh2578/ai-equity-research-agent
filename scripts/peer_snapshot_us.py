"""
US Peer 실시간 스냅샷 (KR peer_snapshot.py 의 미국판, v5.5 신설)

JYP v1 사고(Peer 시총/PER 를 추정치로 기재)의 미국판 재발을 막는다.
기존에는 /research 실행 중 인라인 코드로 만들어 재현성이 없었다.

사용법:
    python scripts/peer_snapshot_us.py AMD semicon
    python scripts/peer_snapshot_us.py AMD --peers "NVIDIA:NVDA,Intel:INTC,Broadcom:AVGO"

출력: data/{TICKER}/_peer_snapshot.json
      (generate_all.py 검증 #10 / verify_numbers_us.py B1 이 읽는 스키마와 동일)
"""
import sys
import io
import os
import json
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    import yfinance as yf
except ImportError:
    print("[ERR] yfinance 미설치. pip install yfinance", file=sys.stderr)
    sys.exit(1)


# 업종키 -> Peer 목록 (KR peer_snapshot.py 의 업종키 체계와 동일 사상)
SECTORS = {
    'semicon':   {'NVIDIA': 'NVDA', 'AMD': 'AMD', 'Intel': 'INTC', 'Broadcom': 'AVGO', 'Qualcomm': 'QCOM'},
    'semieq':    {'ASML': 'ASML', 'Applied Materials': 'AMAT', 'Lam Research': 'LRCX', 'KLA': 'KLAC', 'TEL': 'TOELY'},
    'software':  {'Microsoft': 'MSFT', 'Oracle': 'ORCL', 'Salesforce': 'CRM', 'Adobe': 'ADBE', 'ServiceNow': 'NOW'},
    'security':  {'Palo Alto': 'PANW', 'CrowdStrike': 'CRWD', 'Fortinet': 'FTNT', 'Zscaler': 'ZS', 'Check Point': 'CHKP'},
    'media':     {'Netflix': 'NFLX', 'Disney': 'DIS', 'Warner Bros': 'WBD', 'Paramount': 'PARA', 'Comcast': 'CMCSA'},
    'auto':      {'Tesla': 'TSLA', 'GM': 'GM', 'Ford': 'F', 'Rivian': 'RIVN', 'BYD': 'BYDDY'},
    'pharma':    {'UnitedHealth': 'UNH', 'Eli Lilly': 'LLY', 'Pfizer': 'PFE', 'Merck': 'MRK', 'AbbVie': 'ABBV'},
    'megacap':   {'Apple': 'AAPL', 'Microsoft': 'MSFT', 'Alphabet': 'GOOGL', 'Amazon': 'AMZN', 'Meta': 'META'},
    'retail':    {'Walmart': 'WMT', 'Costco': 'COST', 'Target': 'TGT', 'Amazon': 'AMZN', 'Kroger': 'KR'},
    'bank':      {'JPMorgan': 'JPM', 'Bank of America': 'BAC', 'Wells Fargo': 'WFC', 'Citigroup': 'C', 'Goldman': 'GS'},
}


def _f(v, default=None):
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def snap(name: str, ticker: str) -> dict:
    t = yf.Ticker(ticker)
    try:
        info = t.info or {}
    except Exception as e:
        print(f"  [WARN] {name}({ticker}) info 조회 실패: {type(e).__name__}")
        return {'ticker': ticker, 'error': type(e).__name__}

    cap = _f(info.get('marketCap'))
    return {
        'ticker': ticker,
        'price': _f(info.get('currentPrice') or info.get('regularMarketPrice')),
        'market_cap_b': round(cap / 1e9, 2) if cap else None,
        'per_trailing': _f(info.get('trailingPE')),
        'per_forward': _f(info.get('forwardPE')),
        'pbr': _f(info.get('priceToBook')),
        'ps_trailing': _f(info.get('priceToSalesTrailing12Months')),
        'ev_ebitda': _f(info.get('enterpriseToEbitda')),
        'revenue_growth': _f(info.get('revenueGrowth')),
        'op_margin': _f(info.get('operatingMargins')),
        'high_52w': _f(info.get('fiftyTwoWeekHigh')),
        'low_52w': _f(info.get('fiftyTwoWeekLow')),
        'target_price': _f(info.get('targetMeanPrice')),
        'beta': _f(info.get('beta')),
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python scripts/peer_snapshot_us.py {TICKER} [업종키] "
              "[--peers \"Name:TICK,Name2:TICK2\"]")
        print(f"  업종키: {', '.join(SECTORS)}")
        return 1

    main_ticker = sys.argv[1].upper()
    peers = {}

    if '--peers' in sys.argv:
        raw = sys.argv[sys.argv.index('--peers') + 1]
        for item in raw.split(','):
            if ':' in item:
                n, c = item.split(':', 1)
                peers[n.strip()] = c.strip().upper()
    elif len(sys.argv) > 2 and not sys.argv[2].startswith('--'):
        key = sys.argv[2]
        if key not in SECTORS:
            print(f"[ERR] 업종키 '{key}' 없음. 사용 가능: {', '.join(SECTORS)}")
            return 1
        peers = dict(SECTORS[key])
    else:
        print("[ERR] 업종키 또는 --peers 필요.")
        return 1

    # 본 종목이 Peer 목록에 없으면 맨 앞에 추가
    if main_ticker not in peers.values():
        peers = {main_ticker: main_ticker, **peers}

    print(f"[{main_ticker}] Peer 실시간 조회 {len(peers)}종목 (yfinance)")
    out = {}
    for name, tick in peers.items():
        out[name] = snap(name, tick)
        r = out[name]
        if 'error' in r:
            continue
        print(f"  {name:<18} {tick:<7} ${(r['price'] or 0):>9,.2f}  "
              f"시총 ${(r['market_cap_b'] or 0):>9,.1f}B  "
              f"PER {(r['per_trailing'] or 0):>7.1f}  "
              f"Fwd {(r['per_forward'] or 0):>6.1f}  "
              f"PBR {(r['pbr'] or 0):>6.1f}")

    # 검증: 본 종목 순위
    valid = {k: v for k, v in out.items() if v.get('market_cap_b')}
    if valid:
        by_cap = sorted(valid.items(), key=lambda kv: kv[1]['market_cap_b'], reverse=True)
        rank = [i for i, (k, v) in enumerate(by_cap, 1) if v['ticker'] == main_ticker]
        if rank:
            print(f"\n  시총 순위: {rank[0]}/{len(by_cap)}")
        fwd = {k: v['per_forward'] for k, v in valid.items() if v.get('per_forward')}
        if fwd and main_ticker in [v['ticker'] for v in valid.values()]:
            srt = sorted(fwd.items(), key=lambda kv: kv[1])
            names = [k for k, v in srt]
            mine = [k for k, v in valid.items() if v['ticker'] == main_ticker]
            if mine and mine[0] in names:
                print(f"  Forward PER 순위(저 -> 고): {names.index(mine[0]) + 1}/{len(names)}  "
                      f"[{' < '.join(f'{k} {v:.0f}' for k, v in srt)}]")

    out['_collected_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    os.makedirs(f'data/{main_ticker}', exist_ok=True)
    path = f'data/{main_ticker}/_peer_snapshot.json'
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"\n[OK] saved: {path}")
    print("  이 스냅샷과 다른 Peer 수치를 리포트에 쓰면 generate_all.py 검증 #10 이 차단한다.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
