import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import extract_pdf as ep


def test_clean_text_strips_email_and_url():
    raw = "문의 analyst@brokerage.co.kr 자료 https://research.example.com/a?b=1 본문 유지"
    out = ep.clean_text(raw)
    assert "@" not in out
    assert "http" not in out
    assert "본문 유지" in out          # 일반 텍스트는 보존


def test_is_too_short_floor():
    assert ep.is_too_short(2, floor=5) is True
    assert ep.is_too_short(10, floor=5) is False
