"""
SEC EDGAR 데이터 수집 스크립트
- 회사 정보 조회
- 최근 재무제표 (10-K, 10-Q) 수집
- 매출, 영업이익, 순이익, EPS 등 추출
- 10-K/10-Q 본문 다운로드 및 핵심 섹션 추출
"""

import requests
import json
import sys
import re
import time
from html.parser import HTMLParser

HEADERS = {
    "User-Agent": "StockResearchAgent admin@example.com",
    "Accept": "application/json"
}

def get_cik(ticker: str) -> str:
    """티커로 CIK 번호 조회"""
    url = "https://efts.sec.gov/LATEST/search-index/company-search?q={}&dateRange=custom&startdt=2020-01-01&enddt=2026-12-31"
    # 더 간단한 방법: tickers.json 사용
    url = "https://www.sec.gov/files/company_tickers.json"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()

    ticker_upper = ticker.upper()
    for entry in data.values():
        if entry["ticker"] == ticker_upper:
            cik = str(entry["cik_str"]).zfill(10)
            print(f"[OK] {entry['title']} (CIK: {cik})")
            return cik

    raise ValueError(f"티커 '{ticker}'를 찾을 수 없습니다.")


def get_company_facts(cik: str) -> dict:
    """회사의 모든 재무 데이터 조회 (XBRL)"""
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def extract_financials(facts: dict) -> dict:
    """핵심 재무지표 추출"""
    us_gaap = facts.get("facts", {}).get("us-gaap", {})

    # 추출할 지표 매핑 (v2: 40+ 필드로 확장)
    metrics = {
        # === 손익계산서 ===
        "Revenue (매출)": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax"],
        "COGS (매출원가)": ["CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold"],
        "Gross Profit (매출총이익)": ["GrossProfit"],
        "Operating Income (영업이익)": ["OperatingIncomeLoss"],
        "SGA (판관비)": ["SellingGeneralAndAdministrativeExpense"],
        "R&D Expense (연구개발비)": ["ResearchAndDevelopmentExpense"],
        "Interest Expense (이자비용)": ["InterestExpense", "InterestExpenseDebt"],
        "Income Tax (법인세)": ["IncomeTaxExpenseBenefit"],
        "Pretax Income (세전이익)": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
        "Net Income (순이익)": ["NetIncomeLoss"],
        "EPS (주당순이익)": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
        "DPS (주당배당금)": ["CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"],
        # === 재무상태표 ===
        "Total Assets (총자산)": ["Assets"],
        "Current Assets (유동자산)": ["AssetsCurrent"],
        "Cash (현금)": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsAndShortTermInvestments"],
        "Short-term Investments (단기투자)": ["ShortTermInvestments", "MarketableSecuritiesCurrent"],
        "Receivables (매출채권)": ["AccountsReceivableNetCurrent", "AccountsReceivableNet"],
        "Inventory (재고자산)": ["InventoryNet", "Inventories"],
        "Non-current Assets (비유동자산)": ["AssetsNoncurrent"],
        "PP&E (유형자산)": ["PropertyPlantAndEquipmentNet"],
        "Goodwill (영업권)": ["Goodwill"],
        "Intangibles (무형자산)": ["IntangibleAssetsNetExcludingGoodwill"],
        "Total Liabilities (총부채)": ["Liabilities"],
        "Current Liabilities (유동부채)": ["LiabilitiesCurrent"],
        "Payables (매입채무)": ["AccountsPayableCurrent", "AccountsPayableAndAccruedLiabilitiesCurrent"],
        "Short-term Debt (단기차입금)": ["ShortTermBorrowings", "CommercialPaper"],
        "Non-current Liabilities (비유동부채)": ["LiabilitiesNoncurrent"],
        "Long-term Debt (장기차입금)": ["LongTermDebt", "LongTermDebtNoncurrent"],
        "Total Debt (총차입금)": ["DebtCurrent", "LongTermDebtAndCapitalLeaseObligations"],
        "Stockholders Equity (자기자본)": ["StockholdersEquity"],
        "Retained Earnings (이익잉여금)": ["RetainedEarningsAccumulatedDeficit"],
        "Shares Outstanding (발행주식수)": ["CommonStockSharesOutstanding", "WeightedAverageNumberOfShareOutstandingBasicAndDiluted", "WeightedAverageNumberOfDilutedSharesOutstanding"],
        # === 현금흐름표 ===
        "Operating Cash Flow (영업현금흐름)": ["NetCashProvidedByUsedInOperatingActivities"],
        "D&A (감가상각비)": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "Depreciation"],
        "CapEx (설비투자)": ["PaymentsToAcquirePropertyPlantAndEquipment"],
        "Investing Cash Flow (투자현금흐름)": ["NetCashProvidedByUsedInInvestingActivities"],
        "Financing Cash Flow (재무현금흐름)": ["NetCashProvidedByUsedInFinancingActivities"],
        "Dividends Paid (배당금지급)": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
        "Share Repurchase (자사주매입)": ["PaymentsForRepurchaseOfCommonStock"],
        "Stock Comp (주식보상비)": ["ShareBasedCompensation"],
    }

    result = {}

    def _extract_annual(key_name):
        """단일 XBRL 태그에서 연간 데이터 추출. {year: {period, value}} 반환."""
        if key_name not in us_gaap:
            return {}
        units = us_gaap[key_name].get("units", {})
        for unit_type in ["USD", "shares", "USD/shares"]:
            if unit_type in units:
                entries = units[unit_type]
                annual = [
                    e for e in entries
                    if e.get("form") in ("10-K", "10-K/A")
                    and e.get("fp") == "FY"
                ]
                annual.sort(key=lambda x: x.get("filed", ""), reverse=True)
                seen = {}
                for e in annual:
                    year = e["end"][:4]
                    if year not in seen:
                        seen[year] = {"period": e["end"], "value": e["val"]}
                return seen
        return {}

    for label, possible_keys in metrics.items():
        # 모든 후보 태그에서 데이터를 병합 (첫 태그 우선, 빈 연도만 후순위로 채움)
        merged = {}
        for key in possible_keys:
            year_data = _extract_annual(key)
            for year, entry in year_data.items():
                if year not in merged:
                    merged[year] = entry

        if merged:
            sorted_years = sorted(merged.keys())
            recent = [merged[y] for y in sorted_years[-5:]]
            result[label] = recent

    return result


def extract_quarterly_financials(facts: dict, num_quarters: int = 8) -> dict:
    """SEC XBRL에서 분기(10-Q) 재무 데이터 추출.

    Returns: { "Revenue (매출)": [{"period": "2024-09-30", "value": ..., "fp": "Q3"}, ...], ... }
    최근 num_quarters 분기만 반환.
    """
    us_gaap = facts.get("facts", {}).get("us-gaap", {})

    # 연간과 동일한 지표를 분기로 추출 (주요 항목만)
    metrics = {
        "Revenue (매출)": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                          "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax"],
        "COGS (매출원가)": ["CostOfGoodsAndServicesSold", "CostOfRevenue"],
        "Gross Profit (매출총이익)": ["GrossProfit"],
        "Operating Income (영업이익)": ["OperatingIncomeLoss"],
        "Net Income (순이익)": ["NetIncomeLoss"],
        "EPS (주당순이익)": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
        "Operating Cash Flow (영업현금흐름)": ["NetCashProvidedByUsedInOperatingActivities"],
        "CapEx (설비투자)": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    }

    result = {}

    for label, possible_keys in metrics.items():
        merged = {}  # key: "YYYY-QN" -> entry
        for key_name in possible_keys:
            if key_name not in us_gaap:
                continue
            units = us_gaap[key_name].get("units", {})
            for unit_type in ["USD", "shares", "USD/shares"]:
                if unit_type in units:
                    entries = units[unit_type]
                    quarterly = [
                        e for e in entries
                        if e.get("form") in ("10-Q", "10-Q/A")
                        and e.get("fp") in ("Q1", "Q2", "Q3")
                    ]
                    quarterly.sort(key=lambda x: x.get("filed", ""), reverse=True)
                    for e in quarterly:
                        qkey = f"{e['end'][:4]}-{e['fp']}"
                        if qkey not in merged:
                            merged[qkey] = {
                                "period": e["end"],
                                "value": e["val"],
                                "fp": e["fp"],
                            }
                    break  # unit_type found

        if merged:
            sorted_entries = sorted(merged.values(), key=lambda x: x["period"])
            result[label] = sorted_entries[-num_quarters:]

    return result


def get_recent_filings(cik: str, form_type: str = "10-K", count: int = 5) -> list:
    """최근 공시 목록 조회"""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()

    filings = data.get("filings", {}).get("recent", {})
    forms = filings.get("form", [])
    dates = filings.get("filingDate", [])
    accessions = filings.get("accessionNumber", [])
    descriptions = filings.get("primaryDocDescription", [])

    results = []
    for i, form in enumerate(forms):
        if form == form_type and len(results) < count:
            results.append({
                "form": form,
                "date": dates[i],
                "accession": accessions[i],
                "description": descriptions[i] if i < len(descriptions) else ""
            })

    return results


def format_value(val):
    """숫자를 읽기 쉽게 포맷"""
    if val is None:
        return "N/A"
    try:
        val = float(val)
    except (ValueError, TypeError):
        return "N/A"
    if abs(val) >= 1_000_000_000:
        return f"${val/1_000_000_000:.2f}B"
    elif abs(val) >= 1_000_000:
        return f"${val/1_000_000:.1f}M"
    elif abs(val) >= 1000:
        return f"${val/1000:.1f}K"
    else:
        return f"${val:.2f}"


# ============================================
# 10-K/10-Q 본문 추출
# ============================================

class SECTextExtractor(HTMLParser):
    """HTML에서 텍스트만 추출"""
    def __init__(self):
        super().__init__()
        self.result = []
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip = True
        if tag in ('br', 'p', 'div', 'tr', 'li', 'h1', 'h2', 'h3', 'h4'):
            self.result.append('\n')
        if tag == 'td':
            self.result.append('\t')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = False

    def handle_data(self, data):
        if not self.skip:
            self.result.append(data)

    def get_text(self):
        text = ''.join(self.result)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()


def sec_html_to_text(html_content: str) -> str:
    """SEC HTML을 텍스트로 변환"""
    parser = SECTextExtractor()
    parser.feed(html_content)
    return parser.get_text()


def get_filing_documents(cik: str, accession: str) -> list:
    """공시의 문서 목록 조회 — 가장 큰 HTM이 본문"""
    acc_no_dash = accession.replace("-", "")
    cik_clean = cik.lstrip('0')
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{acc_no_dash}/index.json"
    time.sleep(0.15)
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()

    docs = []
    for item in data.get("directory", {}).get("item", []):
        name = item.get("name", "")
        if name.endswith(".htm") or name.endswith(".html"):
            size_str = str(item.get("size", "0")).strip()
            try:
                size = int(size_str) if size_str else 0
            except ValueError:
                size = 0
            docs.append({
                "name": name,
                "size": size,
                "url": f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{acc_no_dash}/{name}"
            })

    # 가장 큰 HTML이 보통 본문 (R*.htm 제외 — XBRL viewer 파일)
    main_docs = [d for d in docs if not re.match(r'^R\d+\.htm', d["name"])]
    if main_docs:
        main_docs.sort(key=lambda x: x["size"], reverse=True)
        return main_docs
    # R*.htm밖에 없으면 전체에서 가장 큰 것
    docs.sort(key=lambda x: x["size"], reverse=True)
    return docs


def download_filing_text(doc_url: str) -> str:
    """SEC 공시 HTML 다운로드 후 텍스트 변환"""
    time.sleep(0.2)  # SEC rate limit
    resp = requests.get(doc_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return sec_html_to_text(resp.text)


def extract_sec_sections(full_text: str) -> dict:
    """10-K 본문에서 핵심 섹션 추출 (Item 기반)"""

    # SEC 10-K Item 패턴
    section_config = {
        "Business": {
            "patterns": [
                r"(?:ITEM|Item)\s*1[\.\s]*[\-—]?\s*(?:Business|BUSINESS)",
            ],
            "max_chars": 15000,
        },
        "Risk_Factors": {
            "patterns": [
                r"(?:ITEM|Item)\s*1A[\.\s]*[\-—]?\s*(?:Risk|RISK)",
            ],
            "max_chars": 10000,
        },
        "MDA": {
            "patterns": [
                r"(?:ITEM|Item)\s*7[\.\s]*[\-—]?\s*(?:Management|MANAGEMENT)",
            ],
            "max_chars": 15000,
        },
        "Market_Risk": {
            "patterns": [
                r"(?:ITEM|Item)\s*7A[\.\s]*[\-—]?\s*(?:Quantitative|QUANTITATIVE)",
            ],
            "max_chars": 5000,
        },
        "Directors": {
            "patterns": [
                r"(?:ITEM|Item)\s*10[\.\s]*[\-—]?\s*(?:Directors|DIRECTORS)",
            ],
            "max_chars": 5000,
        },
        "Compensation": {
            "patterns": [
                r"(?:ITEM|Item)\s*11[\.\s]*[\-—]?\s*(?:Executive|EXECUTIVE)",
            ],
            "max_chars": 5000,
        },
        "Security_Ownership": {
            "patterns": [
                r"(?:ITEM|Item)\s*12[\.\s]*[\-—]?\s*(?:Security|SECURITY)",
            ],
            "max_chars": 5000,
        },
    }

    sections = {}

    for section_name, config in section_config.items():
        best_match = ""
        max_chars = config["max_chars"]

        for pattern in config["patterns"]:
            matches = list(re.finditer(pattern, full_text))
            if matches:
                # 마지막 매치 사용 (목차가 아닌 본문)
                match = matches[-1]
                start = match.start()
                extracted = full_text[start:start + max_chars]
                if len(extracted) > len(best_match):
                    best_match = extracted

        if best_match and len(best_match) > 200:  # 너무 짧으면 목차일 수 있음
            sections[section_name] = best_match
            print(f"    [OK] {section_name}: {len(best_match)}자 추출")
        else:
            print(f"    [--] {section_name}: 미발견")

    return sections


def get_all_sec_reports(cik: str) -> list:
    """최근 4개 분기보고서 + 전년 10-K = 최대 5개 본문 수집"""
    print("\n[SEC 보고서 본문 수집 (최근 4개 + 전년 10-K)]")

    # 최근 공시 목록
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()

    filings = data.get("filings", {}).get("recent", {})
    forms = filings.get("form", [])
    dates = filings.get("filingDate", [])
    accessions = filings.get("accessionNumber", [])
    primary_docs = filings.get("primaryDocument", [])

    # 10-K와 10-Q 선별 (최근 순으로 최대 5개, 10-K 최소 1개 보장)
    quarterly = []
    annual = []
    for i, form in enumerate(forms):
        entry = {
            "form": form, "date": dates[i],
            "accession": accessions[i],
            "primary_doc": primary_docs[i] if i < len(primary_docs) else "",
        }
        if form in ("10-K", "10-K/A") and len(annual) < 2:
            annual.append(entry)
        elif form in ("10-Q", "10-Q/A") and len(quarterly) < 4:
            quarterly.append(entry)
        if len(annual) + len(quarterly) >= 6:
            break

    # 최근 4개 + 10-K 최소 1개 보장
    all_reports = sorted(quarterly + annual, key=lambda x: x["date"], reverse=True)[:4]
    has_annual = any(r["form"] in ("10-K", "10-K/A") for r in all_reports)
    if not has_annual and annual:
        all_reports.append(annual[0])
    elif len(all_reports) < 5 and len(annual) > 0:
        for a in annual:
            if a not in all_reports:
                all_reports.append(a)
                break

    selected = all_reports[:5]
    for r in selected:
        print(f"    [OK] {r['form']} ({r['date']}) - accession: {r['accession']}")

    # 본문 다운로드
    results = []
    for i, r in enumerate(selected):
        print(f"\n  --- [{i+1}/{len(selected)}] {r['form']} ({r['date']}) 다운로드 중...")

        try:
            # 문서 목록에서 가장 큰 HTML 찾기
            docs = get_filing_documents(cik, r["accession"])
            if not docs:
                print(f"    문서 목록 없음, 건너뜀")
                continue

            # 가장 큰 HTML 다운로드 (=본문)
            main_doc = docs[0]
            print(f"    본문: {main_doc['name']} ({main_doc['size']/1024:.0f} KB)")

            full_text = download_filing_text(main_doc["url"])
            if len(full_text) < 1000:
                print(f"    텍스트 너무 짧음 ({len(full_text)}자), 건너뜀")
                continue

            # 섹션 추출
            sections = extract_sec_sections(full_text)

            results.append({
                "form": r["form"],
                "date": r["date"],
                "accession": r["accession"],
                "sections": sections,
                "total_chars": len(full_text),
            })

        except Exception as e:
            print(f"    에러: {e}")
            continue

    print(f"\n[OK] 총 {len(results)}개 보고서 수집 완료")
    return results


def test_sec(ticker: str):
    """SEC EDGAR 테스트"""
    print(f"\n{'='*60}")
    print(f"  SEC EDGAR 데이터 수집 테스트: {ticker}")
    print(f"{'='*60}\n")

    # 1. CIK 조회
    print("[1] CIK 조회 중...")
    cik = get_cik(ticker)

    # 2. 최근 공시 목록
    print("\n[2] 최근 10-K 공시 목록:")
    filings = get_recent_filings(cik, "10-K")
    for f in filings:
        print(f"    {f['date']} | {f['form']} | {f['description']}")

    print("\n    최근 10-Q 공시 목록:")
    filings_q = get_recent_filings(cik, "10-Q", 4)
    for f in filings_q:
        print(f"    {f['date']} | {f['form']} | {f['description']}")

    # 3. 재무 데이터
    print("\n[3] 재무 데이터 수집 중...")
    facts = get_company_facts(cik)
    financials = extract_financials(facts)

    print(f"\n    회사명: {facts.get('entityName', 'N/A')}")
    print(f"    {'─'*55}")

    for label, data_points in financials.items():
        print(f"\n    {label}:")
        for dp in data_points:
            val = dp['value']
            if "EPS" in label:
                formatted = f"${val:.2f}"
            elif "Shares" in label:
                formatted = f"{val/1_000_000:.0f}M shares"
            else:
                formatted = format_value(val)
            print(f"      {dp['period'][:7]}  →  {formatted}")

    # 4. 보고서 본문 추출
    print("\n[4] 보고서 본문 추출:")
    reports = get_all_sec_reports(cik)
    if reports:
        print(f"\n    === 수집 결과 요약 ===")
        for r in reports:
            section_count = len(r.get("sections", {}))
            total_sec_chars = sum(len(v) for v in r.get("sections", {}).values())
            print(f"    {r['form']} ({r['date']}): {section_count}개 섹션, {total_sec_chars:,}자")

    print(f"\n{'='*60}")
    print("  SEC EDGAR 테스트 완료!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    test_sec(ticker)
