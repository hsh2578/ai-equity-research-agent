"""
US 종목 재무 데이터 자동 정리 스크립트

SEC EDGAR XBRL + KIS 해외주식 API + yfinance(선택)를 통합하여
한국 financial_summary.py와 동일한 포맷의 financial_summary.json을 생성한다.

사용법:
    python scripts/financial_summary_us.py TSLA
    python scripts/financial_summary_us.py TSLA NAS   # 거래소 지정 (NAS/NYS/AMS)

출력:
    data/{TICKER}/financial_summary.json
"""

import json
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sec_edgar import get_cik, get_company_facts, extract_financials, extract_quarterly_financials
from kis_api import get_us_current_price, get_us_daily_price

# yfinance (optional - forward estimates)
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False
    print("[WARN] yfinance not installed. Forward estimates unavailable. pip install yfinance", file=sys.stderr)


def _safe_div(a, b, pct=False):
    """Safe division, returns None on failure."""
    try:
        if b is None or b == 0:
            return None
        result = a / b
        return round(result * 100, 2) if pct else round(result, 4)
    except (TypeError, ZeroDivisionError):
        return None


def _yoy(curr, prev):
    """YoY growth rate (%)."""
    return _safe_div(curr - prev, abs(prev), pct=True) if curr is not None and prev is not None else None


def _billions(val):
    """Convert raw USD to billions (B), rounded."""
    if val is None:
        return None
    return round(val / 1_000_000_000, 3)


def _millions(val):
    """Convert raw USD to millions (M), rounded."""
    if val is None:
        return None
    return round(val / 1_000_000, 1)


def build_yearly_data(sec_financials: dict) -> dict:
    """SEC EDGAR extract_financials() 결과를 연도별 dict로 재구성.

    Returns: { "2023": {"revenue": ..., "net_income": ..., ...}, ... }
    """
    # 모든 지표에서 존재하는 연도 수집
    all_years = set()
    for label, entries in sec_financials.items():
        for e in entries:
            year = e["period"][:4]
            all_years.add(year)

    # 필드명 매핑: SEC label -> internal key
    field_map = {
        "Revenue (매출)": "revenue",
        "COGS (매출원가)": "cogs",
        "Gross Profit (매출총이익)": "gross_profit",
        "Operating Income (영업이익)": "op_income",
        "SGA (판관비)": "sga",
        "R&D Expense (연구개발비)": "rnd",
        "Interest Expense (이자비용)": "interest_expense",
        "Income Tax (법인세)": "income_tax",
        "Pretax Income (세전이익)": "pretax_income",
        "Net Income (순이익)": "net_income",
        "EPS (주당순이익)": "eps",
        "DPS (주당배당금)": "dps",
        "Total Assets (총자산)": "total_assets",
        "Current Assets (유동자산)": "current_assets",
        "Cash (현금)": "cash",
        "Short-term Investments (단기투자)": "short_term_investments",
        "Receivables (매출채권)": "receivables",
        "Inventory (재고자산)": "inventory",
        "Non-current Assets (비유동자산)": "non_current_assets",
        "PP&E (유형자산)": "ppe",
        "Goodwill (영업권)": "goodwill",
        "Intangibles (무형자산)": "intangibles",
        "Total Liabilities (총부채)": "total_debt_all",
        "Current Liabilities (유동부채)": "current_liabilities",
        "Payables (매입채무)": "payables",
        "Short-term Debt (단기차입금)": "short_term_borrowings",
        "Non-current Liabilities (비유동부채)": "non_current_liabilities",
        "Long-term Debt (장기차입금)": "long_term_debt",
        "Total Debt (총차입금)": "total_borrowings",
        "Stockholders Equity (자기자본)": "total_equity",
        "Retained Earnings (이익잉여금)": "retained_earnings",
        "Shares Outstanding (발행주식수)": "shares_outstanding",
        "Operating Cash Flow (영업현금흐름)": "ocf",
        "D&A (감가상각비)": "depreciation",
        "CapEx (설비투자)": "capex",
        "Investing Cash Flow (투자현금흐름)": "invest_cf",
        "Financing Cash Flow (재무현금흐름)": "finance_cf",
        "Dividends Paid (배당금지급)": "dividends_paid",
        "Share Repurchase (자사주매입)": "share_repurchase",
        "Stock Comp (주식보상비)": "stock_comp",
    }

    yearly = {}
    for year in sorted(all_years):
        yearly[year] = {}

    for label, entries in sec_financials.items():
        key = field_map.get(label)
        if not key:
            continue
        for e in entries:
            year = e["period"][:4]
            if year in yearly:
                yearly[year][key] = e["value"]

    return yearly


def compute_ratios(yearly: dict) -> dict:
    """연도별 데이터에 파생 비율을 추가."""
    years = sorted(yearly.keys())

    for i, year in enumerate(years):
        d = yearly[year]
        rev = d.get("revenue")
        op = d.get("op_income")
        ni = d.get("net_income")
        ta = d.get("total_assets")
        tl = d.get("total_debt_all")
        eq = d.get("total_equity")
        ca = d.get("current_assets")
        cl = d.get("current_liabilities")
        ocf = d.get("ocf")
        capex = d.get("capex")
        cogs = d.get("cogs")
        gp = d.get("gross_profit")

        # Gross Profit (역산)
        if gp is None and rev is not None and cogs is not None:
            gp = rev - cogs
            d["gross_profit"] = gp

        # 수익성 비율
        d["gross_margin"] = _safe_div(gp, rev, pct=True)
        d["opm"] = _safe_div(op, rev, pct=True)
        d["npm"] = _safe_div(ni, rev, pct=True)
        d["roe"] = _safe_div(ni, eq, pct=True)
        d["roa"] = _safe_div(ni, ta, pct=True)

        # 안정성 비율
        d["debt_ratio"] = _safe_div(tl, eq, pct=True)
        d["current_ratio"] = _safe_div(ca, cl, pct=True)

        # FCF
        if ocf is not None and capex is not None:
            d["fcf"] = ocf - abs(capex)  # capex는 보통 음수로 보고됨
        elif ocf is not None and capex is None:
            d["fcf"] = None

        # EBITDA (Op Income + D&A)
        da = d.get("depreciation")
        if op is not None and da is not None:
            d["ebitda"] = op + abs(da)
        elif op is not None:
            d["ebitda"] = None

        # Net Debt
        cash = d.get("cash", 0) or 0
        st_inv = d.get("short_term_investments", 0) or 0
        ltd = d.get("long_term_debt", 0) or 0
        std = d.get("short_term_borrowings", 0) or 0
        d["net_debt"] = (ltd + std) - (cash + st_inv) if (ltd or std) else None

        # Effective Tax Rate
        pretax = d.get("pretax_income")
        tax = d.get("income_tax")
        d["effective_tax_rate"] = _safe_div(tax, pretax, pct=True)

        # YoY 성장률
        if i > 0:
            prev = yearly[years[i - 1]]
            d["revenue_yoy"] = _yoy(rev, prev.get("revenue"))
            d["op_income_yoy"] = _yoy(op, prev.get("op_income"))
            d["net_income_yoy"] = _yoy(ni, prev.get("net_income"))
            d["eps_yoy"] = _yoy(d.get("eps"), prev.get("eps"))

    return yearly


def _build_quarterly_data(quarterly_raw: dict) -> dict:
    """extract_quarterly_financials() 결과를 분기별 dict로 재구성.

    Returns: { "2024-Q3": {"revenue": ..., "op_income": ..., ...}, ... }
    """
    field_map = {
        "Revenue (매출)": "revenue",
        "COGS (매출원가)": "cogs",
        "Gross Profit (매출총이익)": "gross_profit",
        "Operating Income (영업이익)": "op_income",
        "Net Income (순이익)": "net_income",
        "EPS (주당순이익)": "eps",
        "Operating Cash Flow (영업현금흐름)": "ocf",
        "CapEx (설비투자)": "capex",
    }

    # 모든 분기 키 수집
    all_qkeys = set()
    for label, entries in quarterly_raw.items():
        for e in entries:
            qkey = f"{e['period'][:4]}-{e['fp']}"
            all_qkeys.add(qkey)

    quarterly = {qk: {} for qk in sorted(all_qkeys)}

    for label, entries in quarterly_raw.items():
        key = field_map.get(label)
        if not key:
            continue
        for e in entries:
            qkey = f"{e['period'][:4]}-{e['fp']}"
            if qkey in quarterly:
                quarterly[qkey][key] = e["value"]
                quarterly[qkey]["_period_end"] = e["period"]

    # SEC XBRL 10-Q는 YTD 누적으로 보고됨 (Q1=3개월, Q2=6개월 누적, Q3=9개월 누적)
    # 독립 분기 = 현재 누적 - 전 분기 누적으로 역산
    flow_fields = ["revenue", "cogs", "gross_profit", "op_income", "net_income", "ocf", "capex"]
    sorted_keys = sorted(quarterly.keys())  # "2023-Q2", "2023-Q3", "2024-Q1", ...

    standalone = {}
    for i, qk in enumerate(sorted_keys):
        d = quarterly[qk]
        year, qn = qk.split("-")
        sd = {"_period_end": d.get("_period_end")}

        if qn == "Q1":
            # Q1은 이미 독립 분기 (1~3월)
            for f in flow_fields:
                sd[f] = d.get(f)
            sd["eps"] = d.get("eps")
        else:
            # Q2 = H1 누적 - Q1, Q3 = 9M 누적 - H1 누적
            prev_qn = "Q1" if qn == "Q2" else "Q2"
            prev_key = f"{year}-{prev_qn}"
            prev_d = quarterly.get(prev_key, {})

            for f in flow_fields:
                curr = d.get(f)
                prev = prev_d.get(f)
                if curr is not None and prev is not None:
                    sd[f] = curr - prev
                elif curr is not None and qn == "Q2" and prev is None:
                    # Q1 데이터 없으면 누적값 그대로 (부정확하지만 null보다 나음)
                    sd[f] = None
                else:
                    sd[f] = None

            # EPS도 역산
            curr_eps = d.get("eps")
            prev_eps = prev_d.get("eps")
            if curr_eps is not None and prev_eps is not None:
                sd["eps"] = round(curr_eps - prev_eps, 2)
            else:
                sd["eps"] = None

        standalone[qk] = sd

    quarterly = standalone

    # OPM/NPM 계산
    for qk, d in quarterly.items():
        rev = d.get("revenue")
        d["opm"] = _safe_div(d.get("op_income"), rev, pct=True)
        d["npm"] = _safe_div(d.get("net_income"), rev, pct=True)
        d["gross_margin"] = _safe_div(d.get("gross_profit"), rev, pct=True)

    # 비어있는 분기 제거
    quarterly = {qk: d for qk, d in quarterly.items() if d.get("revenue") is not None}
    return quarterly


def get_yfinance_data(ticker: str) -> dict:
    """yfinance에서 forward estimates + analyst consensus 수집."""
    if not HAS_YFINANCE:
        return {}

    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}

        result = {
            "forward_pe": info.get("forwardPE"),
            "trailing_pe": info.get("trailingPE"),
            "peg_ratio": info.get("pegRatio"),
            "forward_eps": info.get("forwardEps"),
            "trailing_eps": info.get("trailingEps"),
            "target_mean": info.get("targetMeanPrice"),
            "target_high": info.get("targetHighPrice"),
            "target_low": info.get("targetLowPrice"),
            "analyst_count": info.get("numberOfAnalystOpinions"),
            "recommendation": info.get("recommendationKey"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "ev_revenue": info.get("enterpriseToRevenue"),
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
            "return_on_equity": info.get("returnOnEquity"),
            "beta": info.get("beta"),
            "dividend_yield": info.get("dividendYield"),
            "payout_ratio": info.get("payoutRatio"),
            "short_ratio": info.get("shortRatio"),
            "short_pct_float": info.get("shortPercentOfFloat"),
            "held_pct_insiders": info.get("heldPercentInsiders"),
            "held_pct_institutions": info.get("heldPercentInstitutions"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            # KIS fallback 보완용 (KIS 해외 API가 0 반환 시)
            "high_52w": info.get("fiftyTwoWeekHigh"),
            "low_52w": info.get("fiftyTwoWeekLow"),
            "pbr": info.get("priceToBook"),
            "bps": info.get("bookValue"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        }

        # None 값 제거
        result = {k: v for k, v in result.items() if v is not None}
        if result:
            print(f"  [OK] yfinance: {len(result)}개 필드 수집")
        return result

    except Exception as e:
        print(f"  [WARN] yfinance 조회 실패: {e}", file=sys.stderr)
        return {}


def build_summary(ticker: str, excd: str = "NAS") -> dict:
    """US 종목 재무 요약 생성 (메인 함수)."""

    print(f"\n{'='*60}")
    print(f"  US Financial Summary: {ticker}")
    print(f"{'='*60}\n")

    # --------------------------------------------------
    # 1. SEC EDGAR
    # --------------------------------------------------
    print("[1/4] SEC EDGAR XBRL 재무 데이터 수집...")
    cik = get_cik(ticker)
    facts = get_company_facts(cik)
    company_name = facts.get("entityName", ticker)
    sec_financials = extract_financials(facts)
    print(f"  [OK] {company_name} - {len(sec_financials)}개 지표 추출")

    yearly = build_yearly_data(sec_financials)
    # 의미 있는 연도만 유지 (revenue 또는 net_income 존재)
    yearly = {y: d for y, d in yearly.items()
              if d.get("revenue") is not None or d.get("net_income") is not None}
    yearly = compute_ratios(yearly)
    years = sorted(yearly.keys())
    print(f"  [OK] {len(years)}개년 데이터: {', '.join(years)}")

    # 분기 데이터 추출
    print("  분기(10-Q) 데이터 추출...")
    quarterly_raw = extract_quarterly_financials(facts, num_quarters=8)
    quarterly = _build_quarterly_data(quarterly_raw)
    print(f"  [OK] {len(quarterly)}개 분기 데이터")

    # --------------------------------------------------
    # 2. KIS 해외주식 시세
    # --------------------------------------------------
    print("\n[2/4] KIS 해외주식 시세 조회...")
    kis_price = {}
    daily_prices = []
    try:
        kis_price = get_us_current_price(ticker, excd)
        if "error" in kis_price:
            print(f"  [WARN] KIS 조회 실패: {kis_price['error']}", file=sys.stderr)
            kis_price = {}
        else:
            print(f"  [OK] 현재가: ${kis_price.get('현재가', 'N/A')}, PER: {kis_price.get('PER', 'N/A')}")
    except Exception as e:
        print(f"  [WARN] KIS 현재가 조회 실패 (API 키 미설정?): {e}", file=sys.stderr)

    try:
        print("  KIS 일봉 120일 조회...")
        daily_prices = get_us_daily_price(ticker, excd, 120)
        print(f"  [OK] {len(daily_prices)}일 일봉 수집")
    except Exception as e:
        print(f"  [WARN] KIS 일봉 조회 실패: {e}", file=sys.stderr)

    # --------------------------------------------------
    # 3. yfinance (optional)
    # --------------------------------------------------
    print("\n[3/4] yfinance forward estimates...")
    yf_data = get_yfinance_data(ticker)

    # --------------------------------------------------
    # 4. 통합 + 파생 지표 계산
    # --------------------------------------------------
    print("\n[4/4] 통합 요약 생성...")

    # KIS 시세 정리 (0이면 yfinance로 보완)
    cur_price = kis_price.get("현재가", 0) or yf_data.get("current_price", 0)
    per = kis_price.get("PER", 0) or yf_data.get("trailing_pe", 0)
    pbr = kis_price.get("PBR", 0) or yf_data.get("pbr", 0)
    eps_kis = kis_price.get("EPS", 0) or yf_data.get("trailing_eps", 0)
    bps_kis = kis_price.get("BPS", 0) or yf_data.get("bps", 0)
    hi_52 = kis_price.get("52주최고", 0) or yf_data.get("high_52w", 0)
    lo_52 = kis_price.get("52주최저", 0) or yf_data.get("low_52w", 0)
    mktcap_raw = kis_price.get("시가총액", "")

    # 시가총액 파싱 (KIS는 문자열로 반환할 수 있음)
    market_cap_usd = None
    if yf_data.get("market_cap"):
        market_cap_usd = yf_data["market_cap"]
    elif mktcap_raw:
        try:
            market_cap_usd = float(str(mktcap_raw).replace(",", ""))
        except (ValueError, TypeError):
            pass

    # 억원 환산 (참고용, 환율 1,380원 가정)
    krw_rate = 1380
    market_cap_억 = round(market_cap_usd / 100_000_000 * krw_rate) if market_cap_usd else None
    market_cap_B = round(market_cap_usd / 1_000_000_000, 1) if market_cap_usd else None

    # EPS 교차검증
    latest_year = years[-1] if years else None
    eps_sec = yearly[latest_year].get("eps") if latest_year else None
    eps_diff = None
    if eps_kis and eps_sec:
        eps_diff = round(abs(eps_kis - eps_sec) / max(abs(eps_kis), 0.01) * 100, 1)

    # Forward PER (yfinance 우선, 없으면 KIS)
    forward_pe = yf_data.get("forward_pe") or (per if per else None)
    forward_eps = yf_data.get("forward_eps")

    # 배당수익률
    div_yield = yf_data.get("dividend_yield")
    if div_yield and div_yield < 1:  # yfinance는 0.02 형태
        div_yield = round(div_yield * 100, 2)

    # alerts -- 이상치 경고 (v2: 강화)
    alerts = []
    if cur_price == 0:
        alerts.append("[ERROR] 현재가 0 - KIS/yfinance 조회 모두 실패")
    if eps_diff and eps_diff > 20:
        alerts.append(f"[WARN] EPS 차이 {eps_diff}% (KIS: {eps_kis}, SEC: {eps_sec})")
    if latest_year and yearly[latest_year].get("debt_ratio") and yearly[latest_year]["debt_ratio"] > 300:
        alerts.append(f"[WARN] 부채비율 {yearly[latest_year]['debt_ratio']}% - 재무 안정성 점검 필요")

    # 연도별 이상치 스캔
    for y in years:
        d = yearly[y]
        # 실효세율 비정상 (이연법인세 등)
        etr = d.get("effective_tax_rate")
        if etr is not None and (etr < -10 or etr > 50):
            alerts.append(f"[WARN] {y} 실효세율 {etr}% 비정상 - 이연법인세/일회성 항목 확인 필요")
        # NPM > OPM 역전 (영업외이익 과다)
        opm = d.get("opm")
        npm = d.get("npm")
        if opm is not None and npm is not None and npm > opm + 5:
            alerts.append(f"[WARN] {y} NPM({npm}%) > OPM({opm}%) - 영업외이익 과다, 일회성 여부 확인")
        # OPM 급변 (전년 대비 10%p+)
        idx = years.index(y)
        if idx > 0:
            prev_opm = yearly[years[idx - 1]].get("opm")
            if opm is not None and prev_opm is not None and abs(opm - prev_opm) > 10:
                alerts.append(f"[WARN] {y} OPM 급변 {prev_opm}% -> {opm}% ({opm - prev_opm:+.1f}%p)")
        # 매출 30%+ 급변
        rev_yoy = d.get("revenue_yoy")
        if rev_yoy is not None and abs(rev_yoy) > 30:
            alerts.append(f"[INFO] {y} 매출 YoY {rev_yoy:+.1f}% - 사업 구조 변화 확인")
        # ROE 마이너스
        roe = d.get("roe")
        if roe is not None and roe < 0:
            alerts.append(f"[WARN] {y} ROE {roe}% 음수 - 적자 또는 자본잠식 확인")

    # 최근 연도 주요 지표 요약 출력
    if latest_year:
        ld = yearly[latest_year]
        print(f"\n  --- {latest_year} 주요 지표 ---")
        print(f"  Revenue: ${_billions(ld.get('revenue')):.1f}B" if ld.get('revenue') else "  Revenue: N/A")
        print(f"  Op Income: ${_billions(ld.get('op_income')):.1f}B" if ld.get('op_income') else "  Op Income: N/A")
        print(f"  Net Income: ${_billions(ld.get('net_income')):.1f}B" if ld.get('net_income') else "  Net Income: N/A")
        print(f"  OPM: {ld.get('opm')}%  NPM: {ld.get('npm')}%  ROE: {ld.get('roe')}%")
        print(f"  EPS: ${ld.get('eps', 'N/A')}  FCF: ${_billions(ld.get('fcf')):.1f}B" if ld.get('fcf') else "")

    # --------------------------------------------------
    # 결과 조립
    # --------------------------------------------------
    summary = {
        "_description": f"US Financial Summary - SEC EDGAR + KIS + yfinance (v1)",
        "_sources": {
            "financials": "SEC EDGAR XBRL (us-gaap, 5yr annual)",
            "price": f"KIS OpenAPI (해외주식, excd={excd})",
            "forward": "yfinance" if yf_data else "N/A",
        },
        "meta": {
            "stock_name": company_name,
            "stock_code": ticker.upper(),
            "country": "US",
            "exchange": excd,
            "sector": yf_data.get("sector", ""),
            "industry": yf_data.get("industry", ""),
            "years_available": years,
        },
        "kis": {
            "current_price": cur_price,
            "market_cap_B": market_cap_B,
            "market_cap_억": market_cap_억,
            "per": per,
            "pbr": pbr,
            "eps": eps_kis,
            "bps": bps_kis,
            "high_52w": hi_52,
            "low_52w": lo_52,
            "dividend_yield": div_yield,
            "per_12m_forward": forward_pe,
            "forward_eps": forward_eps,
            "eps_validation": {
                "kis_eps": eps_kis,
                "sec_eps": eps_sec,
                "diff_pct": eps_diff,
                "ok": (eps_diff or 0) < 20,
            },
        },
        "financials": {},
        "quarterly": quarterly if quarterly else None,
        "forward": {},
        "yfinance": yf_data if yf_data else None,
        "alerts": alerts,
    }

    # 연도별 재무 데이터 (단위: raw USD, 사용 시 변환)
    for year in years:
        d = yearly[year]
        summary["financials"][year] = {
            # 손익 (USD)
            "revenue": d.get("revenue"),
            "cogs": d.get("cogs"),
            "gross_profit": d.get("gross_profit"),
            "op_income": d.get("op_income"),
            "sga": d.get("sga"),
            "rnd": d.get("rnd"),
            "interest_expense": d.get("interest_expense"),
            "pretax_income": d.get("pretax_income"),
            "income_tax": d.get("income_tax"),
            "net_income": d.get("net_income"),
            "ebitda": d.get("ebitda"),
            "eps": d.get("eps"),
            "dps": d.get("dps"),
            # 재무상태 (USD)
            "total_assets": d.get("total_assets"),
            "current_assets": d.get("current_assets"),
            "cash": d.get("cash"),
            "short_term_investments": d.get("short_term_investments"),
            "receivables": d.get("receivables"),
            "inventory": d.get("inventory"),
            "non_current_assets": d.get("non_current_assets"),
            "ppe": d.get("ppe"),
            "goodwill": d.get("goodwill"),
            "intangibles": d.get("intangibles"),
            "total_liabilities": d.get("total_debt_all"),
            "current_liabilities": d.get("current_liabilities"),
            "payables": d.get("payables"),
            "short_term_borrowings": d.get("short_term_borrowings"),
            "non_current_liabilities": d.get("non_current_liabilities"),
            "long_term_debt": d.get("long_term_debt"),
            "total_equity": d.get("total_equity"),
            "retained_earnings": d.get("retained_earnings"),
            "shares_outstanding": d.get("shares_outstanding"),
            "net_debt": d.get("net_debt"),
            # 현금흐름 (USD)
            "ocf": d.get("ocf"),
            "capex": d.get("capex"),
            "fcf": d.get("fcf"),
            "invest_cf": d.get("invest_cf"),
            "finance_cf": d.get("finance_cf"),
            "depreciation": d.get("depreciation"),
            "dividends_paid": d.get("dividends_paid"),
            "share_repurchase": d.get("share_repurchase"),
            "stock_comp": d.get("stock_comp"),
            # 비율 (%)
            "gross_margin": d.get("gross_margin"),
            "opm": d.get("opm"),
            "npm": d.get("npm"),
            "roe": d.get("roe"),
            "roa": d.get("roa"),
            "debt_ratio": d.get("debt_ratio"),
            "current_ratio": d.get("current_ratio"),
            "effective_tax_rate": d.get("effective_tax_rate"),
            # 성장률 (%)
            "revenue_yoy": d.get("revenue_yoy"),
            "op_income_yoy": d.get("op_income_yoy"),
            "net_income_yoy": d.get("net_income_yoy"),
            "eps_yoy": d.get("eps_yoy"),
        }

    # Forward estimates (yfinance)
    if yf_data:
        summary["forward"] = {
            "forward_pe": yf_data.get("forward_pe"),
            "forward_eps": yf_data.get("forward_eps"),
            "peg_ratio": yf_data.get("peg_ratio"),
            "ev_ebitda": yf_data.get("ev_ebitda"),
            "ev_revenue": yf_data.get("ev_revenue"),
            "target_mean": yf_data.get("target_mean"),
            "target_high": yf_data.get("target_high"),
            "target_low": yf_data.get("target_low"),
            "analyst_count": yf_data.get("analyst_count"),
            "recommendation": yf_data.get("recommendation"),
            "beta": yf_data.get("beta"),
            "short_ratio": yf_data.get("short_ratio"),
            "insider_pct": yf_data.get("held_pct_insiders"),
            "institution_pct": yf_data.get("held_pct_institutions"),
        }

    return summary


def main():
    if len(sys.argv) < 2:
        print("Usage: python financial_summary_us.py TICKER [EXCD]")
        print("  EXCD: NAS (default), NYS, AMS")
        sys.exit(1)

    ticker = sys.argv[1].upper()
    excd = sys.argv[2].upper() if len(sys.argv) > 2 else "NAS"

    # 자동 거래소 추정
    NYSE_TICKERS = {"GM", "F", "BA", "GE", "JPM", "BAC", "WMT", "JNJ", "PG",
                    "V", "MA", "UNH", "HD", "DIS", "KO", "PEP", "MCD", "NKE", "CVX",
                    "XOM", "T", "VZ", "IBM", "CAT", "MMM", "GS", "MS", "C", "WFC",
                    "BRK-B", "LMT", "RTX", "NOC", "GD", "DAL", "UAL", "AAL", "LUV",
                    "DE", "HON", "UPS", "FDX", "TGT", "LOW", "CL", "ABT", "TMO",
                    "DHR", "BMY", "MRK", "PFE", "LLY", "ABBV"}
    if excd == "NAS" and ticker in NYSE_TICKERS:
        excd = "NYS"
        print(f"[INFO] {ticker} -> NYSE 자동 감지 (excd=NYS)")

    # 출력 디렉토리
    out_dir = os.path.join("data", ticker)
    os.makedirs(out_dir, exist_ok=True)

    summary = build_summary(ticker, excd)

    out_path = os.path.join(out_dir, "financial_summary.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n[OK] 저장 완료: {out_path}")
    print(f"  - {len(summary.get('financials', {}))}개년 재무 데이터")
    print(f"  - Forward estimates: {'있음' if summary.get('forward') else '없음'}")
    if summary.get("alerts"):
        print(f"\n  === Alerts ===")
        for a in summary["alerts"]:
            print(f"  {a}")

    print(f"\n{'='*60}")
    print(f"  완료!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
