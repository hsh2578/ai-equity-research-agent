"""
US Peer 실시간 스냅샷 (KR peer_snapshot.py 의 미국판, v5.5 신설)

JYP v1 사고(Peer 시총/PER 를 추정치로 기재)의 미국판 재발을 막는다.
기존에는 /research 실행 중 인라인 코드로 만들어 재현성이 없었다.

사용법:
    python scripts/peer_snapshot_us.py AMD semicon
    python scripts/peer_snapshot_us.py AMD --peers "NVIDIA:NVDA,Intel:INTC,Broadcom:AVGO"

출력: data/{TICKER}/_peer_snapshot.json

스키마 (두 소비자를 동시에 만족시켜야 한다)
--------------------------------------------
- verify_numbers_us.py B1/B3 : `market_cap_b`($B) / `per_trailing` / `price` 를 읽는다.
- generate_all.py 검증 #10   : KR 판과 같은 `market_cap_uk` / `per` 를 읽는다.
                               (`snap.get("market_cap_uk", 0)` / `snap.get("per", 0)`)

초판은 앞의 두 키만 썼다. generate_all 은 뒤의 두 키를 기본값 0 으로 읽었고,
값이 0 이면 비교를 건너뛰도록 돼 있어서 **US 종목 Peer 교차검증이 에러 한 줄 없이
통째로 무력화**됐다 -- JYP v1(Peer 추정치 기재) 의 미국판 재발 통로.
지금은 두 스키마를 **함께** 제공한다 (기존 키는 그대로 유지, 호환 키만 추가).

단위: generate_all 은 analysis.json `peers[].market_cap` 문자열을 숫자로 파싱해
      `market_cap_uk` 와 비율 비교한다. US 리포트의 그 문자열은 $B 표기이므로
      `market_cap_uk` 에도 **$B 값**을 넣는다 (KR 은 억원, US 는 $B -- 시장별로
      "그 시장 리포트가 쓰는 단위" 라는 규칙이 동일하다).
"""
import sys
import io
import os
import json
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
# 아래 decision_log 도 import 시점에 stdout 을 다시 감싼다. 참조를 잡아두지 않으면
# 이 래퍼가 GC 되면서 공유 buffer 를 닫아 이후 print 가 ValueError 를 낸다.
_STDOUT_KEEP = sys.stdout
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decision_log import flag_value   # --flag 가 마지막 인자일 때 IndexError 방지


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


def build_record(ticker: str, info: dict) -> dict:
    """yfinance `.info` dict -> 스냅샷 레코드 (네트워크 없는 순수 함수).

    `market_cap_uk` / `per` 는 generate_all.py 검증 #10 이 읽는 호환 키다.
    결측이면 0 이 아니라 None 으로 둔다 -- 0 은 "값 없음" 이 아니라
    "시총 0 / PER 0" 으로 읽혀 검증을 조용히 통과시킨다.
    """
    info = info or {}
    cap = _f(info.get('marketCap'))
    cap_b = round(cap / 1e9, 2) if cap else None
    per_trailing = _f(info.get('trailingPE'))
    rec = {
        'ticker': ticker,
        'price': _f(info.get('currentPrice') or info.get('regularMarketPrice')),
        'market_cap_b': cap_b,
        'per_trailing': per_trailing,
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
    # --- KR peer_snapshot.py 와 동일한 키 이름 (generate_all.py 검증 #10 용) ---
    rec['market_cap_uk'] = cap_b          # US 리포트 표기 단위인 $B
    rec['per'] = per_trailing             # TTM PER
    return rec


def snap(name: str, ticker: str) -> dict:
    import yfinance as yf               # 지연 import -- 테스트/파싱에는 불필요
    t = yf.Ticker(ticker)
    try:
        info = t.info or {}
    except Exception as e:
        print(f"  [WARN] {name}({ticker}) info 조회 실패: {type(e).__name__}")
        return {'ticker': ticker, 'error': type(e).__name__}
    return build_record(ticker, info)


def parse_peers(raw) -> dict:
    """'NVIDIA:NVDA,Intel:INTC' -> {'NVIDIA': 'NVDA', 'Intel': 'INTC'}"""
    peers = {}
    for item in str(raw or '').split(','):
        if ':' in item:
            n, c = item.split(':', 1)
            n, c = n.strip(), c.strip().upper()
            if n and c:
                peers[n] = c
    return peers


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: python scripts/peer_snapshot_us.py {TICKER} [업종키] "
              "[--peers \"Name:TICK,Name2:TICK2\"]")
        print(f"  업종키: {', '.join(SECTORS)}")
        return 1

    main_ticker = args[0].upper()
    peers = {}

    if '--peers' in args:
        # 초판은 args[index+1] 을 직접 읽어 '--peers' 가 마지막 인자면 IndexError 였다.
        # decision_log.flag_value 는 값 없음/다음 토큰이 또 다른 플래그를 default 로 처리한다.
        peers = parse_peers(flag_value(args, '--peers'))
        if not peers:
            print("[ERR] --peers 값이 비어 있다. \"Name:TICK,Name2:TICK2\" 형식으로 줄 것.")
            return 1
    elif len(args) > 1 and not args[1].startswith('--'):
        key = args[1]
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
