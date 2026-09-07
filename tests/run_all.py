"""전체 테스트 실행기 (v5.5).

    python tests/run_all.py

- 자체 스위트: 의존성 없이 python 단독 실행 (assert 기반)
- tests/broker/: 이식본이라 원 프로젝트 방식대로 pytest 로 돈다
"""
import io
import os
import sys
import subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
SUITES = ['test_quarter_labels.py', 'test_decision_log.py', 'test_guard_hook.py',
          'test_wf_chart_planner.py', 'test_wf_charts.py', 'test_rs_table.py',
          'test_fdr_band_us.py', 'test_evidence_scan.py', 'test_us_consensus.py',
          'test_fetch_broker_reports.py',
          'test_peer_snapshot_us.py', 'test_build_snapshot.py',
          'test_verify_check_ids.py', 'test_market_cap_parse.py']
PYTEST_DIRS = ['broker']

fails = []
total = 0

for s in SUITES:
    p = os.path.join(HERE, s)
    if not os.path.exists(p):
        continue
    total += 1
    r = subprocess.run([sys.executable, p], capture_output=True, text=True, encoding='utf-8')
    tail = [l for l in (r.stdout or '').splitlines() if '테스트:' in l]
    print(f"  [{'OK  ' if r.returncode == 0 else 'FAIL'}] {s:<26} {tail[0].strip() if tail else ''}")
    if r.returncode != 0:
        fails.append(s)
        print((r.stdout or '')[-600:])

for d in PYTEST_DIRS:
    dd = os.path.join(HERE, d)
    if not os.path.isdir(dd):
        continue
    total += 1
    r = subprocess.run([sys.executable, '-m', 'pytest', dd, '-q'],
                       capture_output=True, text=True, encoding='utf-8')
    tail = [l for l in (r.stdout or '').splitlines() if 'passed' in l or 'failed' in l]
    label = f'{d}/ (pytest)'
    print(f"  [{'OK  ' if r.returncode == 0 else 'FAIL'}] {label:<26} {tail[-1].strip() if tail else ''}")
    if r.returncode != 0:
        fails.append(d)
        print((r.stdout or '')[-600:])

print(f"\n  스위트 {total - len(fails)}/{total} 통과")
sys.exit(1 if fails else 0)
