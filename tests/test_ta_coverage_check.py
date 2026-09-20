"""ta_coverage_check.py 테스트 -- 분석가 brief 반영 게이트 (Task 11).

날짜·수치 매칭은 오탐이 나서 쓰지 않는다. brief 의 항목 ID 와 작성자의
coverage_map 만으로 결정론적으로 판정한다. 네트워크 없음 -- 전부 임시 폴더에
picture 를 만들어 tc.PROJECT_ROOT 를 갈아끼운다.

실행: python tests/test_ta_coverage_check.py
"""
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import ta_common as tc                                  # noqa: E402
import ta_coverage_check as cc                           # noqa: E402

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


# ==================== 표 파싱 ====================
TABLE_TEXT = """
# brief

## 산업 (N)

| 항목 | ID | 설명 | 필수 |
|---|---|---|---|
| 밸류체인 | N01 | 밸류체인 재편 | Y |
| 참고 | n02 | 소문자는 ID 형식 아님 | Y |
| 자리수 | NNN123 | 3글자 접두는 ID 형식 아님 | Y |
| 보류 | N03 |  | n |
| 공백필수 | N04 |  |  |

## 재무 (F)

| ID | 필수 | 비고 |
|---|---|---|
| F01 | Y | 순현금 |
| F02 | y | 대소문자 허용 |
| 1 | Y | 숫자만은 ID 형식 아님 |
"""

rows = cc.parse_tables(TABLE_TEXT)
ids_found = sorted(r['id'] for r in rows)
eq(ids_found, ['F01', 'F02', 'N01', 'N03', 'N04'], 'ID 형식 아닌 행은 무시하고, 열 위치가 다른 두 표를 모두 읽는다')
eq({r['id']: r['required'] for r in rows}['N01'], True, '필수=Y')
eq({r['id']: r['required'] for r in rows}['N03'], False, '필수=n(소문자 n) 은 required 아님')
eq({r['id']: r['required'] for r in rows}['N04'], False, '필수 공백은 required 아님')
eq({r['id']: r['required'] for r in rows}['F02'], True, '필수=y(소문자) 도 Y 로 인정')

# ==================== 중복 ID ====================
occ_dup = cc.parse_briefs_text({'brief_a.md': '| ID | 필수 |\n|---|---|\n| N01 | Y |\n',
                                 'brief_b.md': '| ID | 필수 |\n|---|---|\n| N01 | Y |\n'})
report = cc.evaluate(occ_dup, {}, {})
item = next(i for i in report['items'] if i['id'] == 'N01')
eq(item['status'], 'FAIL', '같은 ID 가 여러 brief 에 있으면 FAIL')
eq(item['reason'], 'duplicate_id', '중복 ID 사유는 duplicate_id')

# N/N 중복(둘 다 필수 아님)도 fail_items 에는 반드시 잡힌다 -- required 통계는 오염시키지 않되
# 종료코드/manifest 판정은 이걸로 해야 한다 (리뷰어 지적, round 1)
occ_dup_nn = cc.parse_briefs_text({'brief_a.md': '| ID | 필수 |\n|---|---|\n| N05 | N |\n',
                                    'brief_b.md': '| ID | 필수 |\n|---|---|\n| N05 | N |\n'})
report_nn = cc.evaluate(occ_dup_nn, {}, {})
eq(report_nn['required'], 0, 'N/N 중복은 필수 통계 required 에 안 들어간다')
eq(report_nn['failed'], 0, 'N/N 중복은 필수 통계 failed 에도 안 들어간다')
eq(report_nn['fail_items'], 1, '하지만 fail_items(전체 FAIL 수)에는 잡힌다')

# ==================== quote 정규화 ====================
occ = cc.parse_briefs_text({'b.md': '| ID | 필수 |\n|---|---|\n| N01 | Y |\n'})
sections = {'s02_thesis_catalysts': '앞뒤 문장\n\n**펠리클 확장 투자** 재원을 확보했다고 밝혔다\n\n뒷 문장'}
cov = {'N01': {'section': 's02_thesis_catalysts', 'quote': '펠리클 확장 투자 재원을 확보했다고 밝혔다'}}
report = cc.evaluate(occ, cov, sections)
item = report['items'][0]
eq(item['status'], 'PASS', '볼드·줄바꿈 정규화 후 부분일치하면 PASS')
eq(item['reason'], 'covered', '정상 반영 사유는 covered')

# ==================== missing ====================
occ1 = cc.parse_briefs_text({'b.md': '| ID | 필수 |\n|---|---|\n| N01 | Y |\n'})
report = cc.evaluate(occ1, {}, {'s01_opinion_thesis': '아무 내용'})
eq(report['items'][0]['status'], 'FAIL', 'coverage_map 에 없으면 FAIL')
eq(report['items'][0]['reason'], 'missing', 'missing 사유')

# ==================== weak_exclusion ====================
cov = {'N01': {'excluded': '짧음'}}
report = cc.evaluate(occ1, cov, {})
eq(report['items'][0]['status'], 'FAIL', '제외 사유 10자 미만이면 FAIL')
eq(report['items'][0]['reason'], 'weak_exclusion', 'weak_exclusion 사유')

cov_ok = {'N01': {'excluded': '결론에 영향 없음 -- 일회성 자회사 청산, 금액 0.3억'}}
report = cc.evaluate(occ1, cov_ok, {})
eq(report['items'][0]['status'], 'PASS', '제외 사유 10자 이상이면 PASS')
eq(report['items'][0]['reason'], 'excluded', '제외 PASS 사유는 excluded')

# ==================== bad_section ====================
cov = {'N01': {'section': 's99_없음', 'quote': '스무자 이상 아무 문장을 여기에 채워넣는다'}}
report = cc.evaluate(occ1, cov, {'s01_opinion_thesis': '내용'})
eq(report['items'][0]['status'], 'FAIL', 'sections 에 없는 section 은 FAIL')
eq(report['items'][0]['reason'], 'bad_section', 'bad_section 사유')

cov2 = {'N01': {'section': '', 'quote': '스무자 이상 아무 문장을 여기에 채워넣는다'}}
report = cc.evaluate(occ1, cov2, {'s01_opinion_thesis': '내용'})
eq(report['items'][0]['reason'], 'bad_section', '빈 section 문자열도 bad_section')

# ==================== short_quote ====================
cov = {'N01': {'section': 's01_opinion_thesis', 'quote': '짧은문장'}}
report = cc.evaluate(occ1, cov, {'s01_opinion_thesis': '짧은문장 포함된 긴 본문 내용입니다'})
eq(report['items'][0]['status'], 'FAIL', 'quote 20자 미만이면 FAIL')
eq(report['items'][0]['reason'], 'short_quote', 'short_quote 사유')

# ==================== quote_not_found ====================
cov = {'N01': {'section': 's01_opinion_thesis', 'quote': '본문에 전혀 존재하지 않는 스무 자 이상의 문장입니다'}}
report = cc.evaluate(occ1, cov, {'s01_opinion_thesis': '전혀 다른 내용의 본문입니다'})
eq(report['items'][0]['status'], 'FAIL', '본문에 없는 quote 는 FAIL')
eq(report['items'][0]['reason'], 'quote_not_found', 'quote_not_found 사유')

# ==================== unknown_id ====================
occ_empty = cc.parse_briefs_text({'b.md': '| ID | 필수 |\n|---|---|\n| N01 | Y |\n'})
cov = {'N01': {'section': 's01_opinion_thesis',
               'quote': '스무자 이상 아무 문장을 여기에 채워넣는다 완성'},
       'X99': {'section': 's01_opinion_thesis', 'quote': '어떤 brief 에도 없는 항목입니다'}}
report = cc.evaluate(occ_empty, cov, {'s01_opinion_thesis':
                      '스무자 이상 아무 문장을 여기에 채워넣는다 완성한 본문'})
warn = next(i for i in report['items'] if i['id'] == 'X99')
eq(warn['status'], 'WARN', 'coverage_map 에만 있고 brief 에 없으면 WARN')
eq(warn['reason'], 'unknown_id', 'unknown_id 사유')

# ==================== 통계 집계 ====================
eq(report['required'], 1, '필수 통계: required 는 brief 의 필수=Y 항목 수')
eq(report['covered'], 1, '필수 통계: covered')
eq(report['excluded'], 0, '필수 통계: excluded')
eq(report['failed'], 0, '필수 통계: failed')
eq(report['by_prefix']['N']['required'], 1, '접두 N 집계')

# ==================== 종료코드 (main, 파일시스템 fixture) ====================
with tempfile.TemporaryDirectory() as td:
    orig_root = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        os.makedirs(os.path.join(td, 'scripts'), exist_ok=True)
        analysis_path = os.path.join(td, 'scripts', 'analysis_테스트종목_ta.json')
        with open(analysis_path, 'w', encoding='utf-8') as f:
            json.dump({'sections': {'s01_opinion_thesis':
                      '스무자 이상 아무 문장을 여기에 채워넣는다 완성한 본문입니다'}}, f, ensure_ascii=False)

        ta = tc.ta_dir('테스트종목')
        with open(os.path.join(ta, 'brief_industry.md'), 'w', encoding='utf-8') as f:
            f.write('| ID | 필수 |\n|---|---|\n| N01 | Y |\n')
        with open(os.path.join(ta, 'coverage_map.json'), 'w', encoding='utf-8') as f:
            json.dump({'N01': {'section': 's01_opinion_thesis',
                                'quote': '스무자 이상 아무 문장을 여기에 채워넣는다 완성한 본문'}}, f, ensure_ascii=False)

        code = cc.main(['테스트종목'])
        eq(code, 0, '전부 PASS 면 종료코드 0')

        report_path = os.path.join(ta, 'coverage_report.json')
        eq(os.path.exists(report_path), True, 'coverage_report.json 을 만든다')
        on_disk = json.load(open(report_path, encoding='utf-8'))
        eq(on_disk['failed'], 0, '저장된 리포트에도 failed=0')

        # 이제 필수 항목을 하나 더 추가하되 coverage_map 에서 빠뜨린다 -> FAIL
        with open(os.path.join(ta, 'brief_industry.md'), 'w', encoding='utf-8') as f:
            f.write('| ID | 필수 |\n|---|---|\n| N01 | Y |\n| N02 | Y |\n')
        code2 = cc.main(['테스트종목'])
        eq(code2, 1, '필수 항목이 반영되지 않으면 종료코드 1')
    finally:
        tc.PROJECT_ROOT = orig_root

# N/N 중복 ID만 있고 필수 항목은 전혀 없어도(즉 required=0, failed=0) exit code 는 1 이어야 한다
with tempfile.TemporaryDirectory() as td:
    orig_root = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        os.makedirs(os.path.join(td, 'scripts'), exist_ok=True)
        with open(os.path.join(td, 'scripts', 'analysis_중복종목_ta.json'), 'w', encoding='utf-8') as f:
            json.dump({'sections': {}}, f)

        ta = tc.ta_dir('중복종목')
        with open(os.path.join(ta, 'brief_a.md'), 'w', encoding='utf-8') as f:
            f.write('| ID | 필수 |\n|---|---|\n| N05 | N |\n')
        with open(os.path.join(ta, 'brief_b.md'), 'w', encoding='utf-8') as f:
            f.write('| ID | 필수 |\n|---|---|\n| N05 | N |\n')

        code3 = cc.main(['중복종목'])
        eq(code3, 1, 'N/N 중복 ID 만 있어도(필수 항목 0개) 종료코드 1')

        on_disk3 = json.load(open(os.path.join(ta, 'coverage_report.json'), encoding='utf-8'))
        eq(on_disk3['required'], 0, '저장된 리포트: required=0')
        eq(on_disk3['failed'], 0, '저장된 리포트: failed(필수 통계)=0')
        eq(on_disk3['fail_items'], 1, '저장된 리포트: fail_items=1 (duplicate_id)')
    finally:
        tc.PROJECT_ROOT = orig_root

# ==================== 정독 노트 반영 (v5.26-c) ====================
with tempfile.TemporaryDirectory() as d:
    nd = os.path.join(d, 'notes'); os.makedirs(nd)
    for stem in ('nv_1', 'nv_2', 'ir_2026Q2', '_summary'):
        open(os.path.join(nd, stem + '.md'), 'w', encoding='utf-8').write('# ' + stem)
    occ = cc.parse_notes(nd)
    eq(sorted(occ), ['note:ir_2026Q2', 'note:nv_1', 'note:nv_2'], '노트 파일 = 필수 ID, _summary 제외')
    secs = {'s04_industry_competition': '중국 면세 회복이 더디다는 것이 시장의 전제였는데 관세청 수치는 반대로 간다.',
            's07_valuation': '증권사 12곳의 배수 근거는 대부분 과거 평균이다.',
            's10_earnings_consensus': '회사 덱은 2분기 면세 마진 급락의 사유를 적지 않았다.'}
    cmap = {'note:nv_1': {'section': 's04_industry_competition', 'quote': '중국 면세 회복이 더디다는 것이 시장의 전제였는데'},
            'note:nv_2': {'section': 's07_valuation', 'quote': '증권사 12곳의 배수 근거는 대부분 과거 평균이다'},
            'note:ir_2026Q2': {'section': 's10_earnings_consensus', 'quote': '회사 덱은 2분기 면세 마진 급락의 사유를 적지 않았다'}}
    rep_ = cc.evaluate(occ, cmap, secs)
    eq(rep_['fail_items'], 0, '세 노트 모두 본문 문장으로 반영 -> 0 FAIL')
    eq(rep_['notes'], {'report_notes': 2, 'in_core': 1, 'outside_core': ['note:nv_2']}, 'IR 노트 제외, 리포트 노트 2편 중 s04 착지 1편')
    rep2 = cc.evaluate(occ, {k: v for k, v in cmap.items() if k != 'note:nv_1'}, secs)
    eq([it['id'] for it in rep2['items'] if it['status'] == 'FAIL'], ['note:nv_1'], '지도에 없는 노트는 FAIL(missing)')
    eq(cc._prefix('note:nv_1'), 'note', 'by_prefix 버킷 note')

print('=' * 66)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  ta_coverage_check 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
