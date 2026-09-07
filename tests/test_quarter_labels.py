"""
quarter_labels 모듈 테스트 (v5.5 신설 -- 이 프로젝트 최초의 테스트)

실행: python tests/test_quarter_labels.py
     (pytest 불필요 -- 의존성 추가 없이 돌도록 순수 assert 로 작성)

배경: B13 이 v4.20 부터 죽어 있었던 것을 발견했다. 검증기 자체가 검증되지 않으면
      "PASS" 는 아무 의미가 없다. 새 검증 로직은 테스트를 먼저 통과시킨다.
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from quarter_labels import parse_label, is_estimate, collect_quarters, find_gaps, check

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


# --- parse_label: 표기 변형 ---
eq(parse_label('1Q25'), (2025, 1), "parse '1Q25'")
eq(parse_label('4Q25'), (2025, 4), "parse '4Q25'")
eq(parse_label("Q3'25"), (2025, 3), "parse \"Q3'25\" (AMD 실제 표기)")
eq(parse_label('Q1 26'), (2026, 1), "parse 'Q1 26'")
eq(parse_label('2Q FY26'), (2026, 2), "parse '2Q FY26'")
eq(parse_label('1Q2025'), (2025, 1), "parse '1Q2025' (4자리 연도)")
eq(parse_label('25.3Q'), (2025, 3), "parse '25.3Q' (연도 선행)")
eq(parse_label('2025 1Q'), (2025, 1), "parse '2025 1Q' (에스엠 실제 표기)")
eq(parse_label('2025 4Q'), (2025, 4), "parse '2025 4Q'")
eq(parse_label('항목'), None, "parse '항목' -> None")
eq(parse_label('매출 (억 달러)'), None, "parse '매출 (억 달러)' -> None")
eq(parse_label(''), None, "parse '' -> None")
eq(parse_label('5Q25'), None, "parse '5Q25' -> None (분기 범위 초과)")

# --- is_estimate ---
truthy(is_estimate('2Q26E'), "is_estimate '2Q26E'")
truthy(is_estimate("Q1'26 가이던스"), "is_estimate \"Q1'26 가이던스\" (AMD 실제)")
truthy(is_estimate('3Q26(E)'), "is_estimate '3Q26(E)'")
falsy(is_estimate('1Q25'), "is_estimate '1Q25' -> False")
falsy(is_estimate("Q3'25"), "is_estimate \"Q3'25\" -> False")

# --- collect_quarters: headers 방향 (KR/US 실제 구조) ---
kr = {'headers': ['항목', '1Q25', '2Q25', '3Q25', '4Q25', '1Q26', '2Q26'],
      'rows': [['매출', 1, 2, 3, 4, 5, 6], ['영업이익', 1, 2, 3, 4, 5, 6]]}
c, e, raw = collect_quarters(kr)
eq(c, [(2025, 1), (2025, 2), (2025, 3), (2025, 4), (2026, 1), (2026, 2)],
   "collect_quarters KR headers 방향 (기존 B13 이 놓치던 케이스)")
eq(e, [], "collect_quarters KR 추정치 없음")

# --- collect_quarters: rows 첫 열 방향 (구버전 가정) ---
legacy = {'headers': ['분기', '매출', '영업이익'],
          'rows': [['1Q25', 100, 10], ['2Q25', 110, 12]]}
c2, _, _ = collect_quarters(legacy)
eq(c2, [(2025, 1), (2025, 2)], "collect_quarters rows 방향도 지원")

# --- collect_quarters: AMD 실제 데이터 (추정 분리) ---
amd = {'headers': ['항목', "Q3'25", "Q4'25", "Q1'26 가이던스", "Q2'26E", "Q3'26E"],
       'rows': [['매출 (억 달러)', '92.5', '102.6', '98G', '108', '120']]}
c3, e3, _ = collect_quarters(amd)
eq(c3, [(2025, 3), (2025, 4)], "AMD 확정 분기 2개")
eq(e3, [(2026, 1), (2026, 2), (2026, 3)], "AMD 추정 분기 3개 (가이던스+E)")

# --- find_gaps: 에스엠 1Q25 누락 사고 재현 ---
eq(find_gaps([(2025, 2), (2025, 3), (2025, 4)]), [], "연속 3분기 -> 구멍 없음")
eq(find_gaps([(2025, 1), (2025, 3), (2025, 4)]), ['2Q25'], "2Q25 누락 감지")
eq(find_gaps([(2024, 4), (2025, 2)]), ['1Q25'], "연도 경계 넘는 누락 감지")
eq(find_gaps([(2025, 1), (2025, 2), (2026, 1)]), ['3Q25', '4Q25'], "복수 누락 감지")
eq(find_gaps([(2025, 1)]), [], "1개면 판정 불가 -> 빈 리스트")

# --- check: 진행 중 연도를 오탐하지 않는다 ---
errs, _ = check({'headers': ['항목', '1Q25', '2Q25', '3Q25', '4Q25', '1Q26']})
eq(errs, [], "1Q26 까지만 있는 진행 중 연도 -> 오탐 없음 (기존 '4분기 충족' 규칙의 오탐 제거)")

# --- check: 실제 누락은 잡는다 ---
errs, _ = check({'headers': ['항목', '1Q25', '3Q25', '4Q25', '1Q26']})
truthy(any('2Q25' in x for x in errs), "check 가 2Q25 누락을 FAIL 로 보고")

# --- check: 표 부재 ---
errs, _ = check({})
truthy(any('부재' in x for x in errs), "check 가 빈 quarterly 를 FAIL 로 보고")

# --- check: 파싱 실패 (분기 라벨이 아예 없는 표) ---
errs, _ = check({'headers': ['항목', '2024', '2025'], 'rows': [['매출', 1, 2]]})
truthy(any('파싱 실패' in x for x in errs), "연간 표를 분기 표로 오인하지 않고 파싱 실패 보고")

# --- 에스엠 실제 헤더 회귀 케이스 ---
sm = {'headers': ['항목', '2025 1Q', '2025 2Q', '2025 3Q', '2025 4Q'], 'rows': [['매출', 1, 2, 3, 4]]}
c_sm, _, _ = collect_quarters(sm)
eq(c_sm, [(2025, 1), (2025, 2), (2025, 3), (2025, 4)], "에스엠 '2025 1Q' 헤더 파싱")
errs_sm, _ = check(sm)
eq(errs_sm, [], "에스엠 4분기 완전 -> 통과")

# --- 기아 실제 헤더: 연도 없는 맨 분기 ---
kia = {'headers': ['', 'Q1', 'Q2', 'Q3', 'Q4'], 'rows': [['매출', 1, 2, 3, 4]]}
errs_kia, det_kia = check(kia)
truthy(any('연도가 없음' in x for x in errs_kia), "기아 '연도 없는 분기' 를 파싱실패와 구분해 보고")

# --- check: 확정 분기 부족 경고 ---
errs, _ = check({'headers': ['항목', "Q3'25", "Q4'25", "Q2'26E"]})
truthy(any('확정 분기 2개' in x for x in errs), "확정 분기 4개 미만 경고 (AMD 실제 케이스)")


print(f"\n{'=' * 60}")
print(f"  quarter_labels 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
