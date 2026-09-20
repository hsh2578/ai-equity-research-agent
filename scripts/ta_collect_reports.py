"""ta_collect_reports.py -- 증권사 리포트 수집: 종목/산업 분리 (Task 8, /research-ta).

기존 fetch_broker_reports.py(한경만, 분리 없음)와 collect_kirs_reports.py(IR협의회
전용)를 이 스크립트가 대체하지 않는다 -- 둘 다 import 만 해서 재사용하고, 새로
네이버 리서치(종목/산업) 소스를 얹어 '종목리포트'와 '산업리포트'를 분리해 받는다.

소스 2개, kind 2개(company/industry) = 최대 4갈래 수집:
  - 네이버(m.stock.naver.com/api/research/company|industry) -- 목록 -> 상세(attachUrl) -> PDF
  - 한경 컨센서스 -- scripts/broker/* 를 fetch_broker_reports.py 경유로 import 만 해서 재사용
    (fetch_broker_reports.py 의 main()/파일 저장 경로는 절대 타지 않는다 -- 그건
    data/{종목}/_broker_reports.json 을 덮어써 /research 가 쓰는 파일을 망친다)

두 소스에서 모은 후보를 (증권사, 날짜, 제목정규화) 로 중복 제거(네이버 우선) ->
최신순 정렬 -> limit 자르기 -> 그제서야 PDF 를 받고 fitz 로 텍스트를 뽑는다
(불필요한 상세/다운로드 호출을 줄이기 위해 자르기를 다운로드보다 먼저 한다).

출력: data/{종목}/ta/reports/{company,industry}/{id}.pdf|.txt + _manifest.json
      id 는 'nv_{researchId}' 또는 'hk_{report_idx}'.

사용:
    python scripts/ta_collect_reports.py 에프에스티 --code 036810 --months 12 \
        --industry-category 반도체 --keywords 펠리클,EUV \
        --limit-company 15 --limit-industry 15
"""
import hashlib
import io
import os
import re
import sys
import time
import argparse
from datetime import timedelta

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests            # noqa: E402
import ta_common as tc     # noqa: E402

NAVER_LIST_COMPANY = 'https://m.stock.naver.com/api/research/company'
NAVER_DETAIL_COMPANY = 'https://m.stock.naver.com/api/research/company/{rid}'
NAVER_LIST_INDUSTRY = 'https://m.stock.naver.com/api/research/industry'
NAVER_DETAIL_INDUSTRY = 'https://m.stock.naver.com/api/research/industry/{rid}'
NAVER_HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://m.stock.naver.com/'}

TOO_SHORT_CHARS = 500
DAY_PER_MONTH = 30.44

# 네이버 페이지 예산 (fix round 2 -- 컨트롤러 실측: m.stock.naver.com 의
# company/industry 목록은 itemCode 를 쿼리로 안 받고(종목 지정 불가), PC
# finance.naver.com 쪽 리서치 목록은 SPA 라 서버렌더 표가 없다 -- 즉 "종목 전용
# 엔드포인트"가 없고 시장 전체 목록을 훑어 클라이언트에서 거르는 것이 유일한
# 방법이다. 고정 60페이지 상한은 --months 가 크면(또는 기업 목록처럼 원래
# 전종목이 섞인 목록이면) cutoff 도달 전에 조용히 끊긴다 -- 개월수에 비례한
# 예산으로 바꾸고, 그래도 못 끝내면 truncated 로 드러낸다(조용한 절삭 금지).
NAVER_PAGE_DELAY = 0.3
_NAVER_PAGES_PER_MONTH = 20
_NAVER_MIN_PAGES = 60
_NAVER_MAX_PAGES = 300

# 한경 rate limit (실측 IP 차단 사고). 다운로드는 순차 처리라 동시성은
# 구조적으로 1 -- "workers <= 2" 제약을 코드로 다시 강제할 필요가 없다.
HANKYUNG_PAGE_DELAY = 1.0
HANKYUNG_PDF_DELAY = 0.6


def naver_page_budget(months):
    """개월수에 비례한 네이버 목록 페이지 예산: min(300, max(60, months*20))."""
    return min(_NAVER_MAX_PAGES, max(_NAVER_MIN_PAGES, int(months) * _NAVER_PAGES_PER_MONTH))


# ==================== 시점 유틸 ====================

def _parse_ymd(s):
    if not s:
        return None
    try:
        from datetime import datetime as _dt
        return _dt.strptime(str(s)[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def compute_age_months(write_date, today):
    """write_date('YYYY-MM-DD') 와 today 사이 경과월(소수 1자리). 못 읽으면 None."""
    d = _parse_ymd(write_date)
    if d is None:
        return None
    days = (today - d).days
    return round(days / DAY_PER_MONTH, 1)


def age_band(months):
    if months is None:
        return None
    if months <= 3:
        return '<=3'
    if months <= 12:
        return '3-12'
    return '>12'


# ==================== 중복 제거 ====================

def _collapse_repeat(s):
    """단어 시퀀스가 통째로 반복되면 최소 반복 단위만 남긴다
    (broker/fetch_list._dedupe_title 과 같은 알고리즘 -- 한경 목록 HTML 파싱
    단계에서도 한 번 걷어내지만, 그걸 거치지 않는 경로가 있을 수 있어 여기서도
    방어적으로 한 번 더 한다)."""
    words = s.split()
    n = len(words)
    for p in range(1, n // 2 + 1):
        if n % p == 0 and all(words[i] == words[i % p] for i in range(n)):
            return ' '.join(words[:p])
    return s


def _strip_stock_prefix(t, stock_name, code):
    """한경 기업 리포트 제목은 '{종목명}({코드}) {실제 제목}' 형태로 종목
    접두어가 붙는데 네이버 제목엔 없다 -- 그대로 두면 같은 리포트인데 제목
    정규화 키가 달라져 중복 제거를 통과한다(에프에스티 nv_91252/hk_648115
    실측 사고, 바이트까지 동일한 PDF 가 두 번 저장됐다)."""
    if not (stock_name and code):
        return t
    for prefix in (f'{stock_name}({code})', f'{stock_name}({code}) '):
        if t.startswith(prefix):
            return t[len(prefix):].strip()
    return t


def _norm_title(t, stock_name=None, code=None):
    t = _strip_stock_prefix(t or '', stock_name, code)
    t = _collapse_repeat(t)
    return re.sub(r'[\s\W_]+', '', t)


def _norm_broker(b):
    return (b or '').strip()


def dedupe_reports(stubs, stock_name=None, code=None):
    """(증권사정규화, 날짜, 제목정규화) 같으면 하나. 네이버 우선(목표가 필드가 있어서).
    제목 정규화 전에 종목 접두어를 떼고 반복 구간을 접는다(fix round 3)."""
    seen = {}
    order = []
    for s in stubs:
        key = (_norm_broker(s.get('broker')), s.get('date'),
               _norm_title(s.get('title'), stock_name, code))
        if key not in seen:
            seen[key] = s
            order.append(key)
        elif s.get('source') == 'naver' and seen[key].get('source') != 'naver':
            seen[key] = s
    return [seen[k] for k in order]


# ==================== 네이버 ====================

def _default_json_get(url, params=None):
    r = requests.get(url, params=params, headers=NAVER_HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def _default_pdf_get(url):
    r = requests.get(url, headers=NAVER_HEADERS, timeout=15)
    r.raise_for_status()
    return r.content


def naver_company_list(item_code, months, fetch=None, today=None, page_size=100,
                        max_pages=None, delay=NAVER_PAGE_DELAY, sleeper=None):
    """itemCode 일치만 남기고, writeDate 가 cutoff 이전인 항목이 나오는
    페이지에서 중단한다(목록은 최신순, 시장 전체가 섞여 있다 -- itemCode 쿼리
    필터가 없어 클라이언트에서 거른다).

    max_pages 생략 시 naver_page_budget(months) 를 쓴다. 페이지 사이 delay 초
    쉰다(첫 페이지 앞에는 쉬지 않는다).

    반환: (items, meta). meta['truncated'] 는 cutoff 를 만나지도, 빈 페이지로
    자연히 끝나지도 못하고 페이지 예산에 걸려 멈췄다는 뜻 -- 이 경우 실제로는
    더 있는데 못 받았을 수 있다(조용한 절삭 금지, 컨트롤러 지적 사항).
    meta['oldest_date_seen'] 은 실제로 훑은 범위(스캔이 어디까지 갔는지)를
    truncated 여부와 무관하게 남긴다."""
    fetch = fetch or _default_json_get
    sleeper = sleeper or time.sleep
    today = today or tc.now_kst().date()
    cutoff = today - timedelta(days=round(months * DAY_PER_MONTH))
    mp = max_pages if max_pages is not None else naver_page_budget(months)
    out = []
    pages_fetched = 0
    oldest = None
    for page in range(1, mp + 1):
        if page > 1 and delay:
            sleeper(delay)
        items = fetch(NAVER_LIST_COMPANY, {'page': page, 'pageSize': page_size}) or []
        pages_fetched = page
        if not items:
            break
        stop = False
        for it in items:
            d = _parse_ymd(it.get('writeDate'))
            if d is not None and (oldest is None or d < oldest):
                oldest = d
            if d is not None and d < cutoff:
                stop = True
                break
            if str(it.get('itemCode') or '') == str(item_code):
                out.append(it)
        if stop:
            break
    else:
        # for-else: 페이지 예산을 다 돌 때까지 break(빈 페이지 or cutoff)를 못 만남
        return out, {'truncated': True, 'pages': pages_fetched,
                      'oldest_date_seen': oldest.isoformat() if oldest else None}
    return out, {'truncated': False, 'pages': pages_fetched,
                  'oldest_date_seen': oldest.isoformat() if oldest else None}


def naver_industry_list(category, keywords, months, fetch=None, today=None, page_size=100,
                         max_pages=None, delay=NAVER_PAGE_DELAY, sleeper=None):
    """(category 일치 OR 제목에 keywords 중 하나 포함) AND Daily/데일리 아님.
    Weekly/주간 이면 is_weekly=True 로 표시. 매칭 방식(match/match_keyword)도
    함께 남겨 랭킹(키워드 우선)에 쓴다. max_pages/delay/truncated/oldest_date_seen
    의미는 naver_company_list 와 동일."""
    fetch = fetch or _default_json_get
    sleeper = sleeper or time.sleep
    today = today or tc.now_kst().date()
    cutoff = today - timedelta(days=round(months * DAY_PER_MONTH))
    mp = max_pages if max_pages is not None else naver_page_budget(months)
    kws = [k for k in (keywords or []) if k]
    out = []
    pages_fetched = 0
    oldest = None
    for page in range(1, mp + 1):
        if page > 1 and delay:
            sleeper(delay)
        items = fetch(NAVER_LIST_INDUSTRY, {'page': page, 'pageSize': page_size}) or []
        pages_fetched = page
        if not items:
            break
        stop = False
        for it in items:
            d = _parse_ymd(it.get('writeDate'))
            if d is not None and (oldest is None or d < oldest):
                oldest = d
            if d is not None and d < cutoff:
                stop = True
                break
            title = it.get('title') or ''
            if 'Daily' in title or '데일리' in title:
                continue
            hit_kw = next((k for k in kws if k in title), None)
            cat_match = bool(category) and it.get('category') == category
            if hit_kw is None and not cat_match:
                continue
            row = dict(it)
            row['is_weekly'] = ('Weekly' in title) or ('주간' in title)
            row['match'] = 'keyword' if hit_kw is not None else 'category'
            row['match_keyword'] = hit_kw
            out.append(row)
        if stop:
            break
    else:
        return out, {'truncated': True, 'pages': pages_fetched,
                      'oldest_date_seen': oldest.isoformat() if oldest else None}
    return out, {'truncated': False, 'pages': pages_fetched,
                  'oldest_date_seen': oldest.isoformat() if oldest else None}


def naver_detail(kind, rid, fetch=None):
    fetch = fetch or _default_json_get
    url = (NAVER_DETAIL_COMPANY if kind == 'company' else NAVER_DETAIL_INDUSTRY).format(rid=rid)
    d = fetch(url) or {}
    return d.get('researchContent') or d


def _naver_stub(it):
    rid = it.get('researchId')
    broker = it.get('brokerName') or ''
    return {
        'id': f'nv_{rid}', 'source': 'naver', 'research_id': rid,
        'broker': broker, 'date': it.get('writeDate'), 'title': it.get('title') or '',
        'is_kirs': 'IR협의회' in broker, 'is_weekly': bool(it.get('is_weekly', False)),
        'match': it.get('match'), 'match_keyword': it.get('match_keyword'),
    }


# ==================== 한경 (scripts/broker 를 fetch_broker_reports 경유로 재사용) ====================

def _import_hankyung():
    """fetch_broker_reports 를 import 만 한다 (main() 은 절대 호출하지 않는다)."""
    try:
        import fetch_broker_reports as fbr
        return fbr, None
    except Exception as e:
        return None, f'{type(e).__name__}: {e}'


def hankyung_scan(fbr, category, months, keywords, limit, today, fetch=None, parse=None):
    """한경 목록을 category 당 **딱 한 번만** 스캔한다 (fix round 3 -- 키워드마다
    스캔하면 max_pages(최대 400) x 1.0s x 키워드 수만큼 걸린다. 실측: 키워드 5개
    파일럿이 15분+ 째 안 끝남). keywords 는 str(기업, 종목명 하나) 또는
    list(산업, 키워드 OR 매칭) 둘 다 받는다 -- 로컬(클라이언트)에서 매칭한다.

    fetch/parse 는 fbr.paged_fetcher 로 그대로 주입한다(테스트가 네트워크 없이
    실제 페이징/조기종료 로직을 검증할 수 있게).

    반환: (matched_reports, pages_scanned)."""
    kws = [keywords] if isinstance(keywords, str) else [k for k in (keywords or []) if k]
    start = today - timedelta(days=months * 31)
    max_pages = fbr.page_budget(months)
    scanned = {'pages': 0}

    def _match_any(r):
        return any(fbr.matches(r, kw, category) for kw in kws)

    def _need_met(rows):
        return sum(1 for r in rows if _match_any(r)) >= limit

    def _progress(pages, _total_rows):
        scanned['pages'] = pages

    fetcher = fbr.paged_fetcher(HANKYUNG_PAGE_DELAY, max_pages, fetch=fetch, parse=parse,
                                 stop_when=_need_met, progress=_progress)
    reports = fbr.fr.fetch_range(start, today, max_pages=max_pages, page_fetcher=fetcher)
    scoped = fbr.fr.filter_range(reports, start, today, category=category, drop_daily=True)
    matched = [r for r in scoped if any(fbr.keyword_hit(r, kw) for kw in kws)]
    matched.sort(key=lambda r: r.date or '', reverse=True)
    return matched[:limit], scanned['pages']


def _hankyung_stub(r, match_keyword=None):
    """match_keyword 가 주어지면(산업: 키워드별로 조회하므로 항상 그 키워드가
    맞아 떨어진 것) match='keyword' 로 표시한다. 기업 리포트는 종목명으로만
    조회하므로 match 개념이 없다(None -> 랭킹에서 category 취급, 날짜순과 동일)."""
    return {
        'id': f'hk_{r.report_idx}', 'source': 'hankyung', 'pdf_url': r.pdf_url,
        'broker': r.publisher or '', 'date': r.date, 'title': r.title or '',
        'is_kirs': False, 'is_weekly': False,
        'match': 'keyword' if match_keyword else None, 'match_keyword': match_keyword,
    }


# ==================== PDF 저장 ====================

def extract_pdf_text(content):
    import fitz
    doc = fitz.open(stream=content, filetype='pdf')
    try:
        pages = len(doc)
        text = '\n'.join(p.get_text() for p in doc)
    finally:
        doc.close()
    return text, pages


def save_report(id_, url, out_dir, download=None, extract=None):
    """PDF 다운로드 -> %PDF 매직 검증 -> fitz 텍스트 추출 -> 저장.

    실패해도 예외를 삼키지 않고 (None, {"id","reason"}) 로 구조화해 돌려준다
    (에러 페이지가 HTTP 200 으로 오는 사고 -- collect_kirs_reports.py 참고).
    """
    download = download or _default_pdf_get
    extract = extract or extract_pdf_text
    try:
        content = download(url)
    except Exception as e:
        return None, {'id': id_, 'reason': f'{type(e).__name__}: {e}'}
    if not content or not content.startswith(b'%PDF'):
        return None, {'id': id_, 'reason': 'PDF 매직바이트 아님(에러 페이지)'}
    try:
        text, pages = extract(content)
    except Exception as e:
        return None, {'id': id_, 'reason': f'텍스트추출 실패: {type(e).__name__}: {e}'}
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, f'{id_}.pdf')
    txt_path = os.path.join(out_dir, f'{id_}.txt')
    with open(pdf_path, 'wb') as f:
        f.write(content)
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(text)
    # v5.26: 괘선 표는 행·열 그대로 {id}.tables.md 로 (fitz 는 표를 한 셀 한 줄로 푼다). 실패해도 수집은 계속, 사유는 남긴다
    from ta_pdf_tables import write_tables_md
    n_tables, tables_err = write_tables_md(pdf_path)
    return {'pages': pages, 'chars': len(text), 'too_short': len(text) < TOO_SHORT_CHARS,
            'pdf': pdf_path, 'txt': txt_path, 'sha256': hashlib.sha256(content).hexdigest(),
            'tables': n_tables, 'tables_err': tables_err}, None


# ==================== 오케스트레이션 ====================

def reports_dir(stock, kind):
    d = os.path.join(tc.ta_dir(stock), 'reports', kind)
    os.makedirs(d, exist_ok=True)
    return d


def rank_reports(stubs):
    """관련도 우선 정렬: (a) 제목에 키워드 있음(tier 1) (b) 카테고리만 일치(tier 2).
    같은 tier 안에서는 최신순, Weekly 는 같은 tier/최신도 안에서 뒤로 민다.
    'match' 가 없는 stub(기업 리포트 -- itemCode 로만 골랐으므로 랭킹 개념이 없음)은
    전부 tier 2 취급이라 순수 최신순과 동일하게 동작한다(회귀 없음)."""
    ranked = sorted(stubs, key=lambda s: s.get('date') or '', reverse=True)
    ranked = sorted(ranked, key=lambda s: (0 if s.get('match') == 'keyword' else 1,
                                            1 if s.get('is_weekly') else 0))
    return ranked


CATEGORY_ONLY_CAP = 5


def _apply_limit(ranked, limit):
    """랭킹 순서(관련도 우선)를 지키며 limit 을 채우되, match=='category'(제목에
    키워드가 하나도 없이 카테고리만 일치)는 최대 CATEGORY_ONLY_CAP 슬롯까지만
    허용한다 -- fix round 1 랭킹 수정으로 키워드매칭이 우선하게 됐지만, 키워드
    매칭이 적으면 여전히 카테고리매칭이 limit 대부분을 채워 '반도체 아무거나'가
    되는 문제가 남는다. 상한을 넘는 카테고리매칭은 건너뛰고 뒤 후보로 자리를
    채운다(빈 슬롯을 남기지 않는다). 키워드 매칭은 개수 제한이 없다(limit 까지).
    반환: (limited, category_only_capped: bool -- 실제로 걸러낸 것이 있었는가)."""
    limited = []
    cat_count = 0
    capped = False
    for s in ranked:
        if len(limited) >= limit:
            break
        if s.get('match') == 'category':
            if cat_count >= CATEGORY_ONLY_CAP:
                capped = True
                continue
            cat_count += 1
        limited.append(s)
    return limited, capped


def collect(kind, stock, code, months, category, keywords, limit, use_hankyung,
            today=None, naver_fetch=None, naver_download=None, pdf_extract=None,
            hankyung_importer=None, naver_delay=NAVER_PAGE_DELAY, naver_sleeper=None,
            hankyung_fetch=None, hankyung_parse=None):
    """kind('company'|'industry') 리포트를 네이버(+한경)에서 모아 저장한다.

    반환: (reports, sources, failures, duplicates, category_only_capped). 저장
    경로는 항상 data/{stock}/ta/reports/{kind}/ (_broker_reports.json 은 건드리지
    않는다). naver_delay/naver_sleeper 는 테스트에서 페이지 간 실제 대기를 끄는
    용도(naver_delay=0)이고, 운영 기본값은 0.3초다. hankyung_fetch/hankyung_parse
    는 fbr.paged_fetcher 로 그대로 주입(테스트가 진짜 스캔 로직을 네트워크 없이
    검증). category_only_capped 는 _apply_limit() 의 카테고리매칭 상한이 실제로
    걸렸는지(True) 여부다.
    """
    today = today or tc.now_kst().date()
    industry_skip = kind == 'industry' and not category
    sources = {}
    stubs = []

    # ---- 네이버 ----
    if industry_skip:
        sources['naver'] = {'status': 'skipped', 'count': 0}
    else:
        try:
            if kind == 'company':
                raw, list_meta = naver_company_list(code, months, fetch=naver_fetch, today=today,
                                                      delay=naver_delay, sleeper=naver_sleeper)
            else:
                raw, list_meta = naver_industry_list(category, keywords, months, fetch=naver_fetch,
                                                      today=today, delay=naver_delay,
                                                      sleeper=naver_sleeper)
            stubs.extend(_naver_stub(it) for it in raw)
            sources['naver'] = {'status': 'ok', 'count': len(raw),
                                 'pages_scanned': list_meta['pages'],
                                 'oldest_date_seen': list_meta.get('oldest_date_seen')}
            if list_meta.get('truncated'):
                budget = naver_page_budget(months)
                sources['naver']['truncated'] = True
                sources['naver']['reason'] = (
                    f"페이지 예산({budget}, months={months}) 소진 -- cutoff 이전 항목을 만나기 전에 멈춤 "
                    f"(pages_scanned={list_meta['pages']}, oldest_date_seen="
                    f"{list_meta.get('oldest_date_seen')}), 더 있을 수 있음")
        except Exception as e:
            sources['naver'] = {'status': 'failed', 'reason': f'{type(e).__name__}: {e}'}

    # ---- 한경 ----
    fbr = None
    if industry_skip or not use_hankyung:
        sources['hankyung'] = {'status': 'skipped', 'count': 0}
    else:
        importer = hankyung_importer or _import_hankyung
        fbr, err = importer()
        if err:
            sources['hankyung'] = {'status': 'failed', 'reason': err}
        else:
            try:
                if kind == 'company':
                    hk, hk_pages = hankyung_scan(fbr, '기업', months, stock, limit, today,
                                                  fetch=hankyung_fetch, parse=hankyung_parse)
                    stubs.extend(_hankyung_stub(r) for r in hk)
                else:
                    hk, hk_pages = hankyung_scan(fbr, '산업', months, keywords or [], limit, today,
                                                  fetch=hankyung_fetch, parse=hankyung_parse)
                    for r in hk:
                        mk = next((kw for kw in (keywords or []) if fbr.keyword_hit(r, kw)), None)
                        stubs.append(_hankyung_stub(r, match_keyword=mk))
                sources['hankyung'] = {'status': 'ok', 'count': len(hk), 'pages_scanned': hk_pages}
            except Exception as e:
                sources['hankyung'] = {'status': 'failed', 'reason': f'{type(e).__name__}: {e}'}

    deduped = dedupe_reports(stubs, stock_name=stock, code=code)
    ranked = rank_reports(deduped)
    limited, category_only_capped = _apply_limit(ranked, limit)

    out_dir = reports_dir(stock, kind)
    materialized, failures = [], []
    for stub in limited:
        try:
            if stub['source'] == 'naver':
                detail = naver_detail(kind, stub['research_id'], fetch=naver_fetch)
                url = detail.get('attachUrl')
                if not url:
                    failures.append({'id': stub['id'], 'reason': 'attachUrl 없음'})
                    continue
                stub['opinion'] = detail.get('opinion')
                stub['goal_price'] = detail.get('goalPrice')
                stub['prev_goal_price'] = detail.get('prevGoalPrice')
                stub['price_at_write'] = detail.get('priceAtWriteDate')
                download = naver_download
            else:
                url = stub['pdf_url']
                download = fbr.fa.polite_downloader(delay=HANKYUNG_PDF_DELAY) if fbr else None
        except Exception as e:
            failures.append({'id': stub['id'], 'reason': f'{type(e).__name__}: {e}'})
            continue

        saved, fail = save_report(stub['id'], url, out_dir, download=download, extract=pdf_extract)
        if fail:
            failures.append(fail)
            continue
        materialized.append((stub, saved))

    # ---- sha256 콘텐츠 중복 제거 (fix round 3) ----
    # 제목이 달라도 바이트가 같은 PDF 가 두 번 저장되는 사고를 잡는다(에프에스티
    # 실측: nv_91252.pdf == hk_648115.pdf, 1,038,368 바이트 동일. 한경 제목의
    # '종목명(코드)' 접두어 때문에 제목 기반 dedupe 를 통과했다). 네이버를 우선
    # 남기고 -- 처리 순서와 무관하게 -- 나머지를 지운다.
    duplicates = []
    kept = []
    kept_index_by_hash = {}
    for stub, saved in materialized:
        h = saved['sha256']
        if h not in kept_index_by_hash:
            kept_index_by_hash[h] = len(kept)
            kept.append((stub, saved))
            continue
        idx = kept_index_by_hash[h]
        existing_stub, existing_saved = kept[idx]
        if stub['source'] == 'naver' and existing_stub['source'] != 'naver':
            duplicates.append({'id': existing_stub['id'], 'same_as': stub['id'], 'by': 'sha256'})
            _remove_saved_files(existing_saved)
            kept[idx] = (stub, saved)
        else:
            duplicates.append({'id': stub['id'], 'same_as': existing_stub['id'], 'by': 'sha256'})
            _remove_saved_files(saved)

    reports = []
    base = tc.data_dir(stock)
    for stub, saved in kept:
        months_old = compute_age_months(stub.get('date'), today)
        # data/{stock}/ 기준 상대경로 -- ta_plan_agents 등 소비자가 다른 ta 입력과
        # 마찬가지로 data/{종목}/ 를 기준으로 경로를 푼다(프로젝트 루트 기준이면
        # 조용히 못 찾는다, 컨트롤러 지적 사항).
        reports.append({
            'id': stub['id'], 'source': stub['source'], 'broker': stub.get('broker'),
            'date': stub.get('date'), 'title': stub.get('title'),
            'age_months': months_old, 'age_band': age_band(months_old),
            'pages': saved['pages'], 'chars': saved['chars'], 'too_short': saved['too_short'],
            'is_kirs': stub.get('is_kirs', False), 'is_weekly': stub.get('is_weekly', False),
            'match': stub.get('match'), 'match_keyword': stub.get('match_keyword'),
            'opinion': stub.get('opinion'), 'goal_price': stub.get('goal_price'),
            'prev_goal_price': stub.get('prev_goal_price'), 'price_at_write': stub.get('price_at_write'),
            'pdf': os.path.relpath(saved['pdf'], base).replace('\\', '/'),
            'txt': os.path.relpath(saved['txt'], base).replace('\\', '/'),
        })

    return reports, sources, failures, duplicates, category_only_capped


def _remove_saved_files(saved):
    for k in ('pdf', 'txt'):
        p = saved.get(k)
        if p and os.path.exists(p):
            os.remove(p)


_STALE_FILE_RE = re.compile(r'^(nv|hk)_[^.]+\.(pdf|txt)$')


def cleanup_stale(out_dir, kept_ids):
    """out_dir 안의 nv_*/hk_* .pdf|.txt 파일 중 이번 manifest.reports(kept_ids)
    에 없는 것(다른 --months/키워드로 예전에 받은 잔재, 예: nv_42556.* 가
    --months 3 재실행 후에도 남아 있던 것)을 지운다. 이 패턴에 안 맞는 파일
    (_manifest.json 등)은 절대 건드리지 않는다. 반환: 지운 파일명 리스트."""
    removed = []
    if not os.path.isdir(out_dir):
        return removed
    for fn in sorted(os.listdir(out_dir)):
        if not _STALE_FILE_RE.match(fn):
            continue
        stem = fn.rsplit('.', 1)[0]
        if stem not in kept_ids:
            os.remove(os.path.join(out_dir, fn))
            removed.append(fn)
    return removed


def _manifest(kind, months, category, keywords, reports, sources, failures, duplicates,
               removed_stale, category_only_capped):
    return {
        'kind': kind,
        'collected_at': tc.now_kst().isoformat(),
        'params': {'months': months, 'category': category, 'keywords': keywords or []},
        'sources': sources,
        'reports': reports,
        'failures': failures,
        'duplicates': duplicates,
        'removed_stale': removed_stale,
        'category_only_capped': category_only_capped,
    }


def run_kind(kind, stock, code, months, category, keywords, limit, use_hankyung, today=None):
    reports, sources, failures, duplicates, category_only_capped = collect(
        kind, stock, code, months, category, keywords, limit, use_hankyung, today=today)

    out_dir = reports_dir(stock, kind)
    # 성공한 실행 끝에만 잔재를 지운다 -- industry-category 없이 skip 된 호출이나
    # 네이버가 통째로 실패한 호출에서 지우면, 이번에 아무것도 못 받았을 뿐인데
    # 이전에 잘 받아둔 파일까지 날아간다(일시적 실패가 데이터를 파괴하면 안 된다).
    skip_cleanup = (kind == 'industry' and not category) or \
        sources.get('naver', {}).get('status') == 'failed'
    removed_stale = [] if skip_cleanup else cleanup_stale(out_dir, {r['id'] for r in reports})

    manifest = _manifest(kind, months, category, keywords, reports, sources, failures,
                          duplicates, removed_stale, category_only_capped)
    tc.write_json(os.path.join(out_dir, '_manifest.json'), manifest)

    if sources.get('naver', {}).get('truncated'):
        print(f"[WARN] {kind} 네이버 목록 절삭 가능성: {sources['naver'].get('reason')}")

    if kind == 'industry' and not category:
        status = 'skipped'
    elif not reports and sources.get('naver', {}).get('status') == 'failed' \
            and sources.get('hankyung', {}).get('status') in ('failed', 'skipped'):
        status = 'failed'
    else:
        status = 'ok'
    tc.manifest_update(stock, f'reports_{kind}', status,
                        count=len(reports), sources=sources, failures=len(failures))
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description='증권사 리포트 수집 (종목/산업 분리)')
    ap.add_argument('stock')
    ap.add_argument('--code', default=None)
    ap.add_argument('--months', type=int, default=12)
    ap.add_argument('--industry-category', default=None)
    ap.add_argument('--keywords', default=None, help='콤마로 구분 (예: 펠리클,EUV,포토마스크)')
    ap.add_argument('--limit-company', type=int, default=15)
    ap.add_argument('--limit-industry', type=int, default=15)
    ap.add_argument('--no-hankyung', action='store_true')
    a = ap.parse_args(argv)

    keywords = [k.strip() for k in a.keywords.split(',')] if a.keywords else []
    keywords = [k for k in keywords if k]

    if a.code:
        code = str(a.code).zfill(6)
    else:
        try:
            code = tc.resolve_stock(a.stock)['code']
        except LookupError as e:
            print(f'[ERROR] 종목코드를 찾을 수 없음: {e}')
            return 1

    use_hankyung = not a.no_hankyung

    print('=' * 70)
    print(f'  증권사 리포트 수집: {a.stock} ({code})')
    print('=' * 70)

    t0 = time.time()
    m1 = run_kind('company', a.stock, code, a.months, None, None, a.limit_company, use_hankyung)
    print(f"  [기업] 네이버 {m1['sources'].get('naver')} / 한경 {m1['sources'].get('hankyung')}")
    print(f"         수집 {len(m1['reports'])}건 / 실패 {len(m1['failures'])}건 / "
          f"중복제거 {len(m1['duplicates'])}건 / 잔재삭제 {len(m1['removed_stale'])}건 / "
          f"{time.time() - t0:.1f}s")

    t1 = time.time()
    m2 = run_kind('industry', a.stock, code, a.months, a.industry_category, keywords,
                   a.limit_industry, use_hankyung)
    if a.industry_category:
        print(f"  [산업] 네이버 {m2['sources'].get('naver')} / 한경 {m2['sources'].get('hankyung')}")
        print(f"         수집 {len(m2['reports'])}건 / 실패 {len(m2['failures'])}건 / "
              f"중복제거 {len(m2['duplicates'])}건 / 잔재삭제 {len(m2['removed_stale'])}건 / "
              f"카테고리상한적용 {m2['category_only_capped']} / {time.time() - t1:.1f}s")
    else:
        print('  [산업] --industry-category 없음 -- skipped')

    print('=' * 70)
    return 0


if __name__ == '__main__':
    sys.exit(main())
