"""rating_distribution.py -- 등급과 목표가가 한쪽으로 기울지 않았는지 본다.

배경(2026-09-09): 사용자가 "BUY 가 나오는 종목이 있어"라고 물어 세어 봤더니
v5.14 이후 8건 중 SELL 이 62% 였다(그 이전 29건은 7%). 더 깊이 보니 등급이
아니라 **목표주가**가 먼저 기울어 있었다 -- 컨센 대비 중앙값이 v5.8 까지
-7.7% 였는데 v5.9 이후 -25% 로 벌어졌고, **30종목 중 컨센을 넘는 목표가는 5건**뿐이다.

이 기울기 자체가 틀렸다는 뜻은 아니다. 국내 셀사이드 목표가는 낙관 편향이
문서화돼 있고, bottom-up(v5.10 규칙 3)·자본효율 정당화(v5.12 규칙 5)·
DCF 병행(v5.15 규칙 3)은 전부 좋은 규칙이다. **다만 셋이 같은 방향을 밀기
때문에 누적 효과를 눈으로 봐야 한다.**

사람이 우연히 발견하는 대신 코드가 보여 준다.

사용:
    python scripts/rating_distribution.py            # 전체
    python scripts/rating_distribution.py --since 2026-06-01
"""
import glob
import io
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# verify_facts 는 import 시점에 sys.stdout 을 자기 wrapper 로 바꾼다.
# 먼저 감싸 두면 그쪽이 교체하면서 이쪽 버퍼가 닫혀 ValueError 가 난다.
# 그래서 **import 를 먼저 하고 그다음에 감싼다.** (실측 2회)
try:
    from verify_facts import consensus_target
except Exception as _e:                                        # noqa: BLE001
    consensus_target = None
    _import_err = f'{type(_e).__name__}: {_e}'
else:
    _import_err = None

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 스킬 버전대 경계 -- 규칙이 크게 바뀐 날
ERAS = [
    ('2026-09-08', 'v5.14+  (1차 출처·6축)'),
    ('2026-06-01', 'v5.9~13 (수상작 논증)'),
    ('0000-00-00', 'v4.x~5.8'),
]

# 경고 임계 -- 넘으면 편향을 의심한다
MAX_ONE_SIDE = 0.75      # 한 등급이 75% 넘게 몰리면
MAX_MEDIAN_GAP = 25.0    # 컨센 대비 중앙값이 |25%| 넘게 벌어지면
MIN_N = 5                # 표본이 이보다 적으면 경고하지 않는다


def era_of(date_str):
    for boundary, label in ERAS:
        if (date_str or '') >= boundary:
            return label
    return ERAS[-1][1]


def collect(since=None):
    """analysis_*.json 을 모아 (종목, 날짜, 등급, 컨센 괴리%) 로 만든다."""
    ct_fn = consensus_target
    if ct_fn is None:
        print(f'[WARN] verify_facts import 실패({_import_err}) -- 컨센 괴리는 건너뛴다')
        def ct_fn(_):                                          # noqa: E306
            return None, None

    rows = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'scripts', 'analysis_*.json'))):
        name = os.path.basename(p)[len('analysis_'):-len('.json')]
        if name == 'template':
            continue
        try:
            d = json.load(open(p, encoding='utf-8'))
        except Exception as e:                                 # noqa: BLE001
            print(f'[WARN] {name}: 읽기 실패 {type(e).__name__}')
            continue
        date = (d.get('meta') or {}).get('date', '')
        if since and date < since:
            continue
        rating = ((d.get('opinion') or {}).get('rating') or '?').split()[0].upper()
        base = (d.get('opinion') or {}).get('target_base')
        ct, _src = ct_fn(name)
        gap = (float(base) / float(ct) - 1) * 100 if (base and ct) else None
        rows.append({'name': name, 'date': date, 'rating': rating, 'gap': gap})
    return rows


def summarize(rows):
    """버전대별 등급 분포와 컨센 괴리."""
    out = {}
    for r in rows:
        out.setdefault(era_of(r['date']), []).append(r)
    return out


def warnings_for(bucket):
    """이 표본이 한쪽으로 기울었는가. 문자열 목록을 돌려준다."""
    msgs = []
    n = len(bucket)
    if n < MIN_N:
        return msgs
    counts = {}
    for r in bucket:
        counts[r['rating']] = counts.get(r['rating'], 0) + 1
    for rating, c in counts.items():
        if rating in ('BUY', 'HOLD', 'SELL') and c / n > MAX_ONE_SIDE:
            msgs.append(f'{rating} 가 {c}/{n} ({c / n * 100:.0f}%) -- 한쪽 쏠림 의심')
    gaps = [r['gap'] for r in bucket if r['gap'] is not None]
    if len(gaps) >= MIN_N:
        med = statistics.median(gaps)
        if abs(med) > MAX_MEDIAN_GAP:
            msgs.append(f'컨센 대비 중앙값 {med:+.1f}% -- 목표가가 한 방향으로 치우쳤다')
        above = sum(1 for g in gaps if g > 0)
        if above == 0:
            msgs.append(f'{len(gaps)}종목 전부 컨센 아래 -- 컨센을 넘는 판단이 한 건도 없다')
    return msgs


def main(argv):
    since = None
    if '--since' in argv:
        i = argv.index('--since')
        if i + 1 < len(argv):
            since = argv[i + 1]

    rows = collect(since)
    if not rows:
        print('[ERR] analysis_*.json 을 찾지 못했다')
        return 2

    print('=' * 74)
    print('  rating_distribution -- 등급·목표가 편향 점검')
    print(f'  대상 {len(rows)}종목' + (f' (since {since})' if since else ''))
    print('=' * 74)

    buckets = summarize(rows)
    total_warn = 0
    for _boundary, label in ERAS:
        b = buckets.get(label)
        if not b:
            continue
        n = len(b)
        c = {k: sum(1 for r in b if r['rating'] == k) for k in ('BUY', 'HOLD', 'SELL')}
        gaps = [r['gap'] for r in b if r['gap'] is not None]
        gtxt = (f'컨센 대비 중앙값 {statistics.median(gaps):+6.1f}% (n={len(gaps)})'
                if gaps else '컨센 데이터 없음')
        print(f'\n  [{label}]  n={n}')
        print(f'    BUY {c["BUY"]:2d} ({c["BUY"] / n * 100:3.0f}%) / '
              f'HOLD {c["HOLD"]:2d} ({c["HOLD"] / n * 100:3.0f}%) / '
              f'SELL {c["SELL"]:2d} ({c["SELL"] / n * 100:3.0f}%)')
        print(f'    {gtxt}')
        for m in warnings_for(b):
            total_warn += 1
            print(f'    [!] {m}')

    print()
    print('-' * 74)
    if total_warn:
        print(f'  경고 {total_warn}건. **틀렸다는 뜻이 아니라 확인하라는 뜻이다.**')
        print('  국내 셀사이드 목표가는 낙관 편향이 있어 컨센 아래가 정상일 수 있다.')
        print('  다만 bottom-up(v5.10) · 자본효율(v5.12) · DCF 병행(v5.15)이')
        print('  모두 같은 방향을 밀기 때문에 누적 효과를 주기적으로 본다.')
    else:
        print('  쏠림 경고 없음.')
    print('=' * 74)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
