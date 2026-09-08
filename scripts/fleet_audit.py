"""fleet_audit.py -- 발간한 모든 리포트를 현행 검증기로 한 번에 훑는다.

v5.20 규칙 1("새 검증기는 그날 안에 전 종목에 돌린다")을 손으로 하지 않게 만든다.

배경(2026-09-09): `section_rubric`(v5.15)을 만들고 그 주 리포트 6건에만 돌렸다.
같은 주의 나머지 둘에서 10 FAIL 이 나왔는데 그 상태로 "전부 0 FAIL"이라고
보고했다. 규칙으로 적어도 손으로 하면 또 빠뜨린다.

**옛 리포트가 FAIL 이라고 곧바로 고치라는 뜻이 아니다.** 4~5월 리포트는
데이터가 5개월 지나 v5.4 규칙 8 상 전면 재수집 대상이고, 고치는 것은
수정이 아니라 새로 쓰는 일이다. 이 도구의 목적은 **어느 리포트가 현행
기준을 만족하는지 알고 있는 것** -- 옛것을 최신인 줄 알고 인용하지 않기 위해서다.

사용:
    python scripts/fleet_audit.py                 # 전체
    python scripts/fleet_audit.py --since 2026-09-01
    python scripts/fleet_audit.py --checker section_rubric
"""
import glob
import io
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# (스크립트, 표시 이름, US 전용 여부)
CHECKERS = [
    ('section_rubric', '루브릭', None),
    ('source_coverage', '출처', None),
    ('verify_facts', '팩트', None),
    ('verify_numbers', '수치', 'KR'),
    ('verify_numbers_us', '수치', 'US'),
]

_FAIL_PATTERNS = [
    re.compile(r'FAIL\s+(\d+)건'),
    re.compile(r'총 FAIL:\s*(\d+)'),
    re.compile(r'총 D 블록 FAIL[^:]*:\s*(\d+)'),
]


def parse_fail(out):
    """검증기 출력에서 FAIL 건수를 뽑는다. SKIP 이면 None."""
    if not out:
        return None
    if '[SKIP]' in out and 'FAIL' not in out:
        return None
    for pat in _FAIL_PATTERNS:
        m = pat.search(out)
        if m:
            return int(m.group(1))
    if '[OK]' in out:
        return 0
    return None


def is_us(name):
    """KR/US 판정. `meta.country` 를 먼저 본다.

    CLAUDE.md 는 `data_kis_us.json` 존재로 분기하라고 적어 두었는데,
    그 파일은 수집 방식에 따라 없을 수도 있다(LULU 실측 -- 파일이 없는데
    verify_numbers_us 는 정상 동작). 파일만 보면 US 종목에 KR 검증기를
    돌려 '판정 불가'가 된다.
    """
    p = os.path.join(ROOT, 'scripts', f'analysis_{name}.json')
    try:
        c = (json.load(open(p, encoding='utf-8')).get('meta') or {}).get('country', '')
        if str(c).upper() in ('US', 'USA'):
            return True
        if str(c).upper() in ('KR', 'KOR'):
            return False
    except Exception:                                          # noqa: BLE001
        pass
    return os.path.exists(os.path.join(ROOT, 'data', name, 'data_kis_us.json'))


def report_names(since=None):
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'scripts', 'analysis_*.json'))):
        name = os.path.basename(p)[len('analysis_'):-len('.json')]
        if name == 'template':
            continue
        date = ''
        try:
            date = (json.load(open(p, encoding='utf-8')).get('meta') or {}).get('date', '')
        except Exception:                                      # noqa: BLE001
            pass
        if since and date < since:
            continue
        out.append((name, date))
    return out


def run_one(checker, name):
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', f'{checker}.py'), name],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', cwd=ROOT)
    return parse_fail(r.stdout)


def audit(since=None, only=None):
    rows = []
    for name, date in report_names(since):
        us = is_us(name)
        res = {}
        for script, label, scope in CHECKERS:
            if scope == 'KR' and us:
                continue
            if scope == 'US' and not us:
                continue
            if only and script != only:
                continue
            res[label] = run_one(script, name)
        rows.append({'name': name, 'date': date, 'us': us, 'res': res})
    return rows


def main(argv):
    since = only = None
    if '--since' in argv:
        i = argv.index('--since')
        since = argv[i + 1] if i + 1 < len(argv) else None
    if '--checker' in argv:
        i = argv.index('--checker')
        only = argv[i + 1] if i + 1 < len(argv) else None

    rows = audit(since, only)
    if not rows:
        print('[ERR] 대상 리포트가 없다')
        return 2

    labels = []
    for r in rows:
        for k in r['res']:
            if k not in labels:
                labels.append(k)

    print('=' * 78)
    print(f'  fleet_audit -- 발간 리포트 {len(rows)}건을 현행 검증기로 훑는다')
    if since:
        print(f'  since {since}')
    print('=' * 78)
    print('  %-20s %-10s %s' % ('종목', '발간일',
                                ' '.join(f'{x:>7}' for x in labels)))
    print('  ' + '-' * 74)

    clean, dirty, unknown = [], [], []
    for r in sorted(rows, key=lambda x: x['date'], reverse=True):
        cells = []
        vals = []
        for lb in labels:
            v = r['res'].get(lb)
            vals.append(v)
            cells.append('%7s' % ('-' if v is None else v))
        print('  %-20s %-10s %s' % (r['name'][:20], r['date'] or '?', ' '.join(cells)))
        known = [v for v in vals if v is not None]
        if not known:
            unknown.append(r['name'])
        elif sum(known) == 0:
            clean.append(r['name'])
        else:
            dirty.append(r['name'])

    print()
    print('-' * 78)
    print(f'  현행 기준 통과 {len(clean)}건 / 결함 {len(dirty)}건 / 판정 불가 {len(unknown)}건')
    print()
    print('  [판정 불가] 1차 출처 덤프가 없어 검증이 성립하지 않는 리포트다.')
    print('  [결함] 대부분 그 검증기가 없던 시점에 쓴 리포트다.')
    print('  **곧바로 고치라는 뜻이 아니다** -- 데이터가 7일 넘게 지났으면')
    print('  v5.4 규칙 8 상 전면 재수집 대상이고, 그것은 수정이 아니라 새로 쓰는 일이다.')
    print('  이 표의 목적은 **어느 리포트가 현행 기준인지 알고 있는 것**이다.')
    print('=' * 78)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
