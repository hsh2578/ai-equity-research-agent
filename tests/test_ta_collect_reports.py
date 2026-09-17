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

Fix round 3 (실전 파일럿: 키워드 5개로 --no-hankyung 없이 돌렸더니 15분+ 째
안 끝났고, 같은 리포트가 nv_91252.pdf/hk_648115.pdf 로 바이트까지 동일하게
두 번 저장됐다):
  7. 한경 산업 스캔을 키워드마다 하지 않고 category 당 **한 번만** 스캔,
     로컬에서 키워드 OR 매칭(hankyung_scan). 기업도 같은 함수로 통일.
  8. 콘텐츠(sha256) 중복 제거 -- 제목이 달라도 바이트가 같으면 네이버를 남기고
     (처리 순서 무관) 나머지 파일을 지우고 manifest.duplicates 에 기록.
  9. 제목 정규화에 종목 접두어("{종목명}({코드}) ") 제거 + 반복 구간 접기를
     title-dedupe 이전에 적용.

실행: python tests/test_ta_collect_reports.py
"""
import contextlib
import io
import os
import sys
import types
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
        reports, sources, failures, duplicates, category_only_capped = ta.collect(
            'company', '에프에스티', '036810', 1, None, None, 15, False,
            today=TODAY, naver_fetch=_collect_fetch, naver_download=_collect_download,
            pdf_extract=_collect_extract, naver_delay=0)

        eq(duplicates, [], '중복 없으면 duplicates 는 빈 리스트')
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
    return b'%PDF-1.4 ' + url.encode()  # url 마다 다른 바이트 -- sha256 dedupe 오인 방지


with tempfile.TemporaryDirectory() as td:
    orig_root = ta.tc.PROJECT_ROOT
    ta.tc.PROJECT_ROOT = td
    try:
        reports, sources, failures, duplicates, category_only_capped = ta.collect(
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
        reports, sources, failures, duplicates, category_only_capped = ta.collect(
            'company', '에프에스티', '036810', 1, None, None, 15, True,
            today=TODAY, naver_fetch=_collect_fetch, naver_download=_collect_download,
            pdf_extract=_collect_extract, naver_delay=0,
            hankyung_importer=lambda: (None, 'ImportError: no module named broker'))
        eq(sources['hankyung'], {'status': 'failed', 'reason': 'ImportError: no module named broker'},
           '한경 import 실패는 failed 로 기록된다')
        eq(sources['naver']['status'], 'ok', '한경이 실패해도 네이버는 정상')

        # --no-hankyung (use_hankyung=False)
        reports2, sources2, _, _, _ = ta.collect(
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
        reports3, sources3, failures3, duplicates3, capped3 = ta.collect(
            'industry', '에프에스티', '036810', 6, None, ['펠리클'], 15, True, today=TODAY)
        eq(sources3['naver'], {'status': 'skipped', 'count': 0}, 'industry-category 없으면 네이버도 skip')
        eq(sources3['hankyung'], {'status': 'skipped', 'count': 0}, 'industry-category 없으면 한경도 skip')
        eq(reports3, [], '수집 결과 없음')
        eq(failures3, [], '실패도 없음(애초에 안 돌았으므로)')
        eq(duplicates3, [], '중복도 없음')
        eq(capped3, False, '아무것도 안 돌았으니 카테고리 상한도 적용되지 않는다')
    finally:
        ta.tc.PROJECT_ROOT = orig_root

# ==================== _collapse_repeat / _strip_stock_prefix / _norm_title ====================
eq(ta._collapse_repeat('EUV 펠리클 공급망 EUV 펠리클 공급망'), 'EUV 펠리클 공급망',
   '단어 시퀀스 전체가 반복되면 최소 반복 단위만 남긴다')
eq(ta._collapse_repeat('EUV 펠리클 공급망'), 'EUV 펠리클 공급망', '반복이 없으면 그대로')
eq(ta._strip_stock_prefix('에프에스티(036810) ArF 펠리클 시장 내 독보적 지배력', '에프에스티', '036810'),
   'ArF 펠리클 시장 내 독보적 지배력', '종목명(코드) 접두어를 뗀다')
eq(ta._strip_stock_prefix('ArF 펠리클 시장 내 독보적 지배력', '에프에스티', '036810'),
   'ArF 펠리클 시장 내 독보적 지배력', '접두어가 없으면 그대로')
eq(ta._norm_title('에프에스티(036810) ArF 펠리클 시장 내 독보적 지배력', '에프에스티', '036810'),
   ta._norm_title('ArF 펠리클 시장 내 독보적 지배력'),
   '접두어를 뗀 뒤 정규화하면 접두어 없는 원제목과 같은 키가 된다')

# stock_name/code 를 주면 종목 접두어만 다른 두 제목이 title-dedupe 로도 하나가 된다
PREFIX_STUBS = [
    {'id': 'hk_648115', 'source': 'hankyung', 'broker': '유안타증권', 'date': '2026-04-06',
     'title': '에프에스티(036810) ArF 펠리클 시장 내 독보적 지배력, EUV로 증명할 시간'},
    {'id': 'nv_91252', 'source': 'naver', 'broker': '유안타증권', 'date': '2026-04-06',
     'title': 'ArF 펠리클 시장 내 독보적 지배력, EUV로 증명할 시간'},
]
dd_prefix = ta.dedupe_reports(PREFIX_STUBS, stock_name='에프에스티', code='036810')
eq(len(dd_prefix), 1, '종목 접두어만 다르면 title-dedupe 로 하나가 된다(stock_name/code 를 줬을 때)')
eq(dd_prefix[0]['id'], 'nv_91252', '네이버가 남는다')
dd_no_prefix_ctx = ta.dedupe_reports(PREFIX_STUBS)
eq(len(dd_no_prefix_ctx), 2,
   'stock_name/code 없이는 접두어를 못 떼 둘로 남는다 -- sha256 백업이 필요한 이유')

# ==================== 한경: category 당 한 번만 스캔 (기업 1회, 산업 1회 -- 키워드 5개여도) ====================
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts', 'broker'))


class _FakeReport:
    def __init__(self, date, category, title, publisher, report_idx):
        self.date, self.category, self.title = date, category, title
        self.publisher, self.author, self.report_idx = publisher, '', report_idx

    @property
    def pdf_url(self):
        return f'http://hk/{self.report_idx}.pdf'


def _fake_matches(r, keyword, category):
    if category and r.category != category:
        return False
    if not keyword:
        return True
    return keyword in (r.title or '')


def _fake_keyword_hit(r, keyword):
    if not keyword:
        return True
    return keyword in (r.title or '')


def _make_fake_fbr(pages, scan_counter, pdf_bytes=None, page_budget=10):
    """pages: list[list[_FakeReport]] (페이지별 응답, 빈 리스트가 나오면 자연 종료).
    scan_counter['scans'] 에 fr.fetch_range 호출 횟수(= 카테고리 스캔 횟수)를 기록한다.
    실제 HTML 정규식 파서를 흉내낼 필요 없이 hankyung_scan 이 '스캔을 몇 번 도는지',
    '조기 종료가 되는지' 만 검증하면 되므로 page_fetcher 가 rows 를 바로 돌려준다."""

    def paged_fetcher(delay, max_pages, fetch=None, parse=None, sleeper=None,
                       stop_when=None, progress=None):
        state = {'pages': 0, 'rows': [], 'done': False}

        def _fetch(url):
            if state['done'] or state['pages'] >= max_pages or state['pages'] >= len(pages):
                return []
            rows = pages[state['pages']]
            state['pages'] += 1
            state['rows'].extend(rows)
            if progress:
                progress(state['pages'], len(state['rows']))
            if stop_when and stop_when(state['rows']):
                state['done'] = True
            return rows
        return _fetch

    class _FR:
        @staticmethod
        def fetch_range(start, end, max_pages=400, page_fetcher=None, progress=None):
            scan_counter['scans'] = scan_counter.get('scans', 0) + 1
            collected = []
            for _ in range(max_pages):
                rows = page_fetcher('dummy-url')
                if not rows:
                    break
                collected.extend(rows)
            return collected

        @staticmethod
        def filter_range(reports, start, end, category=None, drop_daily=True):
            return [r for r in reports if not category or r.category == category]

    class _FA:
        @staticmethod
        def polite_downloader(delay=0.6):
            if pdf_bytes is not None:
                return lambda url: pdf_bytes
            return lambda url: b'%PDF-1.4 ' + url.encode()  # url 마다 달라 우연한 sha256 충돌 방지

    return types.SimpleNamespace(
        page_budget=lambda months: page_budget,
        paged_fetcher=paged_fetcher,
        matches=_fake_matches,
        keyword_hit=_fake_keyword_hit,
        pick=lambda reports, keyword, limit: sorted(
            [r for r in reports if _fake_keyword_hit(r, keyword)],
            key=lambda r: r.date or '', reverse=True)[:limit],
        fr=_FR(),
        fa=_FA(),
    )


HK_PAGES = [
    [_FakeReport('2026-09-10', '산업', '포토마스크 산업 점검', '한경사', '9001'),
     _FakeReport('2026-09-09', '산업', 'EUV 노광 공급망 분석', '한경사', '9002')],
    [_FakeReport('2026-09-08', '산업', '칠러 장비 동향', '한경사', '9003')],
    [],  # 빈 페이지 -> 자연 종료
]
scan_counter = {}
fake_fbr = _make_fake_fbr(HK_PAGES, scan_counter)

with tempfile.TemporaryDirectory() as td:
    orig_root = ta.tc.PROJECT_ROOT
    ta.tc.PROJECT_ROOT = td
    try:
        reports, sources, failures, duplicates, category_only_capped = ta.collect(
            'industry', '에프에스티', '036810', 3, '반도체',
            ['펠리클', 'EUV', '포토마스크', '칠러', '에스앤에스텍'], 15, True,
            today=TODAY, naver_fetch=lambda *a, **k: [],
            pdf_extract=lambda c: ('본문 ' * 300, 3),
            hankyung_importer=lambda: (fake_fbr, None))
        eq(scan_counter.get('scans'), 1,
           '키워드가 5개여도 fr.fetch_range(=한경 목록 스캔)는 category 당 딱 한 번만 호출된다')
        eq(sources['hankyung']['count'], 3, '3건 모두 다섯 키워드 중 하나 이상과 맞는다')
        eq(sources['hankyung']['pages_scanned'], 3, '데이터 2페이지 + 빈 페이지 확인 1번 = 3')
        eq(len(reports), 3, '한경 3건이 최종 리포트로 반영된다(네이버는 0건)')
        got_ids = {r['id'] for r in reports}
        eq(got_ids, {'hk_9001', 'hk_9002', 'hk_9003'}, '기대한 3건이 그대로 들어온다')
    finally:
        ta.tc.PROJECT_ROOT = orig_root

# ---- 조기 종료: 필요한 매칭 수를 채우면 남은 페이지는 스캔하지 않는다 ----
HK_PAGES_EARLY = [
    [_FakeReport('2026-09-10', '기업', '에프에스티 실적 점검', '한경사', '8001')],
    [_FakeReport('2026-09-05', '기업', '에프에스티 목표가 상향', '한경사', '8002')],
    [_FakeReport('2026-09-01', '기업', '에프에스티 공급계약', '한경사', '8003')],
]
scan_counter_early = {}
fake_fbr_early = _make_fake_fbr(HK_PAGES_EARLY, scan_counter_early)
with tempfile.TemporaryDirectory() as td:
    orig_root = ta.tc.PROJECT_ROOT
    ta.tc.PROJECT_ROOT = td
    try:
        reports, sources, failures, duplicates, category_only_capped = ta.collect(
            'company', '에프에스티', '036810', 3, None, None, 1, True,
            today=TODAY, naver_fetch=lambda *a, **k: [],
            pdf_extract=lambda c: ('본문 ' * 300, 3),
            hankyung_importer=lambda: (fake_fbr_early, None))
        eq(sources['hankyung']['pages_scanned'], 1,
           'limit=1 을 1페이지에서 이미 채우면 나머지 2페이지는 스캔하지 않는다(조기 종료)')
        eq(sources['hankyung']['count'], 1, '조기 종료로 1건만 확보')
    finally:
        ta.tc.PROJECT_ROOT = orig_root

# ==================== sha256 콘텐츠 중복 제거 (제목이 달라도 바이트가 같으면 하나만) ====================
SAME_BYTES = b'%PDF-1.4 identical content for dedupe test'
HK_DUP_PAGES = [[_FakeReport('2026-04-07', '기업', '에프에스티, ArF 펠리클 목표주가 48000원 유지',
                              '유안타증권', '648115')], []]
scan_counter_dup = {}
fake_fbr_dup = _make_fake_fbr(HK_DUP_PAGES, scan_counter_dup, pdf_bytes=SAME_BYTES)


def _nv_fetch_dup(url, params=None):
    if url == ta.NAVER_LIST_COMPANY:
        page = (params or {}).get('page', 1)
        return [{'itemCode': '036810', 'itemName': '에프에스티', 'researchId': 501,
                 'title': 'ArF 펠리클 시장 내 독보적 지배력', 'brokerName': '유안타증권',
                 'writeDate': '2026-04-06'}] if page == 1 else []
    if url == ta.NAVER_DETAIL_COMPANY.format(rid=501):
        return {'researchContent': {'attachUrl': 'http://nv/501.pdf', 'opinion': 'Buy', 'goalPrice': 48000}}
    raise AssertionError(f'예상치 못한 URL: {url}')


with tempfile.TemporaryDirectory() as td:
    orig_root = ta.tc.PROJECT_ROOT
    ta.tc.PROJECT_ROOT = td
    try:
        reports, sources, failures, duplicates, category_only_capped = ta.collect(
            'company', '에프에스티', '036810', 6, None, None, 15, True,
            today=TODAY, naver_fetch=_nv_fetch_dup, naver_download=lambda u: SAME_BYTES,
            pdf_extract=lambda c: ('본문 ' * 300, 3), naver_delay=0,
            hankyung_importer=lambda: (fake_fbr_dup, None))
        # 한경 리포트(hk_648115, 2026-04-07)가 네이버(nv_501, 2026-04-06)보다 최신이라
        # 랭킹상 먼저 처리된다 -- '먼저 저장된 쪽이 이긴다'가 아니라 '네이버가 이긴다'
        # 는 걸 검증하려면 처리 순서를 일부러 뒤집어야 한다.
        eq(len(reports), 1, '제목 표현이 달라 title-dedupe 는 못 잡아도 바이트가 같으면 하나만 남는다')
        eq(reports[0]['id'], 'nv_501', '처리 순서와 무관하게 네이버가 남는다')
        eq(len(duplicates), 1, '중복 1건 기록')
        eq(duplicates[0], {'id': 'hk_648115', 'same_as': 'nv_501', 'by': 'sha256'},
           'duplicates 항목 형식: id/same_as/by')

        out_dir = os.path.join(td, 'data', '에프에스티', 'ta', 'reports', 'company')
        files = sorted(os.listdir(out_dir))
        eq([f for f in files if f.startswith('hk_')], [], '중복으로 판정된 한경 파일은 삭제된다')
        eq('nv_501.pdf' in files, True, '살아남은 네이버 파일은 그대로 있다')
    finally:
        ta.tc.PROJECT_ROOT = orig_root

# ==================== _apply_limit: 카테고리매칭 상한 5, 키워드매칭은 무제한 ====================
# ranked 는 이미 rank_reports() 를 거친 순서(키워드 tier 먼저)라고 가정한다.
_kw = lambda i: {'id': f'kw{i}', 'match': 'keyword'}       # noqa: E731
_cat = lambda i: {'id': f'cat{i}', 'match': 'category'}    # noqa: E731

# (a) 카테고리 공급이 상한보다 많고 limit 도 넉넉하면 -- 상한이 진짜 병목이 된다
ranked_a = [_kw(1), _kw(2)] + [_cat(i) for i in range(1, 11)]
limited_a, capped_a = ta._apply_limit(ranked_a, 8)
eq([s['id'] for s in limited_a], ['kw1', 'kw2', 'cat1', 'cat2', 'cat3', 'cat4', 'cat5'],
   '키워드는 전부, 카테고리는 최대 5개까지만 -- limit(8) 을 다 못 채워도 상한을 넘지 않는다')
eq(capped_a, True, '카테고리 공급이 상한을 넘어 실제로 걸러냈으므로 capped=True')

# (b) 카테고리매칭이 상한 이내면 안 걸린다
ranked_b = [_kw(1), _kw(2), _kw(3)] + [_cat(i) for i in range(1, 4)]
limited_b, capped_b = ta._apply_limit(ranked_b, 10)
eq(len(limited_b), 6, '카테고리가 3개뿐이면(상한 5 이내) 전부 들어간다')
eq(capped_b, False, '상한에 걸린 적이 없으면 capped=False')

# (c) 상한과 limit 이 같은 지점에서 동시에 끝나면 capped=False (진짜로 걸러낸 게 없다)
ranked_c = [_kw(1), _kw(2), _kw(3)] + [_cat(i) for i in range(1, 11)]
limited_c, capped_c = ta._apply_limit(ranked_c, 8)
eq(len(limited_c), 8, 'limit 이 8이면 8개까지만')
eq(capped_c, False, 'limit 자체가 먼저 찼을 뿐 상한이 후보를 걸러내지는 않았다')

# ==================== cleanup_stale: manifest 에 없는 nv_*/hk_* 만 지운다 ====================
with tempfile.TemporaryDirectory() as td:
    def _put(fn, content):
        mode, enc = ('wb', None) if fn.endswith('.pdf') else ('w', 'utf-8')
        with open(os.path.join(td, fn), mode, **({} if enc is None else {'encoding': enc})) as f:
            f.write(content if fn.endswith('.pdf') else content)

    _put('nv_1.pdf', b'a')
    _put('nv_1.txt', 'a')
    _put('nv_2.pdf', b'b')     # kept_ids 에 없음 -> 잔재
    _put('nv_2.txt', 'b')
    _put('hk_3.pdf', b'c')     # kept_ids 에 없음 -> 잔재
    _put('hk_3.txt', 'c')
    with open(os.path.join(td, '_manifest.json'), 'w', encoding='utf-8') as f:
        f.write('{}')
    with open(os.path.join(td, 'random.txt'), 'w', encoding='utf-8') as f:
        f.write('x')

    removed = ta.cleanup_stale(td, {'nv_1'})
    eq(sorted(removed), ['hk_3.pdf', 'hk_3.txt', 'nv_2.pdf', 'nv_2.txt'],
       'kept_ids 에 없는 nv_*/hk_* .pdf|.txt 만 지운다')
    eq(sorted(os.listdir(td)), ['_manifest.json', 'nv_1.pdf', 'nv_1.txt', 'random.txt'],
       '패턴이 안 맞는 파일(_manifest.json, random.txt)과 kept id 파일은 절대 안 건드린다')

    eq(ta.cleanup_stale(os.path.join(td, '없는폴더'), set()), [], '없는 폴더는 조용히 빈 리스트')

# ==================== run_kind: 성공한 실행 끝에 잔재를 지우고 removed_stale 에 기록 ====================
with tempfile.TemporaryDirectory() as td:
    orig_root = ta.tc.PROJECT_ROOT
    ta.tc.PROJECT_ROOT = td
    orig_ncl, orig_detail, orig_save = ta.naver_company_list, ta.naver_detail, ta.save_report
    ta.naver_company_list = lambda *a, **k: (
        [{'itemCode': '036810', 'itemName': '에프에스티', 'researchId': 777,
          'title': '테스트 리포트', 'brokerName': 'A증권', 'writeDate': '2026-09-10'}],
        {'truncated': False, 'pages': 1, 'oldest_date_seen': '2026-09-10'})
    ta.naver_detail = lambda kind, rid, fetch=None: {'attachUrl': 'http://x/777.pdf'}

    def _fake_save(id_, url, out_dir, download=None, extract=None):
        pdf_path = os.path.join(out_dir, f'{id_}.pdf')
        txt_path = os.path.join(out_dir, f'{id_}.txt')
        with open(pdf_path, 'wb') as f:
            f.write(b'%PDF-fake')
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write('본문')
        return {'pages': 1, 'chars': 2, 'too_short': True, 'pdf': pdf_path, 'txt': txt_path,
                'sha256': 'deadbeef'}, None
    ta.save_report = _fake_save
    try:
        stale_dir = ta.reports_dir('에프에스티', 'company')
        for fn, txt in (('nv_999.pdf', 'stale-pdf'), ('nv_999.txt', 'stale-txt')):
            with open(os.path.join(stale_dir, fn), 'w', encoding='utf-8') as f:
                f.write(txt)

        manifest = ta.run_kind('company', '에프에스티', '036810', 1, None, None, 15, False, today=TODAY)

        eq(manifest['removed_stale'], ['nv_999.pdf', 'nv_999.txt'],
           '이번 manifest.reports 에 없는 잔재(다른 --months 로 예전에 받은 nv_999) 를 지우고 기록한다')
        eq(os.path.exists(os.path.join(stale_dir, 'nv_999.pdf')), False, '실제로 파일이 지워진다')
        eq(os.path.exists(os.path.join(stale_dir, 'nv_777.pdf')), True, '이번에 받은 파일은 그대로 남는다')
    finally:
        ta.naver_company_list, ta.naver_detail, ta.save_report = orig_ncl, orig_detail, orig_save
        ta.tc.PROJECT_ROOT = orig_root

# ---- 네이버가 통째로 실패하면 잔재를 지우지 않는다(일시 실패가 데이터를 파괴하면 안 된다) ----
with tempfile.TemporaryDirectory() as td:
    orig_root = ta.tc.PROJECT_ROOT
    ta.tc.PROJECT_ROOT = td
    orig_ncl = ta.naver_company_list

    def _raise(*a, **k):
        raise RuntimeError('네트워크 끊김')
    ta.naver_company_list = _raise
    try:
        stale_dir = ta.reports_dir('에프에스티', 'company')
        with open(os.path.join(stale_dir, 'nv_999.pdf'), 'w', encoding='utf-8') as f:
            f.write('stale')

        manifest = ta.run_kind('company', '에프에스티', '036810', 1, None, None, 15, False, today=TODAY)

        eq(manifest['sources']['naver']['status'], 'failed', '네이버가 실패로 기록된다')
        eq(manifest['removed_stale'], [], '네이버 실패 시 잔재를 지우지 않는다')
        eq(os.path.exists(os.path.join(stale_dir, 'nv_999.pdf')), True, '파일이 그대로 남아 있다')
    finally:
        ta.naver_company_list = orig_ncl
        ta.tc.PROJECT_ROOT = orig_root

# ---- industry-category 없이 skip 되면 잔재를 지우지 않는다 ----
with tempfile.TemporaryDirectory() as td:
    orig_root = ta.tc.PROJECT_ROOT
    ta.tc.PROJECT_ROOT = td
    try:
        stale_dir = ta.reports_dir('에프에스티', 'industry')
        with open(os.path.join(stale_dir, 'nv_999.pdf'), 'w', encoding='utf-8') as f:
            f.write('stale')

        manifest = ta.run_kind('industry', '에프에스티', '036810', 6, None, ['펠리클'], 15, False,
                                today=TODAY)

        eq(manifest['removed_stale'], [], 'industry-category 없이 skip 되면 잔재를 지우지 않는다')
        eq(os.path.exists(os.path.join(stale_dir, 'nv_999.pdf')), True, '파일이 그대로 남아 있다')
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
