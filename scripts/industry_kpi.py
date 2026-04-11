"""
업종별 핵심 KPI 자동 수집 모듈

업종을 판별하고, 해당 업종의 핵심 지표를 웹 검색으로 수집합니다.

사용법:
  from industry_kpi import detect_industry, get_kpi_search_queries

  industry = detect_industry("삼성SDI", "2차전지")
  queries = get_kpi_search_queries(industry, "삼성SDI")
  # → 웹 검색에 사용할 쿼리 목록 반환
"""

# ============================================
# 업종 분류 체계
# ============================================
INDUSTRY_MAP = {
    "반도체": {
        "keywords": ["반도체", "semiconductor", "메모리", "파운드리", "DRAM", "NAND", "HBM", "칩"],
        "kpis": [
            "DRAM/NAND 스팟 가격 추이",
            "HBM 수요/공급 전망",
            "가동률 (Utilization Rate)",
            "재고일수 (Days of Inventory)",
            "ASP (Average Selling Price) 추이",
            "CapEx 투자 사이클",
            "AI 반도체 수요 전망",
        ],
        "search_templates": [
            "{year} DRAM NAND spot price trend forecast",
            "{company} {year} 가동률 재고 ASP 반도체 실적",
            "HBM 수요 전망 {year} AI GPU 반도체",
            "글로벌 반도체 시장 전망 {year} 메모리 파운드리 capex",
        ],
    },
    "2차전지": {
        "keywords": ["2차전지", "배터리", "battery", "리튬", "ESS", "전기차", "EV배터리", "양극재"],
        "kpis": [
            "리튬/니켈/코발트 가격 추이",
            "글로벌 EV 배터리 출하량 (GWh)",
            "ESS 시장 규모 및 성장률",
            "업체별 글로벌 점유율",
            "ASP 추이 ($/kWh)",
            "전고체 배터리 개발 현황",
            "LFP vs 삼원계 비중 변화",
        ],
        "search_templates": [
            "리튬 니켈 코발트 가격 추이 {year}",
            "글로벌 EV 배터리 출하량 점유율 {year} CATL LG 삼성SDI",
            "ESS 에너지저장장치 시장 규모 전망 {year}",
            "{company} 배터리 ASP 가격 출하량 {year}",
        ],
    },
    "바이오/제약": {
        "keywords": ["바이오", "제약", "pharmaceutical", "biotech", "임상", "FDA", "신약", "파이프라인"],
        "kpis": [
            "핵심 파이프라인 (임상 단계별)",
            "FDA/EMA 승인 일정",
            "임상 성공 확률 (Phase별)",
            "특허 만료 일정 (LOE)",
            "R&D 투자 대비 신약 승인률",
            "바이오시밀러 경쟁 현황",
            "적응증별 시장 규모 (TAM)",
        ],
        "search_templates": [
            "{company} pipeline clinical trial phase FDA approval {year}",
            "{company} 파이프라인 임상 진행 현황 FDA 승인 {year}",
            "{company} 핵심 신약 적응증 시장 규모 경쟁 약물",
            "바이오 제약 산업 전망 {year} FDA 승인 트렌드",
        ],
    },
    "미디어/엔터": {
        "keywords": ["미디어", "엔터테인먼트", "OTT", "스트리밍", "콘텐츠", "K-POP", "드라마", "streaming"],
        "kpis": [
            "MAU (월간활성이용자수)",
            "유료 가입자수 추이",
            "ARPU (가입자당 매출)",
            "콘텐츠 투자 규모",
            "광고 매출 성장률",
            "이탈률 (Churn Rate)",
            "OTT 플랫폼별 점유율",
        ],
        "search_templates": [
            "{company} 가입자수 MAU ARPU {year}",
            "OTT 스트리밍 점유율 넷플릭스 디즈니 {year}",
            "{company} 콘텐츠 투자 규모 광고 매출 {year}",
            "미디어 엔터테인먼트 산업 전망 {year}",
        ],
    },
    "플랫폼/IT": {
        "keywords": ["플랫폼", "SaaS", "클라우드", "소프트웨어", "AI", "데이터", "cloud", "platform"],
        "kpis": [
            "ARR (연간반복매출)",
            "NRR (순매출유지율)",
            "MAU/DAU",
            "ARPU",
            "클라우드 시장 점유율",
            "AI 매출 비중",
            "Rule of 40 (성장률+마진)",
        ],
        "search_templates": [
            "{company} ARR NRR revenue retention rate {year}",
            "{company} cloud AI revenue growth {year}",
            "클라우드 시장 점유율 AWS Azure GCP {year}",
            "{company} DAU MAU ARPU 사용자 {year}",
        ],
    },
    "금융/은행": {
        "keywords": ["은행", "금융", "banking", "보험", "증권", "카드", "NIM"],
        "kpis": [
            "NIM (순이자마진)",
            "충당금 전입액",
            "NPL 비율 (부실채권)",
            "CET1 비율",
            "대출 성장률",
            "ROE/ROA",
            "배당성향",
        ],
        "search_templates": [
            "{company} NIM 순이자마진 충당금 NPL {year}",
            "은행 금융 산업 전망 금리 NIM {year}",
            "{company} CET1 자본적정성 배당 {year}",
            "국내 은행 ROE ROA 비교 {year}",
        ],
    },
    "보험/MCO": {
        "keywords": ["보험", "insurance", "managed care", "Medicare", "MLR", "헬스케어"],
        "kpis": [
            "MLR (의료손실률)",
            "가입자수 추이 (MA/Commercial)",
            "보험료 인상률",
            "Combined Ratio",
            "Medicare Advantage Rate",
            "Operating Margin",
            "Value-based Care 비중",
        ],
        "search_templates": [
            "{company} MLR medical loss ratio membership {year}",
            "Medicare Advantage rate {year} CMS",
            "{company} insurance premium growth operating margin {year}",
            "managed care industry outlook {year} competition",
        ],
    },
    "소비재/유통": {
        "keywords": ["소비재", "유통", "retail", "식품", "화장품", "의류", "consumer"],
        "kpis": [
            "SSS (Same Store Sales) 성장률",
            "점포수 추이",
            "온라인 매출 비중",
            "원재료 가격 추이",
            "소비자 신뢰지수",
            "재고회전율",
            "브랜드 파워 지수",
        ],
        "search_templates": [
            "{company} 동일매장매출 SSS 점포수 {year}",
            "{company} 온라인 매출 비중 이커머스 {year}",
            "소비재 유통 산업 전망 {year} 소비 트렌드",
            "{company} 원재료 가격 마진 {year}",
        ],
    },
    "조선/방산": {
        "keywords": ["조선", "방산", "shipbuilding", "defense", "군수", "함정", "LNG선"],
        "kpis": [
            "수주잔고 (Backlog)",
            "수주/매출 비율 (Book-to-Bill)",
            "신조선가 지수 (Newbuilding Price Index)",
            "건조량 (CGT)",
            "방산 수출 계약 현황",
            "글로벌 선박 발주량",
            "LNG선/컨테이너선 수요",
        ],
        "search_templates": [
            "{company} 수주잔고 수주 실적 {year}",
            "신조선가 지수 클락슨 선박 발주 {year}",
            "{company} 방산 수출 계약 {year}",
            "조선 방산 산업 전망 LNG선 {year}",
        ],
    },
    "자동차": {
        "keywords": ["자동차", "automotive", "EV", "전기차", "완성차", "모빌리티"],
        "kpis": [
            "글로벌/지역별 판매량",
            "전기차 비중 (EV Mix)",
            "ASP 추이",
            "인센티브/할인율",
            "재고일수",
            "시장 점유율",
            "자율주행 기술 수준",
        ],
        "search_templates": [
            "{company} 판매량 글로벌 지역별 {year}",
            "{company} 전기차 EV 판매 비중 {year}",
            "글로벌 자동차 시장 전망 {year} EV 하이브리드",
            "{company} ASP 재고 인센티브 {year}",
        ],
    },
    "지주회사": {
        "keywords": ["지주", "holdings", "홀딩스", "그룹", "투자회사"],
        "kpis": [
            "NAV (순자산가치) 대비 할인율",
            "상장 자회사 지분 가치",
            "비상장 자회사 추정 가치",
            "지주회사 할인율 추이",
            "배당수익률 / 배당성향",
            "자사주 비율 및 소각 계획",
            "자회사별 영업이익 기여도",
        ],
        "search_templates": [
            "{company} NAV 순자산가치 지주할인 {year}",
            "{company} 자회사 지분 가치 상장 비상장 {year}",
            "{company} 배당 자사주 소각 주주환원 {year}",
            "{company} 자회사 실적 기여도 {year}",
        ],
        "required_analysis": "NAV 분석 필수: 상장 자회사 시가 기준 지분가치 + 비상장 자회사 추정가치 = NAV, 현재 시총 대비 할인율 계산",
    },
    "항공": {
        "keywords": ["항공", "airline", "aviation", "여객", "화물", "공항", "FSC", "LCC"],
        "kpis": [
            "RPK (유상여객킬로미터)",
            "ASK (유효좌석킬로미터)",
            "탑승률 (Load Factor)",
            "Yield (단위 수익)",
            "CASK (좌석당 비용)",
            "항공유 가격",
            "노선별 실적",
        ],
        "search_templates": [
            "{company} RPK ASK 탑승률 load factor {year}",
            "항공유 jet fuel 가격 전망 {year}",
            "{company} 노선 실적 여객 화물 {year}",
            "항공 산업 전망 {year} IATA 수요",
        ],
        "required_analysis": "항공유 가격 민감도 분석 필수, 노선별(국제/국내/화물) 수익성 분석",
    },
    "건설/인프라": {
        "keywords": ["건설", "construction", "시공", "주택", "토목", "플랜트", "인프라"],
        "kpis": [
            "수주잔고 (Backlog)",
            "신규 수주액",
            "매출채권 회전율",
            "원가율 (매출원가/매출)",
            "PF 우발채무",
            "주택 분양 실적",
            "해외 수주 비중",
        ],
        "search_templates": [
            "{company} 수주잔고 신규수주 {year}",
            "{company} PF 우발채무 리스크 {year}",
            "건설 산업 전망 {year} 주택 분양 인프라",
            "{company} 해외 수주 플랜트 {year}",
        ],
        "required_analysis": "수주잔고/매출 비율(Book-to-Bill) 분석 필수, PF 리스크 점검",
    },
    "통신": {
        "keywords": ["통신", "telecom", "5G", "통신사", "MVNO", "이동통신", "KT", "SKT", "LGU"],
        "kpis": [
            "ARPU (가입자당 매출)",
            "가입자수 (이동/초고속인터넷)",
            "해지율 (Churn Rate)",
            "설비투자 (CapEx/매출)",
            "배당수익률",
            "비통신 매출 비중 (AI/클라우드 등)",
            "5G 가입자 비중",
        ],
        "search_templates": [
            "{company} ARPU 가입자수 해지율 {year}",
            "{company} 5G AI 클라우드 신사업 {year}",
            "통신 산업 전망 {year} ARPU 배당",
            "{company} 배당 CapEx 투자 {year}",
        ],
        "required_analysis": "ARPU 추이 분석 필수, 비통신 매출 성장률 별도 분석",
    },
    "리츠/부동산": {
        "keywords": ["리츠", "REIT", "부동산", "임대", "오피스", "물류센터", "real estate"],
        "kpis": [
            "FFO (운영자금)",
            "NOI (순영업소득)",
            "임대율 (Occupancy Rate)",
            "Cap Rate",
            "배당수익률",
            "NAV 대비 할인/프리미엄",
            "LTV (부채비율)",
        ],
        "search_templates": [
            "{company} FFO NOI 임대율 {year}",
            "{company} 배당수익률 NAV {year}",
            "리츠 부동산 시장 전망 {year} 금리",
            "{company} 포트폴리오 자산 가치 {year}",
        ],
        "required_analysis": "FFO 기반 밸류에이션 필수, NAV 대비 할인율 계산, 금리 민감도",
    },
}


# ============================================
# 업종 판별
# ============================================
def detect_industry(company_name: str, description: str = "") -> str:
    """회사명과 설명으로 업종을 판별합니다.

    Args:
        company_name: 회사명 (예: "삼성SDI", "Netflix")
        description: 업종 설명 또는 사업보고서 내용 (선택)

    Returns:
        업종명 (예: "2차전지", "미디어/엔터")
    """
    text = f"{company_name} {description}".lower()

    best_match = None
    best_score = 0

    for industry, config in INDUSTRY_MAP.items():
        score = 0
        for keyword in config["keywords"]:
            if keyword.lower() in text:
                score += 1

        if score > best_score:
            best_score = score
            best_match = industry

    return best_match or "기타"


# ============================================
# KPI 검색 쿼리 생성
# ============================================
def get_kpi_search_queries(industry: str, company_name: str, year: int = 2026) -> list:
    """업종별 KPI 수집을 위한 웹 검색 쿼리를 생성합니다.

    Returns:
        list of str: 웹 검색에 사용할 쿼리 목록
    """
    config = INDUSTRY_MAP.get(industry, {})
    templates = config.get("search_templates", [])

    queries = []
    for template in templates:
        query = template.format(
            company=company_name,
            year=year,
        )
        queries.append(query)

    return queries


def get_kpi_list(industry: str) -> list:
    """업종의 핵심 KPI 목록을 반환합니다."""
    config = INDUSTRY_MAP.get(industry, {})
    return config.get("kpis", [])


def get_all_industries() -> list:
    """지원하는 업종 목록을 반환합니다."""
    return list(INDUSTRY_MAP.keys())


# ============================================
# 테스트
# ============================================
if __name__ == "__main__":
    test_cases = [
        ("삼성SDI", "2차전지 배터리 ESS"),
        ("SK하이닉스", "반도체 DRAM HBM"),
        ("Netflix", "streaming OTT content"),
        ("삼성바이오로직스", "바이오 CMO 신약"),
        ("현대차", "자동차 전기차 EV"),
        ("한화오션", "조선 LNG선 방산"),
        ("카카오", "플랫폼 AI 클라우드"),
        ("KB금융", "은행 금융 NIM"),
        ("UnitedHealth", "insurance managed care Medicare"),
        ("CJ ENM", "미디어 콘텐츠 OTT 엔터테인먼트"),
        ("아모레퍼시픽", "화장품 소비재"),
    ]

    print("=== 업종 판별 테스트 ===\n")
    for name, desc in test_cases:
        industry = detect_industry(name, desc)
        kpis = get_kpi_list(industry)
        queries = get_kpi_search_queries(industry, name)
        print(f"  {name:<20} → {industry:<12} KPI: {len(kpis)}개, 검색: {len(queries)}개")
        for kpi in kpis[:3]:
            print(f"    - {kpi}")
        print()
