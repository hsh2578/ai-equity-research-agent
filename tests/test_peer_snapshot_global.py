# -*- coding: utf-8 -*-
"""peer_snapshot_global 테스트: 환율 환산·결측 None·선행 PER 이상값 flag·비ASCII 이름 (네트워크 없음)."""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
_KEEP = sys.stdout  # 모듈이 stdout 을 다시 감싼다. 참조가 없으면 이 래퍼가 GC 되며 buffer 를 닫는다
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
import peer_snapshot_global as g  # noqa: E402

_failed = []


def eq(a, b, msg):
    if a != b:
        _failed.append(msg)
        print(f'  [FAIL] {msg}\n      기대: {b!r}\n      실제: {a!r}')


# 중국선박공업 실측(2026-09-20)과 같은 모양의 info
CSSC = {'shortName': 'CHINA CSSC HOLDINGS LIMITED', 'currency': 'CNY', 'marketCap': 297036283904, 'trailingPE': 20.45,
        'forwardPE': 11.13, 'priceToBook': 1.95, 'currentPrice': 39.47, 'fiftyTwoWeekHigh': 45.0, 'fiftyTwoWeekLow': 30.0}
r = g.build_record('중국선박공업', '600150.SS', CSSC, 197.0)
eq(r['market_cap_uk'], round(297036283904 * 197.0 / 1e8), 'CNY 시총 -> 억원 환산')
eq(r['per'], 20.45, 'per = trailingPE')
eq(r['per_forward'], 11.13, 'per_forward = forwardPE')
eq(r['flags'], [], '정상 레코드는 flags 없음')
eq(r['currency'], 'CNY', 'currency 대문자')

# 가와사키重형: 선행 PER 이 후행의 0.3배 미만 -> 값은 두되 flag
KHI = {'currency': 'JPY', 'marketCap': 2099603046400, 'trailingPE': 18.59, 'forwardPE': 4.21, 'priceToBook': 2.27}
r = g.build_record('가와사키중공업', '7012.T', KHI, 9.3)
eq(r['flags'], ['forward_pe_suspect'], '선행 PER 이상값 flag')
eq(r['per_forward'], 4.21, '이상값이어도 값은 보존')

# 결측은 None, 0 아님
r = g.build_record('X', 'X.T', {'currency': 'JPY'}, 9.3)
eq((r['market_cap_uk'], r['per'], r['pbr']), (None, None, None), '결측 None')
eq(r['flags'], [], '시총 자체가 없으면 fx_missing 도 아님')

# 환율 없음
r = g.build_record('Y', 'Y.HE', {'currency': 'EUR', 'marketCap': 1.6e10, 'trailingPE': 25.4}, None)
eq((r['market_cap_uk'], r['flags']), (None, ['fx_missing']), '환율 없으면 시총 None + fx_missing')

# 비ASCII 이름
r = g.build_record('바르질라', 'WRT1V.HE', {'shortName': 'Wärtsilä Corporation', 'currency': 'EUR', 'marketCap': 1.6e10}, 1600.0)
eq(r['name_en'], 'Wärtsilä Corporation', '비ASCII 이름 보존')

# fx 캐시·KRW
cache = {}
eq(g.fx_to_krw('KRW', cache), 1.0, 'KRW 는 1')
eq(g.fx_to_krw('CNY', cache, fetch=lambda tk: 197.3 if tk == 'CNYKRW=X' else None), 197.3, 'CNYKRW=X 조회')
eq(g.fx_to_krw('CNY', cache, fetch=lambda tk: 999), 197.3, '캐시 재사용')
eq(g.fx_to_krw('USD', cache, fetch=lambda tk: 1368.0 if tk == 'KRW=X' else None), 1368.0, 'USD 는 KRW=X')
eq(g.fx_to_krw('XXX', cache, fetch=lambda tk: (_ for _ in ()).throw(RuntimeError())), None, '조회 예외면 None')

# 업종키 + --peers 병합
p = g.resolve_peers('shipbuild', '바르질라:wrt1v.he, 잘못된항목')
eq(list(p)[:2], ['중국선박공업', '양쯔장조선'], '업종 템플릿 순서')
eq(p['바르질라'], 'WRT1V.HE', '--peers 티커 대문자화')
eq(len(p), 6, '5 + 1')

print('=' * 66)
if _failed:
    print(f'  peer_snapshot_global 테스트: {len(_failed)}개 실패')
    sys.exit(1)
print('  peer_snapshot_global 테스트: 18개 통과 / 0개 실패')
