import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fetch_quote as fq


def P(*pairs):
    return [{"date": d, "close": float(c)} for d, c in pairs]


def test_period_return_basic():
    assert fq.period_return(P(("2026-03-03", 100), ("2026-08-28", 250))) == 150.0
    assert fq.period_return(P(("2026-03-03", 100))) is None      # 1개면 계산 불가
    assert fq.period_return([]) is None


def test_relative_strength_is_excess_over_bench():
    px = P(("2026-03-03", 100), ("2026-08-28", 200))    # +100%
    bx = P(("2026-03-03", 100), ("2026-08-28", 130))    # +30%
    assert fq.relative_strength(px, bx) == 70.0


def test_monthly_returns_chain_across_month_boundary():
    prices = P(("2026-03-02", 100), ("2026-03-31", 110),
               ("2026-04-01", 111), ("2026-04-30", 132))
    mo = fq.monthly_returns(prices)
    assert round(mo["2026-03"], 1) == 10.0
    assert round(mo["2026-04"], 1) == 20.0      # 3월 종가 110 대비 132


def test_breakout_month_finds_first_surge():
    mo = {"2026-03": 2.0, "2026-04": 18.0, "2026-05": 40.0}
    assert fq.breakout_month(mo, threshold=15.0) == "2026-04"
    assert fq.breakout_month({"2026-03": 1.0}, threshold=15.0) is None


def test_daily_prices_parses_and_sorts(monkeypatch):
    raw = [
        {"localDate": "20260305", "closePrice": 401500.0},
        {"localDate": "20260303", "closePrice": 409000.0},
        {"localDate": "bad", "closePrice": 1.0},          # 형식 불량 → 제외
        {"localDate": "20260304", "closePrice": None},    # 종가 없음 → 제외
    ]
    monkeypatch.setattr(fq, "_get_json", lambda url, timeout=30: raw)
    got = fq.daily_prices("009150", "2026-03-01", "2026-08-29")
    assert [r["date"] for r in got] == ["2026-03-03", "2026-03-05"]


def test_index_code_uses_index_endpoint(monkeypatch):
    seen = {}

    def fake(url, timeout=30):
        seen["url"] = url
        return []

    monkeypatch.setattr(fq, "_get_json", fake)
    fq.daily_prices("KOSPI", "2026-03-01", "2026-08-29")
    assert "/index/KOSPI/" in seen["url"]
    fq.daily_prices("009150", "2026-03-01", "2026-08-29")
    assert "/item/009150/" in seen["url"]
