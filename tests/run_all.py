"""전체 테스트 실행기 (v5.5). 실행: python tests/run_all.py"""
import io, os, sys, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
suites = ['test_quarter_labels.py', 'test_decision_log.py', 'test_guard_hook.py']
fails = []
for s in suites:
    p = os.path.join(HERE, s)
    if not os.path.exists(p):
        continue
    r = subprocess.run([sys.executable, p], capture_output=True, text=True, encoding='utf-8')
    tail = [l for l in (r.stdout or '').splitlines() if '테스트:' in l]
    print(f"  [{'OK  ' if r.returncode == 0 else 'FAIL'}] {s:<26} {tail[0].strip() if tail else ''}")
    if r.returncode != 0:
        fails.append(s)
        print((r.stdout or '')[-600:])
print(f"\n  스위트 {len(suites) - len(fails)}/{len(suites)} 통과")
sys.exit(1 if fails else 0)
