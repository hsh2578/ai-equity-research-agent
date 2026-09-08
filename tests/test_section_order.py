"""
generate_all: meta.section_order 지원 (TDD -- 구현보다 먼저 작성)

배경 (2026-09-08, 위닝펀드 수상작 12편 실측):
  수상 리포트의 본문 섹션은 **6개뿐**이다.

    산업 26% / 기업 19% / 투자포인트 17% / 리스크 10% / 재무 12% / 밸류 16%

  ESG·실행계획·수급·경영진·컨센서스는 **독립 섹션이 없다.** 경영진은 기업분석
  안에, 컨센은 투자포인트/밸류 안에 녹아 있다.

  우리 v5.0 12섹션은 그 5개에 본문의 **32%** 를 쓰고 있었고, 그 결과 스토리
  3섹션(산업+기업+투자포인트)이 27.6% 로 수상작 62% 의 절반 이하였다.
  재무 비중은 문제가 아니었다 (우리 11.9% vs 수상작 12.3% -- 거의 같다).

  그래서 섹션을 **삭제하지 않고 호스트 섹션에 병합**하고, 렌더 순서만
  meta.section_order 로 지정한다. 데이터를 지우면 verify_numbers/verify_facts 가
  읽던 근거가 사라진다.

이 테스트가 지키는 것 -- **병합이 내용을 조용히 삼키지 않을 것**:
  section_order 에서 빠진 정규 키에 본문이 남아 있으면 그 내용은 PDF 에
  영원히 나오지 않는다. 에러도 로그도 없이. 이 프로젝트 사고의 공통 모양이다.
  그래서 그 경우 ValueError 로 죽인다.

실행: python tests/test_section_order.py
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from generate_all import _get_section_titles, _SECTION_TITLES_DETAILED_V5

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected!r}\n      실제: {actual!r}")


def raises(fn, exc, name, must_contain=None):
    global _passed
    try:
        fn()
    except exc as e:
        if must_contain and must_contain not in str(e):
            _failed.append(f"{name}\n      메시지에 {must_contain!r} 가 없다: {e}")
        else:
            _passed += 1
    except Exception as e:
        _failed.append(f"{name}\n      기대: {exc.__name__}\n      실제: {type(e).__name__}: {e}")
    else:
        _failed.append(f"{name}\n      기대: {exc.__name__} 발생\n      실제: 발생하지 않음")


V5 = {'s01_opinion_thesis': 'x', 's02_thesis_catalysts': 'x', 's06_financial': 'x',
      's12_action_plan': 'x'}

# --- 하위 호환: section_order 가 없으면 기존 12섹션 그대로 ---
eq(_get_section_titles({'sections': V5}), _SECTION_TITLES_DETAILED_V5,
   "section_order 미지정이면 기존 v5 12섹션 (기존 리포트 무영향)")

eq(_get_section_titles({'meta': {}, 'sections': V5}), _SECTION_TITLES_DETAILED_V5,
   "meta 는 있고 section_order 가 없어도 12섹션")

eq(len(_get_section_titles({'sections': {'s01_opinion': 'x'}})), 21,
   "v4 21섹션 감지는 그대로")

# --- 6섹션 재편 (위닝펀드 구조) ---
WF6 = ['s04_industry_competition', 's03_company_overview', 's02_thesis_catalysts',
       's09_scenarios_risks', 's06_financial', 's07_valuation']

# 병합된 섹션은 본문을 비워 둔다 (내용은 호스트로 옮겨감)
merged = {k: 'x' for k in WF6}
merged['s01_opinion_thesis'] = 'x'          # 커버 직후 요약, 항상 남긴다
for k in ('s05_management_fieldcheck', 's08_esg', 's10_earnings_consensus',
          's11_supply_shareholder', 's12_action_plan'):
    merged[k] = ''                           # 호스트로 병합 완료

got = _get_section_titles({'meta': {'section_order': ['s01_opinion_thesis'] + WF6},
                           'sections': merged})
eq([k for k, _n, _e, _ko in got], ['s01_opinion_thesis'] + WF6,
   "section_order 순서 그대로 (산업 -> 기업 -> 포인트 -> 리스크 -> 재무 -> 밸류)")
eq([n for _k, n, _e, _ko in got], ['01', '02', '03', '04', '05', '06', '07'],
   "**번호를 다시 매긴다** -- 목차에 01,02,04.. 처럼 구멍이 나면 안 된다")
eq(got[1][3], '산업 분석 & 경쟁 구도', "제목은 정규 테이블에서 가져온다")

# --- 조용한 삼킴 차단 ---
lost = dict(merged)
lost['s08_esg'] = 'ESG 본문이 아직 남아 있다'     # 병합했다면서 원본을 안 비웠다
raises(lambda: _get_section_titles({'meta': {'section_order': ['s01_opinion_thesis'] + WF6},
                                    'sections': lost}),
       ValueError, "**빠진 섹션에 본문이 남아 있으면 죽는다** (조용한 내용 손실 차단)",
       must_contain='s08_esg')

# 공백만 있는 건 비운 것으로 본다
ws = dict(merged)
ws['s08_esg'] = '   \n  '
eq(len(_get_section_titles({'meta': {'section_order': ['s01_opinion_thesis'] + WF6},
                            'sections': ws})), 7,
   "공백만 남은 섹션은 비운 것으로 취급")

# --- 잘못된 키도 조용히 넘기지 않는다 ---
raises(lambda: _get_section_titles({'meta': {'section_order': ['s99_없는섹션']},
                                    'sections': V5}),
       ValueError, "정규 12키에 없는 키는 ValueError", must_contain='s99_없는섹션')

# alias 키를 순서에 넣는 것도 사고다 (본문이 두 번 렌더된다)
raises(lambda: _get_section_titles({'meta': {'section_order': ['s08_financial']},
                                    'sections': V5}),
       ValueError, "alias 키(s08_financial)를 순서에 넣으면 ValueError")

# --- 빈 리스트는 미지정과 같게 (실수로 [] 를 넣어 리포트가 통째로 비는 것 방지) ---
eq(_get_section_titles({'meta': {'section_order': []}, 'sections': V5}),
   _SECTION_TITLES_DETAILED_V5, "빈 리스트는 미지정과 동일 취급")

# --- v4 리포트에 section_order 를 주면 무시 (12키 기준이므로) ---
eq(len(_get_section_titles({'meta': {'section_order': WF6},
                            'sections': {'s01_opinion': 'x'}})), 21,
   "v4 리포트에는 section_order 를 적용하지 않는다")

# --- 중복 키 ---
raises(lambda: _get_section_titles({'meta': {'section_order': ['s06_financial', 's06_financial']},
                                    'sections': merged}),
       ValueError, "중복 키는 ValueError")

print(f"\n{'=' * 62}")
print(f"  meta.section_order 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 62}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
