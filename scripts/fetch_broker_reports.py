"""
종목/업종 애널리스트 리포트 일괄 수집 (v5.5 신설)

/wf-report 의 "정독 의무" (산업 3+ / 기업 3+ 애널리스트 리포트 전문 정독) 를
실행 가능하게 만든다. 지금까지는 종목마다 _cw_fetch_reports.py, _cw_dl.py,
_oci_hist_analyst.py 같은 일회용 스크립트를 새로 짜고 있었다.

수집기 본체는 scripts/broker/ 로 이식된 검증 코드다 (출처: 주식 리포트 카카오톡
프로젝트, 실전 2회 이상 검증). 이 래퍼는 우리 데이터 레이아웃에 맞춰
data/{종목}/reports_text/ 로 떨어뜨리고 목차를 만든다.

사용법
------
    # 한국콜마 기업 리포트 최근 6개월 (목록만 확인)
    python scripts/fetch_broker_reports.py 한국콜마 --months 6 --dry-run

    # 실제 다운로드
    python scripts/fetch_broker_reports.py 한국콜마 --months 6

    # 업종 리포트 (제목/작성자 키워드 매칭)
    python scripts/fetch_broker_reports.py 한국콜마 --category 산업 --keyword 화장품 --months 6

주의: 한경은 IP 단위 rate limit 이 있다. workers 는 2 를 넘기지 말 것
(실측: workers 8 + 동시 작업으로 IP 전면 차단, 796건 중 685건 실패).

차단 위험은 다운로드가 아니라 **목록 수집** 단계에 몰려 있었다 (v5.6 수정).
다운로드는 polite_downloader(delay, workers<=2) 로 조심했는데, 정작 목록은
최대 400 페이지를 지연 없이 전 카테고리로 훑고서 결국 8건 이하만 골랐다.
지금은 세 가지로 줄인다:
  - 페이지 사이 --page-delay 초 지연 (기본 1.0)
  - --months 에 비례한 페이지 예산 (한경 실측 20행/페이지, 약 37페이지/월)
  - 필요한 매칭 건수(--limit)를 채우면 조기 종료
scripts/broker/ 는 이식본이라 손대지 않고, fetch_range 의 page_fetcher 주입점만 쓴다.

출력
----
    data/{종목}/reports_text/{idx}.txt        전문
    data/{종목}/reports_text/{idx}.head.txt   발췌 (기본 16,000자)
    data/{종목}/_broker_reports.json          목차
"""
import sys
import io
import os
import json
import time
import datetime
import argparse

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'broker'))

from dataclasses import asdict     # noqa: E402
import fetch_range as fr           # noqa: E402
import fetch_all as fa             # noqa: E402
import fetch_list as fl            # noqa: E402

# 발췌 길이. 3,500자는 면책 고지가 절반을 차지해 병목/실적 근거가 잘린다는 것이
# 원 프로젝트 실측으로 확인됐다 (reference/pitfalls.md). 16,000자가 실측 하한.
HEAD_CHARS = 16000

# 한경 컨센서스 실측 (2026-09): 20행/페이지, 전 카테고리 약 24건/일 -> 약 37페이지/월.
# 여유를 둬서 45페이지/월로 잡고 상·하한을 건다.
PAGES_PER_MONTH = 45
MAX_PAGES_CAP = 400        # broker/fetch_range 기본값과 동일한 절대 상한
MIN_PAGES = 20
MAX_WORKERS = 2            # docstring 의 "2 를 넘기지 말 것" 을 코드로 강제


def page_budget(months, per_month=PAGES_PER_MONTH):
    """--months 에 비례한 목록 페이지 예산."""
    return max(MIN_PAGES, min(MAX_PAGES_CAP, int(round(months * per_month))))


def clamp_workers(workers):
    """(적용할 workers, 경고 문구 또는 None)."""
    if workers > MAX_WORKERS:
        return MAX_WORKERS, (f"workers={workers} 는 한경 IP 차단 위험이 크다. "
                             f"{MAX_WORKERS} 로 낮춘다.")
    return workers, None


def keyword_hit(r, keyword):
    """제목/작성자/발행사에 키워드가 걸리나."""
    if not keyword:
        return True
    k = keyword.lower()
    return (k in (r.title or '').lower()
            or k in (r.author or '').lower()
            or k in (r.publisher or '').lower())


def matches(r, keyword, category):
    """최종 선택 기준과 동일한 판정 (카테고리 + 데일리 제거 + 키워드).

    조기 종료 판단에 쓰므로 filter_range + pick 과 기준이 같아야 한다.
    """
    if category and r.category != category:
        return False
    if fl.is_daily(r.title or ''):
        return False
    return keyword_hit(r, keyword)


def paged_fetcher(delay, max_pages, fetch=None, parse=None, sleeper=None,
                  stop_when=None, progress=None):
    """fetch_range 에 주입할 page_fetcher. 지연 + 예산 + 조기 종료.

    - 페이지 사이에 delay 초 쉰다 (첫 페이지 앞에는 쉬지 않는다)
    - max_pages 를 넘거나 stop_when(누적 rows) 이 참이면 빈 문자열을 돌려준다.
      fetch_range 는 파싱 결과가 비면 break 하므로 이것이 조기 종료 신호다.
    """
    fetch = fetch or fl.fetch_url
    parse = parse or fl.parse_list_html
    sleeper = sleeper or time.sleep
    state = {'pages': 0, 'rows': [], 'done': False}

    def _fetch(url):
        if state['done'] or state['pages'] >= max_pages:
            return ''
        if state['pages']:
            sleeper(delay)
        html = fetch(url)
        state['pages'] += 1
        rows = parse(html)
        state['rows'].extend(rows)
        if progress:
            progress(state['pages'], len(state['rows']))
        if stop_when and stop_when(state['rows']):
            state['done'] = True
        return html

    return _fetch


def pick(reports, keyword, limit):
    """제목/작성자/발행사에 키워드가 걸리는 리포트를 최신순으로 limit 개."""
    hits = [r for r in reports if keyword_hit(r, keyword)]
    return sorted(hits, key=lambda r: r.date or '', reverse=True)[:limit]


def main(argv=None):
    p = argparse.ArgumentParser(description='종목/업종 애널리스트 리포트 수집')
    p.add_argument('stock', help='종목명 (data/{종목}/ 에 저장)')
    p.add_argument('--keyword', default=None, help='매칭 키워드 (미지정 시 종목명)')
    p.add_argument('--category', default='기업', help='기업 / 산업 / 시장 / 경제 (기본 기업)')
    p.add_argument('--months', type=int, default=6, help='최근 N개월 (기본 6)')
    p.add_argument('--limit', type=int, default=8, help='최대 수집 건수 (기본 8)')
    p.add_argument('--workers', type=int, default=2, help='동시 다운로드 (기본 2, 올리지 말 것)')
    p.add_argument('--delay', type=float, default=0.6, help='PDF 요청 간 지연초 (기본 0.6)')
    p.add_argument('--page-delay', type=float, default=1.0,
                   help='목록 페이지 간 지연초 (기본 1.0, 차단 위험이 여기 몰려 있다)')
    p.add_argument('--max-pages', type=int, default=None,
                   help=f'목록 페이지 상한 (기본 months x {PAGES_PER_MONTH}, 상한 {MAX_PAGES_CAP})')
    p.add_argument('--head-chars', type=int, default=HEAD_CHARS, help=f'발췌 길이 (기본 {HEAD_CHARS})')
    p.add_argument('--dry-run', action='store_true', help='목록만 출력')
    a = p.parse_args(argv)

    a.workers, warn = clamp_workers(a.workers)
    if warn:
        print(f"[WARN] {warn}")

    keyword = a.keyword or a.stock
    end = datetime.date.today()
    start = end - datetime.timedelta(days=a.months * 31)
    max_pages = a.max_pages or page_budget(a.months)

    print(f"[1/3] 한경 컨센서스 목록: {start} ~ {end}")
    print(f"      페이지 예산 {max_pages}p (약 {max_pages * 20:,}건), "
          f"페이지 간 {a.page_delay}s 지연, '{keyword}' {a.limit}건 확보 시 조기 종료")

    def _need_met(rows):
        return sum(1 for r in rows if matches(r, keyword, a.category)) >= a.limit

    fetcher = paged_fetcher(a.page_delay, max_pages, stop_when=_need_met)
    reports = fr.fetch_range(start, end, max_pages=max_pages, page_fetcher=fetcher)
    print(f"      전체 {len(reports)}건")

    # 카테고리 필터 + 데일리 제거는 filter_range 가 한다 (fetch_range 에는 category 인자가 없다)
    scoped = fr.filter_range(reports, start, end, category=a.category, drop_daily=True)
    print(f"      카테고리 '{a.category}' + 데일리 제거 후 {len(scoped)}건")

    chosen = pick(scoped, keyword, a.limit)
    print(f"[2/3] '{keyword}' 매칭 {len(chosen)}건 선택")
    for r in chosen:
        print(f"      {r.date}  {(r.publisher or ''):<10} {(r.title or '')[:52]}")

    if not chosen:
        print("\n[WARN] 매칭 0건. --keyword 를 바꾸거나 --category 를 조정할 것.")
        return 1
    if a.dry_run:
        print("\n[DRY-RUN] 다운로드 생략.")
        return 0

    out_dir = f'data/{a.stock}/reports_text'
    os.makedirs(out_dir, exist_ok=True)
    print(f"[3/3] 전문 다운로드 -> {out_dir}  "
          f"(workers={a.workers}, delay={a.delay}, 발췌 {a.head_chars:,}자)")

    metas = [asdict(r) for r in chosen]
    downloader = fa.polite_downloader(delay=a.delay)
    rows = fa.run(metas, out_dir=out_dir, workers=a.workers,
                  limit=a.head_chars, downloader=downloader)

    ok = [r for r in rows if r.get('ok') and not r.get('too_short')]
    short = [r for r in rows if r.get('too_short')]
    err = [r for r in rows if r.get('error')]

    index = [{
        'idx': r['idx'], 'date': r.get('date'), 'publisher': r.get('publisher'),
        'title': r.get('title'), 'pages': r.get('pages'), 'chars': r.get('chars'),
        'full': os.path.join(out_dir, f"{r['idx']}.txt"),
        'head': os.path.join(out_dir, f"{r['idx']}.head.txt"),
    } for r in ok]

    with open(f'data/{a.stock}/_broker_reports.json', 'w', encoding='utf-8') as f:
        json.dump({'stock': a.stock, 'keyword': keyword, 'category': a.category,
                   'collected_at': datetime.datetime.now().isoformat(timespec='seconds'),
                   'reports': index}, f, ensure_ascii=False, indent=2)

    print(f"\n  성공 {len(ok)} / 페이지부족 {len(short)} / 실패 {len(err)}")
    for r in index:
        print(f"    {r['date']}  {(r['publisher'] or ''):<10} {r['pages']}p  {r['full']}")
    for r in err:
        print(f"    [ERR] {r['idx']}: {r['error'][:80]}")
    print(f"\n[OK] 목차: data/{a.stock}/_broker_reports.json")
    print("  다음 단계: 각 .txt 를 전문 정독하고, 인용 시 원문 grep 매칭 후 100% 복사할 것.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
