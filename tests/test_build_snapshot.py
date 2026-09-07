"""
build_snapshot 테스트 (TDD -- 구현보다 먼저 작성됨)

배경 -- '조용한 무력화' 결함.
_verified_snapshot.md 는 파이프라인이 "모든 정확한 수치 주장의 유일한 출처" 라고
선언한 문서다. 그런데 두 곳에서 **수집된 데이터를 '미수집' 이라고 말했다**:

  1. KR Peer 표가 `v.get('종목코드')` / `v.get('시가총액')` 을 읽는데
     peer_snapshot.py 는 `code` / `market_cap_uk` 로 쓴다.
  2. 변동성이 `b.get('sigma_annual')` 를 읽는데
     volatility_beta.py 는 `vol_annual`(비율), US 인라인은 `vol_annual_pct`(%) 로 쓴다.

에이전트는 이 문서를 근거로 "그 항목은 주장 금지" 라고 결론 낸다.
있는 데이터를 없다고 하면 리포트에서 통째로 빠진다.

실행: python tests/test_build_snapshot.py
"""
import sys
import os
import io
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
# build_snapshot 도 import 시점에 stdout 을 다시 감싼다. 여기서 참조를 잡아두지 않으면
# 위 래퍼가 GC 되면서 underlying buffer 를 닫아 print 가 ValueError 를 낸다.
_KEEP_STDOUT = sys.stdout

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, '..'))
sys.path.insert(0, os.path.join(_ROOT, 'scripts'))
os.chdir(_ROOT)   # Snapshot 은 data/{종목} 상대경로를 쓴다

from build_snapshot import Snapshot, MISSING

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


def blank(name='__none__'):
    """데이터 폴더를 읽지 않는 빈 Snapshot (필드는 테스트가 직접 주입)."""
    return Snapshot(name)


def render(sec_fn, snap):
    snap.lines = []
    sec_fn()
    return '\n'.join(snap.lines)


# ==================== 1. KR Peer 표 ====================
# peer_snapshot.py 가 실제로 쓰는 스키마 (data/GS리테일/_peer_snapshot.json 원본)
KR_PEER = {
    "이마트": {"code": "139480", "price": 113500, "market_cap_uk": 31321,
               "per": 23.06, "pbr": 0.28, "eps": 4921.0, "bps": 410591.0,
               "high_52w": 136400, "low_52w": 79400},
    "롯데쇼핑": {"code": "023530", "price": 138600, "market_cap_uk": 39208,
                "per": 76.07, "pbr": 0.26, "eps": 1822.0, "bps": 537131.0,
                "high_52w": 141900, "low_52w": 67800},
}

s = blank()
s.market = 'KR'
s.peer = KR_PEER
out = render(s.sec_peer, s)
truthy('139480' in out, "KR Peer 표에 종목코드(code) 가 렌더된다")
truthy('31,321' in out, "KR Peer 표에 시총(market_cap_uk) 이 렌더된다")
truthy('23.06' in out, "KR Peer 표에 PER 이 렌더된다")
truthy('0.28' in out, "KR Peer 표에 PBR 이 렌더된다")
falsy(MISSING in out, "수집된 KR Peer 를 '미수집' 으로 표기하지 않는다")

# 구 스키마(한글 키)도 계속 읽어야 한다 -- 과거 산출물 호환
s = blank()
s.market = 'KR'
s.peer = {"삼성전자": {"종목코드": "005930", "시가총액": 5000000, "PER": 12.3, "PBR": 1.1}}
out = render(s.sec_peer, s)
truthy('005930' in out, "구 한글 키(종목코드) 호환 유지")
truthy('5,000,000' in out, "구 한글 키(시가총액) 호환 유지")

# US Peer 는 회귀 없어야 한다
s = blank()
s.market = 'US'
s.peer = {"NVIDIA": {"ticker": "NVDA", "market_cap_b": 5562.5,
                     "per_trailing": 29.16, "per_forward": 14.84, "pbr": 24.29}}
out = render(s.sec_peer, s)
truthy('NVDA' in out and '5,562B' in out, "US Peer 표 회귀 없음")

# 실제 파일 회귀: data/GS리테일/_peer_snapshot.json
if os.path.isfile('data/GS리테일/_peer_snapshot.json'):
    real = Snapshot('GS리테일')
    real.market = 'KR'
    out = render(real.sec_peer, real)
    rows = [l for l in out.splitlines() if l.startswith('| ') and MISSING in l]
    eq(rows, [], "실제 GS리테일 Peer 파일에 '미수집' 셀이 남지 않는다")
    truthy('139480' in out, "실제 GS리테일 파일에서 이마트 코드 렌더")


# ==================== 2. 변동성 / 베타 ====================
# volatility_beta.py 실제 출력 (KR): vol_annual 은 **비율**(0.4525 = 45.25%)
KR_BETA = {"beta": 0.31000861821809733, "r2": 0.12676588532925875,
           "vol_annual": 0.4524864766713778, "market_code": "069500", "n_days": 99}
s = blank()
s.market = 'KR'
s.beta = KR_BETA
out = render(s.sec_risk, s)
falsy(MISSING in out, "수집된 KR 변동성/베타를 '미수집' 으로 표기하지 않는다")
truthy('45.2' in out, "KR vol_annual(비율) 을 % 로 환산해 렌더 (0.4525 -> 45.2%)")
truthy('0.31' in out, "beta 렌더")
truthy('069500' in out, "기준 지수(market_code) 렌더")

# US 인라인 산출물: vol_annual_pct 는 이미 % (data/AMD/_volatility_beta.json)
US_BETA = {"benchmark": "QQQ", "days": 123, "beta": 2.255,
           "r_squared": 0.419, "vol_annual_pct": 62.33}
s = blank()
s.market = 'US'
s.beta = US_BETA
out = render(s.sec_risk, s)
falsy(MISSING in out, "수집된 US 변동성/베타를 '미수집' 으로 표기하지 않는다")
truthy('62.33%' in out, "US vol_annual_pct 는 이미 % 이므로 100배 부풀리지 않는다")
truthy('2.25' in out, "US beta 렌더")
truthy('QQQ' in out, "US 기준 지수(benchmark) 렌더")

# 구 키(sigma_annual) 호환 -- % 단위로 저장돼 있던 과거 산출물
s = blank()
s.market = 'KR'
s.beta = {"beta": 1.1, "sigma_annual": 38.4, "r_squared": 0.5, "benchmark": "KOSPI200"}
out = render(s.sec_risk, s)
truthy('38.40%' in out, "구 키 sigma_annual(%) 호환 유지 -- 100배로 부풀리지 않음")

# 변동성만 없으면 그 항목만 미수집 + gap 기록
s = blank()
s.market = 'KR'
s.beta = {"beta": 1.1, "market_code": "069500"}
out = render(s.sec_risk, s)
truthy(MISSING in out, "변동성 값이 실제로 없으면 '미수집' 으로 표기")
truthy(any('변동성' in g[0] or '변동성' in g[1] for g in s.gaps),
       "변동성 미수집 시 gap 에 기록해 '주장 금지' 목록에 올린다")

# 파일 자체가 없으면 기존대로 전체 미수집 + gap
s = blank()
s.beta = None
out = render(s.sec_risk, s)
truthy(MISSING in out, "_volatility_beta.json 자체가 없으면 미수집")
truthy(s.gaps, "파일 부재 시 gap 기록 (기존 동작 유지)")

# 실제 파일 회귀: data/AMD/_volatility_beta.json
if os.path.isfile('data/AMD/_volatility_beta.json'):
    real = Snapshot('AMD')
    out = render(real.sec_risk, real)
    falsy(MISSING in out, "실제 AMD 변동성 파일이 전부 렌더된다")


print(f"\n{'=' * 60}")
print(f"  build_snapshot 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
