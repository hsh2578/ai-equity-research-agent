"""
간이 DCF (현금흐름 할인) 계산기

FCF 기반으로 적정주가를 3가지 시나리오(Bear/Base/Bull)로 산출합니다.

사용법:
  from dcf_calculator import calculate_dcf
  result = calculate_dcf(
      fcf_current=5000,        # 현재 FCF (억원)
      growth_rates=[0.15, 0.12, 0.10, 0.08, 0.05],  # 5년 성장률
      terminal_growth=0.02,    # 영구 성장률
      wacc=0.09,               # 할인율
      shares_million=100,      # 발행주식수 (백만주)
      net_debt=10000,          # 순차입금 (억원)
  )
"""

def calculate_dcf(
    fcf_current: float,
    growth_rates: list = None,
    terminal_growth: float = 0.02,
    wacc: float = 0.09,
    shares_million: float = 100,
    net_debt: float = 0,
    currency: str = "원",
) -> dict:
    """
    FCF 기반 DCF 밸류에이션

    Args:
        fcf_current: 현재 연간 FCF (억원 또는 $M)
        growth_rates: 향후 5년 FCF 성장률 리스트 [0.15, 0.12, ...]
        terminal_growth: 영구 성장률 (기본 2%)
        wacc: 가중평균자본비용 (기본 9%)
        shares_million: 발행주식수 (백만주)
        net_debt: 순차입금 (억원, 부채-현금. 음수면 순현금)
        currency: "원" 또는 "$"

    Returns:
        dict: {
            "projected_fcf": [...],
            "terminal_value": float,
            "enterprise_value": float,
            "equity_value": float,
            "fair_value_per_share": float,
            "sensitivity": {...}
        }
    """
    if growth_rates is None:
        growth_rates = [0.10, 0.08, 0.06, 0.05, 0.03]

    # 1. 5년간 FCF 추정
    projected_fcf = []
    fcf = fcf_current
    for i, g in enumerate(growth_rates):
        fcf = fcf * (1 + g)
        projected_fcf.append({
            "year": i + 1,
            "growth": g,
            "fcf": round(fcf, 1),
            "pv": round(fcf / ((1 + wacc) ** (i + 1)), 1),
        })

    # 2. 터미널 밸류
    terminal_fcf = projected_fcf[-1]["fcf"] * (1 + terminal_growth)
    terminal_value = terminal_fcf / (wacc - terminal_growth)
    terminal_pv = terminal_value / ((1 + wacc) ** len(growth_rates))

    # 3. 기업가치 (EV)
    sum_pv_fcf = sum(f["pv"] for f in projected_fcf)
    enterprise_value = sum_pv_fcf + terminal_pv

    # 4. 주주가치
    equity_value = enterprise_value - net_debt

    # 5. 주당 적정가
    if shares_million > 0:
        if currency == "원":
            # 억원 → 원 변환: 억원 * 1억 / (백만주 * 100만)
            fair_value = (equity_value * 100_000_000) / (shares_million * 1_000_000)
        else:
            # $M 기준
            fair_value = (equity_value * 1_000_000) / (shares_million * 1_000_000)
    else:
        fair_value = 0

    # 6. 민감도 분석 (WACC ± 1%p, 영구성장률 ± 0.5%p)
    sensitivity = {}
    for wacc_adj in [-0.01, 0, 0.01]:
        for tg_adj in [-0.005, 0, 0.005]:
            w = wacc + wacc_adj
            tg = terminal_growth + tg_adj
            if w <= tg:
                continue
            tv = terminal_fcf / (w - tg)
            tv_pv = tv / ((1 + w) ** len(growth_rates))
            sp = sum(f["fcf"] / ((1 + w) ** f["year"]) for f in projected_fcf)
            ev = sp + tv_pv
            eq = ev - net_debt
            if shares_million > 0:
                if currency == "원":
                    fv = (eq * 100_000_000) / (shares_million * 1_000_000)
                else:
                    fv = (eq * 1_000_000) / (shares_million * 1_000_000)
            else:
                fv = 0
            sensitivity[f"WACC {w*100:.0f}% / TG {tg*100:.1f}%"] = round(fv)

    return {
        "projected_fcf": projected_fcf,
        "terminal_value": round(terminal_value, 1),
        "terminal_pv": round(terminal_pv, 1),
        "sum_pv_fcf": round(sum_pv_fcf, 1),
        "enterprise_value": round(enterprise_value, 1),
        "net_debt": net_debt,
        "equity_value": round(equity_value, 1),
        "shares_million": shares_million,
        "fair_value_per_share": round(fair_value),
        "wacc": wacc,
        "terminal_growth": terminal_growth,
        "sensitivity": sensitivity,
    }


def format_dcf_result(result: dict, currency: str = "원") -> str:
    """DCF 결과를 읽기 쉬운 텍스트로 포맷"""
    c = currency
    lines = []
    lines.append("=== DCF 밸류에이션 ===")
    lines.append(f"WACC: {result['wacc']*100:.1f}%, 영구성장률: {result['terminal_growth']*100:.1f}%")
    lines.append(f"")
    lines.append(f"5년 FCF 추정:")
    for f in result["projected_fcf"]:
        lines.append(f"  Year {f['year']}: FCF {f['fcf']:,.0f}억 (성장 {f['growth']*100:.0f}%), PV {f['pv']:,.0f}억")
    lines.append(f"")
    lines.append(f"FCF 현재가치 합: {result['sum_pv_fcf']:,.0f}억")
    lines.append(f"터미널 밸류 현재가치: {result['terminal_pv']:,.0f}억")
    lines.append(f"기업가치 (EV): {result['enterprise_value']:,.0f}억")
    lines.append(f"순차입금: {result['net_debt']:,.0f}억")
    lines.append(f"주주가치: {result['equity_value']:,.0f}억")
    lines.append(f"발행주식: {result['shares_million']:.0f}백만주")
    lines.append(f"")
    lines.append(f"★ 적정주가: {result['fair_value_per_share']:,}{c}")
    lines.append(f"")
    lines.append(f"민감도 분석:")
    for k, v in result["sensitivity"].items():
        lines.append(f"  {k}: {v:,}{c}")
    return "\n".join(lines)


if __name__ == "__main__":
    # 테스트: LS 기준
    result = calculate_dcf(
        fcf_current=4800,  # 2025 FCF 약 4,800억
        growth_rates=[0.15, 0.12, 0.10, 0.08, 0.05],
        terminal_growth=0.02,
        wacc=0.09,
        shares_million=31.2,  # 약 3,120만주
        net_debt=15000,  # 순차입금 약 1.5조
        currency="원",
    )
    print(format_dcf_result(result))
