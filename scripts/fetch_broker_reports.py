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
    # 한국콜마 기업 리포트 최근 6개월
    python scripts/fetch_broker_reports.py 한국콜마 --months 6

    # 업종 리포트도 같이 (제목/작성자에 키워드 매칭)
    python scripts/fetch_broker_reports.py 한국콜마 --months 6 --category 산업 --keyword 화장품

    # 목록만 보고 받지는 않기
    python scripts/fetch_broker_reports.py 한국콜마 --months 3 --dry-run

주의: 한경은 IP 단위 rate limit 이 있다. workers 는 2 를 넘기지 말 것.
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

import fetch_range as fr          # noqa: E402
import fetch_all as fa            # noqa: E402


def pick(reports, keyword, limit):
    """제목/종목명/작성자에 키워드가 걸리는 리포트를 최신순으로 limit 개."""
    if not keyword:
        hits = reports
    else:
        k = keyword.lower()
        hits = [r for r in reports
                if k in (getattr(r, 'title', '') or '').lower()
                or k in (getattr(r, 'stock_name', '') or '').lower()
                or k in (getattr(r, 'company', '') or '').lower()]
    hits = sorted(hits, key=lambda r: getattr(r, 'date', ''), reverse=True)
    return hits[:limit]


def main(argv=None):
    p = argparse.ArgumentParser(description='종목/업종 애널리스트 리포트 수집')
    p.add_argument('stock', help='종목명 (data/{종목}/ 에 저장)')
    p.add_argument('--keyword', default=None,
                   help='매칭 키워드 (미지정 시 종목명 사용)')
    p.add_argument('--category', default='기업',
                   help='한경 카테고리: 기업 / 산업 / 시장 / 경제 ... (기본 기업)')
    p.add_argument('--months', type=int, default=6, help='최근 N개월 (기본 6)')
    p.add_argument('--limit', type=int, default=8, help='최대 수집 건수 (기본 8)')
    p.add_argument('--workers', type=int, default=2,
                   help='동시 다운로드 (기본 2, 한경 rate limit 때문에 올리지 말 것)')
    p.add_argument('--delay', type=float, default=0.6, help='요청 간 지연초 (기본 0.6)')
    p.add_argument('--dry-run', action='store_true', help='목록만 출력')
    a = p.parse_args(argv)

    if a.workers > 3:
        print(f"[WARN] workers={a.workers} 는 한경 IP 차단 위험이 크다. 2 로 낮춘다.")
        a.workers = 2

    keyword = a.keyword or a.stock
    end = datetime.date.today()
    start = end - datetime.timedelta(days=a.months * 31)
    out_dir = f'data/{a.stock}/reports_text'

    print(f"[1/3] 한경 컨센서스 목록 수집: {start} ~ {end} / 카테고리 {a.category}")
    reports = fr.fetch_range(start, end, category=a.category)
    print(f"      전체 {len(reports)}건")

    chosen = pick(reports, keyword, a.limit)
    print(f"[2/3] '{keyword}' 매칭 {len(chosen)}건 선택")
    for r in chosen:
        print(f"      {getattr(r, 'date', '?')}  {getattr(r, 'company', '?'):<10} "
              f"{(getattr(r, 'title', '') or '')[:52]}")

    if not chosen:
        print("\n[WARN] 매칭 0건. --keyword 를 바꾸거나 --category 를 조정할 것.")
        return 1
    if a.dry_run:
        print("\n[DRY-RUN] 다운로드 생략.")
        return 0

    os.makedirs(out_dir, exist_ok=True)
    print(f"[3/3] 전문 다운로드 -> {out_dir}  (workers={a.workers}, delay={a.delay})")
    idxs = [getattr(r, 'idx', None) for r in chosen]
    idxs = [str(i) for i in idxs if i]
    results = fa.fetch_all(idxs, out_dir=out_dir, workers=a.workers, delay=a.delay)

    ok = [r for r in results if not r.get('error') and not r.get('too_short')]
    short = [r for r in results if r.get('too_short')]
    err = [r for r in results if r.get('error')]

    index = []
    meta_by_idx = {str(getattr(r, 'idx', '')): r for r in chosen}
    for r in ok:
        src = meta_by_idx.get(str(r.get('idx')))
        index.append({
            'idx': r.get('idx'),
            'pages': r.get('pages'),
            'chars': r.get('chars'),
            'path': r.get('path'),
            'date': getattr(src, 'date', None) if src else None,
            'company': getattr(src, 'company', None) if src else None,
            'title': getattr(src, 'title', None) if src else None,
        })
    with open(f'data/{a.stock}/_broker_reports.json', 'w', encoding='utf-8') as f:
        json.dump({'stock': a.stock, 'keyword': keyword, 'category': a.category,
                   'collected_at': datetime.datetime.now().isoformat(timespec='seconds'),
                   'reports': index}, f, ensure_ascii=False, indent=2)

    print(f"\n  성공 {len(ok)} / 페이지부족 {len(short)} / 실패 {len(err)}")
    for r in index:
        print(f"    {r['date']}  {(r['company'] or ''):<10} {r['pages']}p  {r['path']}")
    print(f"\n[OK] 목차: data/{a.stock}/_broker_reports.json")
    print("  다음 단계: 각 .txt 를 전문 정독하고, 인용 시 원문 grep 매칭 후 100% 복사할 것.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
