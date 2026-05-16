"""
재무 데이터 자동 정리 스크립트 (KIS 기반, v2)

KIS API 7개 재무 엔드포인트 + FnGuide 헤더 + KIS 시세를 병합하여
analysis.json에 바로 쓸 수 있는 요약 파일을 생성한다.

**이전 DART 파싱 방식(v1)을 완전히 대체.**
DART는 이제 사업보고서 본문(사업의 내용/위험요인) 전용으로만 사용.

사용법:
    python scripts/financial_summary.py {종목명} {종목코드}
    또는
    python scripts/financial_summary.py data/{종목명}  # 기존 방식 호환

출력:
    data/{종목명}/financial_summary.json
    - 최대 6년 연간 재무 (매출/영업이익/순이익/EBITDA/EPS/BPS/ROE/부채비율 등)
    - KIS 직접 제공 지표 (파싱 실수 제로)
    - FnGuide Forward PER / 업종 PER (선택적)
    - 이상치 경고
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kis_api import (
    get_current_price, get_investor_trend, get_daily_price,
    get_all_financials,
)
try:
    from fnguide_header import get_fnguide_header, get_fnguide_cashflow
except Exception:
    def get_fnguide_header(code):  # fallback
        return {}
    def get_fnguide_cashflow(code):
        return {}

try:
    from naver_finance import (
        get_all_naver_data,
        get_balance_detail,
        get_cashflow_detail,
        get_financial_ratios,
    )
except Exception:
    def get_all_naver_data(code):
        return {}
    def get_balance_detail(code):
        return {}
    def get_cashflow_detail(code):
        return {}
    def get_financial_ratios(code):
        return {}

# 재무 데이터 보유 연수 상한 (최근 N년만)
MAX_YEARS = 5


def to_float(v, default=None):
    """문자열/None/숫자를 float로. '99.99'는 KIS 비공개 마스킹이므로 None 처리."""
    if v is None:
        return default
    try:
        f = float(str(v).replace(",", "").strip())
        if f == 99.99:  # KIS 마스킹 값
            return default
        return f
    except (ValueError, TypeError):
        return default


def yoy(curr, prev):
    """YoY 변화율 %. None 안전."""
    if curr is None or prev is None or prev == 0:
        return None
    return round((curr - prev) / abs(prev) * 100, 1)


def eok(val):
    """KIS는 이미 '억' 단위로 반환. 그대로 반올림."""
    if val is None:
        return None
    return round(val)


def get_year(row) -> str:
    """stac_yymm '202512' → '2025'."""
    ym = str(row.get("stac_yymm", ""))
    return ym[:4] if len(ym) >= 4 else ""


def build_summary(stock_name: str, stock_code: str, data_dir: str) -> dict:
    """KIS 재무 + 시세 + FnGuide 헤더를 병합하여 요약 dict 생성."""
    os.makedirs(data_dir, exist_ok=True)

    # 1. KIS 시세/수급/일봉
    print(f"[1/4] KIS 시세 수집...")
    price = get_current_price(stock_code)
    investor = get_investor_trend(stock_code, 20)
    daily = get_daily_price(stock_code, 120)

    kis_price_path = os.path.join(data_dir, "data_kis.json")
    with open(kis_price_path, "w", encoding="utf-8") as f:
        json.dump({
            "current_price": price,
            "investor_trend": investor,
            "daily_prices": daily,
        }, f, ensure_ascii=False, indent=2)

    # 2. KIS 재무 7개 엔드포인트
    print(f"[2/4] KIS 재무 7개 엔드포인트 수집...")
    fin_raw = get_all_financials(stock_code, period="0")  # 연간
    kis_fin_path = os.path.join(data_dir, "data_kis_financials.json")
    with open(kis_fin_path, "w", encoding="utf-8") as f:
        json.dump(fin_raw, f, ensure_ascii=False, indent=2)

    # 3. FnGuide 헤더 (Forward PER) + 현금흐름표
    print(f"[3/4] FnGuide 헤더 + 현금흐름 수집...")
    fng = get_fnguide_header(stock_code)
    if fng:
        print(f"  [OK] Forward PER: {fng.get('per_12m')}, 업종 PER: {fng.get('sector_per')}")
    else:
        print(f"  [!] FnGuide 헤더 실패 (차단 또는 페이지 구조 변경)")

    fng_cf = get_fnguide_cashflow(stock_code)
    if fng_cf and fng_cf.get("ocf"):
        print(f"  [OK] 현금흐름 {len(fng_cf['ocf'])}년치 (OCF/투자CF/재무CF)")
    else:
        print(f"  [!] 현금흐름 추출 실패 (리포트 s08에서 수동 보완 필요)")

    # 네이버 증권(Wisereport) - 컨센서스 + 주주 + 신용등급 + Forward
    print(f"  네이버 증권 컨센서스 수집...")
    naver = get_all_naver_data(stock_code)
    if naver and naver.get("consensus", {}).get("brokers"):
        brokers_n = len(naver["consensus"]["brokers"])
        avg = naver["consensus"]["summary"].get("avg_target_price")
        print(f"  [OK] 증권사 {brokers_n}개 목표가 (평균 {avg:,}원)" if avg else f"  [OK] 증권사 {brokers_n}개")
    else:
        print(f"  [!] 네이버 증권 수집 실패")

    # Wisereport AJAX - 재무상태표 + 현금흐름표 + 비율 5종
    print(f"  Wisereport 재무상태표/현금흐름/비율 수집...")
    wise_balance = get_balance_detail(stock_code)
    wise_cashflow = get_cashflow_detail(stock_code)
    wise_ratios = get_financial_ratios(stock_code)
    if wise_balance:
        print(f"  [OK] 재무상태표 {len(wise_balance)}년치 (매출채권/재고/CAPEX 포함)")
    if wise_cashflow:
        print(f"  [OK] 현금흐름표 {len(wise_cashflow)}년치 (감가상각/배당/자사주 포함)")
    if wise_ratios:
        print(f"  [OK] 재무비율 5종 (수익성/성장/안정/활동/가치)")

    # 4. 데이터 병합 및 정리
    print(f"[4/4] 통합 요약 생성...")

    # 4-1. KIS 시세 정리
    kis_summary = {
        "current_price": price.get("현재가"),
        "market_cap_억": price.get("시가총액"),
        "market_cap_조": round(price.get("시가총액", 0) / 10000, 2) if price.get("시가총액") else None,
        "per": price.get("PER"),
        "pbr": price.get("PBR"),
        "eps": price.get("EPS"),
        "bps": price.get("BPS"),
        "high_52w": price.get("52주최고"),
        "low_52w": price.get("52주최저"),
        "dividend_yield": price.get("배당수익률") or fng.get("dividend_yield"),
        # FnGuide 보조
        "per_12m_forward": fng.get("per_12m"),
        "sector_per": fng.get("sector_per"),
    }

    # 4-2. 연도별 병합: 손익 + 대차 + 재무비율 + 수익성/안정성/성장성/기타
    years_data = {}

    # 손익계산서
    for row in fin_raw.get("income", []):
        y = get_year(row)
        if not y:
            continue
        years_data.setdefault(y, {})
        d = years_data[y]
        d["revenue"] = eok(to_float(row.get("sale_account")))
        d["cogs"] = eok(to_float(row.get("sale_cost")))
        d["gross_profit"] = eok(to_float(row.get("sale_totl_prfi")))
        d["op_income"] = eok(to_float(row.get("bsop_prti")))
        d["ordinary_income"] = eok(to_float(row.get("op_prfi")))
        d["net_income"] = eok(to_float(row.get("thtr_ntin")))
        # 마진 계산
        if d.get("revenue") and d["revenue"] > 0:
            if d.get("cogs") is not None:
                d["cogs_ratio"] = round(d["cogs"] / d["revenue"] * 100, 1)
            if d.get("op_income") is not None:
                d["opm"] = round(d["op_income"] / d["revenue"] * 100, 1)
            if d.get("net_income") is not None:
                d["npm"] = round(d["net_income"] / d["revenue"] * 100, 1)

    # 대차대조표
    for row in fin_raw.get("balance", []):
        y = get_year(row)
        if y not in years_data:
            continue
        d = years_data[y]
        d["current_assets"] = eok(to_float(row.get("cras")))
        d["non_current_assets"] = eok(to_float(row.get("fxas")))
        d["total_assets"] = eok(to_float(row.get("total_aset")))
        d["current_liabilities"] = eok(to_float(row.get("flow_lblt")))
        d["non_current_liabilities"] = eok(to_float(row.get("fix_lblt")))
        d["total_debt"] = eok(to_float(row.get("total_lblt")))
        d["capital_stock"] = eok(to_float(row.get("cpfn")))  # 자본금
        d["capital_surplus"] = eok(to_float(row.get("cfp_surp")))
        d["retained_earnings"] = eok(to_float(row.get("prfi_surp")))
        d["total_equity"] = eok(to_float(row.get("total_cptl")))  # 자본총계

    # 재무비율 (EPS/BPS/ROE/부채비율/성장률 직접 제공)
    for row in fin_raw.get("ratio", []):
        y = get_year(row)
        if y not in years_data:
            continue
        d = years_data[y]
        d["eps"] = to_float(row.get("eps"))
        d["bps"] = to_float(row.get("bps"))
        d["sps"] = to_float(row.get("sps"))
        d["roe"] = to_float(row.get("roe_val"))
        d["reserve_ratio"] = to_float(row.get("rsrv_rate"))
        d["debt_ratio_from_ratio"] = to_float(row.get("lblt_rate"))
        d["revenue_yoy_kis"] = to_float(row.get("grs"))
        d["op_income_yoy_kis"] = to_float(row.get("bsop_prfi_inrt"))
        d["net_income_yoy_kis"] = to_float(row.get("ntin_inrt"))

    # 수익성비율
    for row in fin_raw.get("profit", []):
        y = get_year(row)
        if y not in years_data:
            continue
        d = years_data[y]
        d["roa"] = to_float(row.get("cptl_ntin_rate"))
        d["roe_profit"] = to_float(row.get("self_cptl_ntin_inrt"))
        d["npm_ratio"] = to_float(row.get("sale_ntin_rate"))
        d["gross_margin"] = to_float(row.get("sale_totl_rate"))

    # 안정성비율
    for row in fin_raw.get("stability", []):
        y = get_year(row)
        if y not in years_data:
            continue
        d = years_data[y]
        d["debt_ratio"] = to_float(row.get("lblt_rate"))  # 핵심
        d["borrowing_dependency"] = to_float(row.get("bram_depn"))
        d["current_ratio"] = to_float(row.get("crnt_rate"))
        d["quick_ratio"] = to_float(row.get("quck_rate"))

    # 성장성비율
    for row in fin_raw.get("growth", []):
        y = get_year(row)
        if y not in years_data:
            continue
        d = years_data[y]
        d["equity_growth"] = to_float(row.get("equt_inrt"))
        d["asset_growth"] = to_float(row.get("totl_aset_inrt"))

    # 기타주요비율 (EBITDA / EV-EBITDA / 배당성향)
    for row in fin_raw.get("other", []):
        y = get_year(row)
        if y not in years_data:
            continue
        d = years_data[y]
        d["payout_ratio"] = to_float(row.get("payout_rate"))
        d["eva"] = eok(to_float(row.get("eva")))
        d["ebitda"] = eok(to_float(row.get("ebitda")))
        d["ev_ebitda"] = to_float(row.get("ev_ebitda"))

    # ============================================
    # Wisereport 데이터 병합 (메인 소스 for BS + CF)
    # ============================================
    #
    # 우선순위: Wisereport > KIS BS 요약 > FnGuide CF
    # (Wisereport가 더 상세한 5년+2026E 데이터를 제공)

    # 1. 재무상태표 상세 (매출채권, 재고, 매입채무, 유형자산, CAPEX 등)
    BS_FIELDS = {
        "자산총계": "total_assets_w",
        "유동자산": "current_assets_w",
        "비유동자산": "non_current_assets_w",
        "재고자산": "inventory",
        "매출채권": "receivables",
        "유형자산": "tangible_assets",
        "무형자산": "intangible_assets",
        "부채총계": "total_debt_w",
        "유동부채": "current_liabilities_w",
        "비유동부채": "non_current_liabilities_w",
        "매입채무": "payables",
        "단기차입금": "short_term_borrowings",
        "장기차입금": "long_term_borrowings",
        "자본총계": "total_equity_w",
        "CAPEX": "capex",  # 재무상태표의 계산항목 (유형자산 증가분)
        "순부채": "net_debt",
        "순이자발생부채": "net_interest_bearing_debt",
    }
    for y, fields in (wise_balance or {}).items():
        if y not in years_data and y.isdigit() and 2000 < int(y) < 2100:
            years_data[y] = {}  # 2026E 연도 추가
        if y not in years_data:
            continue
        d = years_data[y]
        for wise_name, our_name in BS_FIELDS.items():
            if wise_name in fields:
                d[our_name] = round(fields[wise_name])

    # 2. 현금흐름표 상세 (OCF/투자CF/재무CF + 감가상각 + 배당 + 자사주)
    # 주의: Wisereport CF에는 "유형자산취득" 항목이 없고 BS의 "CAPEX"(유형자산 증가분)로 대체.
    CF_FIELDS = {
        "영업활동으로인한현금흐름": "ocf",
        "투자활동으로인한현금흐름": "invest_cf",
        "재무활동으로인한현금흐름": "finance_cf",
        "유형자산감가상각비": "depreciation",
        "기타무형자산상각비": "amortization",
        "법인세납부(-)": "tax_paid",
        "현금배당(-)": "dividends_paid",
        "자기주식매입": "treasury_buyback",
    }
    for y, fields in (wise_cashflow or {}).items():
        if y not in years_data and y.isdigit() and 2000 < int(y) < 2100:
            years_data[y] = {}
        if y not in years_data:
            continue
        d = years_data[y]
        for wise_name, our_name in CF_FIELDS.items():
            if wise_name in fields:
                d[our_name] = round(fields[wise_name])
        # FCF 자동 계산: OCF - |CAPEX(BS 유형자산 증가분)|
        if d.get("ocf") is not None and d.get("capex") is not None:
            d["fcf"] = d["ocf"] - abs(d["capex"])

    # 3. 재무비율 5종 병합 (수익성/성장/안정/활동/가치)
    RATIO_FIELDS = {
        "profitability": ["ROE", "ROA", "ROIC", "매출총이익률", "영업이익률", "순이익률", "EBITDA마진율"],
        "stability": ["부채비율", "유동비율", "당좌비율", "이자보상배율", "차입금의존도", "자본유보율"],
        "activity": ["총자산회전율", "자기자본회전율", "재고자산회전율", "매출채권회전율", "매입채무회전율"],
        "growth": ["매출액증가율", "영업이익증가율", "순이익증가율", "자기자본증가율", "총자산증가율"],
        "valuation": ["PER", "PBR", "PCR", "PSR", "EV/EBITDA", "DPS", "EPS", "BPS", "SPS"],
    }
    for section, fields_list in RATIO_FIELDS.items():
        section_data = (wise_ratios or {}).get(section, {})
        for y, year_fields in section_data.items():
            if y not in years_data and y.isdigit() and 2000 < int(y) < 2100:
                years_data[y] = {}
            if y not in years_data:
                continue
            d = years_data[y]
            d.setdefault(f"_{section}", {})
            for f in fields_list:
                if f in year_fields:
                    d[f"_{section}"][f] = year_fields[f]

    # FnGuide 현금흐름 병합 (백업: Wisereport에 없는 경우에만)
    for fng_key, kis_key in [("ocf", "ocf"), ("invest_cf", "invest_cf"), ("finance_cf", "finance_cf")]:
        for period, val in (fng_cf.get(fng_key) or {}).items():
            y = str(period)[:4]
            if y in years_data and years_data[y].get(kis_key) is None:
                years_data[y][kis_key] = round(val)

    # 2026E (또는 미래 연도) 분리: 손익 데이터가 없으면 years_data에서 제거하고
    # consensus_year 별도 저장 (forward 섹션에서만 참조)
    consensus_year_data = {}
    future_years = [y for y in years_data.keys() if y.isdigit() and int(y) > 2025]
    for fy in future_years:
        fyd = years_data[fy]
        # 매출이 없으면 손익계산서 미제공 → consensus로 이동
        if not fyd.get("revenue"):
            consensus_year_data[fy] = years_data.pop(fy)

    # 최근 N년만 슬라이싱 (사용자 요구: KIS 22년 → 5년으로 축소)
    all_years = sorted(years_data.keys())
    if len(all_years) > MAX_YEARS:
        keep_years = all_years[-MAX_YEARS:]
        years_data = {y: years_data[y] for y in keep_years}

    # YoY 자동 계산 (KIS 성장률이 없거나 보완용)
    sorted_years = sorted(years_data.keys())
    for i in range(1, len(sorted_years)):
        curr_y, prev_y = sorted_years[i], sorted_years[i - 1]
        curr, prev = years_data[curr_y], years_data[prev_y]
        if curr.get("revenue_yoy_kis") is None:
            curr["revenue_yoy"] = yoy(curr.get("revenue"), prev.get("revenue"))
        else:
            curr["revenue_yoy"] = curr["revenue_yoy_kis"]
        if curr.get("op_income_yoy_kis") is None:
            curr["op_income_yoy"] = yoy(curr.get("op_income"), prev.get("op_income"))
        else:
            curr["op_income_yoy"] = curr["op_income_yoy_kis"]
        if curr.get("net_income_yoy_kis") is None:
            curr["net_income_yoy"] = yoy(curr.get("net_income"), prev.get("net_income"))
        else:
            curr["net_income_yoy"] = curr["net_income_yoy_kis"]
        curr["eps_yoy"] = yoy(curr.get("eps"), prev.get("eps"))

    # 4-3. 수급
    supply = {
        "foreign": investor.get("외국인_순매수"),
        "institution": investor.get("기관_순매수"),
        "individual": investor.get("개인_순매수"),
    }

    # 4-4. 이상치 경고
    alerts = []
    for y, d in years_data.items():
        if d.get("revenue_yoy") is not None and abs(d["revenue_yoy"]) > 30:
            alerts.append(f"{y}: 매출 YoY {d['revenue_yoy']:+.1f}% (30%+ 급변 - 원인 분석 필수)")
        if d.get("op_income_yoy") is not None and abs(d["op_income_yoy"]) > 50:
            alerts.append(f"{y}: 영업이익 YoY {d['op_income_yoy']:+.1f}% (50%+ 급변 - 원인 분석 필수)")
        if d.get("opm") is not None and d["opm"] < 0:
            alerts.append(f"{y}: 영업적자 (OPM {d['opm']:.1f}%)")
        if d.get("debt_ratio") is not None and d["debt_ratio"] > 300:
            alerts.append(f"{y}: 부채비율 {d['debt_ratio']:.0f}% (300%+ 고위험)")

    # 5. EPS 교차검증: KIS 시세 EPS vs KIS 재무 최신 EPS
    if sorted_years and kis_summary.get("eps"):
        latest_eps = years_data[sorted_years[-1]].get("eps")
        if latest_eps:
            diff_pct = abs(kis_summary["eps"] - latest_eps) / max(abs(latest_eps), 1) * 100
            kis_summary["eps_validation"] = {
                "price_api_eps": kis_summary["eps"],
                "finance_api_eps": latest_eps,
                "diff_pct": round(diff_pct, 1),
                "ok": diff_pct < 10,
            }

    result = {
        "_description": "KIS API 손익 + Wisereport BS/CF/비율 + 네이버 컨센서스 통합 (v3)",
        "_sources": {
            "income_statement": "KIS Open API (공식, 5년)",
            "balance_sheet": "Wisereport cF3002 rpt=1 (5년 + 2026E, 251 필드)" if wise_balance else "KIS 요약",
            "cashflow": "Wisereport cF3002 rpt=2 (5년 + 2026E, 312 필드)" if wise_cashflow else "FnGuide 백업",
            "ratios": "Wisereport cF4002 rpt=1~5 (5종)" if wise_ratios else "KIS 요약",
            "consensus": "Wisereport (26개 증권사)" if naver.get("consensus") else "N/A",
            "forward_per": "Wisereport finsum_more + FnGuide 헤더",
            "price/supply/daily": "KIS Open API (공식)",
        },
        "meta": {
            "stock_name": stock_name,
            "stock_code": stock_code,
            "years_available": sorted_years,
        },
        "kis": kis_summary,
        "supply": supply,
        "financials": years_data,
        "consensus_year": consensus_year_data,  # 2026E 재무상태표/현금흐름 (손익 제외)
        "consensus": naver.get("consensus", {}),
        "forward": naver.get("forward", {}),
        "shareholders": naver.get("shareholders", []),
        "credit_ratings": naver.get("credit_ratings", []),
        "alerts": alerts,
    }
    return result


def print_summary(data: dict):
    """콘솔 요약 출력."""
    print("=" * 60)
    print(f"  재무 요약: {data['meta']['stock_name']} ({data['meta']['stock_code']})")
    print("=" * 60)

    k = data["kis"]
    print(f"\n[KIS 시세]")
    print(f"  현재가: {k.get('current_price', 0):,}원")
    print(f"  시총: {k.get('market_cap_조', 0)}조 ({k.get('market_cap_억', 0):,}억)")
    print(f"  PER: {k.get('per')}, PBR: {k.get('pbr')}, 배당: {k.get('dividend_yield')}")
    print(f"  EPS: {k.get('eps')}, BPS: {k.get('bps')}")
    if k.get("per_12m_forward"):
        print(f"  Forward PER(12M): {k['per_12m_forward']}, 업종 PER: {k.get('sector_per')}")
    if k.get("eps_validation"):
        v = k["eps_validation"]
        status = "OK" if v["ok"] else "MISMATCH"
        print(f"  EPS 검증: {v['price_api_eps']} vs {v['finance_api_eps']} ({v['diff_pct']}%) [{status}]")

    s = data["supply"]
    print(f"\n[수급 20일]")
    print(f"  외국인: {s.get('foreign'):,}, 기관: {s.get('institution'):,}, 개인: {s.get('individual'):,}")

    print(f"\n[재무 {len(data['financials'])}년치]")
    for y in sorted(data["financials"].keys()):
        f = data["financials"][y]
        rev = f.get("revenue", 0) or 0
        op = f.get("op_income", 0) or 0
        ni = f.get("net_income", 0) or 0
        opm = f.get("opm")
        roe = f.get("roe")
        debt = f.get("debt_ratio")
        line = f"  {y}: 매출 {rev/10000:.2f}조, 영업 {op/10000:.2f}조 (OPM {opm}%), 순이익 {ni/10000:.2f}조"
        if roe is not None:
            line += f", ROE {roe}%"
        if debt is not None:
            line += f", 부채 {debt}%"
        print(line)
        if f.get("ebitda"):
            print(f"       EBITDA {f['ebitda']/10000:.2f}조, EV/EBITDA {f.get('ev_ebitda')}x")
        if f.get("ocf") is not None:
            ocf_v = f.get("ocf") or 0
            inv_v = f.get("invest_cf") or 0
            fin_v = f.get("finance_cf") or 0
            print(f"       OCF {ocf_v/10000:+.2f}조, 투자CF {inv_v/10000:+.2f}조, 재무CF {fin_v/10000:+.2f}조")
        if f.get("capex") is not None:
            capex_v = f.get("capex") or 0
            fcf_v = f.get("fcf") or 0
            dep_v = f.get("depreciation") or 0
            print(f"       CapEx {capex_v/10000:.2f}조, FCF {fcf_v/10000:+.2f}조, 감가상각 {dep_v/10000:.2f}조")
        if f.get("inventory") is not None:
            inv = f.get("inventory") or 0
            rec = f.get("receivables") or 0
            pay = f.get("payables") or 0
            wc = inv + rec - pay
            print(f"       재고 {inv/10000:.2f}조, 매출채권 {rec/10000:.2f}조, 매입채무 {pay/10000:.2f}조, 운전자본 {wc/10000:.2f}조")
        if f.get("dividends_paid") is not None or f.get("treasury_buyback") is not None:
            div = f.get("dividends_paid") or 0
            buy = f.get("treasury_buyback") or 0
            print(f"       배당지급 {abs(div)/10000:.2f}조, 자사주매입 {buy/10000:.2f}조")

    # 컨센서스
    cons = data.get("consensus", {}).get("summary", {})
    if cons:
        print(f"\n[컨센서스 ({cons.get('broker_count','?')}개 증권사)]")
        tgt = cons.get("avg_target_price") or 0
        cur = data["kis"].get("current_price") or 0
        upside = ((tgt - cur) / cur * 100) if (cur and tgt) else 0
        print(f"  평균 목표가: {tgt:,}원 (상승여력 {upside:+.1f}%)")
        print(f"  평균 Forward EPS: {cons.get('avg_eps_forward', 0):,}원")
        print(f"  평균 Forward PER: {cons.get('avg_per_forward')}x")

    # Forward 2026E
    fw = data.get("forward", {})
    if fw.get("eps_forward"):
        print(f"\n[2026E Forward (네이버)]")
        print(f"  PER {fw.get('per_forward')} / PBR {fw.get('pbr_forward')} / EV-EBITDA {fw.get('ev_ebitda_forward')}")
        print(f"  EPS {fw.get('eps_forward'):,.0f}원 / BPS {fw.get('bps_forward'):,.0f}원 / DPS {fw.get('dps_forward'):,.0f}원")

    # 주주
    sh = data.get("shareholders", [])
    if sh:
        print(f"\n[주주 구성]")
        for s in sh[:5]:
            print(f"  {s['name']}: {s['pct']}%")

    # 신용등급
    cr = data.get("credit_ratings", [])
    if cr:
        print(f"\n[신용등급]")
        for c in cr:
            print(f"  {c['agency']}: {c['bond']} ({c['date']})")

    if data["alerts"]:
        print(f"\n[이상치 경고]")
        for a in data["alerts"]:
            print(f"  [!] {a}")


def main():
    args = sys.argv[1:]
    if not args:
        print("사용법:")
        print("  python scripts/financial_summary.py {종목명} {종목코드}")
        print("  예: python scripts/financial_summary.py 기아 000270")
        sys.exit(1)

    # 인자 파싱: 이름+코드 or data/종목명
    if len(args) >= 2:
        stock_name, stock_code = args[0], args[1]
        data_dir = os.path.join("data", stock_name)
    else:
        # data/종목명 경로 형식 호환
        path = args[0].rstrip("/\\").replace("\\", "/")
        stock_name = os.path.basename(path)
        data_dir = path
        # 기존 data_kis.json 에서 코드 뽑아보기
        kis_path = os.path.join(data_dir, "data_kis.json")
        stock_code = None
        if os.path.exists(kis_path):
            try:
                kis = json.load(open(kis_path, encoding="utf-8"))
                # 현재가 API 응답에 종목코드가 없을 수 있음 → 사용자에게 요구
            except Exception:
                pass
        if not stock_code:
            print(f"[ERROR] 종목코드를 찾을 수 없음. 'python financial_summary.py {stock_name} 000000' 형식으로 실행")
            sys.exit(1)

    data = build_summary(stock_name, stock_code, data_dir)

    out_path = os.path.join(data_dir, "financial_summary.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print_summary(data)
    print(f"\n[OK] 저장: {out_path}")


if __name__ == "__main__":
    main()
