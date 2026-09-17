# -*- coding: utf-8 -*-
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
import ta_readability_gate as g  # noqa: E402

_failed = []


def eq(a, b, msg):
    if a != b:
        _failed.append(msg)
        print(f'  [FAIL] {msg}\n      기대: {b!r}\n      실제: {a!r}')


GLOSS = '#### 용어 -- 처음 보는 말\n\n' + '\n'.join(f'- **용어{i}**: 풀이 {i}다.' for i in range(1, 9))
TABLE = '| 언제 | 무엇을 확인한다 | 확인되면 | 안 되면 |\n|---|---|---|---|\n| 9월 | 차환 공시 | 유지 | 매도 검토 |'
S01 = f'### 제목\n\n> **한 줄:** 매출 1,000억원\n\n{TABLE}\n\n주가는 싸다. 이익은 줄었다.\n\n{GLOSS}\n'
A = {'meta': {'stock_name': 'X', 'section_order': ['s01_opinion_thesis', 's06_financial']},
     'sections': {'s01_opinion_thesis': S01, 's06_financial': '매출은 늘었다. 이익은 줄었다. 현금이 715억원으로 줄었다.'}}

by = {r['id']: r for r in g.check(A)}
eq(by['R1']['status'], 'PASS', '액션 표가 있으면 R1 PASS')
eq(by['R3']['status'], 'PASS', '용어 8개면 R3 PASS')
eq(by['R2']['status'], 'PASS', '문장당 숫자 적으면 R2 PASS')
eq(by['R4']['status'], 'PASS', '반복 없으면 R4 PASS')

B = {'meta': A['meta'], 'sections': {'s01_opinion_thesis': '### 제목\n\n주가는 싸다.\n',
                                     's06_financial': '매출 1,000억원 영업이익 100억원 순이익 50억원 부채 300억원이다. ' * 3}}
byb = {r['id']: r for r in g.check(B)}
eq(byb['R1']['status'], 'FAIL', '액션 표 없으면 R1 FAIL')
eq(byb['R3']['status'], 'FAIL', '용어 박스 없으면 R3 FAIL')
eq(byb['R2']['status'], 'WARN', '문장당 숫자 4개면 R2 WARN (기준선 미확정)')

C = {'meta': A['meta'], 'sections': {'s01_opinion_thesis': S01, 's06_financial': '단기차입금은 1,426억원이다. ' * 5}}
byc = {r['id']: r for r in g.check(C)}
eq(byc['R4']['status'], 'WARN', '같은 금액 5회 반복이면 R4 WARN')
eq('1,426억원' in byc['R4']['value'], True, 'R4 는 반복된 금액을 보여준다')

# 표·마진노트·인용은 문장 수에서 뺀다
eq(len(g.prose_sentences('> **한 줄:** 1 2 3 4\n\n| 1 | 2 |\n|---|---|\n\n본문 문장이다. 둘째 문장이다.')), 2, '표·마진노트 제외')

print('=' * 66)
if _failed:
    print(f'  ta_readability_gate 테스트: {len(_failed)}개 실패')
    sys.exit(1)
print('  ta_readability_gate 테스트: 11개 통과 / 0개 실패')
