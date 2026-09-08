"""
volatility_beta 테스트 (TDD -- 구현보다 먼저 작성)

배경 (2026-09 에프에스티 실측 사고):
  에프에스티(036810)는 **코스닥** 종목인데 스크립트가 KOSPI200(069500)을 기본값으로
  쓰고 시장 자동 감지가 없었다. 결과 Beta=0.76 (R2=0.363) -- FnGuide 실측 1.837과
  2.4배 차이. 에러도 경고도 없이 그럴듯한 틀린 베타가 나왔다.
  이 베타는 s12 포지션 사이징과 s09 Sharpe 계산에 그대로 들어간다.

규칙:
  1. 종목코드로 시장을 감지해 벤치마크를 고른다 (KOSPI200 / KOSDAQ150)
  2. 감지 실패 시 두 벤치마크를 모두 회귀해 R2 가 높은 쪽을 쓰고 그 사실을 기록한다
  3. 어느 경로든 **반대편 벤치마크 결과를 함께 저장**한다 (사람이 괴리를 볼 수 있게)
  4. R2 가 낮으면 베타를 '신뢰 불가'로 표시한다 -- 조용히 쓰이면 안 된다

실행: python tests/test_volatility_beta.py
"""
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import numpy as np
from volatility_beta import (KOSPI200, KOSDAQ150, benchmark_for, regress,
                             pick_by_r2, reliability)

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected!r}\n      실제: {actual!r}")


def close(actual, expected, name, tol=1e-6):
    global _passed
    if actual is not None and abs(actual - expected) <= tol:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected}\n      실제: {actual}")


# --- benchmark_for: 시장 -> ETF 코드 ---
eq(benchmark_for('KOSPI'), KOSPI200, "KOSPI -> KODEX200")
eq(benchmark_for('KOSDAQ'), KOSDAQ150, "KOSDAQ -> KODEX 코스닥150")
eq(benchmark_for('kosdaq'), KOSDAQ150, "대소문자 무관")
eq(benchmark_for('KOSDAQ GLOBAL'), KOSDAQ150, "코스닥 글로벌 세그먼트도 코스닥")
eq(benchmark_for(None), None, "감지 실패는 None -- 기본값으로 조용히 때우지 않는다")
eq(benchmark_for('KONEX'), None, "코넥스는 대응 벤치마크 없음 -> None")

# --- regress: 베타/R2/변동성 ---
# 종목 = 시장 x 2 (정확히 2배 움직임) -> beta 2.0, R2 1.0
mkt = np.array([100.0, 101.0, 103.0, 102.0, 104.0, 103.0, 106.0])
mkt_r = np.diff(np.log(mkt))
stock = 100.0 * np.exp(np.concatenate([[0.0], np.cumsum(mkt_r * 2)]))
res = regress(stock, mkt)
close(res['beta'], 2.0, "beta = 2.0 (시장 대비 2배)", 1e-6)
close(res['r2'], 1.0, "R2 = 1.0 (완전 상관)", 1e-6)
eq(res['n'], 6, "수익률 표본 수 = 종가 수 - 1")

# 역방향 종목 -> 음의 베타
inv = 100.0 * np.exp(np.concatenate([[0.0], np.cumsum(-mkt_r)]))
close(regress(inv, mkt)['beta'], -1.0, "역상관 종목은 beta = -1.0", 1e-6)

# 길이가 다르면 짧은 쪽에 맞춘다 (거래정지 등으로 일봉 수가 다를 수 있다)
res2 = regress(stock[:5], mkt)
eq(res2['n'], 4, "길이 불일치 시 짧은 쪽 기준")

# 표본 부족은 None (조용히 0 을 내지 않는다)
eq(regress(np.array([100.0, 101.0]), np.array([100.0, 101.0]))['beta'], None,
   "표본 3개 미만이면 beta=None")

# 시장 분산 0 (전일 동일가) -> 0 나눗셈 대신 None
flat = np.array([100.0] * 7)
eq(regress(stock, flat)['beta'], None, "시장 분산 0 이면 beta=None (0 반환 금지)")

# 연환산 변동성: 일간 std x sqrt(252)
daily_std = float(np.std(np.diff(np.log(stock))))
close(regress(stock, mkt)['vol_annual'], daily_std * np.sqrt(252), "연환산 변동성", 1e-9)

# --- pick_by_r2: 감지 실패 시 R2 높은 쪽 ---
a = {'beta': 0.76, 'r2': 0.363}
b = {'beta': 1.84, 'r2': 0.71}
eq(pick_by_r2({KOSPI200: a, KOSDAQ150: b}), KOSDAQ150, "R2 가 높은 벤치마크를 고른다")
eq(pick_by_r2({KOSPI200: b, KOSDAQ150: a}), KOSPI200, "반대 경우")
eq(pick_by_r2({KOSPI200: {'beta': None, 'r2': None}, KOSDAQ150: b}), KOSDAQ150,
   "산출 불가한 쪽은 후보에서 제외")
eq(pick_by_r2({KOSPI200: {'beta': None, 'r2': None},
               KOSDAQ150: {'beta': None, 'r2': None}}), None, "둘 다 불가면 None")

# --- reliability: R2 로 신뢰도 판정 ---
eq(reliability(0.71), 'OK', "R2 0.7 이상은 신뢰")
eq(reliability(0.42), 'WEAK', "R2 0.3~0.5 는 약함")
eq(reliability(0.363), 'WEAK', "에프에스티 KOSPI200 회귀 = 약함")
eq(reliability(0.12), 'UNRELIABLE', "R2 0.2 미만은 신뢰 불가")
eq(reliability(None), 'UNRELIABLE', "산출 불가는 신뢰 불가")

print(f"\n{'=' * 60}")
print(f"  volatility_beta 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
