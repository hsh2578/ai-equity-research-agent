"""meta.section_titles -- IR협의회 목차를 정규 12키에 얹는다 (v5.21).

배경: IR협의회 기업분석 16편의 목차는
  기업개요 및 연혁 / 주주구성 및 자회사 / 주요 제품 및 기술력 /
  산업현황 / 투자포인트 / 실적 추이 및 전망 / Valuation / 리스크요인
인데, 정규 12키의 한글 제목은 "경영진 & 현장 검증", "수급 & 주주환원" 이다.
키에 담아도 **PDF 에 찍히는 제목이 내용과 다르다.**

여기서 지키는 것은 두 가지다.
  1) 오버라이드가 없으면 기존 리포트 동작이 **완전히** 그대로일 것
  2) 오타난 키는 조용히 무시되지 말고 죽을 것 (조용히 무시되면 제목이 안 바뀐 채 나간다)
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

# generate_all 은 import 시점에 sys.stdout 을 갈아끼운다. 먼저 import 하고 감싼다.
from generate_all import _get_section_titles        # noqa: E402

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_passed = 0
_failed = []


def eq(got, want, label):
    global _passed
    if got == want:
        _passed += 1
    else:
        _failed.append((label, want, got))


ORDER = ['s01_opinion_thesis', 's03_company_overview', 's05_management_fieldcheck',
         's11_supply_shareholder', 's10_earnings_consensus']
SECS = {k: 'x' for k in ORDER}


def titles_of(meta):
    return {k: ko for k, _n, _en, ko in _get_section_titles({'meta': meta, 'sections': SECS})}


# ---------- 오버라이드 적용 ----------
t = titles_of({'section_order': ORDER, 'section_titles': {
    's05_management_fieldcheck': '주요 제품 및 기술력',
    's11_supply_shareholder': '주주구성 및 자회사',
    's10_earnings_consensus': '실적 추이 및 전망',
}})
eq(t['s05_management_fieldcheck'], '주요 제품 및 기술력',
   "**제품 설명 장 -- 기본 제목은 '경영진 & 현장 검증' 이라 내용과 어긋난다**")
eq(t['s11_supply_shareholder'], '주주구성 및 자회사', '주주구성 (기본: 수급 & 주주환원)')
eq(t['s10_earnings_consensus'], '실적 추이 및 전망', '실적 추이 (기본: 실적 · 컨센)')
eq(t['s03_company_overview'], '기업 분석',
   '오버라이드 안 준 키는 기본 제목을 유지한다')

# ---------- 오버라이드가 없으면 기존 동작 그대로 ----------
t0 = titles_of({'section_order': ORDER})
eq(t0['s05_management_fieldcheck'], '경영진 & 현장 검증',
   "**오버라이드 없으면 기존 리포트와 완전히 동일해야 한다**")
eq(t0['s11_supply_shareholder'], '수급 & 주주환원', '기존 동작 유지')

# section_order 자체가 없으면 12섹션 기본값
full = _get_section_titles({'meta': {}, 'sections': {'s01_opinion_thesis': 'x'}})
eq(len(full), 12, 'section_order 없으면 12섹션 기본값')

# ---------- 오타는 죽어야 한다 ----------
try:
    titles_of({'section_order': ORDER, 's' 'ection_titles': {'s05_managment_fieldcheck': 'x'}})
    _failed.append(('오타난 키는 ValueError 여야 한다', 'ValueError', '통과됨'))
except ValueError:
    _passed += 1

# dict 가 아니면 죽어야 한다
try:
    titles_of({'section_order': ORDER, 'section_titles': ['주요 제품']})
    _failed.append(('리스트를 주면 ValueError 여야 한다', 'ValueError', '통과됨'))
except ValueError:
    _passed += 1

print('=' * 66)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  meta.section_titles 오버라이드: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
