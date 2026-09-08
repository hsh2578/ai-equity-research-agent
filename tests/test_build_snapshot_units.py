"""
build_snapshot 단위 변환 테스트 (TDD -- 구현보다 먼저 작성)

배경 (2026-09 실측 사고):
  스냅샷 '2. 연간 실적' 표가 **모든 KR 종목에서 매출/영업이익/순이익을 0 으로** 찍고 있었다.
  풍산 2025 매출은 50,486억(5.05조)인데 표에는 `0` 이었다.

  원인: `financials[연도]['revenue']` 는 `eok()` 를 거쳐 **이미 억원**인데
  (`"KIS는 이미 '억' 단위로 반환. 그대로 반올림."`), 표를 그릴 때 1e8 로 한 번 더 나눴다.
  EPS/OPM 은 나누지 않아 정상으로 보였기 때문에 표가 그럴듯했다.

  이게 특히 나쁜 이유: `_verified_snapshot.md` 는 v5.5 규칙 2 가
  "모든 정확한 수치 주장의 유일한 출처" 로 선언한 파일이다.
  틀린 값이 여기 있으면 리포트 전체가 그걸 따라간다.

  US 는 financial_summary_us 가 **raw USD** 를 담으므로 1e9 나눗셈($B)이 맞다.
  (LULU 2026 revenue = 11,102,600,000 -> $11.1B)

실행: python tests/test_build_snapshot_units.py
"""
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from build_snapshot import (income_divisor, income_unit_label, format_income,
                            fmt, MISSING)

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected!r}\n      실제: {actual!r}")


# --- 나눗수: KR 은 이미 억원이므로 나누지 않는다 ---
eq(income_divisor('KR'), 1, "KR 은 financials 가 이미 억원 -> 나눗수 1")
eq(income_divisor('US'), 1e9, "US 는 raw USD -> $B 로 1e9")

eq(income_unit_label('KR'), '억원', "KR 단위 라벨")
eq(income_unit_label('US'), '$B', "US 단위 라벨")

# --- 실측값이 표에 제대로 찍히는가 ---
# 풍산 2025: 50,486억
eq(format_income(50486, 'KR'), '50,486', "풍산 2025 매출 50,486억")
# 에프에스티 2025: 2,802.63억
eq(format_income(2802.63, 'KR'), '2,803', "에프에스티 2025 매출 2,803억")
# 에프에스티 2025 영업이익 -5.47억 -- 소액 적자가 0 으로 뭉개지면 안 된다
eq(format_income(-5.47, 'KR'), '-5.47', "소액 적자 -5.47억이 0 으로 뭉개지지 않는다")
# GS리테일 2025: 119,574억 (11.96조)
eq(format_income(119574, 'KR'), '119,574', "GS리테일 2025 매출 119,574억")

# LULU 2026: 11,102,600,000 USD -> 11.1
eq(format_income(11102600000, 'US'), '11.10', "LULU 매출 $11.10B")
eq(format_income(1579183000, 'US'), '1.58', "LULU 순이익 $1.58B")

# --- 결측은 0 이 아니라 '미수집' ---
eq(format_income(None, 'KR'), MISSING, "None 은 '미수집'")
eq(fmt(None), MISSING, "fmt 도 None 은 '미수집'")

# --- 회귀 가드: 옛 동작(1e8 나눗셈)이 돌아오면 이 테스트가 깨진다 ---
eq(fmt(50486 / 1e8, '', 2), '0.00',
   "(참고) 옛 나눗수 1e8 이면 풍산 5조 매출이 '0' 이 된다 -- 이 사고를 고정한다")

print(f"\n{'=' * 60}")
print(f"  build_snapshot 단위 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
