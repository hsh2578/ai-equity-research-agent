"""generate_all._apply_section_order 의 meta.section_labels 선택 필드 테스트 (task-13).

배경: /research-ta 가 기술적 분석 섹션을 정규키 s08_esg 자리에 넣으면
본문 캡션이 "08 · ESG" 로 영문 오표기된다. meta.section_titles(한글 제목
교체, v5.21)와 같은 방식으로 영문 캡션만 덮는 meta.section_labels 를 추가한다.
section_labels 가 없으면 동작이 바이트 단위로 기존과 같아야 한다.

실행: python tests/test_generate_all_section_labels.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import importlib  # noqa: E402

# generate_all import 자체는 가볍다 (playwright 는 함수 내부 lazy import).
# 그래도 브리핑 지시대로 importlib 로 로드해 부작용 여부를 명시적으로 검증한다.
#
# 순서 주의: generate_all.py 는 import 시점에 sys.stdout 을 무조건
# utf-8 TextIOWrapper 로 재할당한다(가드 없음). 이 테스트가 먼저 자체
# wrapper 를 씌우면 생성 all 이 그 위에 또 wrapper 를 씌우면서 앞 wrapper 가
# GC 되어 공유 버퍼를 닫아버려 "I/O operation on closed file" 이 난다
# (실측). 그래서 import 를 먼저 하고, 인코딩 확인은 그 뒤에 한다.
ga = importlib.import_module('generate_all')

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


def raises(fn, exc_type, label):
    global _passed
    try:
        fn()
    except exc_type:
        _passed += 1
    except Exception as e:  # pragma: no cover - 진단용
        _failed.append((label, f'{exc_type.__name__}', f'{type(e).__name__}: {e}'))
    else:
        _failed.append((label, f'{exc_type.__name__}', '예외 없음'))


ORDER = ['s01_opinion_thesis', 's03_company_overview', 's08_esg']
SECTIONS = {}  # 순서에서 빠진 정규키 본문이 없어야 dropped 체크 통과

# ---------- labels 없음: 기존 반환과 바이트 단위 동일 ----------
baseline = ga._apply_section_order(ORDER, SECTIONS)
no_labels = ga._apply_section_order(ORDER, SECTIONS, labels=None)
eq(no_labels, baseline, 'labels 없음: 기존 반환과 동일')

# meta.section_titles 만 쓸 때도 회귀 없음 (기존 v5.21 경로)
titles_only = ga._apply_section_order(ORDER, SECTIONS, titles={'s08_esg': '기술적 분석'})
eq(titles_only[2], ('s08_esg', '03', 'ESG', '기술적 분석'), 'titles 만: 한글 제목 교체, 영문은 그대로')

# ---------- labels 지정: 영문 라벨만 교체, 한글은 titles 로 별도 교체 ----------
labeled = ga._apply_section_order(
    ORDER, SECTIONS,
    titles={'s08_esg': '기술적 분석'},
    labels={'s08_esg': 'Technical Analysis'},
)
eq(labeled[0], ('s01_opinion_thesis', '01', 'Opinion & Thesis', '투자의견 & 한 줄 투자 논문'),
   '라벨 미지정 항목은 그대로')
eq(labeled[2], ('s08_esg', '03', 'Technical Analysis', '기술적 분석'),
   '라벨 지정 항목: 영문 Technical Analysis + 한글 기술적 분석')

# labels 만 주고 titles 생략 -> 한글은 기본값 유지, 영문만 교체
labels_only = ga._apply_section_order(ORDER, SECTIONS, labels={'s08_esg': 'Technical Analysis'})
eq(labels_only[2], ('s08_esg', '03', 'Technical Analysis', 'ESG 분석'),
   'labels 만: 영문 교체 + 한글은 기본값')

# ---------- 잘못된 입력 ----------
raises(lambda: ga._apply_section_order(ORDER, SECTIONS, labels='not-a-dict'),
       ValueError, 'labels 가 dict 아니면 ValueError')
raises(lambda: ga._apply_section_order(ORDER, SECTIONS, labels={'s99_bad': 'X'}),
       ValueError, 'labels 에 정규 12키 아닌 키 -> ValueError')

# ---------- _get_section_titles 가 section_labels 를 전달하는지 ----------
data = {
    'meta': {
        'section_order': ORDER,
        'section_titles': {'s08_esg': '기술적 분석'},
        'section_labels': {'s08_esg': 'Technical Analysis'},
    },
    'sections': {'s01_opinion_thesis': '본문', 's08_esg': '본문'},
}
via_get = ga._get_section_titles(data)
eq(via_get[2], ('s08_esg', '03', 'Technical Analysis', '기술적 분석'),
   '_get_section_titles 가 meta.section_labels 를 반영')

# section_labels 없는 기존 데이터 -> 기존 동작과 동일 (회귀 없음)
data_no_labels = {
    'meta': {'section_order': ORDER, 'section_titles': {'s08_esg': '기술적 분석'}},
    'sections': {'s01_opinion_thesis': '본문', 's08_esg': '본문'},
}
via_get_no_labels = ga._get_section_titles(data_no_labels)
eq(via_get_no_labels[2], ('s08_esg', '03', 'ESG', '기술적 분석'),
   '_get_section_titles: section_labels 없으면 기존과 동일')

print(f'  generate_all_section_labels 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
if _failed:
    for label, want, got in _failed:
        print(f'    FAIL {label}: want={want!r} got={got!r}')
sys.exit(1 if _failed else 0)
