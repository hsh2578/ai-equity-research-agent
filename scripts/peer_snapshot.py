"""
STEP 2.3: Peer 시총/PER/PBR KIS API 실시간 일괄 조회

사용법:
    python scripts/peer_snapshot.py {종목명} [업종키] [name:code ...]
    python scripts/peer_snapshot.py {종목명} --peers "고려아연:010130,LS:006260"

업종키: kpop, auto, semicon, battery, shipbuild, finance, pharma, retail, it, air, default

v5.7 CLI 가드
-------------
초판은 `sys.argv[2]` 를 무조건 업종키로 읽어 `--peers` 같은 플래그가 업종키로
해석됐고, name:code 만 주면 그것이 업종키로 먹혔다. US 판(peer_snapshot_us.py)
초판은 `args[args.index('--peers') + 1]` 을 직접 읽어 플래그가 마지막 인자일 때
IndexError 로 죽었다. 두 문제를 같은 규칙으로 막는다:
decision_log.flag_value (값 없음/다음 토큰이 또 다른 플래그면 default) 를 재사용하고,
위치 인자는 ':' 유무로 업종키와 name:code 를 가른다.
"""
import sys
import io
import os
import json

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from decision_log import flag_value


# 업종별 기본 Peer 템플릿
PEER_TEMPLATES = {
    'kpop': {'HYBE': '352820', 'SM': '041510', 'JYP': '035900', 'YG': '122870'},
    'auto': {'현대차': '005380', '기아': '000270', '현대모비스': '012330'},
    'semicon': {'SK하이닉스': '000660', 'DB하이텍': '000990', 'LG전자': '066570', 'LG이노텍': '011070'},
    'battery': {'LG에너지솔루션': '373220', '삼성SDI': '006400', '에코프로비엠': '247540', '포스코퓨처엠': '003670'},
    'shipbuild': {'한국조선해양': '009540', '삼성중공업': '010140', '현대미포조선': '010620'},
    'finance': {'KB금융': '105560', '신한지주': '055550', '하나금융지주': '086790', '우리금융지주': '316140'},
    'pharma': {'삼성바이오로직스': '207940', '셀트리온': '068270', '유한양행': '000100'},
    'retail': {'이마트': '139480', '롯데쇼핑': '023530', '신세계': '004170', 'BGF리테일': '282330'},
    'air': {'대한항공': '003490', '아시아나항공': '020560', '제주항공': '089590', '티웨이항공': '091810'},
    'it': {'네이버': '035420', '카카오': '035720', '크래프톤': '259960'},
    'default': {},
}


def parse_args(args):
    """CLI 인자 -> (종목명, 업종키, [name:code, ...]).

    args 는 sys.argv[1:]. 플래그가 마지막 인자여도 IndexError 를 내지 않는다
    (decision_log.flag_value 와 동일 규칙).
    """
    args = list(args or [])
    stock_name = args[0] if args and not args[0].startswith('--') else None
    rest = args[1:] if stock_name is not None else args

    # --peers 값은 flag_value 가 안전하게 꺼낸다. 그 값을 위치 인자로 다시 세면 안 되므로
    # 소비한 인덱스를 기록해 둔다.
    peers_csv = flag_value(rest, '--peers')
    consumed = set()
    if '--peers' in rest:
        i = rest.index('--peers')
        consumed.add(i)
        if peers_csv is not None:
            consumed.add(i + 1)

    industry_key = None
    extra = []
    for i, tok in enumerate(rest):
        if i in consumed or tok.startswith('--'):
            continue
        if ':' in tok:
            extra.append(tok)
        elif industry_key is None:
            industry_key = tok

    for chunk in (peers_csv or '').split(','):
        chunk = chunk.strip()
        if ':' in chunk:
            extra.append(chunk)

    return stock_name, industry_key or 'default', extra


def resolve_peers(industry_key, extra_peers):
    """업종 템플릿 + name:code 인자를 병합한 {이름: 코드}. 인자가 우선."""
    peers = dict(PEER_TEMPLATES.get(industry_key, {}))
    for p in extra_peers or []:
        if ':' in p:
            name, code = p.split(':', 1)
            name, code = name.strip(), code.strip()
            if name and code:
                peers[name] = code
    return peers


def main(stock_name, industry_key='default', extra_peers=None):
    from kis_api import get_current_price

    peers = resolve_peers(industry_key, extra_peers)

    if not peers:
        print(f"[WARN] Peer 목록 없음. 업종키 '{industry_key}' 확인 또는 name:code 인자 제공.")
        print("       예: python scripts/peer_snapshot.py 풍산 --peers \"고려아연:010130,LS:006260\"")
        return 1

    os.makedirs(f'data/{stock_name}', exist_ok=True)
    snapshot = {}
    for peer_name, peer_code in peers.items():
        try:
            p = get_current_price(peer_code)
            snapshot[peer_name] = {
                'code': peer_code,
                'price': int(p.get('현재가', 0)),
                'market_cap_uk': int(p.get('시가총액', 0)),
                'per': float(p.get('PER', 0)),
                'pbr': float(p.get('PBR', 0)),
                'eps': float(p.get('EPS', 0)),
                'bps': float(p.get('BPS', 0)),
                'high_52w': int(p.get('52주최고', 0)),
                'low_52w': int(p.get('52주최저', 0)),
            }
            print(f"  {peer_name}: 시총 {snapshot[peer_name]['market_cap_uk']:,}억, "
                  f"PER {snapshot[peer_name]['per']}, PBR {snapshot[peer_name]['pbr']}")
        except Exception as e:
            print(f"  [ERR] {peer_name} ({peer_code}): {e}")

    out = f'data/{stock_name}/_peer_snapshot.json'
    json.dump(snapshot, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"[OK] saved: {out} ({len(snapshot)} peers)")
    return 0


if __name__ == '__main__':
    stock_name, industry_key, extra = parse_args(sys.argv[1:])
    if not stock_name:
        print("usage: python scripts/peer_snapshot.py {종목명} [업종키] [name:code ...]")
        print("       python scripts/peer_snapshot.py {종목명} --peers \"이름:코드,이름2:코드2\"")
        sys.exit(1)
    sys.exit(main(stock_name, industry_key, extra))
