"""
peer_snapshot_us 테스트 (TDD -- 구현보다 먼저 작성됨)

배경 -- '조용한 무력화' 결함.
peer_snapshot_us.py 는 `market_cap_b` / `per_trailing` 로 저장하는데,
generate_all.py 의 Peer 교차검증(검증 #10)은 `snap.get("market_cap_uk", 0)` 와
`snap.get("per", 0)` 을 읽는다. 둘 다 기본값 0 이라 **US 종목의 Peer 검증이
에러 없이 통째로 건너뛰어졌다**. JYP v1(Peer 추정치 기재) 의 미국판 재발 통로다.

추가로 `--peers` 가 마지막 인자일 때 `argv[index+1]` 이 IndexError 를 냈다.

실행: python tests/test_peer_snapshot_us.py
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
# 대상 모듈들도 import 시점에 stdout 을 다시 감싼다. 참조를 잡아두지 않으면
# 이 래퍼가 GC 되면서 공유 buffer 를 닫아 이후 print 가 ValueError 를 낸다.
_KEEP_STDOUT = sys.stdout
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import peer_snapshot_us as ps

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected}\n      실제: {actual}")


def truthy(actual, name):
    eq(bool(actual), True, name)


def falsy(actual, name):
    eq(bool(actual), False, name)


# yfinance .info 를 흉내낸 실제 형태 (data/AMD/_peer_snapshot.json 의 NVDA 값)
NVDA_INFO = {
    'currentPrice': 230.36,
    'marketCap': 5562_500_000_000,
    'trailingPE': 29.159492,
    'forwardPE': 14.843682,
    'priceToBook': 24.291891,
    'priceToSalesTrailing12Months': 18.359913,
    'enterpriseToEbitda': 27.466,
    'revenueGrowth': 1.059,
    'operatingMargins': 0.66236997,
    'fiftyTwoWeekHigh': 236.54,
    'fiftyTwoWeekLow': 164.27,
    'targetMeanPrice': 327.12808,
    'beta': 2.217,
}

rec = ps.build_record('NVDA', NVDA_INFO)

# --- 기존 스키마 보존 (verify_numbers_us.py B1/B3 이 읽는 키) ---
eq(rec['ticker'], 'NVDA', "ticker 유지")
eq(rec['market_cap_b'], 5562.5, "market_cap_b 유지 ($B)")
eq(rec['per_trailing'], 29.159492, "per_trailing 유지")
eq(rec['per_forward'], 14.843682, "per_forward 유지")
eq(rec['price'], 230.36, "price 유지")
eq(rec['pbr'], 24.291891, "pbr 유지")

# --- generate_all.py 검증 #10 이 읽는 호환 키 (이게 없어서 검증이 무력화됐다) ---
truthy('market_cap_uk' in rec, "generate_all 이 읽는 market_cap_uk 키 존재")
truthy('per' in rec, "generate_all 이 읽는 per 키 존재")
eq(rec['market_cap_uk'], rec['market_cap_b'],
   "market_cap_uk = $B 값 (generate_all 은 analysis.peers.market_cap 문자열과 같은 단위로 비교)")
eq(rec['per'], rec['per_trailing'], "per = per_trailing (TTM)")

# generate_all 은 `snap.get("per", 0)` 이 0 이면 비교를 건너뛴다.
# 값이 있는데 0 으로 읽히면 그것이 바로 조용한 무력화다.
truthy(rec.get('per', 0) != 0, "per 이 0 이 아니어야 generate_all PER 비교가 실제로 돈다")
truthy(rec.get('market_cap_uk', 0) != 0, "market_cap_uk 가 0 이 아니어야 시총 비교가 실제로 돈다")

# --- 결측 필드는 None 을 유지하되 키 자체는 존재해야 한다 ---
empty = ps.build_record('XXXX', {})
eq(empty['market_cap_b'], None, "marketCap 없으면 market_cap_b None")
eq(empty['market_cap_uk'], None, "marketCap 없으면 market_cap_uk 도 None (0 으로 위장 금지)")
eq(empty['per'], None, "trailingPE 없으면 per None")
eq(empty['ticker'], 'XXXX', "결측이어도 ticker 는 유지")

# --- KR 판(peer_snapshot.py) 과 키 이름이 실제로 겹치는지 ---
KR_KEYS = {'price', 'market_cap_uk', 'per', 'pbr', 'high_52w', 'low_52w'}
eq(sorted(KR_KEYS - set(rec)), [], "KR peer_snapshot.py 와 공통 키를 모두 제공")

# --- parse_peers: --peers 문자열 파싱 ---
eq(ps.parse_peers('NVIDIA:NVDA,Intel:INTC'), {'NVIDIA': 'NVDA', 'Intel': 'INTC'},
   "parse_peers 기본")
eq(ps.parse_peers('NVIDIA:nvda'), {'NVIDIA': 'NVDA'}, "parse_peers 티커 대문자화")
eq(ps.parse_peers(''), {}, "parse_peers 빈 문자열 -> {}")
eq(ps.parse_peers(None), {}, "parse_peers None -> {}")
eq(ps.parse_peers('NVDA'), {}, "parse_peers 콜론 없는 항목 무시")

# --- --peers 가 마지막 인자일 때 IndexError 를 내지 않는다 ---
err = None
rc = None
try:
    rc = ps.main(['AMD', '--peers'])
except IndexError as e:
    err = e
eq(err, None, "'--peers' 가 마지막 인자여도 IndexError 없음")
eq(rc, 1, "값 없는 --peers 는 사용법 에러(return 1) 로 처리")

# --peters 뒤에 또 다른 플래그가 오는 경우도 값으로 오인하지 않는다
err = None
try:
    rc = ps.main(['AMD', '--peers', '--verbose'])
except IndexError as e:
    err = e
eq(err, None, "--peers 뒤가 또 다른 플래그여도 IndexError 없음")
eq(rc, 1, "--peers 뒤가 플래그면 값 없음으로 처리")

# 업종키 오타는 네트워크 호출 전에 걸러진다
eq(ps.main(['AMD', 'nonexistent_sector']), 1, "없는 업종키는 return 1")
eq(ps.main([]), 1, "인자 없으면 usage 출력 후 return 1")


print(f"\n{'=' * 60}")
print(f"  peer_snapshot_us 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
