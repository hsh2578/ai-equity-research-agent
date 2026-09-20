# -*- coding: utf-8 -*-
"""ta_gates.py -- /research-ta STEP 7 게이트 13종을 한 명령으로 돌린다 (v5.25).

usage: python scripts/ta_gates.py {종목명} [--only verify_tone,section_rubric]

하이브 실측: 12종을 손으로 7바퀴 돌리는 데 30분이 갔다. 이 러너는 (1) -ta 전용 게이트 4종을 먼저,
(2) 기존 검증기가 고정으로 읽는 scripts/analysis_{종목}.json 자리에 _ta 파일을 잠시 복사해 7종을 돌리고,
(3) 원본을 반드시 복원한 뒤, 게이트별 FAIL 수와 한 줄 결과만 표로 낸다. --only 로 깨진 것 하나만 다시 돌린다.
전체 결과는 data/{종목}/ta/gates.json 에 남긴다.
"""
import io
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta_common as tc  # noqa: E402

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# (이름, 인자 형식, _ta 파일을 analysis_{종목}.json 자리에 복사해야 하는가)
GATES = [
    ('ta_coverage_check', '{s}', False),
    ('ta_calc_ledger', 'check {s}', False),
    ('ta_industry_gate', '{s}', False),
    ('preflight_check', '{s}_ta', False),
    ('verify_numbers', '{s}', True),
    ('verify_facts', '{s}', True),
    ('verify_tone', '{s}', True),
    ('verify_content', '{s}', True),
    ('source_coverage', '{s}', True),
    ('section_rubric', '{s}', True),
    ('verify_style', '{s}', True),
]
_FAIL_RE = re.compile(r'\[(?:✗|X|FAIL|ERROR)[ \]]|\[ERROR\]|Traceback|총 FAIL: ?[1-9]|(?<!0건 )FAIL [1-9]\d* ?건|/ FAIL [1-9]|FAIL: [1-9]\d* /')
_SUMMARY_RE = re.compile(r'총 FAIL|FAIL \d+건|/ FAIL|FAIL 0건|점수|통과|합계|calc_check|_gate\]|coverage_check\]|preflight')
_SCORE_RE = re.compile(r'점수[^:]*:\s*(\d+)/100')


def is_fail_line(line):
    """검증기 출력 한 줄이 실제 FAIL 인가. '[✓ D4] ... 0건 FAIL' / '총 FAIL: 0건' / 'PASS 20 / FAIL 0' 은 아니다."""
    if '✓' in line or '[v ' in line:
        return False
    return bool(_FAIL_RE.search(line))


def select_gates(only):
    """--only 'a,b' -> 그 이름만. 모르는 이름은 ValueError."""
    if not only:
        return list(GATES)
    want = [x.strip() for x in only.split(',') if x.strip()]
    names = {g[0] for g in GATES}
    bad = [w for w in want if w not in names]
    if bad:
        raise ValueError(f'모르는 게이트: {bad} (가능: {sorted(names)})')
    return [g for g in GATES if g[0] in want]


def _run(name, argfmt, stock):
    args = [sys.executable, os.path.join(tc.PROJECT_ROOT, 'scripts', name + '.py')] + argfmt.format(s=stock).split()
    p = subprocess.run(args, capture_output=True, cwd=tc.PROJECT_ROOT, env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    out = (p.stdout + p.stderr).decode('utf-8', 'replace')
    lines = out.splitlines()
    fails = [l for l in lines if is_fail_line(l)]
    summary = [l.strip() for l in lines if _SUMMARY_RE.search(l)]
    if name == 'verify_style':
        # 점수 게이트: 참고-리포트 톤은 85± 가 정상(wf-report 규칙). 80 미만일 때만 FAIL 로 본다
        m = [_SCORE_RE.search(l) for l in lines]
        score = next((int(x.group(1)) for x in m if x), None)
        fails = [f'서술 품질 {score}점 < 80'] if score is not None and score < 80 else []
        summary = [f'서술 품질 {score}/100 (참고-리포트 톤 85± 정상)'] if score is not None else summary
    return {'gate': name, 'exit': p.returncode, 'fail_lines': fails[:20], 'summary': summary[-1] if summary else '', 'raw_tail': lines[-3:]}


def run_gates(stock, only=None):
    gates = select_gates(only)
    ta = os.path.join(tc.PROJECT_ROOT, 'scripts', f'analysis_{stock}_ta.json')
    base = os.path.join(tc.PROJECT_ROOT, 'scripts', f'analysis_{stock}.json')
    if not os.path.exists(ta):
        print(f'[ERROR] {ta} 없음'); return 2
    need_copy = any(g[2] for g in gates)
    had = os.path.exists(base)
    if need_copy:
        if had:
            shutil.copy2(base, base + '.bak_gates')
        shutil.copy2(ta, base)
    results = []
    try:
        for name, argfmt, _ in gates:
            r = _run(name, argfmt, stock)
            results.append(r)
            mark = 'FAIL' if r['fail_lines'] else 'ok'
            print(f"  [{mark:4}] {name:20} exit={r['exit']}  {r['summary'][:110]}")
            for l in r['fail_lines'][:6]:
                print(f'           {l.strip()[:150]}')
    finally:
        if need_copy:
            if had:
                shutil.move(base + '.bak_gates', base)
            else:
                os.remove(base)
    n_fail = sum(1 for r in results if r['fail_lines'])
    tc.write_json(os.path.join(tc.ta_dir(stock), 'gates.json'), {'stock': stock, 'results': results, 'gates_with_fail': n_fail})
    print(f'[ta_gates] {stock} -- {len(results)}종 중 FAIL 있는 게이트 {n_fail}개 (원본 analysis_{stock}.json {"복원" if had else "복사본 제거"})')
    return 1 if n_fail else 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('stock')
    ap.add_argument('--only', help='쉼표로 게이트 이름')
    a = ap.parse_args(argv)
    return run_gates(a.stock, a.only)


if __name__ == '__main__':
    raise SystemExit(main())
