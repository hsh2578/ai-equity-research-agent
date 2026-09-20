"""
해외 비교기업 실시간 스냅샷 (KR 종목용, yfinance) -- v5.24 신설

KR 리포트의 비교기업은 `peer_snapshot.py`(KIS) 가 국내 상장사만 잡는다. 그래서 신한이 실은
블룸버그 글로벌 피어 표(중국 10.9배·일본 25.1배)와 SK 가 엔진 가치에 쓴 바르질라 18.5배를
읽고도 본문에 못 넣었다(HD현대중공업 4판, 2026-09-20). 이 스크립트가 그 빈틈을 채운다.

사용법:
    python scripts/peer_snapshot_global.py HD현대중공업 shipbuild
    python scripts/peer_snapshot_global.py HD현대중공업 shipbuild --peers "바르질라:WRT1V.HE"

출력: data/{종목}/_peer_snapshot_global.json  (KIS 스냅샷 `_peer_snapshot.json` 은 건드리지 않는다)
      verify_facts D4 와 generate_all 검증 #10 이 이 파일을 KIS 스냅샷에 병합해 읽는다.

레코드 규칙
- `market_cap_uk` 는 **억원 환산**(검증기가 본문 "N억원" 과 비율 비교), `per` 는 후행(검증기가 비교하는 값).
- 결측은 0 이 아니라 None (0 은 검증을 조용히 통과시킨다 -- peer_snapshot_us.py 사고).
- `per_forward` 가 후행의 0.3배 미만·3배 초과면 값은 두되 `flags: ['forward_pe_suspect']` (가와사키重 실측 fPE 4.2 vs tPE 18.6).
  환율을 못 받으면 `market_cap_uk` None + `flags: ['fx_missing']`. **flags 가 있는 값은 리포트에 쓰지 않는다.**
"""
import io
import json
import os
import sys
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')  # 'Wärtsilä' 가 cp949 콘솔을 죽인다
_STDOUT_KEEP = sys.stdout
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decision_log import flag_value  # noqa: E402

# 업종키 -> {표시명: yfinance 티커}. 신한 2026-09-11 글로벌 피어 표 + SK 엔진 배수 근거(바르질라).
# 에버런스(옛 MAN ES)는 폭스바겐 자회사라 상장이 없다. 다른 업종은 --peers 로 넣는다(YAGNI).
GLOBAL_SECTORS = {
    'shipbuild': {'중국선박공업': '600150.SS', '양쯔장조선': 'BS6.SI', '미쓰비시중공업': '7011.T',
                  '가와사키중공업': '7012.T', '케펠': 'BN4.SI'},
    'engine': {'바르질라': 'WRT1V.HE'},
    'default': {},
}
FX_TICKER = {'USD': 'KRW=X'}  # 나머지 통화는 f'{CUR}KRW=X' (CNYKRW=X, JPYKRW=X, SGDKRW=X, EURKRW=X, HKDKRW=X)


def _f(v, default=None):
    try:
        return default if v is None else float(v)
    except (TypeError, ValueError):
        return default


def fx_to_krw(cur, cache, fetch=None):
    """통화 -> 원화 환율(1단위당 원). 실패면 None. cache 에 저장해 종목마다 다시 받지 않는다."""
    cur = (cur or '').upper()
    if cur == 'KRW':
        return 1.0
    if cur in cache:
        return cache[cur]
    if fetch is None:
        def fetch(tk):
            import yfinance as yf
            h = yf.Ticker(tk).history(period='5d')
            return float(h['Close'].dropna().iloc[-1]) if len(h) else None
    try:
        rate = fetch(FX_TICKER.get(cur, f'{cur}KRW=X'))
    except Exception:
        rate = None
    cache[cur] = _f(rate)
    return cache[cur]


def build_record(name, ticker, info, fx_rate):
    """yfinance `.info` + 환율 -> 레코드 (네트워크 없는 순수 함수)."""
    info = info or {}
    cap = _f(info.get('marketCap'))
    per = _f(info.get('trailingPE'))
    fper = _f(info.get('forwardPE'))
    flags = []
    cap_uk = round(cap * fx_rate / 1e8) if (cap and fx_rate) else None
    if cap and not fx_rate:
        flags.append('fx_missing')
    if per and fper and (fper < 0.3 * per or fper > 3 * per):
        flags.append('forward_pe_suspect')
    return {
        'ticker': ticker, 'name_en': info.get('shortName') or info.get('longName') or '',
        'exchange': info.get('exchange') or '', 'currency': (info.get('currency') or '').upper(),
        'price': _f(info.get('currentPrice') or info.get('regularMarketPrice')),
        'market_cap_local': cap, 'market_cap_uk': cap_uk,
        'per': per, 'per_forward': fper, 'pbr': _f(info.get('priceToBook')),
        'high_52w': _f(info.get('fiftyTwoWeekHigh')), 'low_52w': _f(info.get('fiftyTwoWeekLow')),
        'flags': flags,
    }


def snap(name, ticker, fx_cache):
    import yfinance as yf
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception as e:
        print(f"  [WARN] {name}({ticker}) info 조회 실패: {type(e).__name__}")
        return {'ticker': ticker, 'error': type(e).__name__}
    return build_record(name, ticker, info, fx_to_krw(info.get('currency'), fx_cache))


def resolve_peers(sector, extra_csv):
    peers = dict(GLOBAL_SECTORS.get(sector or 'default', {}))
    for chunk in str(extra_csv or '').split(','):
        if ':' in chunk:
            n, t = chunk.split(':', 1)
            if n.strip() and t.strip():
                peers[n.strip()] = t.strip().upper()
    return peers


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0].startswith('--'):
        print('usage: python scripts/peer_snapshot_global.py {종목명} [업종키] [--peers "이름:TICKER,이름:TICKER"]')
        print(f"  업종키: {', '.join(k for k in GLOBAL_SECTORS if k != 'default')}")
        return 1
    stock = args[0]
    sector = next((a for a in args[1:] if not a.startswith('--') and ':' not in a), None)
    if sector and sector not in GLOBAL_SECTORS:
        print(f"[ERR] 업종키 '{sector}' 없음. 사용 가능: {', '.join(GLOBAL_SECTORS)}")
        return 1
    peers = resolve_peers(sector, flag_value(args, '--peers'))
    if not peers:
        print('[ERR] 업종키 또는 --peers 필요.')
        return 1

    print(f'[{stock}] 해외 비교기업 {len(peers)}종목 (yfinance, 시총은 원화 환산)')
    fx, out = {}, {}
    for name, tick in peers.items():
        r = out[name] = snap(name, tick, fx)
        if 'error' in r:
            continue
        uk = f"{r['market_cap_uk']:,}억원" if r['market_cap_uk'] else 'n/a'
        print(f"  {name:<8} {tick:<10} {r['currency']:<4} 시총 {uk:>14}  후행 PER {(r['per'] or 0):>6.1f}  "
              f"선행 {(r['per_forward'] or 0):>6.1f}  PBR {(r['pbr'] or 0):>5.2f}" + (f"  [flags: {', '.join(r['flags'])}]" if r['flags'] else ''))
    out['_collected_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    out['_fx'] = {k: v for k, v in fx.items() if v}
    os.makedirs(f'data/{stock}', exist_ok=True)
    path = f'data/{stock}/_peer_snapshot_global.json'
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    bad = [n for n, r in out.items() if isinstance(r, dict) and (r.get('flags') or 'error' in r)]
    print(f'\n[OK] saved: {path}  환율 {out["_fx"]}')
    if bad:
        print(f"  flags/error 있는 종목은 리포트에 쓰지 않는다: {', '.join(bad)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
