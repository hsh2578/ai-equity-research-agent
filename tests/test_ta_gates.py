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
# v5.26 형식 게이트: source_coverage 는 warn 으로만 표시하고 실패 수에 넣지 않는다
eq('source_coverage' in g.FORM_GATES, True, 'source_coverage 는 FORM_GATES')
eq('verify_numbers' in g.FORM_GATES, False, '수치 게이트는 FORM_GATES 아님')
# FAIL 줄 판정 (하이브 실측 출력)
for line, want in [
    ('총 FAIL: 0건', False), ('  [✓ D4] Peer 테이블 0건 FAIL', False), ('총 D 블록 FAIL (B19~B22+D5+D6 포함 v5.2): 0', False),
    ('[calc_check] PASS 20 / FAIL 0 / WARN 13', False), ('  [v G2] PASS 98%', False), ('[industry_gate] FAIL 0건', False),
    ('  [✗ T1] 본문 볼드 비율 2.9%', True), ('총 FAIL: 14 / 전체 체크 87', True), ('Traceback (most recent call last):', True),
    ('[calc_check] PASS 20 / FAIL 2 / WARN 13', True), ('[ERROR] preflight 실패', True), ('  FAIL 3건 / WARN 2건', True),
]:
    eq(g.is_fail_line(line), want, f'is_fail_line({line.strip()[:30]!r})')

eq(g.build_args('check {s}', 'CJ ENM'), ['check', 'CJ ENM'], '공백 있는 종목명은 한 인자')
eq(g.build_args('{s}_ta', 'CJ ENM'), ['CJ ENM_ta'], '접미사 포맷도 한 인자')
print('=' * 66)
for label, want, got in _failed:
    print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')

# 병렬 실행 -- 결과 순서는 GATES 순서, analysis 를 고치는 preflight 는 다른 것보다 먼저 끝나 있어야 한다
_calls = []
_orig_run = g._run
def _fake_run(name, argfmt, stock):
    import time as _t
    _t.sleep(0.01 if name == 'preflight_check' else 0.001)
    _calls.append(name)
    return {'gate': name, 'exit': 0, 'fail_lines': [], 'summary': '', 'raw_tail': []}
g._run = _fake_run
import tempfile as _tf, json as _j, io as _io, contextlib as _cl
_tmp = os.path.join(g.tc.PROJECT_ROOT, 'scripts', 'analysis___gates_test___ta.json')
open(_tmp, 'w', encoding='utf-8').write('{}')
try:
    with _cl.redirect_stdout(_io.StringIO()):
        rc = g.run_gates('__gates_test__', None, workers=4)
    res = g.tc.read_json(os.path.join(g.tc.ta_dir('__gates_test__'), 'gates.json'))
    eq([r['gate'] for r in res['results']], [x[0] for x in g.GATES], '병렬이어도 gates.json 순서는 GATES 순서')
    eq(_calls[0], 'preflight_check', 'analysis 를 고치는 preflight 가 먼저 혼자 돈다')
    eq(rc, 0, 'FAIL 없으면 0')
finally:
    g._run = _orig_run
    os.remove(_tmp)
    import shutil as _sh
    _sh.rmtree(g.tc.data_dir('__gates_test__'), ignore_errors=True)

print(f'  ta_gates 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
