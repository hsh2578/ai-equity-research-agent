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
    "철강/비철금속": {
        "keywords": ["철강", "steel", "비철금속", "non-ferrous", "구리", "copper", "황동",
                     "신동", "알루미늄", "아연", "납", "니켈", "동제련", "전기동", "압연"],
        "kpis": [
            "LME 비철금속 가격 (구리·알루미늄·아연·납)",
            "SHFE 상해선물거래소 가격",
            "철강 HRC/Rebar 가격",
            "신동 가공량 + 수출",
            "중국 가전·전자 수요",
            "글로벌 EV 침투율 (구리 수요)",
            "용해비/가공 마진",
        ],
        "search_templates": [
            "LME 구리 알루미늄 가격 추이 {year}",
            "{company} 신동 압연 수주 매출 {year}",
            "철강 HRC 가격 중국 수요 {year}",
            "구리 수요 EV 인프라 {year}",
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
# v5.3 섹터별 매트릭스 (와이지엔터 일류 격차 분석 후, 2026-05)
# ============================================
# 각 섹터의 (1) 거시 데이터 소스, (2) 사업보고서 grep 키워드,
# (3) 모멘텀 트리거, (4) 사이클 저점 압축률, (5) Self-Attack 가설 종류
#
# 사용:
#   from industry_kpi import SECTOR_MATRIX_V5_3, get_sector_matrix
#   m = get_sector_matrix("반도체")
#   # m['macro_sources'], m['biz_grep'], m['momentum_triggers'], ...
SECTOR_MATRIX_V5_3 = {
    "반도체": {
        "macro_sources": ["WSTS Worldwide Semi", "TrendForce DRAM/NAND ASP", "Gartner",
                          "SIA Semiconductor Industry Association", "DRAMeXchange spot"],
        "biz_grep": ["HBM", "DRAM", "NAND", "파운드리", "캐파", "가동률", "미세공정", "8단/12단",
                     "재고일수", "ASP", "AI 반도체", "고객사 다변화"],
        "momentum_triggers": ["분기 가이던스 (가이던스 +N% 시 컨센 상향 트리거)",
                              "HBM 양산 일정 / 12단 인증",
                              "NVIDIA·AMD 차세대 GPU 발표",
                              "Capex 사이클 (TSMC/삼성/Intel)"],
        "cycle_trough_compression": "DRAM ASP 사이클 저점 -30~50% (역사적: 2019 -47%, 2023 -38%). PER 압축 -30~40%",
        "self_attack_themes": ["AI 사이클 정점 가설 부정 (수요 정체)",
                               "HBM 점유율 가설 부정 (마이크론 추격)",
                               "기술 격차 가설 부정 (TSMC 3나노 격차)"]
    },
    "2차전지": {
        "macro_sources": ["BloombergNEF EV Outlook", "SNE Research 글로벌 배터리",
                          "Benchmark Mineral 리튬/니켈", "IEA Global EV Outlook"],
        "biz_grep": ["GWh", "ESS", "양극재", "음극재", "전해질", "분리막", "LFP", "삼원계",
                     "전고체", "수주잔고", "고객사", "OEM"],
        "momentum_triggers": ["IRA 보조금 정책",
                              "OEM 수주 발표 (Ford/GM/현대차 등)",
                              "분기 GWh 출하 데이터",
                              "리튬·니켈 가격 변동"],
        "cycle_trough_compression": "리튬 가격 사이클 저점 -75% (2022 6.8만/t → 2024 1.5만/t). EV 침투율 정체 시 OPM -10%p",
        "self_attack_themes": ["EV 침투율 가속 가설 부정 (OEM 둔화)",
                               "ESS 시장 가설 부정 (CATL LFP 가격 우위)",
                               "전고체 우위 가설 부정 (양산 5년+ 지연)"]
    },
    "바이오/제약": {
        "macro_sources": ["IQVIA Global Market Outlook", "FDA 승인 통계",
                          "EvaluatePharma 파이프라인", "BioPharma Catalyst", "Clinical Trials.gov"],
        "biz_grep": ["임상", "Phase 1/2/3", "FDA", "라이선스 아웃", "마일스톤", "로열티",
                     "파이프라인", "원개발사", "특허 만료", "바이오시밀러", "CMO/CDMO"],
        "momentum_triggers": ["임상 결과 발표 (Phase 2/3 readout)",
                              "FDA 승인 일정 (PDUFA date)",
                              "라이선스 아웃 계약",
                              "특허 만료 + 바이오시밀러 진입"],
        "cycle_trough_compression": "임상 실패 시 -50~80% 단일 주가 충격. PER N/A (적자 다수) → P/Sales 또는 rNPV 기준",
        "self_attack_themes": ["블록버스터 가설 부정 (경쟁 약물 등장)",
                               "임상 성공 확률 가설 부정 (Phase 3 historical 50%)",
                               "특허 가설 부정 (제네릭 진입)"]
    },
    "미디어/엔터": {
        "macro_sources": ["IFPI Global Music Report", "Luminate (구 Nielsen Music) 시장 점유율",
                          "MPA 글로벌 박스오피스", "Statista OTT 시장", "MIDiA Research"],
        "biz_grep": ["IP", "음반", "공연", "투어", "MD", "라이선스", "글로벌 매출",
                     "스트리밍", "구독자", "ARPU", "콘텐츠 라이브러리"],
        "momentum_triggers": ["IR Day / 라인업 발표",
                              "신보 / 투어 일정 공개",
                              "분기 음반·공연 매출",
                              "글로벌 차트 진입 (빌보드 200 / Top 50)"],
        "cycle_trough_compression": "K-POP 글로벌 -7% (IFPI 2024). 음반 단가 -15% / 콘서트 동원 -10% 시 OP -25%",
        "self_attack_themes": ["다각화 우위 가설 부정 (HBM 군 복귀로 격차)",
                               "IP 라인업 가설 부정 (시장 이미 알고 매도 응답)",
                               "글로벌 침투 가설 부정 (BTS 공백 종료 후 점유율 회귀)"]
    },
    "플랫폼/IT": {
        "macro_sources": ["Gartner IT Spending", "IDC Worldwide", "App Annie 모바일",
                          "eMarketer 디지털 광고", "Cloud market share (Synergy Research)"],
        "biz_grep": ["MAU", "DAU", "ARPU", "GMV", "Take rate", "트래픽", "클라우드", "AI Capex",
                     "구독", "광고", "커머스"],
        "momentum_triggers": ["분기 MAU/DAU 가이던스",
                              "광고 수익 증가율",
                              "AI 모델 발표 / 신기능 출시",
                              "Capex 가이던스"],
        "cycle_trough_compression": "광고 사이클 -20% (2022 메타 사례). MAU 정체 시 EV/Sales -30%",
        "self_attack_themes": ["AI 수익화 가설 부정 (Capex 회수 5년+)",
                               "Take rate 가설 부정 (경쟁 압력)",
                               "M&A 시너지 가설 부정 (역사적 50% 실패)"]
    },
    "금융/은행": {
        "macro_sources": ["BIS 신용 사이클", "한은 금융안정보고서", "FSS 은행 통계",
                          "S&P Global Bank Ratings", "Federal Reserve H.8"],
        "biz_grep": ["NIM", "순이자마진", "BIS 자기자본비율", "CET1", "대손비용", "Coverage Ratio",
                     "부실채권", "NPL", "충당금", "자기자본이익률", "ROE"],
        "momentum_triggers": ["기준금리 결정 (한은/FOMC)",
                              "분기 NIM 가이던스",
                              "충당금 정책 변화",
                              "주주환원 정책 (배당·자사주)"],
        "cycle_trough_compression": "NIM -50bp (사이클 저점) = NI -25%. NPL +1%p = 충당금 +50%",
        "self_attack_themes": ["NIM 방어 가설 부정 (예금 경쟁)",
                               "신용 비용 가설 부정 (PF 부실 노출)",
                               "주주환원 가설 부정 (자본비율 압박)"]
    },
    "보험/MCO": {
        "macro_sources": ["S&P Insurance Outlook", "한국보험연구원", "AM Best Rating",
                          "Swiss Re Sigma", "CMS National Health Expenditure"],
        "biz_grep": ["손해율", "사업비율", "Combined Ratio", "RBC", "K-ICS", "신계약가치",
                     "보험금 지급", "MCR", "Medical Cost Ratio"],
        "momentum_triggers": ["손해율 가이던스",
                              "K-ICS / RBC 자본비율",
                              "신계약 보험료 증가율",
                              "보험사고 발생률"],
        "cycle_trough_compression": "Combined Ratio +5%p = NI -30%. 자연재해 시 일회성 -20% 단일 충격",
        "self_attack_themes": ["언더라이팅 가설 부정 (가격 경쟁)",
                               "투자수익 가설 부정 (금리 인하)",
                               "K-ICS 자본 가설 부정 (제도 변경)"]
    },
    "소비재/유통": {
        "macro_sources": ["통계청 소매판매", "한국유통학회", "Nielsen 소비자",
                          "Statista 글로벌 소비재", "USDA 농산물 가격"],
        "biz_grep": ["동일점포", "SSS", "Same Store Sales", "점포당 매출", "회전율",
                     "GMV", "온라인 비중", "PB", "프라이빗 브랜드", "원재료비"],
        "momentum_triggers": ["월별 동일점포 매출 (SSS)",
                              "분기 매출 성장률 vs 컨센",
                              "원재료 가격 변동",
                              "신규 브랜드·점포 출점"],
        "cycle_trough_compression": "SSS -10% 시 OP -25% (영업 레버리지). 원재료 +20% 시 GPM -3%p",
        "self_attack_themes": ["브랜드 파워 가설 부정 (PB 침투)",
                               "글로벌 침투 가설 부정 (현지 경쟁)",
                               "온라인 전환 가설 부정 (수익성 악화)"]
    },
    "조선/방산": {
        "macro_sources": ["Clarksons 신조선가지수", "BIMCO 발주잔량", "SIPRI 글로벌 군사비",
                          "NATO 2% 목표", "한국방위산업진흥회"],
        "biz_grep": ["수주잔고", "수주잔량", "신조선가", "LNG선", "VLCC", "방산 수주",
                     "해외 수주", "K-2", "K-9", "MRO", "양산"],
        "momentum_triggers": ["수주 발표 (분기 1조+)",
                              "Clarksons 신조선가 추이",
                              "정부 국방예산안 통과",
                              "NATO·중동 수주 확정"],
        "cycle_trough_compression": "신조선가 -25% (사이클 저점). 수주잔고 -40% 시 매출 가시성 -2년",
        "self_attack_themes": ["수주잔고 가설 부정 (신조선가 정점)",
                               "NATO 2% 가설 부정 (도달 후 정체)",
                               "방산 수출 가설 부정 (지정학 완화)"]
    },
    "자동차": {
        "macro_sources": ["LMC Automotive 글로벌 판매", "S&P Mobility (구 IHS Markit)",
                          "J.D. Power 품질", "EV-Volumes", "한국자동차산업협회"],
        "biz_grep": ["판매대수", "ASP", "M/S", "시장점유율", "EV 비중", "하이브리드",
                     "현지 생산", "관세", "USMCA", "IRA"],
        "momentum_triggers": ["월별 글로벌 판매",
                              "신차 발표 / EV 출시",
                              "관세 정책 변경",
                              "M/S 변동"],
        "cycle_trough_compression": "글로벌 판매 -15% (2008/2020 사례). EV 침투율 정체 시 OPM -3%p",
        "self_attack_themes": ["EV 전환 가설 부정 (하이브리드 회귀)",
                               "하이엔드 가설 부정 (중국 BYD 추격)",
                               "관세 흡수 가설 부정 (현지화 한계)"]
    },
    "지주회사": {
        "macro_sources": ["NAV discount 추이 (Bloomberg 지주사 지수)",
                          "자회사 시가 합계 (KIS API)", "KOSPI 시총 가중"],
        "biz_grep": ["NAV", "할인율", "자회사", "지분율", "배당수익", "사업회사",
                     "순현금", "차입금", "투자자산"],
        "momentum_triggers": ["자회사 IPO / 합병",
                              "배당 정책 변경",
                              "M&A 발표",
                              "NAV 할인율 변동"],
        "cycle_trough_compression": "NAV 할인 60%+ (역사적 저점). 자회사 시총 -30% 시 NAV -20%",
        "self_attack_themes": ["NAV 할인 축소 가설 부정 (구조적 50%+)",
                               "자회사 가치 가설 부정 (개별 사이클)",
                               "지배구조 개선 가설 부정 (오너 의지 부재)"]
    },
    "항공": {
        "macro_sources": ["IATA RPK·PLF·Yield", "Cirium 운임지수", "ICAO 통계",
                          "ACI 공항 통계", "한국공항공사"],
        "biz_grep": ["RPK", "ASK", "PLF", "탑승률", "운임", "Yield", "유류비", "유가",
                     "환율 민감도", "여객", "화물", "노선"],
        "momentum_triggers": ["월별 RPK·PLF 데이터",
                              "유가 변동 (WTI/Brent)",
                              "환율 (USD/KRW)",
                              "성수기·비수기 운임"],
        "cycle_trough_compression": "PLF 75% → 60% (코로나 사례) = 매출 -20%, OP -50%. 유가 +30% = OP -25%",
        "self_attack_themes": ["수요 회복 가설 부정 (경기 침체)",
                               "유가 안정 가설 부정 (지정학 충격)",
                               "운임 정상화 가설 부정 (LCC 경쟁)"]
    },
    "건설/인프라": {
        "macro_sources": ["국토교통부 주택통계", "한국건설산업연구원",
                          "Global Construction Outlook", "원자재 가격 (시멘트·철근)"],
        "biz_grep": ["수주잔고", "분양", "착공", "준공", "PF", "프로젝트 파이낸싱",
                     "원가율", "GPM", "해외 수주", "토목"],
        "momentum_triggers": ["월별 분양 데이터",
                              "정부 SOC 예산",
                              "PF 부실 위기",
                              "원자재 가격"],
        "cycle_trough_compression": "분양 -30% 시 매출 가시성 -1년. 원가율 +5%p = OP -50%",
        "self_attack_themes": ["수주 회복 가설 부정 (PF 위기 지속)",
                               "원가 안정 가설 부정 (인건비 상승)",
                               "해외 수주 가설 부정 (중동 사이클)"]
    },
    "통신": {
        "macro_sources": ["과기정통부 통신통계", "OFCOM Global Mobile",
                          "Ericsson Mobility Report", "GSMA Intelligence"],
        "biz_grep": ["ARPU", "가입자", "5G 침투율", "MVNO", "주파수 경매",
                      "Capex", "Spectrum", "B2B"],
        "momentum_triggers": ["분기 ARPU·가입자 가이던스",
                              "주파수 경매 결과",
                              "5G 신규 단말 출시",
                              "B2B 솔루션 수주"],
        "cycle_trough_compression": "ARPU -10% (요금제 경쟁 시) = NI -20%",
        "self_attack_themes": ["5G 수익화 가설 부정 (Capex 회수 지연)",
                               "B2B 가설 부정 (경쟁 격화)",
                               "주주환원 가설 부정 (배당 정체)"]
    },
    "리츠/부동산": {
        "macro_sources": ["NAREIT 글로벌 리츠", "JLL 시장 보고서",
                          "한국부동산원", "공실률 통계"],
        "biz_grep": ["FFO", "AFFO", "NOI", "임대율", "공실률", "Cap Rate",
                     "NAV", "LTV", "WALE", "주요 임차인"],
        "momentum_triggers": ["분기 FFO 가이던스",
                              "기준금리 변동 (할인율)",
                              "신규 자산 편입",
                              "주요 임차인 갱신"],
        "cycle_trough_compression": "Cap Rate +100bp = NAV -15%. 공실률 +5%p = NOI -10%",
        "self_attack_themes": ["임대료 인상 가설 부정 (수요 둔화)",
                               "Cap Rate 안정 가설 부정 (금리 상승)",
                               "포트폴리오 다각화 가설 부정 (자산 집중)"]
    },
    "철강/비철금속": {
        "macro_sources": ["LME (London Metal Exchange) 비철 가격", "SHFE 상해선물거래소",
                          "World Steel Association", "S&P Global Platts Steel",
                          "CRU Group Steel/Copper"],
        "biz_grep": ["LME", "구리", "신동", "압연", "황동", "전기동", "용해", "가공 마진",
                     "수주잔고", "방산 수주", "탄약", "용강", "철근", "HRC"],
        "momentum_triggers": ["LME 구리 가격 변동 (분기)",
                              "중국 PMI / 가전·전자 수요",
                              "글로벌 EV 침투율 (구리 수요 +25kg/EV)",
                              "방산 수주 발표"],
        "cycle_trough_compression": "LME 구리 사이클 -30% (역사: 2015 -50%, 2022 -33%). 가공 마진 -25% 시 OP -50%",
        "self_attack_themes": ["EV 구리 수요 가설 부정 (LFP 침투로 구리 사용 -10%)",
                               "방산 수주 가설 부정 (탄약 가격 정상화)",
                               "스프레드 가설 부정 (중국 자급률 95%)"]
    },
    "화학": {
        "macro_sources": ["ICIS 스프레드", "Platts 가격", "S&P Global Commodity Insights",
                          "Dow Jones Chemical Index", "한국석유화학협회"],
        "biz_grep": ["스프레드", "PE", "PP", "PVC", "에틸렌", "프로필렌", "PX",
                     "가동률", "정제 마진", "원유 가격", "납사"],
        "momentum_triggers": ["스프레드 변동 (분기)",
                              "원유 가격 (WTI/Brent)",
                              "중국 가동률",
                              "글로벌 정제마진"],
        "cycle_trough_compression": "스프레드 -30% (2022 → 2023 사례) = OP -60%. 가동률 70% 이하 시 적자",
        "self_attack_themes": ["스프레드 회복 가설 부정 (중국 자급률)",
                               "친환경 전환 가설 부정 (Capex 부담)",
                               "고부가 가설 부정 (스페셜티 경쟁)"]
    },
}


def get_sector_matrix(industry: str, country: str = "KR") -> dict:
    """v5.3 섹터별 매트릭스 반환 (거시·grep·모멘텀·사이클·Self-Attack).

    country: "KR" 또는 "US" -- 글로벌 데이터 + 지역 특화 데이터 결합 반환.
    """
    base = dict(SECTOR_MATRIX_V5_3.get(industry, {}))
    if not base:
        return base
    overlay = SECTOR_REGION_OVERLAY.get(country.upper(), {}).get(industry, {})
    if overlay:
        # macro_sources에 지역 특화 추가
        base['macro_sources'] = base.get('macro_sources', []) + overlay.get('macro_extra', [])
        # biz_grep을 국가별 키워드로 교체 (영문 SEC vs 한국 사업보고서)
        if overlay.get('biz_grep'):
            base['biz_grep'] = overlay['biz_grep']
        # 모멘텀 트리거에 지역 특화 추가
        base['momentum_triggers'] = base.get('momentum_triggers', []) + overlay.get('momentum_extra', [])
    base['country'] = country.upper()
    return base


# ============================================
# v5.3 KR/US 지역별 오버레이 (옵션 A, 2026-05)
# ============================================
# - macro_extra: 해당 지역 특화 거시 데이터 소스
# - biz_grep: 사업보고서/SEC grep 키워드 (KR=한국어, US=영문)
# - momentum_extra: 지역별 모멘텀 트리거
SECTOR_REGION_OVERLAY = {
    "KR": {
        "반도체": {
            "macro_extra": ["KIDB 메모리 통계", "관세청 반도체 수출"],
            "biz_grep": ["HBM", "DRAM", "NAND", "파운드리", "캐파", "가동률", "미세공정",
                         "8단", "12단", "재고일수", "ASP", "AI 반도체", "고객사"],
            "momentum_extra": ["KIDB 월간 메모리 수출", "한은 기준금리"]
        },
        "금융/은행": {
            "macro_extra": ["한은 금융안정보고서", "FSS 은행 통계", "예보 금융통계"],
            "biz_grep": ["NIM", "순이자마진", "BIS", "CET1", "대손비용", "Coverage Ratio",
                         "부실채권", "NPL", "충당금", "ROE", "K-IFRS"],
            "momentum_extra": ["한은 기준금리 결정 (분기)", "FSS 충당금 정책"]
        },
        "소비재/유통": {
            "macro_extra": ["통계청 소매판매", "한국유통학회"],
            "biz_grep": ["동일점포", "SSS", "점포당 매출", "회전율", "GMV", "온라인 비중", "PB"],
            "momentum_extra": ["통계청 월간 소매판매", "정부 내수 진작 정책"]
        },
        "건설/인프라": {
            "macro_extra": ["국토교통부 주택통계", "한국건설산업연구원", "주택산업연구원"],
            "biz_grep": ["수주잔고", "분양", "착공", "준공", "PF", "프로젝트 파이낸싱",
                         "원가율", "GPM", "해외 수주", "토목"],
            "momentum_extra": ["월별 분양 데이터", "정부 SOC 예산 / 부동산 규제"]
        },
        "자동차": {
            "macro_extra": ["한국자동차산업협회 (KAMA)", "한국수입자동차협회"],
            "biz_grep": ["판매대수", "ASP", "M/S", "시장점유율", "EV 비중", "하이브리드",
                         "현지 생산", "관세", "환율 민감도"],
            "momentum_extra": ["KAMA 월간 판매", "환율 (USD/KRW)"]
        },
        "항공": {
            "macro_extra": ["한국공항공사 통계", "인천공항공사"],
            "biz_grep": ["RPK", "ASK", "PLF", "탑승률", "운임", "Yield", "유류비",
                         "환율 민감도", "여객", "화물", "노선"],
            "momentum_extra": ["인천공항 월별 여객", "유가 (Dubai 기준)"]
        },
        "조선/방산": {
            "macro_extra": ["한국방위산업진흥회 (KDIA)", "한국조선해양플랜트협회"],
            "biz_grep": ["수주잔고", "수주잔량", "신조선가", "LNG선", "VLCC", "방산 수주",
                         "해외 수주", "K-2", "K-9", "MRO"],
            "momentum_extra": ["국방예산안 통과", "K-2/K-9 해외 수출 발표"]
        },
        "화학": {
            "macro_extra": ["한국석유화학협회 (KPIA)", "정유산업협회"],
            "biz_grep": ["스프레드", "PE", "PP", "PVC", "에틸렌", "프로필렌", "PX",
                         "가동률", "정제 마진", "납사"],
            "momentum_extra": ["KPIA 분기 통계", "원유 가격 (Dubai)"]
        },
        "보험/MCO": {
            "macro_extra": ["한국보험연구원", "보험개발원"],
            "biz_grep": ["손해율", "사업비율", "Combined Ratio", "RBC", "K-ICS", "신계약가치",
                         "MCR"],
            "momentum_extra": ["K-ICS 자본비율", "분기 손해율 가이던스"]
        },
        "통신": {
            "macro_extra": ["과학기술정보통신부 통신통계", "한국통신사업자연합회"],
            "biz_grep": ["ARPU", "가입자", "5G 침투율", "MVNO", "주파수 경매",
                         "Capex", "Spectrum", "B2B"],
            "momentum_extra": ["과기정통부 5G 가입자 통계", "주파수 경매 일정"]
        },
        "리츠/부동산": {
            "macro_extra": ["한국부동산원", "한국리츠협회"],
            "biz_grep": ["FFO", "AFFO", "NOI", "임대율", "공실률", "Cap Rate",
                         "NAV", "LTV", "WALE"],
            "momentum_extra": ["부동산원 분기 자산가격 동향", "한은 기준금리"]
        },
        "지주회사": {
            "macro_extra": ["KOSPI 지주사 지수", "공정거래위원회 지주사 통계"],
            "biz_grep": ["NAV", "할인율", "자회사", "지분율", "배당수익", "사업회사",
                         "순현금", "차입금"],
            "momentum_extra": ["자회사 IPO·합병 발표", "공정위 지주사 정책"]
        },
        "미디어/엔터": {
            "macro_extra": ["한국콘텐츠진흥원 (KOCCA)", "한터차트", "써클차트"],
            "biz_grep": ["IP", "음반", "공연", "투어", "MD", "라이선스", "글로벌 매출",
                         "스트리밍", "구독자", "ARPU"],
            "momentum_extra": ["한터/써클차트 주간 음반", "K-POP 글로벌 차트"]
        },
        "바이오/제약": {
            "macro_extra": ["식약처 (MFDS)", "한국바이오협회"],
            "biz_grep": ["임상", "Phase 1/2/3", "FDA", "MFDS", "라이선스 아웃", "마일스톤",
                         "파이프라인", "특허 만료", "바이오시밀러", "CMO/CDMO"],
            "momentum_extra": ["MFDS 승인 일정", "분기 임상 결과"]
        },
        "2차전지": {
            "macro_extra": ["SNE Research (KR 본사)", "관세청 2차전지 수출"],
            "biz_grep": ["GWh", "ESS", "양극재", "음극재", "전해질", "분리막", "LFP", "삼원계",
                         "전고체", "수주잔고", "OEM"],
            "momentum_extra": ["관세청 월간 2차전지 수출", "정부 IRA 대응 정책"]
        },
        "플랫폼/IT": {
            "macro_extra": ["한국인터넷진흥원 (KISA)", "통계청 e-커머스"],
            "biz_grep": ["MAU", "DAU", "ARPU", "GMV", "Take rate", "트래픽", "클라우드",
                         "구독", "광고", "커머스"],
            "momentum_extra": ["네이버/카카오 분기 MAU", "방통위 플랫폼 규제"]
        },
        "철강/비철금속": {
            "macro_extra": ["KOMIS 한국자원정보서비스", "한국비철금속협회",
                            "한국철강협회", "관세청 비철 수출입"],
            "biz_grep": ["LME", "구리", "신동", "압연", "황동", "전기동", "용해", "가공 마진",
                         "수주잔고", "방산 수주", "탄약", "용강", "철근", "HRC", "고로", "전기로"],
            "momentum_extra": ["KOMIS 월간 비철 가격", "방산 K-탄약 해외 수출"]
        }
    },
    "US": {
        "반도체": {
            "macro_extra": ["TechInsights", "Semiconductor Industry Association (SIA US)",
                            "Bureau of Economic Analysis (semi exports)"],
            "biz_grep": ["HBM", "DRAM", "NAND", "foundry", "capacity", "utilization",
                         "process node", "5nm", "3nm", "days of inventory", "ASP",
                         "AI accelerator", "customer concentration"],
            "momentum_extra": ["FOMC rate decision", "TSMC/Samsung Capex announcement",
                               "NVIDIA/AMD GPU launch"]
        },
        "금융/은행": {
            "macro_extra": ["FDIC Quarterly Banking Profile", "Fed Stress Test (CCAR)",
                            "Federal Reserve H.8 Weekly"],
            "biz_grep": ["NIM", "net interest margin", "CET1", "credit loss provision",
                         "non-performing loan", "NPL", "allowance", "ROE", "GAAP"],
            "momentum_extra": ["FOMC decision", "CCAR results (June)"]
        },
        "소비재/유통": {
            "macro_extra": ["US Census Retail Sales", "NRF (National Retail Federation)",
                            "Conference Board Consumer Confidence"],
            "biz_grep": ["same-store sales", "comparable sales", "comp", "store count",
                         "GMV", "online penetration", "private label", "PB"],
            "momentum_extra": ["Census monthly retail", "Holiday season (Q4) sales"]
        },
        "건설/인프라": {
            "macro_extra": ["NAHB Housing Market Index", "Census Construction Spending",
                            "AIA Architecture Billings"],
            "biz_grep": ["backlog", "new orders", "starts", "completions",
                         "gross margin", "GPM", "international", "infrastructure"],
            "momentum_extra": ["Monthly housing starts (Census)", "Federal infrastructure spending"]
        },
        "자동차": {
            "macro_extra": ["NADA (National Auto Dealers)", "Bureau of Economic Analysis",
                            "Ward's Auto Sales"],
            "biz_grep": ["units sold", "ASP", "market share", "EV mix", "hybrid",
                         "local production", "tariff", "USMCA", "IRA"],
            "momentum_extra": ["Monthly US auto sales", "DOE EV sales data"]
        },
        "항공": {
            "macro_extra": ["BTS T-100 (Bureau of Transportation Statistics)",
                            "FAA Air Traffic", "DOT Form 41"],
            "biz_grep": ["RPK", "ASK", "load factor", "PLF", "yield", "fuel cost",
                         "passenger", "cargo", "route"],
            "momentum_extra": ["BTS monthly enplanements", "Jet fuel price (USGC)"]
        },
        "조선/방산": {
            "macro_extra": ["DoD Budget Justification", "GAO Defense Reports",
                            "SIPRI Arms Transfers Database"],
            "biz_grep": ["backlog", "orders", "newbuild prices", "LNG carrier",
                         "defense", "international orders", "MRO", "production rate"],
            "momentum_extra": ["Pentagon budget submission (Feb)", "Foreign Military Sales (FMS)"]
        },
        "화학": {
            "macro_extra": ["ACC (American Chemistry Council)", "ICIS US",
                            "EIA Petroleum (WTI)"],
            "biz_grep": ["spread", "ethylene", "propylene", "PVC", "PE", "PP",
                         "utilization", "cracker margin", "naphtha"],
            "momentum_extra": ["ICIS monthly spread", "WTI crude price"]
        },
        "보험/MCO": {
            "macro_extra": ["NAIC (National Association of Insurance Commissioners)",
                            "AM Best US Ratings", "CMS National Health Expenditure"],
            "biz_grep": ["loss ratio", "expense ratio", "combined ratio", "RBC",
                         "MLR", "Medical Loss Ratio", "MCR", "membership"],
            "momentum_extra": ["CMS Medicare Advantage rate notice", "Quarterly MLR guidance"]
        },
        "통신": {
            "macro_extra": ["FCC Broadband Reports", "CTIA Wireless Indicator",
                            "Pew Research Mobile"],
            "biz_grep": ["ARPU", "subscribers", "5G penetration", "MVNO", "spectrum auction",
                         "Capex", "B2B", "fiber"],
            "momentum_extra": ["FCC spectrum auction", "Quarterly subscriber net adds"]
        },
        "리츠/부동산": {
            "macro_extra": ["NAREIT", "JLL US Market Reports", "CoStar"],
            "biz_grep": ["FFO", "AFFO", "NOI", "occupancy", "vacancy", "Cap Rate",
                         "NAV", "LTV", "WALE", "tenant"],
            "momentum_extra": ["FOMC decision (cap rate impact)", "JLL quarterly cap rate"]
        },
        "지주회사": {
            "macro_extra": ["S&P 500 Conglomerates Index", "Closed-End Fund Discount"],
            "biz_grep": ["NAV", "discount", "subsidiary", "stake", "dividend income",
                         "operating company", "net cash", "buyback"],
            "momentum_extra": ["Subsidiary IPO/spin-off", "Activist investor"]
        },
        "미디어/엔터": {
            "macro_extra": ["MPA (Motion Picture Association)", "Luminate (US)",
                            "Nielsen Streaming Reports"],
            "biz_grep": ["IP", "content library", "subscribers", "ARPU", "churn",
                         "advertising tier", "licensing", "global revenue"],
            "momentum_extra": ["Netflix/Disney quarterly subs", "Theatrical release calendar"]
        },
        "바이오/제약": {
            "macro_extra": ["FDA Drug Approval Database", "Clinical Trials.gov",
                            "BioPharma Catalyst", "EvaluatePharma"],
            "biz_grep": ["clinical trial", "Phase 1/2/3", "FDA", "PDUFA",
                         "license out", "milestone", "royalty", "pipeline",
                         "patent expiry", "biosimilar", "CMO/CDMO"],
            "momentum_extra": ["PDUFA date", "Phase 2/3 readout calendar"]
        },
        "2차전지": {
            "macro_extra": ["BloombergNEF EV Outlook (US)", "EIA Battery Storage",
                            "DOE Energy Storage Reports"],
            "biz_grep": ["GWh", "ESS", "cathode", "anode", "electrolyte", "separator",
                         "LFP", "NCM", "solid-state", "backlog", "OEM"],
            "momentum_extra": ["IRA tax credit policy", "OEM contract announcement (Ford/GM)"]
        },
        "플랫폼/IT": {
            "macro_extra": ["Gartner US IT Spending", "IDC US",
                            "eMarketer US Digital Ad", "Synergy Research Cloud Share"],
            "biz_grep": ["MAU", "DAU", "ARPU", "GMV", "take rate", "traffic", "cloud",
                         "AI Capex", "subscription", "advertising", "commerce"],
            "momentum_extra": ["FOMC (rate sensitivity)", "Earnings call AI Capex guidance"]
        },
        "철강/비철금속": {
            "macro_extra": ["AISI (American Iron and Steel Institute)",
                            "USGS Mineral Commodity Summaries",
                            "Comex Copper Futures", "World Bank Pink Sheet"],
            "biz_grep": ["LME", "Comex", "copper", "brass", "rolling", "fabrication margin",
                         "backlog", "ammunition", "defense orders", "HRC", "rebar",
                         "blast furnace", "EAF"],
            "momentum_extra": ["LME monthly copper price", "DoD ammunition contracts (FMS)"]
        }
    }
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
