"""ta_collect_all 테스트 -- 작업 표·의존·선택·명령 조립 (서브프로세스는 돌리지 않는다)."""
import io
import os
import sys
import types

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
import ta_collect_all as c  # noqa: E402

FAILS = []


def eq(got, want, label):
    if got != want:
        FAILS.append(label)
        print(f'  [FAIL] {label}: got={got!r} want={want!r}')
    else:
        print(f'  [ok  ] {label}')


def opts(**kw):
    base = dict(peer_key=None, peers=None, global_peers=None, industry_category=None, keywords=None, hankyung=False)
    base.update(kw)
    return types.SimpleNamespace(**base)


T = c.build_tasks('CJ ENM', '035760', opts(peer_key='media', industry_category='미디어', keywords='OTT,광고'))
names = [t['name'] for t in T]
byn = {t['name']: t for t in T}

eq(len(names), len(set(names)), '작업명 중복 없음')
for t in T:
    for d in t['deps']:
        eq(d in byn, True, f'의존 {t["name"]} <- {d} 가 표에 있다')
    eq(all(names.index(d) < names.index(t['name']) for d in t['deps']), True, f'{t["name"]} 의존이 먼저 온다')
eq([t['name'] for t in T if t['kis']][0], 'financial_summary', 'KIS 레인 첫 작업은 financial_summary')
eq(byn['financial_summary']['argv'], ['financial_summary.py', 'CJ ENM', '035760'], '공백 종목명이 한 인자')
eq(byn['reports']['argv'], ['ta_collect_reports.py', 'CJ ENM', '--industry-category', '미디어', '--keywords', 'OTT,광고', '--no-hankyung'], '리포트 수집기 인자 + 한경 기본 제외')
eq('--no-hankyung' in c.build_tasks('CJ ENM', '035760', opts(hankyung=True))[names.index('reports')]['argv'], False, '--hankyung 이면 한경 포함')
eq(byn['peer_snapshot']['argv'], ['peer_snapshot.py', 'CJ ENM', 'media'], '업종키 전달')
eq(byn['event_study_2']['deps'], ['news_window'], '이벤트 스터디 2회차는 뉴스 창 뒤')
eq(byn['company_voice']['deps'], ['kind_ir', 'news_body'], 'company_voice 는 IR + 뉴스 본문 뒤')
eq(byn['news_body']['deps'], ['news_window'], 'news_body 와 news_window 는 같은 파일을 쓰므로 직렬')
eq(byn['company_ir']['deps'], ['kind_ir'], 'company_ir 와 kind_ir 는 같은 index.json 을 쓰므로 직렬')
eq(set(byn['event_study']['deps']) >= {'dart_filings', 'price_cycles'}, True, 'event_study 는 공시·사이클 파일 뒤')
eq(byn['trade_stats']['needs'].endswith('trade_query.json'), True, 'trade_stats 는 입력 파일 있을 때만')
eq('financial_summary' in byn['build_snapshot']['deps'], True, 'build_snapshot 은 KIS 레인 뒤')

S = c.select(T, ['event_study_2'], None)
eq([t['name'] for t in S], ['dart_filings', 'price_cycles', 'news', 'event_study', 'news_window', 'event_study_2'], '--only 는 의존을 자동 포함하고 순서 유지')
S2 = c.select(T, None, ['reports', 'evidence_scan'])
eq('reports' in [t['name'] for t in S2], False, '--skip 제외')
try:
    c.select(T, ['없는작업'], None)
    eq(True, False, '모르는 작업명은 SystemExit')
except SystemExit:
    eq(True, True, '모르는 작업명은 SystemExit')

cmd = c._cmd(['fdr_band.py', 'CJ ENM', '035760'], real_kis=True)
eq(os.path.basename(cmd[1]), '_run_with_real_kis.py', '실전이면 래퍼로 감싼다')
eq(cmd[-2:], ['CJ ENM', '035760'], '래퍼 뒤에 원래 인자')
cmd2 = c._cmd(['fdr_band.py', 'CJ ENM', '035760'], real_kis=False)
eq(any('_run_with_real_kis' in x for x in cmd2), False, '모의면 래퍼 없음')

print(f'\n  ta_collect_all 테스트: {len(FAILS)}개 실패' if FAILS else '\n  ta_collect_all 테스트: 전부 통과')
sys.exit(1 if FAILS else 0)
