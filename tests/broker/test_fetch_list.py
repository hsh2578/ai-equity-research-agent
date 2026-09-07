import datetime
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fetch_list as fl

# 한경 list 구조를 모사한 픽스처 (제목 3중 반복 + report_idx 링크)
SAMPLE_HTML = """
<table><tbody>
<tr>
  <td>2026-06-15</td><td>산업</td>
  <td><a href="/analysis/downpdf?report_idx=650067">AI 컴퓨팅 파워 선물이 온다 AI 컴퓨팅 파워 선물이 온다 AI 컴퓨팅 파워 선물이 온다</a></td>
  <td>황성현</td><td>유진투자증권</td>
</tr>
<tr>
  <td>2026-06-15</td><td>외환</td>
  <td><a href="/analysis/downpdf?report_idx=650070">Daily Forex Live Daily Forex Live Daily Forex Live</a></td>
  <td>민경원</td><td>우리은행</td>
</tr>
<tr><td>광고행</td><td>없음</td></tr>
</tbody></table>
"""


def test_parse_extracts_reports_with_fields():
    reports = fl.parse_list_html(SAMPLE_HTML)
    assert len(reports) == 2          # report_idx 없는 광고행 제외
    r = reports[0]
    assert r.report_idx == "650067"
    assert r.date == "2026-06-15"
    assert r.category == "산업"
    assert r.title == "AI 컴퓨팅 파워 선물이 온다"   # 3중 반복 dedupe
    assert r.publisher == "유진투자증권"
    assert r.pdf_url == "https://consensus.hankyung.com/analysis/downpdf?report_idx=650067"


def test_normalize_date_two_digit_year():
    assert fl.normalize_date("26.06.15") == "2026-06-15"
    assert fl.normalize_date("2026-06-15") == "2026-06-15"


def test_is_daily_detects_briefs():
    assert fl.is_daily("Daily Forex Live") is True
    assert fl.is_daily("06/15, Kiwoom Morning Letter") is True
    assert fl.is_daily("안녕하세요 위클리에요") is True
    assert fl.is_daily("Market View") is True
    # 깊이 있는 리포트는 통과
    assert fl.is_daily("AI 컴퓨팅 파워 선물이 온다") is False
    assert fl.is_daily("애플 너마저: 메모리 병목 앞에 선 온디바이스 AI") is False
    # 깊은 주간전략은 살아남아야 함 (weekly/위클리 하드컷 제거 — 페이지하한·채점이 판단)
    assert fl.is_daily("반도체 Weekly 전망") is False
    assert fl.is_daily("위클리 매크로 전략") is False


def test_week_range_weekend_run():
    # 토요일(06-20) 실행 → 그 주 월~금 (06-15 ~ 06-19)
    mon, fri = fl.week_range(datetime.date(2026, 6, 20))
    assert mon == datetime.date(2026, 6, 15)
    assert fri == datetime.date(2026, 6, 19)
    # 일요일(06-21) 실행도 같은 주 월~금
    mon, fri = fl.week_range(datetime.date(2026, 6, 21))
    assert (mon, fri) == (datetime.date(2026, 6, 15), datetime.date(2026, 6, 19))
    # 평일(수 06-17) 실행 → 직전 완료 주(06-08 ~ 06-12)
    mon, fri = fl.week_range(datetime.date(2026, 6, 17))
    assert (mon, fri) == (datetime.date(2026, 6, 8), datetime.date(2026, 6, 12))


def test_filter_candidates_window_category_daily():
    reports = [
        fl.Report("2026-06-15", "산업", "AI 컴퓨팅 파워 선물이 온다", "황", "유진", "1"),
        fl.Report("2026-06-15", "외환", "Daily Forex Live", "민", "우리", "2"),   # 데일리 컷
        fl.Report("2026-06-08", "산업", "지난주 리포트", "김", "A", "3"),          # 윈도우 밖
        fl.Report("2026-06-19", "시장", "FOMC 프리뷰 심층", "이", "메리츠", "4"),
    ]
    start, end = datetime.date(2026, 6, 15), datetime.date(2026, 6, 19)
    out = fl.filter_candidates(reports, start, end)
    idxs = {r.report_idx for r in out}
    assert idxs == {"1", "4"}
