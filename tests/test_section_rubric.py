"""section_rubric -- 애널리스트 6축에 필수 도구가 붙었는지 보는가.

배경(2026-09-08): LS일렉트릭 리포트를 애널리스트 리포트로 놓고 채점하니
**이미 규칙으로 있는 도구가 세 군데 빠져 있었다** -- 밸류에이션의 DCF·민감도(Q1/Q2),
투자포인트의 bottom-up 산식(v5.10 규칙 3), 리스크의 확률·영향 정량.
규칙이 없어서가 아니라 실행되지 않아서다. 그래서 코드로 옮겼다.

**오탐이 나면 아무도 안 보게 되므로** 표기 방식에 의존하는 판정을 피한다.
실측으로 걸러낸 오탐 케이스를 아래에 고정한다.
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from section_rubric import grade, _hit, section_text   # noqa: E402

_passed = 0
_failed = []


def eq(got, want, label):
    global _passed
    if got == want:
        _passed += 1
    else:
        _failed.append((label, want, got))


def st(rows, axis, label):
    for a, l, s, _ in rows:
        if a == axis and l == label:
            return s
    return None


# ---------- 특수 패턴 ----------
FOUR = '#### 가\n내용\n#### 나\n내용\n#### 다\n내용\n#### 라\n내용\n'
eq(_hit('BLOCKS>=3', FOUR, ''), True, "소제목 4개면 BLOCKS>=3 통과")
eq(_hit('BLOCKS>=3', '#### 가\n#### 나\n', ''), False, "소제목 2개면 미달")
eq(_hit('BLOCKS>=3', '', ''), False, "빈 섹션은 미달")
eq(_hit('REPORT:동종', '섹션엔 없다', '리포트 전체엔 동종 비교가 있다'), True,
   "REPORT: 는 섹션이 아니라 리포트 전체를 본다")
eq(_hit('REPORT:동종', '섹션엔 없다', '리포트에도 없다'), False,
   "리포트 전체에도 없으면 미달")

# ---------- 오탐 방지 (실측 케이스) ----------
# 1) '포인트 1' 이라 안 쓰고 소제목만 두는 리포트가 실측 3/3 이었다
SEC = {'s02_thesis_catalysts': FOUR + '2026년 11월 실적 x 3.2 산식',
       's04_industry_competition': '시장 규모 30조 동종 비교',
       's03_company_overview': '사업 구성 표 | 부문 | 최대주주 지분',
       's09_scenarios_risks': FOUR + '확률 30% 로 시총 -25%',
       's06_financial': '영업활동현금흐름 / ROE 13.3% / 부채비율',
       's07_valuation': 'WACC 9.5% 민감도 분석 Bear Bull 동종 4사'}
rows = grade(SEC)
eq(st(rows, '투자포인트', '논거 블록 3개 이상'), 'PASS',
   "**'포인트 N' 표기가 없어도 소제목 4개면 통과** (표기 의존 오탐 차단)")
eq(st(rows, '리스크', '리스크 블록 3개 이상'), 'PASS', "리스크도 구조로 센다")

# 2) Peer 표는 sections 밖에서 렌더된다 -- 섹션만 보면 거짓 FAIL
SEC2 = dict(SEC, s07_valuation='WACC 9.5% 민감도 Bear Bull')
SEC2['s04_industry_competition'] = '시장 규모 30조, 동종 5사 비교표'
eq(st(grade(SEC2), '밸류에이션', 'Peer 상대비교'), 'PASS',
   "밸류 섹션에 없어도 리포트 어딘가에 동종 비교가 있으면 통과")

# 3) '지분 5%p 매각' 같은 다른 뜻의 '지분'이 지배구조로 통과하면 안 된다
SEC3 = dict(SEC, s03_company_overview='사업 구성 표 | 부문 | 지분 5%p 를 매각했다')
eq(st(grade(SEC3), '기업분석', '지배구조·최대주주'), 'FAIL',
   "'지분 매각' 은 지배구조 서술이 아니다")

# ---------- 진짜 결함은 잡는다 ----------
rows = grade(dict(SEC, s07_valuation='PER 로만 계산했다 Bear Bull 동종'))
eq(st(rows, '밸류에이션', 'DCF 또는 미사용 사유'), 'FAIL', "**배수법만 쓰면 FAIL**")
eq(st(rows, '밸류에이션', '민감도 분석'), 'FAIL', "민감도가 없으면 FAIL")

# 안 쓰는 이유를 밝히면 통과 (적자기업에 DCF 를 강요하지 않는다)
rows = grade(dict(SEC, s07_valuation=(
    '적자라 DCF 는 의미가 없어 쓰지 않는다. 민감도 분석 표. Bear Bull 동종 4사')))
eq(st(rows, '밸류에이션', 'DCF 또는 미사용 사유'), 'PASS',
   "DCF 를 왜 안 쓰는지 밝히면 통과 -- Q5 와 충돌하지 않는다")

rows = grade(dict(SEC, s09_scenarios_risks=FOUR + '리스크가 크다'))
eq(st(rows, '리스크', '확률·영향 정량'), 'FAIL', "확률·주가영향 수치가 없으면 FAIL")

rows = grade(dict(SEC, s06_financial='매출이 늘었다'))
eq(st(rows, '재무분석', '현금흐름'), 'FAIL', "현금흐름 미언급은 FAIL")
eq(st(rows, '재무분석', '수익성 분해(ROE/DuPont)'), 'FAIL', "ROE 분해 없으면 FAIL")

# ---------- 입력 방어 ----------
eq([r[2] for r in grade({})].count('SKIP'), 6, "빈 sections 는 6축 전부 SKIP")
eq([r[2] for r in grade(None)].count('SKIP'), 6, "None 도 안전")
eq(section_text({'s08_financial': 'alias 본문'}, 's06_financial'), 'alias 본문',
   "정규 키가 비면 alias 를 본다")

print('=' * 62)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  section_rubric 애널리스트 6축: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 62)
sys.exit(1 if _failed else 0)
