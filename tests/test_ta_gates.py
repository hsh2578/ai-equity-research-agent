# -*- coding: utf-8 -*-
"""ta_gates -- 게이트 러너의 선택·집계 테스트 (네트워크·서브프로세스 없음).

실행: python tests/test_ta_gates.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ta_gates as g  # noqa: E402

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_passed = 0
_failed = []


def eq(got, want, label):
    global _passed
    if got == want:
        _passed += 1
    else:
        _failed.append((label, want, got))


eq(len(g.select_gates(None)), len(g.GATES), '--only 없음이면 전부')
eq([x[0] for x in g.select_gates('verify_tone,section_rubric')], ['verify_tone', 'section_rubric'], '--only 는 GATES 순서 유지')
try:
    g.select_gates('없는게이트'); eq(True, False, '모르는 이름은 ValueError')
except ValueError:
    eq(True, True, '모르는 이름은 ValueError')
eq(g.run_gates('__없는종목__'), 2, '_ta 파일 없으면 2')
# FAIL 줄 판정 (하이브 실측 출력)
for line, want in [
    ('총 FAIL: 0건', False), ('  [✓ D4] Peer 테이블 0건 FAIL', False), ('총 D 블록 FAIL (B19~B22+D5+D6 포함 v5.2): 0', False),
    ('[calc_check] PASS 20 / FAIL 0 / WARN 13', False), ('  [v G2] PASS 98%', False), ('[industry_gate] FAIL 0건', False),
    ('  [✗ T1] 본문 볼드 비율 2.9%', True), ('총 FAIL: 14 / 전체 체크 87', True), ('Traceback (most recent call last):', True),
    ('[calc_check] PASS 20 / FAIL 2 / WARN 13', True), ('[ERROR] preflight 실패', True), ('  FAIL 3건 / WARN 2건', True),
]:
    eq(g.is_fail_line(line), want, f'is_fail_line({line.strip()[:30]!r})')

print('=' * 66)
for label, want, got in _failed:
    print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  ta_gates 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
