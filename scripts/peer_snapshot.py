"""
STEP 2.3: Peer 시총/PER/PBR KIS API 실시간 일괄 조회

사용법:
    python scripts/peer_snapshot.py {종목명} {업종키} [peer1_code peer2_code ...]

업종키: kpop, auto, semicon, battery, shipbuild, finance, pharma, retail, it, default
"""
import sys
import io
import os
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from kis_api import get_current_price


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


def main(stock_name, industry_key='default', extra_peers=None):
    peers = dict(PEER_TEMPLATES.get(industry_key, {}))
    if extra_peers:
        for p in extra_peers:
            if ':' in p:
                name, code = p.split(':', 1)
                peers[name] = code

    if not peers:
        print(f"[WARN] Peer 목록 없음. 업종키 '{industry_key}' 확인 또는 name:code 인자 제공.")
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
    if len(sys.argv) < 2:
        print("usage: python scripts/peer_snapshot.py {종목명} [업종키] [name:code ...]")
        sys.exit(1)
    stock_name = sys.argv[1]
    industry_key = sys.argv[2] if len(sys.argv) > 2 else 'default'
    extra = sys.argv[3:] if len(sys.argv) > 3 else None
    sys.exit(main(stock_name, industry_key, extra))
