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
import datetime
import argparse

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'broker'))

from dataclasses import asdict     # noqa: E402
import fetch_range as fr           # noqa: E402
import fetch_all as fa             # noqa: E402

# 발췌 길이. 3,500자는 면책 고지가 절반을 차지해 병목/실적 근거가 잘린다는 것이
# 원 프로젝트 실측으로 확인됐다 (reference/pitfalls.md). 16,000자가 실측 하한.
HEAD_CHARS = 16000


def pick(reports, keyword, limit):
    """제목/작성자/발행사에 키워드가 걸리는 리포트를 최신순으로 limit 개."""
    if keyword:
        k = keyword.lower()
        hits = [r for r in reports
                if k in (r.title or '').lower()
                or k in (r.author or '').lower()
                or k in (r.publisher or '').lower()]
    else:
        hits = list(reports)
    return sorted(hits, key=lambda r: r.date or '', reverse=True)[:limit]


def main(argv=None):
    p = argparse.ArgumentParser(description='종목/업종 애널리스트 리포트 수집')
    p.add_argument('stock', help='종목명 (data/{종목}/ 에 저장)')
    p.add_argument('--keyword', default=None, help='매칭 키워드 (미지정 시 종목명)')
    p.add_argument('--category', default='기업', help='기업 / 산업 / 시장 / 경제 (기본 기업)')
    p.add_argument('--months', type=int, default=6, help='최근 N개월 (기본 6)')
    p.add_argument('--limit', type=int, default=8, help='최대 수집 건수 (기본 8)')
    p.add_argument('--workers', type=int, default=2, help='동시 다운로드 (기본 2, 올리지 말 것)')
    p.add_argument('--delay', type=float, default=0.6, help='요청 간 지연초 (기본 0.6)')
    p.add_argument('--head-chars', type=int, default=HEAD_CHARS, help=f'발췌 길이 (기본 {HEAD_CHARS})')
    p.add_argument('--dry-run', action='store_true', help='목록만 출력')
    a = p.parse_args(argv)

    if a.workers > 3:
        print(f"[WARN] workers={a.workers} 는 한경 IP 차단 위험이 크다. 2 로 낮춘다.")
        a.workers = 2

    keyword = a.keyword or a.stock
    end = datetime.date.today()
    start = end - datetime.timedelta(days=a.months * 31)

    print(f"[1/3] 한경 컨센서스 목록: {start} ~ {end}")
    reports = fr.fetch_range(start, end)
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
