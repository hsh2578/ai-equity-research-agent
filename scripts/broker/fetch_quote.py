"""네이버 금융 주가/지수 조회 + 수익률·상대강도 계산.

리포트의 '유망하다'는 주장을 주가 사실과 대조하기 위한 축.
  - 이미 오른 업종인가 (상승 서사 역설계의 대상 확정)
  - 아직 안 오른 업종인가 (미리 찾기의 대상)

순수 계산 함수(period_return/relative_strength/monthly_returns)와
라이브 조회(daily_prices/integration)를 분리해 테스트 가능하게 둔다.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "Referer": "https://m.stock.naver.com/"}

ITEM_CHART = ("https://api.stock.naver.com/chart/domestic/item/{code}/day"
              "?startDateTime={s}0000&endDateTime={e}0000")
INDEX_CHART = ("https://api.stock.naver.com/chart/domestic/index/{code}/day"
               "?startDateTime={s}0000&endDateTime={e}0000")
INTEGRATION = "https://m.stock.naver.com/api/stock/{code}/integration"

INDEX_CODES = ("KOSPI", "KOSDAQ", "KPI200")


def _get_json(url: str, timeout: int = 30):
    raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()
    return json.loads(raw.decode("utf-8"))


def _compact(d: str) -> str:
    """'2026-03-01' -> '202603010000' 용 앞 8자리."""
    return d.replace("-", "")[:8]


def daily_prices(code: str, start: str, end: str) -> list[dict]:
    """일봉 리스트. code 가 KOSPI/KOSDAQ/KPI200 이면 지수 엔드포인트를 쓴다.

    반환: [{"date": "2026-03-03", "close": 409000.0}, ...] 날짜 오름차순
    """
    tmpl = INDEX_CHART if code.upper() in INDEX_CODES else ITEM_CHART
    rows = _get_json(tmpl.format(code=code, s=_compact(start), e=_compact(end)))
    out = []
    for r in rows:
        ld = str(r.get("localDate", ""))
        cp = r.get("closePrice")
        if len(ld) != 8 or cp in (None, ""):
            continue
        out.append({"date": f"{ld[:4]}-{ld[4:6]}-{ld[6:]}", "close": float(cp)})
    out.sort(key=lambda r: r["date"])
    return out


def period_return(prices: list[dict]) -> float | None:
    """구간 수익률 % (첫 종가 대비 마지막 종가)."""
    if len(prices) < 2 or not prices[0]["close"]:
        return None
    return (prices[-1]["close"] / prices[0]["close"] - 1.0) * 100.0


def relative_strength(prices: list[dict], bench: list[dict]) -> float | None:
    """상대강도 = 종목 수익률 - 벤치마크 수익률 (%p). 섹터 로테이션/RRG 계열 아이디어."""
    a, b = period_return(prices), period_return(bench)
    if a is None or b is None:
        return None
    return a - b


def monthly_returns(prices: list[dict]) -> dict[str, float]:
    """월별 수익률 % — 상승이 '언제' 시작됐는지 특정하는 데 쓴다."""
    by_month: dict[str, list[dict]] = {}
    for p in prices:
        by_month.setdefault(p["date"][:7], []).append(p)
    out: dict[str, float] = {}
    months = sorted(by_month)
    prev_close = None
    for m in months:
        rows = by_month[m]
        first = prev_close if prev_close is not None else rows[0]["close"]
        last = rows[-1]["close"]
        if first:
            out[m] = (last / first - 1.0) * 100.0
        prev_close = last
    return out


def breakout_month(monthly: dict[str, float], threshold: float = 15.0) -> str | None:
    """월 수익률이 처음으로 threshold% 를 넘긴 달 = 상승 개시 시점 추정."""
    for m in sorted(monthly):
        if monthly[m] >= threshold:
            return m
    return None


def integration(code: str) -> dict:
    """컨센서스(consensusInfo)·업종비교(industryCompareInfo) 등 통합 정보."""
    return _get_json(INTEGRATION.format(code=code))


def profile(code: str, start: str, end: str, bench: str = "KOSPI") -> dict:
    """한 종목의 구간 프로파일 (리포트 표에 그대로 들어가는 형태)."""
    px = daily_prices(code, start, end)
    bx = daily_prices(bench, start, end)
    mo = monthly_returns(px)
    return {
        "code": code,
        "first_date": px[0]["date"] if px else None,
        "last_date": px[-1]["date"] if px else None,
        "first_close": px[0]["close"] if px else None,
        "last_close": px[-1]["close"] if px else None,
        "return_pct": period_return(px),
        "bench_return_pct": period_return(bx),
        "relative_strength_pp": relative_strength(px, bx),
        "monthly_returns": {k: round(v, 1) for k, v in mo.items()},
        "breakout_month": breakout_month(mo),
    }


def main(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(description="네이버 주가 조회 + 수익률/상대강도")
    p.add_argument("codes", nargs="+", help="종목코드 (지수는 KOSPI/KOSDAQ)")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--bench", default="KOSPI")
    p.add_argument("--out", default=None)
    a = p.parse_args(argv)

    results = []
    for c in a.codes:
        try:
            results.append(profile(c, a.start, a.end, a.bench))
        except Exception as exc:
            results.append({"code": c, "error": f"{type(exc).__name__}: {exc}"[:200]})
    text = json.dumps(results, ensure_ascii=False, indent=2)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(a.out)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    raise SystemExit(main(sys.argv[1:]))
