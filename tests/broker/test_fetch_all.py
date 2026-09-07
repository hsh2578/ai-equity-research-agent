import io
import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fetch_all as fa

import pypdf


def _pdf_bytes(pages: int, text: str = "전력기기 수주 잔고가 늘고 있다. ") -> bytes:
    w = pypdf.PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=595, height=842)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


META = {"report_idx": "700001", "date": "2026-08-20", "category": "산업",
        "publisher": "유진투자증권", "author": "김분석", "title": "전력기기 슈퍼사이클"}


def test_head_slice_truncates():
    assert fa.head_slice("가나다라마", 3) == "가나다"
    assert fa.head_slice("가나", 10) == "가나"


def test_save_one_writes_full_head_and_meta(tmp_path):
    out = str(tmp_path)
    row = fa.save_one(META, out, limit=10, downloader=lambda idx: _pdf_bytes(8))
    assert row["ok"] is True
    assert row["pages"] == 8
    assert row["too_short"] is False
    assert os.path.exists(os.path.join(out, "700001.txt"))
    assert os.path.exists(os.path.join(out, "700001.head.txt"))
    with open(os.path.join(out, "700001.head.txt"), encoding="utf-8") as f:
        assert len(f.read()) <= 10


def test_save_one_flags_too_short(tmp_path):
    row = fa.save_one(META, str(tmp_path), downloader=lambda idx: _pdf_bytes(3))
    assert row["ok"] is True and row["too_short"] is True   # 삭제가 아니라 플래그만


def test_save_one_is_resumable(tmp_path):
    out = str(tmp_path)
    calls = []

    def dl(idx):
        calls.append(idx)
        return _pdf_bytes(8)

    fa.save_one(META, out, downloader=dl)
    fa.save_one(META, out, downloader=dl)          # 두 번째는 캐시 사용
    assert len(calls) == 1


def test_save_one_records_error_without_raising(tmp_path):
    def boom(idx):
        raise TimeoutError("dead")

    row = fa.save_one(META, str(tmp_path), downloader=boom)
    assert row["ok"] is False
    assert "TimeoutError" in row["error"]


def test_run_preserves_input_order_and_writes_manifest(tmp_path):
    metas = [{**META, "report_idx": str(700000 + i)} for i in range(5)]
    rows = fa.run(metas, str(tmp_path / "text"), workers=3,
                  downloader=lambda idx: _pdf_bytes(8))
    assert [r["idx"] for r in rows] == [str(700000 + i) for i in range(5)]
    mpath = fa.write_manifest(rows, str(tmp_path / "manifest.csv"))
    with open(mpath, encoding="utf-8") as f:
        head = f.readline().strip()
    assert head.startswith("idx,date,category,sector,publisher")


def test_strip_boilerplate_removes_disclaimers_and_blanks():
    raw = ("www.ibks.com\n"
           "본 조사분석자료는 당사 리서치본부에서 신뢰할 만한 자료를 바탕으로\n"
           "\n"
           "   \n"
           "IBKS Spot Comment\n"
           "2026년 CAPEX를 $18B에서 $20B으로 상향\n"
           "동 자료는 어떠한 경우에도 법적 책임소재의 증빙자료로\n")
    got = fa.strip_boilerplate(raw)
    assert "CAPEX" in got and "IBKS Spot Comment" in got
    assert "조사분석자료" not in got
    assert "법적 책임소재" not in got
    assert "\n\n" not in got            # 빈 줄 제거


def test_head_slice_strips_boilerplate_before_truncating():
    raw = "본 조사분석자료는 신뢰할 만한 자료입니다\n" * 50 + "핵심 논지: 전력 수요 급증\n"
    assert "핵심 논지" in fa.head_slice(raw, 100)


def test_polite_downloader_retries_on_403_then_succeeds():
    import urllib.error
    calls, slept = [], []

    def flaky(url):
        calls.append(url)
        if len(calls) < 3:
            raise urllib.error.HTTPError("u", 403, "Forbidden", {}, None)
        return b"PDF"

    import fetch_all as m
    orig = m.download_url
    m.download_url = flaky
    try:
        dl = m.polite_downloader(delay=0, retry_waits=(1, 2, 3), sleep=slept.append)
        assert dl("1") == b"PDF"
        assert len(calls) == 3
        assert slept == [1, 2]          # 두 번 백오프 대기
    finally:
        m.download_url = orig


def test_polite_downloader_does_not_retry_on_404():
    import urllib.error
    calls = []

    def gone(url):
        calls.append(url)
        raise urllib.error.HTTPError("u", 404, "Not Found", {}, None)

    import fetch_all as m
    orig = m.download_url
    m.download_url = gone
    try:
        dl = m.polite_downloader(delay=0, retry_waits=(1, 2), sleep=lambda s: None)
        try:
            dl("1")
            assert False, "should raise"
        except urllib.error.HTTPError as e:
            assert e.code == 404
        assert len(calls) == 1          # 재시도 없음
    finally:
        m.download_url = orig
