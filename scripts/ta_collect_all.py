"""/research-ta STEP 0~1 수집기를 병렬로 돌린다 (v5.27, 2026-09-21 사용자: "수집은 병렬로 정리하면 되잖아").

    python scripts/ta_collect_all.py {종목명} --peer-key media --industry-category 미디어 --keywords OTT,광고
    python scripts/ta_collect_all.py {종목명} --real-kis            # KIS 모의가 500 이면
    python scripts/ta_collect_all.py {종목명} --only news,event_study --dry-run

메인이 수집기 12개를 하나씩 부르고 결과를 본 뒤 다음을 부르던 것(신세계·CJ ENM 실측 35분)을 한 명령으로 바꾼다.
직렬로 남는 것은 둘뿐이다: ① KIS 를 치는 스크립트(토큰 발급 분당 1회 -- 실전 전환 시 403)는 한 레인에서 순서대로,
② 의존이 있는 것(뉴스 -> 이벤트 스터디 -> 뉴스 창 -> 이벤트 스터디 재실행, DART 전문 -> dart_diff·driver_scan,
리포트+DART -> evidence_scan, IR+뉴스 본문 -> company_voice, 전부 -> build_snapshot·plan_agents).
실패는 삼키지 않는다 -- 각 작업의 returncode·소요·꼬리를 `data/{종목}/ta/collect_log.json` 에 남기고 끝에 FAIL 목록을 찍는다.
의존이 실패하면 그 뒤는 `skip(dep)` 으로 표시한다(조용한 실패 패턴 차단).
"""
import argparse
import datetime as dt
import io
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta_common as tc  # noqa: E402

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SCRIPTS = os.path.join(tc.PROJECT_ROOT, 'scripts')
REAL_KIS_GAP = 65  # 실전 토큰은 분당 1회


def build_tasks(stock, code, opts):
    """(name, argv, deps, kis, optional_input) 목록. argv 는 scripts/ 기준 파일명 + 인자. dry-run·테스트가 이 표를 본다."""
    ta = tc.ta_dir(stock)
    y = dt.date.today().year
    ind = ['--industry-category', opts.industry_category] if opts.industry_category else []
    kw = ['--keywords', opts.keywords] if opts.keywords else []
    peers = ['--peers', opts.peers] if opts.peers else []
    gpeers = ['--peers', opts.global_peers] if opts.global_peers else []
    hk = [] if opts.hankyung else ['--no-hankyung']
    T = []

    def add(name, argv, deps=(), kis=False, needs=None):
        T.append({'name': name, 'argv': argv, 'deps': list(deps), 'kis': kis, 'needs': needs})

    # -- KIS 레인 (순서 고정, 직렬)
    add('financial_summary', ['financial_summary.py', stock, code], kis=True)
    add('market_data', ['ta_market_data.py', stock], kis=True)
    add('board_flow', ['ta_board_flow.py', stock], kis=True)
    add('peer_snapshot', ['peer_snapshot.py', stock] + ([opts.peer_key] if opts.peer_key else []) + peers, kis=True)
    add('fdr_band', ['fdr_band.py', stock, code], kis=True)
    add('volatility_beta', ['volatility_beta.py', stock, code], kis=True)
    # -- 병렬 (의존 없음)
    add('dart_full', ['collect_dart_full.py', stock])
    add('dart_filings', ['collect_dart_filings.py', stock])
    add('dart_quarterly', ['dart_quarterly.py', stock, str(y), str(y - 1)])
    add('wisereport', ['wisereport_consensus.py', stock, code])
    add('price_cycles', ['price_cycles.py', stock, code])
    add('news', ['ta_collect_news.py', stock])
    add('calendar', ['ta_calendar.py', stock])
    add('reports', ['ta_collect_reports.py', stock] + ind + kw + hk)
    add('macro', ['macro_data.py', 'KR', '--out', os.path.join(ta, 'macro.json')])
    add('kind_ir', ['ta_kind_ir.py', stock])
    add('company_ir', ['ta_company_ir.py', stock])
    add('peer_global', ['peer_snapshot_global.py', stock] + ([opts.peer_key] if opts.peer_key else []) + gpeers)
    add('trade_stats', ['ta_trade_stats.py', stock], needs=os.path.join(ta, 'trade_query.json'))
    add('customer_docs', ['ta_customer_docs.py', stock], needs=os.path.join(ta, 'customers.json'))
    # -- 의존 있음
    add('dart_diff', ['ta_dart_diff.py', stock], deps=['dart_full'])
    add('driver_scan', ['driver_scan.py', stock], deps=['dart_full'])
    add('event_study', ['ta_event_study.py', stock], deps=['news'])
    add('news_window', ['ta_news_window.py', stock], deps=['event_study'])
    add('event_study_2', ['ta_event_study.py', stock], deps=['news_window'])
    add('news_body', ['ta_news_body.py', stock], deps=['news'])
    add('evidence_scan', ['evidence_scan.py', stock], deps=['dart_full', 'reports'])
    add('company_voice', ['ta_company_voice.py', stock, '--irtv'], deps=['kind_ir', 'news_body'])
    add('build_snapshot', ['build_snapshot.py', stock], deps=['financial_summary', 'fdr_band', 'peer_snapshot', 'dart_full', 'wisereport'])
    add('plan_agents', ['ta_plan_agents.py', stock], deps=['event_study_2', 'dart_diff', 'reports', 'company_voice', 'board_flow'])
    return T


def select(tasks, only, skip):
    names = {t['name'] for t in tasks}
    for n in (only or []) + (skip or []):
        if n not in names:
            raise SystemExit(f'[collect_all] 모르는 작업: {n} (가능: {", ".join(sorted(names))})')
    if only:
        keep = set(only)
        # 선택한 것의 의존은 같이 돈다
        changed = True
        while changed:
            changed = False
            for t in tasks:
                if t['name'] in keep:
                    for d in t['deps']:
                        if d not in keep:
                            keep.add(d)
                            changed = True
        tasks = [t for t in tasks if t['name'] in keep]
    if skip:
        tasks = [t for t in tasks if t['name'] not in set(skip)]
    return tasks


def _cmd(argv, real_kis):
    exe = [sys.executable]
    if real_kis:
        exe += [os.path.join(SCRIPTS, '_run_with_real_kis.py')]
    return exe + [os.path.join(SCRIPTS, argv[0])] + list(argv[1:])


def run_one(task, real_kis, log, lock):
    if task.get('needs') and not os.path.exists(task['needs']):
        rec = {'status': 'skip', 'reason': f'입력 없음: {os.path.basename(task["needs"])}', 'sec': 0}
    else:
        t0 = time.time()
        p = subprocess.run(_cmd(task['argv'], real_kis and task['kis']), capture_output=True, cwd=tc.PROJECT_ROOT,
                           env=dict(os.environ, PYTHONIOENCODING='utf-8'))
        out = (p.stdout + p.stderr).decode('utf-8', 'replace').splitlines()
        rec = {'status': 'ok' if p.returncode == 0 else 'FAIL', 'returncode': p.returncode,
               'sec': round(time.time() - t0, 1), 'tail': [l for l in out if l.strip()][-6:]}
    with lock:
        log[task['name']] = rec
        mark = {'ok': '[ok  ]', 'FAIL': '[FAIL]', 'skip': '[skip]'}[rec['status']]
        print(f"  {mark} {task['name']:<18} {rec.get('sec', 0):>6}s  {rec.get('reason') or (rec['tail'][-1][:90] if rec.get('tail') else '')}")
        sys.stdout.flush()
    return rec['status']


def run_all(tasks, real_kis, workers, log, lock):
    """KIS 레인은 한 스레드에서 순서대로(실전이면 65초 간격), 나머지는 의존이 풀리는 대로 풀에 넣는다."""
    status = {}
    known = {t['name'] for t in tasks}
    for t in tasks:  # --skip 으로 빠진 의존은 skip 으로 두어 대기가 영원히 안 풀리는 일을 막는다
        for d in t['deps']:
            if d not in known:
                status[d] = 'skip'
    kis_tasks = [t for t in tasks if t['kis']]
    other = [t for t in tasks if not t['kis']]

    def kis_lane():
        for i, t in enumerate(kis_tasks):
            if real_kis and i > 0:
                time.sleep(REAL_KIS_GAP)
            status[t['name']] = run_one(t, real_kis, log, lock)

    pool = ThreadPoolExecutor(max_workers=workers)
    futures = {}
    if kis_tasks:
        futures[pool.submit(kis_lane)] = '__kis__'
    pending = list(other)
    while pending or futures:
        ready = []
        for t in list(pending):
            deps = t['deps']
            if all(status.get(d) == 'ok' for d in deps):
                ready.append(t)
            elif any(status.get(d) in ('FAIL', 'skip') for d in deps):
                bad = [d for d in deps if status.get(d) in ('FAIL', 'skip')]
                with lock:
                    log[t['name']] = {'status': 'skip', 'reason': f'의존 실패: {",".join(bad)}', 'sec': 0}
                    print(f"  [skip] {t['name']:<18} {'':>6}   의존 실패: {','.join(bad)}")
                status[t['name']] = 'skip'
                pending.remove(t)
        for t in ready:
            pending.remove(t)
            futures[pool.submit(run_one, t, real_kis, log, lock)] = t['name']
        if not futures:
            if pending:  # 의존이 영원히 안 풀림(KIS 레인 밖 의존이 kis 작업인데 kis 레인이 끝난 뒤 상태 갱신 전) -- 잠깐 대기
                time.sleep(0.5)
                continue
            break
        done, _ = wait(list(futures), return_when=FIRST_COMPLETED, timeout=1.0)
        for f in done:
            name = futures.pop(f)
            if name != '__kis__':
                status[name] = f.result()
    pool.shutdown(wait=True)
    return status


def main(argv=None):
    ap = argparse.ArgumentParser(description='/research-ta 수집기 병렬 실행')
    ap.add_argument('stock')
    ap.add_argument('--code', default=None)
    ap.add_argument('--peer-key', default=None, help='peer_snapshot / peer_snapshot_global 업종키')
    ap.add_argument('--peers', default=None, help='국내 Peer "이름:코드,..."')
    ap.add_argument('--global-peers', default=None, help='해외 Peer "이름:TICKER,..."')
    ap.add_argument('--industry-category', default=None)
    ap.add_argument('--keywords', default=None)
    ap.add_argument('--hankyung', action='store_true', help='한경 수집기 포함 (기본 제외 -- CJ ENM 30분 무응답)')
    ap.add_argument('--real-kis', action='store_true', help='KIS 실전 엔드포인트(_run_with_real_kis) + 65초 간격')
    ap.add_argument('--only', default=None, help='쉼표 구분 작업명 (의존은 자동 포함)')
    ap.add_argument('--skip', default=None)
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)

    info = tc.resolve_stock(a.stock, a.code)
    code = info['code']
    tasks = build_tasks(a.stock, code, a)
    tasks = select(tasks, a.only.split(',') if a.only else None, a.skip.split(',') if a.skip else None)
    print(f'[collect_all] {a.stock}({code}) -- 작업 {len(tasks)}개, KIS 레인 {sum(t["kis"] for t in tasks)}개'
          f'{" (실전, 65초 간격)" if a.real_kis else ""}, 워커 {a.workers}')
    if a.dry_run:
        for t in tasks:
            print(f"  {'KIS ' if t['kis'] else '    '}{t['name']:<18} {' '.join(t['argv'])}"
                  f"{'  <- ' + ','.join(t['deps']) if t['deps'] else ''}")
        return 0

    log, lock = {}, threading.Lock()
    t0 = time.time()
    status = run_all(tasks, a.real_kis, a.workers, log, lock)
    total = round(time.time() - t0)
    fails = [n for n, s in status.items() if s == 'FAIL']
    skips = [n for n, s in status.items() if s == 'skip']
    out = {'stock': a.stock, 'code': code, 'asof': tc.now_kst().isoformat(), 'total_sec': total,
           'real_kis': a.real_kis, 'tasks': log, 'fails': fails, 'skips': skips}
    path = os.path.join(tc.ta_dir(a.stock), 'collect_log.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tc.write_json(path, out)
    print(f'[collect_all] {a.stock} -- {total // 60}분 {total % 60}초, ok {len(status) - len(fails) - len(skips)} / FAIL {len(fails)} / skip {len(skips)}'
          f'{" -- FAIL: " + ", ".join(fails) if fails else ""} -> {path}')
    if fails:
        print('  실패한 작업은 넘어가지 말고 원인을 본다(조용한 실패 패턴). 단독 재실행: --only ' + ','.join(fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
