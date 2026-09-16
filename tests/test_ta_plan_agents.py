"""ta_plan_agents.py 테스트 -- 분석가 호출 계획 (Task 9).

네트워크 없음. data/{종목}/ 트리를 임시 폴더에 만들고 tc.PROJECT_ROOT 를
바꿔치기해서 build_plan() 을 돈다.

실행: python tests/test_ta_plan_agents.py
"""
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import ta_common as tc               # noqa: E402
import ta_plan_agents as pa          # noqa: E402

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_passed = 0
_failed = []


def eq(got, want, label):
    global _passed
    if got == want:
        _passed += 1
    else:
        _failed.append((label, want, got))


def _write(root, stock, rel, content):
    p = os.path.join(root, 'data', stock, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(content)
    return p


def _calls_by_role_prefix(plan, prefix):
    return [c for c in plan['calls'] if c['role'] == prefix or c['role'].startswith(prefix + '#')]


# ==================== 1. 작은 입력 -> 역할당 1호출 ====================
with tempfile.TemporaryDirectory() as td:
    orig = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        stock = '테스트종목'
        _write(td, stock, 'ta/news_relevant.json', '{"a":1}')
        _write(td, stock, 'ta/dart/business.txt', '사업내용 본문')
        plan = pa.build_plan(stock, max_chars=120000, merge_under=40000)

        news_calls = [c for c in plan['calls'] if c['role'] == 'news']
        eq(len(news_calls), 1, 'news 역할 1호출')
        eq(news_calls[0]['call_id'], 'news', '분할 없으면 call_id == role')
        eq(news_calls[0]['reason'], '단일', '분할 없으면 사유 단일')
        eq(news_calls[0]['inputs'], [{'file': 'ta/news_relevant.json', 'chars': len('{"a":1}')}],
           'news 입력은 news_relevant.json (필터링된 것만)')

        fund_calls = [c for c in plan['calls'] if c['role'] == 'fundamentals']
        eq(len(fund_calls), 1, 'fundamentals 도 1호출(다른 입력 없어도 있는 것만)')
        eq(fund_calls[0]['inputs'],
           [{'file': 'ta/dart/business.txt', 'chars': len('사업내용 본문')}],
           'fundamentals 입력에 있는 파일만 담김')

        eq({s['role'] for s in plan['skipped']}, {'sellside', 'industry', 'macro', 'market'},
           '입력 전부 없는 역할은 skipped')
        for s in plan['skipped']:
            eq(s['reason'], '입력 파일 없음', f"{s['role']} skipped 사유")

        eq(plan['warnings'], [], '누락 manifest 엔트리 없으면 warnings 비어있음')
        eq('missing_inputs' in news_calls[0], False, '누락 없으면 missing_inputs 키를 안 붙인다')
    finally:
        tc.PROJECT_ROOT = orig


# ==================== 2. 합계 초과 -> 파일 단위 분할, 순서 보존 ====================
with tempfile.TemporaryDirectory() as td:
    orig = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        stock = '분할종목'
        # 각 60자, max_chars=100 -> 2개씩 못 들어가므로 파일당 1개 호출 근처가 나온다
        _write(td, stock, 'ta/dart/business.txt', 'A' * 60)
        _write(td, stock, 'ta/dart/risk_mgmt.txt', 'B' * 60)
        _write(td, stock, 'ta/dart/notes_selected.txt', 'C' * 60)
        plan = pa.build_plan(stock, max_chars=100, merge_under=40000)

        fund_calls = sorted((c for c in plan['calls'] if c['role'].startswith('fundamentals')),
                             key=lambda c: c['call_id'])
        eq(len(fund_calls) >= 2, True, '용량 초과면 2호출 이상으로 쪼개진다')
        eq(all(c['reason'].startswith('용량 초과로 분할') for c in fund_calls),
           True, '분할 사유 문구')
        # 순서 보존: 모든 호출의 파일을 이어붙이면 원래 순서
        seen_files = []
        for c in fund_calls:
            for it in c['inputs']:
                seen_files.append(it['file'])
        eq(seen_files, ['ta/dart/business.txt', 'ta/dart/risk_mgmt.txt', 'ta/dart/notes_selected.txt'],
           '분할되어도 파일 순서는 원래 그대로')
        eq(all(c['chars'] <= 100 for c in fund_calls), True, '각 호출은 max_chars 이하')
    finally:
        tc.PROJECT_ROOT = orig


# ==================== 3. 단일 파일 초과 -> 줄 범위 분할 ====================
with tempfile.TemporaryDirectory() as td:
    orig = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        stock = '큰파일종목'
        lines = [f'줄{i:02d}\n' for i in range(1, 21)]  # 각 4자, 총 80자
        _write(td, stock, 'ta/market_data.json', ''.join(lines))
        plan = pa.build_plan(stock, max_chars=25, merge_under=40000)

        market_calls = sorted((c for c in plan['calls'] if c['role'].startswith('market')),
                               key=lambda c: c['call_id'])
        eq(len(market_calls) >= 2, True, '단일 파일 초과는 여러 호출로 쪼개진다')

        ranges = []
        for c in market_calls:
            for it in c['inputs']:
                eq(it['file'], 'ta/market_data.json', '분할된 항목은 같은 파일을 가리킨다')
                eq('lines' in it, True, '분할 항목엔 lines 범위가 있다')
                ranges.append(tuple(it['lines']))

        ranges.sort()
        eq(ranges[0][0], 1, '첫 줄부터 시작')
        eq(ranges[-1][1], 20, '마지막 줄(20)까지 커버')
        # 줄 경계 연속(겹치거나 구멍 없음)
        ok = True
        for a, b in zip(ranges, ranges[1:]):
            if b[0] != a[1] + 1:
                ok = False
        eq(ok, True, '줄 범위가 경계에서만 이어붙는다(겹침/구멍 없음)')
        total_lines_covered = sum(e - s + 1 for s, e in ranges)
        eq(total_lines_covered, 20, '범위 합이 전체 줄 수(20)와 일치')
    finally:
        tc.PROJECT_ROOT = orig


# ==================== 4. sellside+industry 병합 경계 ====================
with tempfile.TemporaryDirectory() as td:
    orig = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        stock = '병합종목'
        tc.write_json(os.path.join(td, 'data', stock, 'ta', 'reports', 'company', '_manifest.json'),
                       {'reports': [{'txt': 'ta/reports/company/nv_1.txt'}]})
        _write(td, stock, 'ta/reports/company/nv_1.txt', 'X' * 100)  # manifest 자체도 카운트됨
        tc.write_json(os.path.join(td, 'data', stock, 'ta', 'reports', 'industry', '_manifest.json'),
                       {'reports': [{'txt': 'ta/reports/industry/nv_2.txt'}]})
        _write(td, stock, 'ta/reports/industry/nv_2.txt', 'Y' * 100)

        # merge_under 를 아주 크게 잡으면 합쳐진다
        plan_merge = pa.build_plan(stock, max_chars=120000, merge_under=10 ** 9)
        merged_calls = [c for c in plan_merge['calls'] if c['role'] == 'sellside+industry']
        eq(len(merged_calls), 1, '합계가 merge_under 미만이면 병합된다')
        eq(merged_calls[0]['call_id'], 'sellside+industry', '병합 call_id')
        eq(merged_calls[0]['reason'], '자료 적음으로 병합', '병합 사유')
        files_in_merge = [it['file'] for it in merged_calls[0]['inputs']]
        eq(files_in_merge, [
            'ta/reports/company/_manifest.json', 'ta/reports/company/nv_1.txt',
            'ta/reports/industry/_manifest.json', 'ta/reports/industry/nv_2.txt',
        ], '병합 입력은 sellside 다음 industry 순서, manifest+reports[].txt 포함')
        eq(any(c['role'] in ('sellside', 'industry') for c in plan_merge['calls']), False,
           '병합되면 개별 sellside/industry 호출은 없다')

        # merge_under 를 아주 작게 잡으면 병합되지 않는다
        plan_nomerge = pa.build_plan(stock, max_chars=120000, merge_under=1)
        roles_nomerge = {c['role'] for c in plan_nomerge['calls']}
        eq('sellside' in roles_nomerge and 'industry' in roles_nomerge, True,
           '합계가 merge_under 이상이면 병합하지 않는다')
        eq('sellside+industry' in roles_nomerge, False, '병합 호출이 없다')
    finally:
        tc.PROJECT_ROOT = orig


# ==================== 5. manifest 의 reports[].txt 를 따라가 입력에 포함 ====================
with tempfile.TemporaryDirectory() as td:
    orig = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        stock = '매니페스트종목'
        tc.write_json(os.path.join(td, 'data', stock, 'ta', 'reports', 'company', '_manifest.json'),
                       {'reports': [
                           {'txt': 'ta/reports/company/nv_1.txt'},
                           {'txt': 'ta/reports/company/nv_2.txt'},   # 실제 파일 없음 -> 빠져야 함
                           {'txt': 'ta/reports/company/hk_3.txt'},
                       ]})
        _write(td, stock, 'ta/reports/company/nv_1.txt', '리포트1')
        _write(td, stock, 'ta/reports/company/hk_3.txt', '리포트3')
        plan = pa.build_plan(stock, max_chars=120000, merge_under=0)

        sell_calls = [c for c in plan['calls'] if c['role'] == 'sellside']
        eq(len(sell_calls), 1, 'sellside 1호출')
        files = [it['file'] for it in sell_calls[0]['inputs']]
        eq(files, ['ta/reports/company/_manifest.json',
                    'ta/reports/company/nv_1.txt', 'ta/reports/company/hk_3.txt'],
           'manifest + 존재하는 reports[].txt 만 순서대로 담긴다 (없는 nv_2 는 inputs 에서 빠짐)')
        # 없는 nv_2.txt 는 조용히 사라지지 않고 missing_inputs/warnings 에 남는다
        eq(sell_calls[0].get('missing_inputs'),
           [{'file': 'ta/reports/company/nv_2.txt', 'reason': 'manifest 에 있으나 파일 없음'}],
           '호출에 missing_inputs 기록')
        eq(plan['warnings'],
           [{'role': 'sellside', 'file': 'ta/reports/company/nv_2.txt',
             'reason': 'manifest 에 있으나 파일 없음'}],
           'top-level warnings 에도 기록')
    finally:
        tc.PROJECT_ROOT = orig


# ==================== 6. macro 의 risk_mgmt.txt 는 fundamentals 와 중복 허용 ====================
with tempfile.TemporaryDirectory() as td:
    orig = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        stock = '중복허용종목'
        _write(td, stock, 'ta/dart/risk_mgmt.txt', '민감도 표')
        plan = pa.build_plan(stock, max_chars=120000, merge_under=40000)
        fund = [c for c in plan['calls'] if c['role'] == 'fundamentals'][0]
        macro = [c for c in plan['calls'] if c['role'] == 'macro'][0]
        eq(any(it['file'] == 'ta/dart/risk_mgmt.txt' for it in fund['inputs']), True,
           'fundamentals 도 risk_mgmt.txt 를 본다')
        eq(any(it['file'] == 'ta/dart/risk_mgmt.txt' for it in macro['inputs']), True,
           'macro 도 risk_mgmt.txt 를 본다(중복 허용)')
    finally:
        tc.PROJECT_ROOT = orig


# ==================== 7. news_relevant.json 없으면 news.json 으로 몰래 대체하지 않는다 ====================
with tempfile.TemporaryDirectory() as td:
    orig = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        stock = '뉴스미완료종목'
        # news.json(원본)만 있고 news_relevant.json(필터링본)은 아직 없음.
        # event_study.json 처럼 news 역할의 다른 입력이 있어도 role 전체를 skipped 로 보낸다.
        _write(td, stock, 'ta/news.json', 'X' * 500000)
        _write(td, stock, 'ta/event_study.json', '{}')
        plan = pa.build_plan(stock, max_chars=120000, merge_under=40000)

        eq(any(c['role'] == 'news' for c in plan['calls']), False,
           'news_relevant.json 없으면 news 호출을 만들지 않는다')
        eq(any('news.json' in it['file'] for c in plan['calls'] for it in c['inputs']), False,
           'news.json(원본) 은 어떤 호출 입력에도 조용히 들어가지 않는다')
        news_skip = [s for s in plan['skipped'] if s['role'] == 'news']
        eq(len(news_skip), 1, 'news 는 skipped 에 1건')
        eq(news_skip[0]['reason'], 'news_relevant.json 없음 (ta_collect_news 재실행 필요)',
           'skipped 사유가 재실행 필요를 명시한다')

        # news.json 도 news_relevant.json 도 둘 다 없으면 일반 사유
        stock2 = '뉴스둘다없음종목'
        plan2 = pa.build_plan(stock2, max_chars=120000, merge_under=40000)
        news_skip2 = [s for s in plan2['skipped'] if s['role'] == 'news']
        eq(news_skip2[0]['reason'], '입력 파일 없음', '뉴스 파일이 둘 다 없으면 일반 skipped 사유')

        # news_relevant.json 이 있으면 news.json 존재 여부와 무관하게 정상 처리
        stock3 = '뉴스정상종목'
        _write(td, stock3, 'ta/news.json', 'X' * 500000)
        _write(td, stock3, 'ta/news_relevant.json', '관련 뉴스만')
        plan3 = pa.build_plan(stock3, max_chars=120000, merge_under=40000)
        news_calls3 = [c for c in plan3['calls'] if c['role'] == 'news']
        eq(len(news_calls3), 1, 'news_relevant.json 이 있으면 news 호출이 정상 생성된다')
        eq([it['file'] for it in news_calls3[0]['inputs']], ['ta/news_relevant.json'],
           'news.json 이 같이 있어도 news_relevant.json 만 쓴다')
    finally:
        tc.PROJECT_ROOT = orig


# ==================== 8. 병합된 sellside+industry 호출도 missing_inputs 를 합쳐서 기록 ====================
with tempfile.TemporaryDirectory() as td:
    orig = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        stock = '병합누락종목'
        tc.write_json(os.path.join(td, 'data', stock, 'ta', 'reports', 'company', '_manifest.json'),
                       {'reports': [
                           {'txt': 'ta/reports/company/nv_1.txt'},
                           {'txt': 'ta/reports/company/nv_missing.txt'},   # 파일 없음
                       ]})
        _write(td, stock, 'ta/reports/company/nv_1.txt', 'X' * 50)
        tc.write_json(os.path.join(td, 'data', stock, 'ta', 'reports', 'industry', '_manifest.json'),
                       {'reports': [
                           {'txt': 'ta/reports/industry/nv_2.txt'},
                           {'txt': 'ta/reports/industry/nv_missing2.txt'},  # 파일 없음
                       ]})
        _write(td, stock, 'ta/reports/industry/nv_2.txt', 'Y' * 50)

        plan = pa.build_plan(stock, max_chars=120000, merge_under=10 ** 9)  # 합계가 작아 병합됨
        merged_calls = [c for c in plan['calls'] if c['role'] == 'sellside+industry']
        eq(len(merged_calls), 1, '병합 호출 1개')
        eq(merged_calls[0].get('missing_inputs'), [
            {'file': 'ta/reports/company/nv_missing.txt', 'reason': 'manifest 에 있으나 파일 없음'},
            {'file': 'ta/reports/industry/nv_missing2.txt', 'reason': 'manifest 에 있으나 파일 없음'},
        ], '병합 호출은 sellside + industry 양쪽 누락을 합쳐 기록')

        eq(sorted(plan['warnings'], key=lambda w: w['file']), sorted([
            {'role': 'sellside', 'file': 'ta/reports/company/nv_missing.txt',
             'reason': 'manifest 에 있으나 파일 없음'},
            {'role': 'industry', 'file': 'ta/reports/industry/nv_missing2.txt',
             'reason': 'manifest 에 있으나 파일 없음'},
        ], key=lambda w: w['file']), 'top-level warnings 는 병합 여부와 무관하게 역할별로 남는다')
    finally:
        tc.PROJECT_ROOT = orig


print('=' * 66)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  ta_plan_agents 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
