import datetime
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fetch_range as fr


def _row(idx, date, cat, title, author="김분석", pub="유진투자증권"):
    return f"""
<tr>
  <td>{date}</td><td>{cat}</td>
  <td><a href="/analysis/downpdf?report_idx={idx}">{title} {title} {title}</a></td>
  <td>{author}</td><td>{pub}</td>
</tr>"""


PAGE1 = "<table>" + _row(1, "2026-08-20", "산업", "전력기기 슈퍼사이클") \
                  + _row(2, "2026-08-19", "기업", "삼성전기 목표가 상향") \
                  + _row(3, "2026-08-18", "산업", "IBKS Daily") + "</table>"
# 3번이 겹치는 2페이지 (한경은 페이지 경계에서 중복이 난다)
PAGE2 = "<table>" + _row(3, "2026-08-18", "산업", "IBKS Daily") \
                  + _row(4, "2026-02-01", "산업", "범위 밖 리포트") + "</table>"


def _fetcher(pages):
    def _f(url):
        n = int(url.rsplit("now_page=", 1)[1])
        return pages[n - 1] if n <= len(pages) else ""
    return _f


def test_build_url_has_range_and_page():
    url = fr.build_url(datetime.date(2026, 3, 1), datetime.date(2026, 8, 29), 7)
    assert "sdate=2026-03-01" in url and "edate=2026-08-29" in url and "now_page=7" in url
    assert "skinType" not in url          # skinType 은 파서를 오정렬시키므로 금지


def test_fetch_range_dedupes_across_pages():
    got = fr.fetch_range(datetime.date(2026, 3, 1), datetime.date(2026, 8, 29),
                         page_fetcher=_fetcher([PAGE1, PAGE2]))
    assert [r.report_idx for r in got] == ["1", "2", "3", "4"]   # 3번 중복 제거


def test_fetch_range_stops_on_empty_page():
    calls = []

    def _f(url):
        calls.append(url)
        return PAGE1 if len(calls) == 1 else ""

    fr.fetch_range(datetime.date(2026, 3, 1), datetime.date(2026, 8, 29), page_fetcher=_f)
    assert len(calls) == 2          # 1페이지 수집 + 2페이지에서 빈 응답 확인 후 중단


def test_filter_range_applies_category_daily_and_dates():
    raw = fr.fetch_range(datetime.date(2026, 3, 1), datetime.date(2026, 8, 29),
                         page_fetcher=_fetcher([PAGE1, PAGE2]))
    kept = fr.filter_range(raw, datetime.date(2026, 3, 1), datetime.date(2026, 8, 29),
                           category="산업")
    ids = [r.report_idx for r in kept]
    assert ids == ["1"]             # 2=기업 제외, 3=데일리 제외, 4=범위 밖 제외


def test_filter_range_keep_daily_flag():
    raw = fr.fetch_range(datetime.date(2026, 3, 1), datetime.date(2026, 8, 29),
                         page_fetcher=_fetcher([PAGE1]))
    kept = fr.filter_range(raw, datetime.date(2026, 3, 1), datetime.date(2026, 8, 29),
                           category="산업", drop_daily=False)
    assert [r.report_idx for r in kept] == ["1", "3"]
