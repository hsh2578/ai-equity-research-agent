"""한경 컨센서스 주간 리포트 목록 수집 + 데일리 필터.

순수 함수(parse/normalize/is_daily/filter)와 라이브 수집(fetch_*)을 분리한다.
"""
from __future__ import annotations

import datetime
import html
import re
import urllib.request
from dataclasses import dataclass, asdict

LIST_URL = "https://consensus.hankyung.com/analysis/list"
PDF_URL = "https://consensus.hankyung.com/analysis/downpdf?report_idx={idx}"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://consensus.hankyung.com/",
}


@dataclass
class Report:
    date: str          # YYYY-MM-DD
    category: str
    title: str
    author: str
    publisher: str
    report_idx: str

    @property
    def pdf_url(self) -> str:
        return PDF_URL.format(idx=self.report_idx)


def normalize_date(s: str) -> str:
    s = s.strip()
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})", s)
    if m:
        return f"20{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return s


def _dedupe_title(blob: str) -> str:
    """한경 list는 제목 텍스트가 N회 반복되어 들어온다. 최소 반복 단위를 복원."""
    words = blob.split()
    n = len(words)
    for p in range(1, n // 2 + 1):
        if n % p == 0 and all(words[i] == words[i % p] for i in range(n)):
            return " ".join(words[:p])
    return blob.strip()


# 데일리/브리핑성 제목 키워드 (소문자 비교)
# 데일리/모닝 브리핑만 컷. '위클리/weekly'는 깊은 주간전략을 죽이므로 제외하지 않는다
# (얕은 위클리는 페이지 하한선 <5p가, 깊은 위클리는 7차원 채점이 거른다).
DAILY_KEYWORDS = (
    "daily", "morning", "아침", "데일리", "모닝", "brief", "wake up", "wake-up",
    "market view", "start with", "forex live", "마감시황",
    "마감 시황", "오프닝", "opening", "letter", "에요", "ibks",
)

# 후보로 삼을 카테고리 (시장=매크로/시황 풀, 기업=와일드카드 후보)
CANDIDATE_CATEGORIES = ("산업", "시장", "채권", "외환", "퀀트", "경제", "기업", "해외")

_DATE_PREFIX = re.compile(r"^\s*\d{1,2}\s*/\s*\d{1,2}\s*,")  # "06/15, ..."


def is_daily(title: str) -> bool:
    t = title.lower().strip()
    if _DATE_PREFIX.match(title):
        return True
    return any(kw in t for kw in DAILY_KEYWORDS)


def week_range(today: datetime.date) -> tuple[datetime.date, datetime.date]:
    """가장 최근 '완료된' 월~금 범위 (주말 실행 기준).

    토/일에 실행하면 그 주 월~금(방금 끝난 주), 평일에 실행하면 직전 주 월~금.
    """
    wd = today.weekday()          # 월=0 .. 일=6
    if wd >= 5:                    # 토(5)/일(6)
        monday = today - datetime.timedelta(days=wd)
    else:                          # 평일: 직전 완료 주
        monday = today - datetime.timedelta(days=wd + 7)
    return monday, monday + datetime.timedelta(days=4)


def filter_candidates(
    reports: list[Report], start: datetime.date, end: datetime.date
) -> list[Report]:
    out: list[Report] = []
    for r in reports:
        try:
            d = datetime.date.fromisoformat(r.date)
        except ValueError:
            continue
        if not (start <= d <= end):
            continue
        if r.category not in CANDIDATE_CATEGORIES:
            continue
        if is_daily(r.title):
            continue
        out.append(r)
    return out


def parse_list_html(raw: str) -> list[Report]:
    reports: list[Report] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", raw, re.S):
        m = re.search(r"report_idx=(\d+)", tr)
        if not m:
            continue
        cells = [
            re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        ]
        cells = [c for c in cells if c]
        if len(cells) < 5:
            continue
        reports.append(
            Report(
                date=normalize_date(cells[0]),
                category=cells[1],
                title=_dedupe_title(cells[2]),
                author=cells[-2],
                publisher=cells[-1],
                report_idx=m.group(1),
            )
        )
    return reports


def fetch_url(url: str) -> str:
    data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()
    for enc in ("utf-8", "euc-kr", "cp949"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "ignore")


def fetch_week(today: datetime.date, max_pages: int = 12) -> list[Report]:
    """지난주(완료된) 월~금에 발행된 후보 리포트를 수집한다."""
    start, end = week_range(today)
    collected: list[Report] = []
    for page in range(1, max_pages + 1):
        url = f"{LIST_URL}?sdate={start}&edate={end}&now_page={page}"
        page_reports = parse_list_html(fetch_url(url))
        if not page_reports:
            break
        collected.extend(page_reports)
        dates = [r.date for r in page_reports if r.date]
        if dates and min(dates) < start.isoformat():
            break
    # report_idx 중복 제거
    seen, uniq = set(), []
    for r in collected:
        if r.report_idx in seen:
            continue
        seen.add(r.report_idx)
        uniq.append(r)
    return filter_candidates(uniq, start, end)


if __name__ == "__main__":
    import json
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    today = datetime.date.today()
    if len(sys.argv) > 1:
        today = datetime.date.fromisoformat(sys.argv[1])
    start, end = week_range(today)
    reports = fetch_week(today)
    payload = {
        "week": {"start": start.isoformat(), "end": end.isoformat()},
        "count": len(reports),
        "reports": [{**asdict(r), "pdf_url": r.pdf_url} for r in reports],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
