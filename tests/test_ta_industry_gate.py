"""ta_industry_gate 테스트(픽스처 analysis dict, I/O 없음).

실행: python tests/test_ta_industry_gate.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import ta_industry_gate as g  # noqa: E402

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


def fx(s04, s01, s07='밴드 대비 Peer 비교', s02='사건'):
    return {'meta': {'stock_name': '에프에스티',
                     'section_order': ['s01_opinion_thesis', 's04_industry_competition', 's02_thesis_catalysts', 's07_valuation']},
            'sections': {'s01_opinion_thesis': s01, 's04_industry_competition': s04,
                         's02_thesis_catalysts': s02, 's07_valuation': s07}}


good04 = ('관세청 통계에 따르면 8486 수출은 늘었다.\n\nSEMI 는 2027년 팹 투자를 전망했다.\n\n램리서치 10-K 는 capex 를 밝혔다.\n\n' * 3) + '에프에스티는 여기에 착지한다.'
good01 = '> **한 줄:** 상반기 영업이익 110억원\n\n> **한 줄:** 램리서치 벤더 등록\n\n> **한 줄:** 3Q26 양산 확인이 판정한다\n\n본문 ' + 'x' * 100
r = {c['id']: c for c in g.check(fx(good04, good01))}
eq(r['G1']['status'], 'PASS', 'G1 분량 20%+')
eq(r['G2']['status'], 'PASS', 'G2 회사밖 90%+')
eq(r['G3']['status'], 'PASS', 'G3 출처 3종+')
eq(r['G4']['status'], 'PASS', 'G4 요약 3불릿 형식')
eq(r['G5']['status'], 'PASS', 'G5 밸류 분리')
eq(r['G6']['status'], 'PASS', 'G6 뉴스 상한')

bad04 = '에프에스티는 동사의 펠리클을 판다. 보도에 따르면 기사에서 보도됐다.'
r2 = {c['id']: c for c in g.check(fx(bad04, '> **한 줄:** 하나뿐', s02='SOTP 시나리오 ' + 'y' * 400, s07='DCF ' + 'z' * 400))}
eq([r2[k]['status'] for k in ('G1', 'G2', 'G3', 'G4', 'G5', 'G6')], ['FAIL'] * 6, '전부 FAIL')
eq(g.outside_ratio('에프에스티 문단.\n\n동사 문단.\n\n삼성전자 문단.\n\nSEMI 문단.', '에프에스티'), 0.5, '회사밖 비율 = 문단 기준')

print(f'ta_industry_gate 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
for label, want, got in _failed:
    print(f'  [FAIL] {label}: want={want!r} got={got!r}')
sys.exit(1 if _failed else 0)
