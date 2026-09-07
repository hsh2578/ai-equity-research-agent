"""한경 컨센서스 임의 기간 리포트 목록 수집기.

fetch_list.py 의 주간(week_range) 전용 수집을 임의 기간으로 일반화한다.
파서/필터는 fetch_list 의 검증된 순수 함수를 그대로 재사용한다.

주의: ?skinType=industry URL 은 컬럼 레이아웃이 달라(카테고리 컬럼 없음)
parse_list_html 이 오정렬된다 — 데일리 필터가 무력화되므로 절대 쓰지 않는다.
파라미터 없는 전체 목록을 받아 클라이언트에서 category 로 거른다.
"""
from __future__ import annotations

import datetime
import sys
import os
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_list import (  # noqa: E402
    LIST_URL,
    Report,
    fetch_url,
    is_daily,
    parse_list_html,
)


def build_url(start: datetime.date, end: datetime.date, page: int) -> str:
    return f"{LIST_URL}?sdate={start}&edate={end}&now_page={page}"


def dedupe(reports: list[Report]) -> list[Report]:
    seen: set[str] = set()
    out: list[Report] = []
    for r in reports:
        if r.report_idx in seen:
            continue
        seen.add(r.report_idx)
        out.append(r)
    return out


def filter_range(
    reports: list[Report],
    start: datetime.date,
    end: datetime.date,
    category: str | None = None,
    drop_daily: bool = True,
) -> list[Report]:
    """날짜 범위 → 카테고리 → 데일리 순으로 거른다 (fetch_list.filter_candidates 와 동일 순서)."""
    out: list[Report] = []
    for r in reports:
        try:
            d = datetime.date.fromisoformat(r.date)
        except ValueError:
            continue
        if not (start <= d <= end):
            continue
        if category and r.category != category:
            continue
        if drop_daily and is_daily(r.title):
            continue
        out.append(r)
    return out


def fetch_range(
    start: datetime.date,
    end: datetime.date,
    max_pages: int = 400,
    page_fetcher=None,
    progress=None,
) -> list[Report]:
    """start~end 전 카테고리 목록을 빈 페이지가 나올 때까지 순회 수집 (미필터, dedupe만)."""
    fetch = page_fetcher or (lambda url: fetch_url(url))
    collected: list[Report] = []
    for page in range(1, max_pages + 1):
        page_reports = parse_list_html(fetch(build_url(start, end, page)))
        if not page_reports:
            break
        collected.extend(page_reports)
        if progress:
            progress(page, len(collected))
    return dedupe(collected)


def main(argv: list[str]) -> int:
    import argparse
    import json

    p = argparse.ArgumentParser(description="한경 컨센서스 기간 목록 수집")
    p.add_argument("start", help="YYYY-MM-DD")
    p.add_argument("end", help="YYYY-MM-DD")
    p.add_argument("--category", default=None, help="산업 / 기업 / 시장 ... (미지정=전체)")
    p.add_argument("--keep-daily", action="store_true", help="데일리성 리포트를 남긴다")
    p.add_argument("--max-pages", type=int, default=400)
    p.add_argument("--out", default=None, help="JSON 저장 경로 (미지정=stdout)")
    a = p.parse_args(argv)

    start = datetime.date.fromisoformat(a.start)
    end = datetime.date.fromisoformat(a.end)

    def _progress(page: int, total: int) -> None:
        print(f"  page {page:>3} ... {total} rows", file=sys.stderr)

    raw = fetch_range(start, end, max_pages=a.max_pages, progress=_progress)
    kept = filter_range(raw, start, end, a.category, drop_daily=not a.keep_daily)

    payload = {
        "range": {"start": a.start, "end": a.end},
        "category": a.category or "전체",
        "fetched": len(raw),
        "count": len(kept),
        "dropped": len(raw) - len(kept),
        "reports": [{**asdict(r), "pdf_url": r.pdf_url} for r in kept],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"{a.out}  (fetched={len(raw)}, kept={len(kept)})")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    raise SystemExit(main(sys.argv[1:]))
