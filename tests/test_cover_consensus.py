"""
커버 '컨센서스 요약' 열 선택 테스트 (TDD -- 구현보다 먼저 작성)

배경 (2026-09 에프에스티 실측 사고):
  커버 대시보드가 "매출 2,946 -> 2,946 / 영업이익 60 -> 60 / EPS -556 -> -556" 을 찍었다.
  추정 열이 없는데 `fwd_idx = last_actual` 로 덮어써서 **같은 열을 두 번** 쓴 결과다.
  라벨은 "컨센서스 요약 / TTM 실적 / TTM 추정" 이었다.

  즉 컨센서스를 수집하지 못한 종목마다 커버 첫 화면에
  **"내년에도 그대로일 전망"이라는 없는 예측**이 찍혀 있었다.
  결측을 결측으로 두지 않고 마지막 실적으로 메운 것이라, v5.6 규칙 5 위반이다.

규칙:
  1. 추정 열(2026E, 2027F 등)이 있으면 (마지막 확정, 첫 추정) 두 열을 쓴다
  2. 추정 열이 없으면 **직전 확정 -> 마지막 확정** 두 열을 쓰고 '추정' 이라 부르지 않는다
  3. 확정 열이 하나뿐이면 비교 자체를 하지 않는다 (None 반환)

실행: python tests/test_cover_consensus.py
"""
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from generate_all import consensus_columns

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected!r}\n      실제: {actual!r}")


# --- 추정 열이 있는 정상 케이스 ---
eq(consensus_columns(['항목(억원)', '2023', '2024', '2025', '2026E', '2027E']),
   (3, 4, True), "2025 확정 / 2026E 추정")
eq(consensus_columns(['항목(조)', '2024', '2025', '2026F']),
   (2, 3, True), "F 접미도 추정으로 인식")
eq(consensus_columns(['항목', '2025', '2026E']),
   (1, 2, True), "확정 1개 + 추정 1개")

# --- 추정 열이 없는 케이스 (에프에스티) ---
eq(consensus_columns(['항목(억원)', '2022', '2023', '2024', '2025', 'TTM']),
   (4, 5, False), "추정 없음 -> 직전 확정(2025)과 마지막(TTM), is_forward=False")
eq(consensus_columns(['항목(억원)', '2023', '2024', '2025']),
   (2, 3, False), "추정 없음 -> 2024 -> 2025")

# --- 비교 불가 ---
eq(consensus_columns(['항목(억원)', '2025']), None, "데이터 열이 하나면 비교 불가")
eq(consensus_columns(['항목(억원)']), None, "데이터 열이 없으면 None")
eq(consensus_columns([]), None, "빈 헤더")
eq(consensus_columns(None), None, "None 헤더")

# --- 회귀 가드: 같은 열을 두 번 쓰지 않는다 ---
for _h in (['항목', '2022', '2023', '2024', '2025', 'TTM'],
           ['항목', '2024', '2025', '2026E'],
           ['항목', '2023', '2024', '2025']):
    _r = consensus_columns(_h)
    eq(_r is not None and _r[0] != _r[1], True, f"같은 열 중복 금지: {_h}")

# 'TTM' 은 추정이 아니다 (T/M 에 E/F 가 없지만, 과거 코드가 대문자 포함 여부로 오판할 소지)
r = consensus_columns(['항목', '2024', '2025', 'TTM'])
eq(r[2], False, "TTM 은 추정 열이 아니다")

print(f"\n{'=' * 60}")
print(f"  커버 컨센서스 열 선택 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
