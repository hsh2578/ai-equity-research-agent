"""ta_collect_reports.py 테스트 -- 종목/산업 리포트 분리 수집 (Task 8).

네트워크 금지. 네이버는 fetch/download 주입, 한경은 hankyung_importer 주입으로
성공 경로를 시뮬레이션하지 않는다 -- 스펙이 요구하는 것은 "모듈 import 실패 또는
--no-hankyung 이면 skipped/failed 로 기록되고 네이버는 정상"이라는 것뿐이다.

Fix round 1 (컨트롤러 지적 3건):
  1. 관련도 우선 랭킹 -- 262건 중 최신 3건만 자르면 '반도체' 카테고리만 맞고
     실제 제품(펠리클/EUV)과 무관한 리포트만 남는다. 제목에 키워드가 있으면
     tier 1, 카테고리만 일치하면 tier 2. tier 안에서는 최신순, Weekly 는 같은
     tier 안에서 뒤로 민다.
  2. 조용한 절삭 금지 -- 페이지 예산에 걸려 cutoff 를 못 만나고 멈추면
     truncated=True + reason 을 sources 에 남기고 WARN 을 찍는다.
  3. txt/pdf 상대경로 기준 -- data/{종목}/ 기준이어야 ta_plan_agents 같은
     소비자가 다른 ta 입력과 동일한 방식으로 경로를 푼다(프로젝트 루트 기준이면
     조용히 못 찾는다).

Fix round 2 (컨트롤러 실측: company/industry 목록 모두 종목 전용 엔드포인트가
없다 -- itemCode 는 쿼리 필터가 아니라 클라이언트에서 거르는 것뿐이고, 전종목이
섞인 시장 전체 목록을 --months 만큼 훑어야 한다):
  4. 고정 60페이지 상한 -> min(300, max(60, months*20)) 페이지 예산.
  5. sources 에 pages_scanned/oldest_date_seen 기록(트렁케이션 여부와 무관하게).
  6. 페이지 사이 0.3초 지연(주입 가능, 테스트는 delay=0 으로 끈다).

실행: python tests/test_ta_collect_reports.py
"""
import contextlib
import io
import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import ta_collect_reports as ta                          # noqa: E402

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


TODAY = date(2026, 9, 17)

# ==================== age_band / compute_age_months ====================
eq(ta.age_band(3.0), '<=3', '3.0 개월은 <=3')
eq(ta.age_band(2.9), '<=3', '2.9 개월도 <=3')
eq(ta.age_band(3.1), '3-12', '3.1 개월은 3-12')
eq(ta.age_band(12.0), '3-12', '12.0 개월은 3-12 (경계는 아래쪽 밴드)')
eq(ta.age_band(12.1), '>12', '12.1 개월은 >12')
eq(ta.age_band(None), None, '못 읽은 날짜는 None')

eq(ta.compute_age_months('2026-09-17', TODAY), 0.0, '같은 날은 0.0개월')
eq(ta.compute_age_months(None, TODAY), None, '날짜 없으면 None')
eq(ta.compute_age_months('이상한값', TODAY), None, '파싱 실패도 None')

# ==================== naver_page_budget: min(300, max(60, months*20)) ====================
eq(ta.naver_page_budget(1), 60, '1개월 -> 하한 60')
eq(ta.naver_page_budget(3), 60, '3개월(=60) -> 하한 60 그대로')
eq(ta.naver_page_budget(6), 120, '6개월 -> 120')
eq(ta.naver_page_budget(12), 240, '12개월 -> 240')
eq(ta.naver_page_budget(20), 300, '20개월(=400) -> 상한 300 으로 clamp')
eq(ta.naver_page_budget(50), 300, '50개월도 상한 300')

# ==================== 종목 목록: itemCode 필터 + cutoff 페이지 중단 ====================
COMPANY_PAGE1 = [
    {'itemCode': '036810', 'itemName': '에프에스티', 'researchId': 1, 'title': '펠리클 점검',
     'brokerName': 'A증권', 'writeDate': '2026-09-10'},
    {'itemCode': '000660', 'itemName': 'SK하이닉스', 'researchId': 2, 'title': 'HBM 점검',
     'brokerName': 'A증권', 'writeDate': '2026-09-09'},
    {'itemCode': '036810', 'itemName': '에프에스티', 'researchId': 3, 'title': 'EUV 공급계약',
     'brokerName': 'B증권', 'writeDate': '2026-08-20'},
]
COMPANY_PAGE2 = [
    {'itemCode': '036810', 'itemName': '에프에스티', 'researchId': 4, 'title': '오래된 리포트',
     'brokerName': 'C증권', 'writeDate': '2026-08-01'},  # cutoff(월=1, ~2026-08-18) 이전 -> 여기서 중단
]
COMPANY_PAGE3 = [
    {'itemCode': '036810', 'itemName': '에프에스티', 'researchId': 5, 'title': '절대 안 보임',
     'brokerName': 'D증권', 'writeDate': '2026-07-01'},
]


def _paged_fetch(pages_by_url):
    calls = {'n': 0}

    def _f(url, params=None):
        calls['n'] += 1
        page = (params or {}).get('page', 1)
        pages = pages_by_url.get(url, [])
        return pages[page - 1] if page - 1 < len(pages) else []
    return _f, calls


fetch1, calls1 = _paged_fetch({ta.NAVER_LIST_COMPANY: [COMPANY_PAGE1, COMPANY_PAGE2, COMPANY_PAGE3]})
got, meta1 = ta.naver_company_list('036810', 1, fetch=fetch1, today=TODAY, delay=0)
eq([it['researchId'] for it in got], [1, 3], 'itemCode 일치 + cutoff 이전 페이지에서 중단')
eq(calls1['n'], 2, 'cutoff 를 만난 페이지(2) 이후 페이지(3)는 호출하지 않는다')
eq(meta1['truncated'], False, 'cutoff 를 만나 멈췄으면 truncated 아니다')
eq(meta1['oldest_date_seen'], '2026-08-01', '실제로 훑은 가장 오래된 날짜를 기록한다(cutoff 를 부른 그 항목까지)')

# ---- 페이지 예산에 걸려 cutoff 를 못 만나면 truncated=True ----
NEVER_OLD_PAGE = [
    {'itemCode': '036810', 'itemName': '에프에스티', 'researchId': 900, 'title': '계속되는 목록',
     'brokerName': 'Z증권', 'writeDate': '2026-09-01'},
]


def _never_ending_fetch(url, params=None):
    return NEVER_OLD_PAGE  # 항상 같은(빈 아닌) 페이지, cutoff 이전 항목도 없음


got_t, meta_t = ta.naver_company_list('036810', 1, fetch=_never_ending_fetch, today=TODAY,
                                       max_pages=3, delay=0)
eq(meta_t['truncated'], True, '페이지 예산까지 다 돌고도 cutoff/빈페이지를 못 만나면 truncated')
eq(meta_t['pages'], 3, '예산 페이지 수만큼 조회했다')
eq(len(got_t), 3, '예산 페이지 수만큼(페이지당 1건) 모았다')
eq(meta_t['oldest_date_seen'], '2026-09-01', '매번 같은 날짜만 보였으면 그게 oldest')

# ---- delay>0 이면 페이지 사이 sleeper 를 부른다(첫 페이지 앞은 안 부른다) ----
sleeps = []
ta.naver_company_list('036810', 1, fetch=_never_ending_fetch, today=TODAY, max_pages=3,
                       delay=0.3, sleeper=lambda s: sleeps.append(s))
eq(sleeps, [0.3, 0.3], '페이지 2, 3 앞에서만 지연(0.3s x 2), 첫 페이지 앞은 안 쉰다')

# ==================== 산업 목록: category/keyword OR, Daily 제외, weekly/match 표시 ====================
INDUSTRY_PAGE1 = [
    {'category': '반도체', 'researchId': 10, 'title': '반도체 업황 점검', 'brokerName': 'A증권',
     'writeDate': '2026-09-10'},
    {'category': '화학', 'researchId': 11, 'title': 'EUV 펠리클 공급망 점검', 'brokerName': 'B증권',
     'writeDate': '2026-09-09'},
    {'category': '반도체', 'researchId': 12, 'title': '[Daily] 반도체 모닝브리프', 'brokerName': 'C증권',
     'writeDate': '2026-09-08'},
    {'category': '반도체', 'researchId': 13, 'title': '반도체 Weekly 전략', 'brokerName': 'D증권',
     'writeDate': '2026-09-07'},
    {'category': '자동차', 'researchId': 14, 'title': '자동차 소식', 'brokerName': 'E증권',
     'writeDate': '2026-09-06'},
]
INDUSTRY_PAGE2 = [
    {'category': '반도체', 'researchId': 15, 'title': '반도체 오래된 리포트', 'brokerName': 'F증권',
     'writeDate': '2026-01-01'},  # 6개월 cutoff 이전
]
fetch2, calls2 = _paged_fetch({ta.NAVER_LIST_INDUSTRY: [INDUSTRY_PAGE1, INDUSTRY_PAGE2]})
got2, meta2 = ta.naver_industry_list('반도체', ['펠리클', 'EUV'], 6, fetch=fetch2, today=TODAY, delay=0)
eq(sorted(it['researchId'] for it in got2), [10, 11, 13],
   'category 일치(10) OR keyword 일치(11), Daily(12)/불일치(14) 제외')
eq(meta2['truncated'], False, 'cutoff 를 만나 멈췄으면 truncated 아니다')
eq(meta2['oldest_date_seen'], '2026-01-01', '산업 목록도 훑은 범위(oldest_date_seen) 를 기록한다')
w = {it['researchId']: it['is_weekly'] for it in got2}
eq(w[10], False, '카테고리만 일치하면 is_weekly False')
eq(w[13], True, "제목에 'Weekly' 있으면 is_weekly True")
m2 = {it['researchId']: (it['match'], it.get('match_keyword')) for it in got2}
eq(m2[10], ('category', None), '카테고리만 일치 -> match=category, match_keyword 없음')
eq(m2[11], ('keyword', '펠리클'), '제목에 키워드 있으면 match=keyword + 어느 키워드인지 기록')
eq(m2[13], ('category', None), 'Weekly 도 카테고리만 일치하면 match=category')

# ==================== rank_reports: 키워드 tier 우선 + tier 내부 최신순 + weekly 는 뒤로 ====================
RANK_STUBS = [
    {'id': 'b', 'date': '2026-09-01', 'match': 'category', 'is_weekly': False},  # 카테고리만, 제일 최신
    {'id': 'a', 'date': '2026-01-01', 'match': 'keyword', 'is_weekly': False},   # 키워드, 제일 오래됨
    {'id': 'c', 'date': '2026-06-01', 'match': 'keyword', 'is_weekly': True},    # 키워드, weekly
    {'id': 'd', 'date': '2026-08-01', 'match': 'keyword', 'is_weekly': False},   # 키워드, 최신
]
ranked = ta.rank_reports(RANK_STUBS)
eq([s['id'] for s in ranked], ['d', 'a', 'c', 'b'],
   '키워드 tier(d,a,c) 가 카테고리 tier(b) 보다 항상 앞선다(b 가 가장 최신이어도); '
   '같은 tier 안에서는 non-weekly 최신순(d,a) 먼저, weekly(c) 는 뒤로 밀린다')

# ==================== dedupe_reports: 네이버/한경 같은 리포트 하나로 ====================
stubs = [
    {'id': 'hk_1', 'source': 'hankyung', 'broker': 'A증권', 'date': '2026-09-10', 'title': '펠리클 실적 점검!!'},
    {'id': 'nv_1', 'source': 'naver', 'broker': 'A증권', 'date': '2026-09-10', 'title': '펠리클 실적 점검'},
    {'id': 'nv_2', 'source': 'naver', 'broker': 'C증권', 'date': '2026-09-01', 'title': '다른 리포트'},
]
dd = ta.dedupe_reports(stubs)
eq(len(dd), 2, '(증권사,날짜,제목정규화) 같으면 하나로 합친다')
eq({s['id'] for s in dd}, {'nv_1', 'nv_2'}, '네이버가 우선한다(목표가 필드가 있어서)')

# ==================== save_report: %PDF 아니면 실패, 계속 진행 ====================
with tempfile.TemporaryDirectory() as td:
    def _extract_ok(content):
        return ('본문 ' * 300, 4)

    saved, fail = ta.save_report('nv_bad', 'http://bad', td,
                                  download=lambda u: b'<html>error page</html>', extract=_extract_ok)
    eq(saved, None, '%PDF 아니면 저장 실패')
    eq(fail['id'], 'nv_bad', '실패 dict 에 id 포함')
    eq('PDF' in fail['reason'], True, '실패 사유에 PDF 매직 언급')

    saved2, fail2 = ta.save_report('nv_good', 'http://good', td,
                                    download=lambda u: b'%PDF-1.4 fake', extract=_extract_ok)
    eq(fail2, None, '%PDF 로 시작하면 성공')
    eq(saved2['too_short'], False, '500자 이상이면 too_short False')
    eq(os.path.exists(saved2['txt']), True, '.txt 파일이 실제로 저장된다')
    eq(os.path.exists(saved2['pdf']), True, '.pdf 파일이 실제로 저장된다')

# ==================== collect(): 네이버 통합(기업) + %PDF 실패해도 계속 + 상대경로 + _broker_reports.json 무영향 ====================
DETAILS = {
    101: {'researchContent': {'itemCode': '036810', 'title': '펠리클 실적 점검', 'brokerName': 'A증권',
                               'writeDate': '2026-09-10', 'attachUrl': 'http://bad.pdf',
                               'opinion': 'BUY', 'goalPrice': 50000, 'prevGoalPrice': 45000,
                               'priceAtWriteDate': 40000}},
    102: {'researchContent': {'itemCode': '036810', 'title': 'EUV 공급 계약', 'brokerName': 'B증권',
                               'writeDate': '2026-09-05', 'attachUrl': 'http://good.pdf',
                               'opinion': 'HOLD', 'goalPrice': 30000, 'prevGoalPrice': 30000,
                               'priceAtWriteDate': 28000}},
}
LIST_FOR_COLLECT = [
    {'itemCode': '036810', 'itemName': '에프에스티', 'researchId': 101, 'title': '펠리클 실적 점검',
     'brokerName': 'A증권', 'writeDate': '2026-09-10'},
    {'itemCode': '036810', 'itemName': '에프에스티', 'researchId': 102, 'title': 'EUV 공급 계약',
     'brokerName': 'B증권', 'writeDate': '2026-09-05'},
]


def _collect_fetch(url, params=None):
    if url == ta.NAVER_LIST_COMPANY:
        page = (params or {}).get('page', 1)
        return LIST_FOR_COLLECT if page == 1 else []
    for rid, d in DETAILS.items():
        if url == ta.NAVER_DETAIL_COMPANY.format(rid=rid):
            return d
    raise AssertionError(f'예상치 못한 URL: {url}')


def _collect_download(url):
    return b'<html>err</html>' if url == 'http://bad.pdf' else b'%PDF-1.4 ...'


def _collect_extract(content):
    return ('본문 ' * 300, 4)


with tempfile.TemporaryDirectory() as td:
    orig_root = ta.tc.PROJECT_ROOT
    ta.tc.PROJECT_ROOT = td
    try:
        reports, sources, failures = ta.collect(
            'company', '에프에스티', '036810', 1, None, None, 15, False,
            today=TODAY, naver_fetch=_collect_fetch, naver_download=_collect_download,
            pdf_extract=_collect_extract, naver_delay=0)

        eq(sources['naver'], {'status': 'ok', 'count': 2, 'pages_scanned': 2,
                               'oldest_date_seen': '2026-09-05'},
           '네이버 목록 2건 확보 + pages_scanned/oldest_date_seen 기록, truncated 키는 없음')
        eq(sources['hankyung'], {'status': 'skipped', 'count': 0}, 'use_hankyung=False -> skipped')
        eq(len(reports), 1, '%PDF 아닌 것 1건은 실패, 나머지 1건만 성공')
        eq(reports[0]['id'], 'nv_102', '성공한 리포트 id')
        eq(reports[0]['opinion'], 'HOLD', '상세 응답의 opinion 이 반영된다')
        eq(reports[0]['goal_price'], 30000, '상세 응답의 goalPrice 가 반영된다')
        eq(reports[0]['match'], None, '기업 리포트는 match 개념 없음(itemCode 로만 골랐으므로)')
        eq(len(failures), 1, '실패 1건 기록')
        eq(failures[0]['id'], 'nv_101', '실패한 리포트 id')

        eq(reports[0]['txt'], 'ta/reports/company/nv_102.txt',
           'txt 는 data/{종목}/ 기준 상대경로(정방향 슬래시) -- ta_plan_agents 가 이 기준으로 읽는다')
        eq(reports[0]['pdf'], 'ta/reports/company/nv_102.pdf', 'pdf 도 data/{종목}/ 기준 상대경로')

        out_dir = os.path.join(td, 'data', '에프에스티', 'ta', 'reports', 'company')
        eq(os.path.exists(os.path.join(out_dir, 'nv_102.pdf')), True, 'PDF 가 ta/reports/company 에 저장된다')
        eq(os.path.exists(os.path.join(out_dir, 'nv_102.txt')), True, 'TXT 가 ta/reports/company 에 저장된다')

        touched = [f for _, _, fs in os.walk(td) for f in fs if f == '_broker_reports.json']
        eq(touched, [], '_broker_reports.json 을 만들거나 건드리지 않는다')
    finally:
        ta.tc.PROJECT_ROOT = orig_root

# ==================== collect(): 산업 랭킹 -- 키워드 일치가 더 최신인 카테고리만 일치를 이긴다 ====================
IND_LIST = [
    {'category': '반도체', 'researchId': 201, 'title': '반도체 업황 전망', 'brokerName': 'X증권',
     'writeDate': '2026-09-15'},   # category-only, 더 최신
    {'category': '화학', 'researchId': 202, 'title': 'EUV 노광 장비 공급망 분석', 'brokerName': 'Y증권',
     'writeDate': '2026-08-01'},   # keyword match('EUV'), 더 오래됨
]
IND_DETAILS = {
    201: {'researchContent': {'title': '반도체 업황 전망', 'brokerName': 'X증권', 'writeDate': '2026-09-15',
                               'attachUrl': 'http://ind201.pdf'}},
    202: {'researchContent': {'title': 'EUV 노광 장비 공급망 분석', 'brokerName': 'Y증권', 'writeDate': '2026-08-01',
                               'attachUrl': 'http://ind202.pdf'}},
}


def _ind_fetch(url, params=None):
    if url == ta.NAVER_LIST_INDUSTRY:
        page = (params or {}).get('page', 1)
        return IND_LIST if page == 1 else []
    for rid, d in IND_DETAILS.items():
        if url == ta.NAVER_DETAIL_INDUSTRY.format(rid=rid):
            return d
    raise AssertionError(f'예상치 못한 URL: {url}')


def _ind_download(url):
    return b'%PDF-1.4 ...'


with tempfile.TemporaryDirectory() as td:
    orig_root = ta.tc.PROJECT_ROOT
    ta.tc.PROJECT_ROOT = td
    try:
        reports, sources, failures = ta.collect(
            'industry', '에프에스티', '036810', 12, '반도체', ['펠리클', 'EUV'], 15, False,
            today=TODAY, naver_fetch=_ind_fetch, naver_download=_ind_download,
            pdf_extract=_collect_extract, naver_delay=0)
        eq([r['id'] for r in reports], ['nv_202', 'nv_201'],
           '키워드 일치(202, 더 오래됨)가 카테고리만 일치(201, 더 최신)보다 앞선다 -- 컨트롤러 지적 재발 방지')
        eq(reports[0]['match'], 'keyword', '202 는 키워드(EUV) 매칭')
        eq(reports[0]['match_keyword'], 'EUV', '어느 키워드가 맞았는지 기록')
        eq(reports[1]['match'], 'category', '201 은 카테고리만 매칭')
        eq(reports[1]['txt'], 'ta/reports/industry/nv_201.txt', 'industry 도 data/{종목}/ 기준 상대경로')
    finally:
        ta.tc.PROJECT_ROOT = orig_root

# ==================== truncated=True 면 run_kind 가 WARN 을 찍는다 ====================
with tempfile.TemporaryDirectory() as td:
    orig_root = ta.tc.PROJECT_ROOT
    ta.tc.PROJECT_ROOT = td
    orig_ncl = ta.naver_company_list
    ta.naver_company_list = lambda *a, **k: ([], {'truncated': True, 'pages': 60})
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ta.run_kind('company', '에프에스티', '036810', 12, None, None, 15, False, today=TODAY)
        out = buf.getvalue()
        eq('[WARN]' in out, True, 'truncated=True 면 WARN 라인을 찍는다(조용한 절삭 금지)')
    finally:
        ta.naver_company_list = orig_ncl
        ta.tc.PROJECT_ROOT = orig_root

# ==================== 한경 모듈 import 실패 / --no-hankyung ====================
with tempfile.TemporaryDirectory() as td:
    orig_root = ta.tc.PROJECT_ROOT
    ta.tc.PROJECT_ROOT = td
    try:
        # import 실패
        reports, sources, failures = ta.collect(
            'company', '에프에스티', '036810', 1, None, None, 15, True,
            today=TODAY, naver_fetch=_collect_fetch, naver_download=_collect_download,
            pdf_extract=_collect_extract, naver_delay=0,
            hankyung_importer=lambda: (None, 'ImportError: no module named broker'))
        eq(sources['hankyung'], {'status': 'failed', 'reason': 'ImportError: no module named broker'},
           '한경 import 실패는 failed 로 기록된다')
        eq(sources['naver']['status'], 'ok', '한경이 실패해도 네이버는 정상')

        # --no-hankyung (use_hankyung=False)
        reports2, sources2, _ = ta.collect(
            'company', '에프에스티', '036810', 1, None, None, 15, False,
            today=TODAY, naver_fetch=_collect_fetch, naver_download=_collect_download,
            pdf_extract=_collect_extract, naver_delay=0)
        eq(sources2['hankyung'], {'status': 'skipped', 'count': 0}, '--no-hankyung 은 skipped 로 기록된다')
        eq(sources2['naver']['status'], 'ok', '--no-hankyung 이어도 네이버는 정상')
    finally:
        ta.tc.PROJECT_ROOT = orig_root

# ==================== industry-category 없으면 산업리포트 전체 skipped ====================
with tempfile.TemporaryDirectory() as td:
    orig_root = ta.tc.PROJECT_ROOT
    ta.tc.PROJECT_ROOT = td
    try:
        reports3, sources3, failures3 = ta.collect(
            'industry', '에프에스티', '036810', 6, None, ['펠리클'], 15, True, today=TODAY)
        eq(sources3['naver'], {'status': 'skipped', 'count': 0}, 'industry-category 없으면 네이버도 skip')
        eq(sources3['hankyung'], {'status': 'skipped', 'count': 0}, 'industry-category 없으면 한경도 skip')
        eq(reports3, [], '수집 결과 없음')
        eq(failures3, [], '실패도 없음(애초에 안 돌았으므로)')
    finally:
        ta.tc.PROJECT_ROOT = orig_root

# ==================== reports_dir 경로 ====================
with tempfile.TemporaryDirectory() as td:
    orig_root = ta.tc.PROJECT_ROOT
    ta.tc.PROJECT_ROOT = td
    try:
        d = ta.reports_dir('테스트종목', 'industry')
        eq(d, os.path.join(td, 'data', '테스트종목', 'ta', 'reports', 'industry'), 'reports_dir 경로 조합')
        eq(os.path.isdir(d), True, 'reports_dir 는 폴더를 실제로 만든다')
    finally:
        ta.tc.PROJECT_ROOT = orig_root

print('=' * 66)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  ta_collect_reports 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
