"""
verify_style C21/C22 -- 스토리 비중 + 표 과다 게이트 (TDD)

배경 (2026-09-08, 사용자 지적):
  "산업분석과 기업분석, 투자포인트가 가장 중요한데 재무분석 위주로 리포트가
   쓰여지면 별로다. 회사의 상태와 미래 비전, 어떤 이슈가 있는지 분석하는 게
   중요하다. 재무도 중요하지만 메인은 스토리텔링 아닐까."

  실측으로 확인됐다. 3종목 섹션별 분량(가이드 대비):

    섹션          에프에스티   LULU    와이지엔터
    산업분석★      110%       87%     **74%**
    기업분석★      107%       88%      102%
    재무          133%      119%      137%
    밸류          147%      135%      132%

  **가장 중요하다고 한 산업분석이 가장 미달이고, 재무·밸류만 30~47% 초과했다.**
  표 비중도 재무 46~57% / 밸류 36~50% 인 반면 시나리오는 19~21% 였다.
  즉 재무·밸류 섹션이 표 덤프가 되고 있었다.

  C21/C22 는 이 균형을 코드로 강제한다. 다음 리포트부터 자동 적용된다.

실행: python tests/test_verify_style_story.py
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from verify_style import table_ratio, check_c22_table_overload

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected!r}\n      실제: {actual!r}")


def close(actual, expected, name, tol=0.6):
    global _passed
    if actual is not None and abs(actual - expected) <= tol:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected}\n      실제: {actual}")


# --- table_ratio: 표 행이 차지하는 비율 ---
eq(table_ratio(''), 0.0, "빈 문자열은 0")
eq(table_ratio('산문만 있다.'), 0.0, "표가 없으면 0")
close(table_ratio('| a | b |\n|---|---|\n| 1 | 2 |'), 100.0, "전부 표면 100%", 1.0)
t = '산문 12345\n| a | b |\n산문 12345'   # 표 9자 / 전체 약 29자
r = table_ratio(t)
eq(0 < r < 100, True, "섞여 있으면 0~100 사이")

# --- C21 (SUPERSEDED) ---
# C21 은 2026-09-08 위닝펀드 수상작 12편 실측 후 **본문 전체 대비 비중(%)** 으로
# 재정의됐다. 분모를 재무+밸류로 잡은 구 정의는 수상작에 없는 섹션 5개가
# 본문의 32% 를 먹는 것을 못 봤다. 새 단정은 tests/test_verify_style_wf.py 에 있다.

# --- C22: 섹션별 표 과다 ---
# 스토리 섹션은 35%, 재무/밸류는 45% 상한
tbl_rows = ('| a | b |\n' * 40)          # 표 400자
prose_ok = 'x' * 900                      # 산문 900자 -> 표 비중 약 31%
prose_bad = 'x' * 400                     # 표 비중 50%

over = check_c22_table_overload({'s04_industry': prose_ok + '\n' + tbl_rows})
eq(over, [], "산업분석 표 31%는 통과(상한 35%)")

over2 = check_c22_table_overload({'s04_industry': prose_bad + '\n' + tbl_rows})
eq(len(over2), 1, "산업분석 표 50%는 적발")
eq(over2[0][0], 's04_industry', "적발된 섹션명")

# 같은 50% 라도 재무 섹션은 상한이 45% 라 역시 적발
over3 = check_c22_table_overload({'s08_financial': prose_bad + '\n' + tbl_rows})
eq(len(over3), 1, "재무 표 50%는 적발(상한 45%)")

# 재무 40% 는 통과
over4 = check_c22_table_overload({'s08_financial': 'x' * 700 + '\n' + tbl_rows})
eq(over4, [], "재무 표 36%는 통과")

# 대상 외 섹션은 보지 않는다
eq(check_c22_table_overload({'s12_action_plan': prose_bad + '\n' + tbl_rows}), [],
   "대상 외 섹션은 판정하지 않는다")

# 빈 섹션 안전
eq(check_c22_table_overload({'s04_industry': ''}), [], "빈 섹션은 적발하지 않는다")
eq(check_c22_table_overload({}), [], "빈 dict")

print(f"\n{'=' * 60}")
print(f"  C21/C22 스토리 비중·표 과다 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
