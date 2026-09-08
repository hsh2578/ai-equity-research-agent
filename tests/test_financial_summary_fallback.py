"""
financial_summary 손익 fallback 테스트 (TDD -- 구현보다 먼저 작성)

배경 (2026-09 에프에스티 실측 사고):
  KIS 재무 API 가 036810 에 대해 **전 항목 0행**을 반환했다. 에러는 없었다.
  그 결과 financial_summary.json 의 financials[연도] 에 revenue/op_income/
  net_income/eps 가 전부 None 으로 남았고, build_snapshot 의 '2. 연간 실적' 표가
  통째로 '미수집' 이 됐다. 스냅샷 규칙상 미수집 항목은 수치 주장이 금지되므로
  **5년 실적을 한 줄도 못 쓰는 리포트**가 될 뻔했다.

  그런데 FnGuide 에는 2022~2025 매출/영업이익/순이익이 전부 있었다.
  CLAUDE.md 가 "풍산 v1 매출/OP 0원 사고를 차단한다" 고 적어둔 바로 그 소스다.

규칙:
  1. KIS 손익이 비어 있으면 FnGuide 연간 손익으로 채운다
  2. **이미 있는 값은 절대 덮어쓰지 않는다** (KIS/DART 가 1차)
  3. 채운 연도는 출처를 남긴다 -- 어디서 온 숫자인지 모르는 표를 만들지 않는다
  4. 마진(OPM/NPM/원가율)은 채운 뒤 다시 계산한다
  5. 결측은 0 이 아니라 None (v5.6 규칙 5)

실행: python tests/test_financial_summary_fallback.py
"""
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from financial_summary import merge_fnguide_income

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected!r}\n      실제: {actual!r}")


# 에프에스티 실측 (억원, FnGuide SVD_Main)
FNG = {
    'revenue': {'2022/12': 2196.24, '2023/12': 1976.09, '2024/12': 2374.08, '2025/12': 2802.63},
    'gross_profit': {'2023/12': 662.91, '2024/12': 805.14, '2025/12': 843.74},
    'operating_income': {'2022/12': 63.34, '2023/12': -107.82, '2024/12': 22.87, '2025/12': -5.47},
    'net_income': {'2022/12': 408.39, '2023/12': -181.03, '2024/12': -16.38, '2025/12': -143.30},
    'net_income_controlling': {'2023/12': -135.51, '2024/12': 14.50, '2025/12': -123.18},
}

# --- 빈 연도를 채운다 ---
yd = {'2024': {'total_assets': 5000}, '2025': {'total_assets': 5750}}
filled = merge_fnguide_income(yd, FNG)
eq(sorted(filled), ['2024', '2025'], "결측 연도만 채운다 (yd 에 없는 2022/2023 은 만들지 않는다)")
eq(yd['2025']['revenue'], 2802.63, "매출")
eq(yd['2025']['op_income'], -5.47, "영업이익 (적자 그대로)")
eq(yd['2025']['net_income'], -143.30, "순이익")
eq(yd['2025']['gross_profit'], 843.74, "매출총이익")
eq(yd['2025']['total_assets'], 5750, "기존 대차 값은 건드리지 않는다")

# --- 출처 표기 ---
eq(yd['2025'].get('_income_source'), 'fnguide', "채운 연도는 출처를 남긴다")
eq(yd['2024'].get('_income_source'), 'fnguide', "2024 도 동일")

# --- 마진 재계산 ---
eq(yd['2025']['opm'], -0.2, "OPM = -5.47/2802.63 = -0.195 -> -0.2")
eq(yd['2024']['opm'], 1.0, "2024 OPM = 22.87/2374.08 = 0.96 -> 1.0")
eq(yd['2025']['npm'], -5.1, "NPM = -143.30/2802.63 = -5.11")

# --- 기존 값은 덮어쓰지 않는다 (KIS/DART 가 1차 출처) ---
yd2 = {'2025': {'revenue': 9999.0, 'op_income': None}}
merge_fnguide_income(yd2, FNG)
eq(yd2['2025']['revenue'], 9999.0, "이미 있는 매출은 유지 (FnGuide 로 덮지 않는다)")
eq(yd2['2025']['op_income'], -5.47, "None 인 항목만 채운다")

# 전부 이미 있으면 채운 연도 0개
yd3 = {'2025': {'revenue': 1.0, 'op_income': 2.0, 'net_income': 3.0, 'gross_profit': 4.0}}
eq(merge_fnguide_income(yd3, FNG), [], "채울 것이 없으면 빈 목록")

# --- EPS: 지배주주 순이익 / 주식수 ---
yd4 = {'2025': {}}
merge_fnguide_income(yd4, FNG, shares=21649789)
eq(yd4['2025']['eps'], -569.0, "EPS = -123.18억 / 21,649,789주 = -568.9원")
yd5 = {'2025': {}}
merge_fnguide_income(yd5, FNG)
eq(yd5['2025'].get('eps'), None, "주식수를 모르면 EPS 는 None (0 으로 때우지 않는다)")

# --- 방어: 입력이 비었을 때 ---
eq(merge_fnguide_income({}, FNG), [], "연도 dict 이 비면 빈 목록")
eq(merge_fnguide_income({'2025': {}}, None), [], "FnGuide 가 없으면 빈 목록")
eq(merge_fnguide_income({'2025': {}}, {}), [], "FnGuide 가 빈 dict 이어도 안전")

# 매출이 0 이면 마진을 계산하지 않는다 (0 나눗셈)
yd6 = {'2030': {}}
eq(merge_fnguide_income(yd6, {'revenue': {'2030/12': 0.0},
                              'operating_income': {'2030/12': 5.0}}), ['2030'],
   "매출 0 연도도 채우기는 한다")
eq(yd6['2030'].get('opm'), None, "매출 0 이면 OPM 은 None")

print(f"\n{'=' * 60}")
print(f"  financial_summary fallback 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
