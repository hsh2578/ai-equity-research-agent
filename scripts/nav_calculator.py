"""
NAV (순자산가치) 계산기 — 지주회사/리츠 밸류에이션용

상장 자회사 지분가치 + 비상장 자회사 추정가치 = NAV
현재 시총 대비 할인율 계산

사용법:
  from nav_calculator import calculate_nav
  result = calculate_nav(
      market_cap=89544,  # 현재 시총 (억원)
      listed_subs=[
          {"name": "LS일렉트릭", "market_cap": 90000, "stake_pct": 53.4},
      ],
      unlisted_subs=[
          {"name": "LS전선", "est_value": 50000, "method": "PER 12x 적용"},
      ],
      treasury_shares_value=5000,  # 자사주 가치 (억원)
      net_debt=0,  # 순차입금 (지주회사 별도)
  )
"""


def calculate_nav(
    market_cap: float,
    listed_subs: list = None,
    unlisted_subs: list = None,
    treasury_shares_value: float = 0,
    net_debt: float = 0,
    other_assets: float = 0,
    shares_million: float = 0,
    currency: str = "원",
) -> dict:
    """
    NAV 계산

    Args:
        market_cap: 현재 시가총액 (억원)
        listed_subs: [{"name", "market_cap", "stake_pct"}, ...]
        unlisted_subs: [{"name", "est_value", "method"}, ...]
        treasury_shares_value: 자사주 시장가치 (억원)
        net_debt: 별도 기준 순차입금 (억원, 음수=순현금)
        other_assets: 기타 자산 (부동산, 브랜드 등)
        shares_million: 발행주식수 (백만주, 0이면 주당NAV 미산출)
        currency: "원" 또는 "$"

    Returns:
        dict with NAV breakdown and discount rate
    """
    if listed_subs is None:
        listed_subs = []
    if unlisted_subs is None:
        unlisted_subs = []

    # 상장 자회사 지분 가치
    listed_total = 0
    listed_detail = []
    for sub in listed_subs:
        stake_value = sub["market_cap"] * sub["stake_pct"] / 100
        listed_total += stake_value
        listed_detail.append({
            "name": sub["name"],
            "market_cap": sub["market_cap"],
            "stake_pct": sub["stake_pct"],
            "stake_value": round(stake_value),
        })

    # 비상장 자회사 추정 가치
    unlisted_total = 0
    unlisted_detail = []
    for sub in unlisted_subs:
        unlisted_total += sub["est_value"]
        unlisted_detail.append({
            "name": sub["name"],
            "est_value": sub["est_value"],
            "method": sub.get("method", "추정"),
        })

    # NAV 계산
    gross_nav = listed_total + unlisted_total + treasury_shares_value + other_assets
    nav = gross_nav - net_debt

    # 할인율
    if nav > 0:
        discount_rate = (1 - market_cap / nav) * 100
    else:
        discount_rate = 0

    # 주당 NAV
    nav_per_share = 0
    if shares_million > 0:
        if currency == "원":
            nav_per_share = (nav * 100_000_000) / (shares_million * 1_000_000)
        else:
            nav_per_share = (nav * 1_000_000) / (shares_million * 1_000_000)

    return {
        "listed_subs": listed_detail,
        "listed_total": round(listed_total),
        "unlisted_subs": unlisted_detail,
        "unlisted_total": round(unlisted_total),
        "treasury_shares_value": treasury_shares_value,
        "other_assets": other_assets,
        "gross_nav": round(gross_nav),
        "net_debt": net_debt,
        "nav": round(nav),
        "market_cap": market_cap,
        "discount_rate": round(discount_rate, 1),
        "nav_per_share": round(nav_per_share),
    }


def format_nav_result(result: dict, currency: str = "원") -> str:
    """NAV 결과를 텍스트로 포맷"""
    c = currency
    lines = []
    lines.append("=== NAV 분석 ===")
    lines.append("")
    lines.append("상장 자회사 지분 가치:")
    for s in result["listed_subs"]:
        lines.append(f"  {s['name']}: 시총 {s['market_cap']:,}억 × {s['stake_pct']}% = {s['stake_value']:,}억")
    lines.append(f"  소계: {result['listed_total']:,}억")
    lines.append("")
    lines.append("비상장 자회사 추정 가치:")
    for s in result["unlisted_subs"]:
        lines.append(f"  {s['name']}: {s['est_value']:,}억 ({s['method']})")
    lines.append(f"  소계: {result['unlisted_total']:,}억")
    lines.append("")
    if result["treasury_shares_value"]:
        lines.append(f"자사주 가치: {result['treasury_shares_value']:,}억")
    if result["other_assets"]:
        lines.append(f"기타 자산: {result['other_assets']:,}억")
    lines.append(f"")
    lines.append(f"Gross NAV: {result['gross_nav']:,}억")
    lines.append(f"순차입금: {result['net_debt']:,}억")
    lines.append(f"★ NAV: {result['nav']:,}억")
    lines.append(f"")
    lines.append(f"현재 시총: {result['market_cap']:,}억")
    lines.append(f"★ 지주할인율: {result['discount_rate']:.1f}%")
    if result["nav_per_share"]:
        lines.append(f"★ 주당 NAV: {result['nav_per_share']:,}{c}")
    return "\n".join(lines)


if __name__ == "__main__":
    # 테스트: LS 기준
    result = calculate_nav(
        market_cap=89544,
        listed_subs=[
            {"name": "LS일렉트릭", "market_cap": 90000, "stake_pct": 53.4},
            {"name": "LS에코에너지", "market_cap": 12000, "stake_pct": 90.9},
        ],
        unlisted_subs=[
            {"name": "LS전선", "est_value": 50000, "method": "PER 10x (영업이익 2,800억 × 10배 × 지분율 반영)"},
            {"name": "LS아이앤디", "est_value": 15000, "method": "PER 8x 추정"},
            {"name": "LS네트웍스", "est_value": 5000, "method": "PBR 0.5x 추정"},
        ],
        treasury_shares_value=10000,
        net_debt=5000,
        shares_million=31.2,
        currency="원",
    )
    print(format_nav_result(result))
