# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

주식 AI 리서치 리포트 자동 생성 시스템. DART(한국 전자공시), 한국투자증권 OpenAPI, SEC EDGAR(미국), FnGuide에서 재무제표·사업보고서·시세·컨센서스를 수집하고, **v5.0 12섹션 구조 (CFA Institute 표준 + IB + 한국 일류 통합)** 증권사 수준 리포트를 자동 생성한다. v4 21섹션 구조도 하위 호환.

**산출 경로 2종 (공용 수집 → analysis.json → 분기)**:
- **`/research`** → `generate_all.py` → **단일 상세 PDF** (Navy/Gold, HTML→PDF). 기본 경로.
- **`/wf-report`** → `generate_word_wf.py` → **위닝펀드 스타일 Word(.docx)** + 본문 소제목에 맞는 도표 하이브리드 삽입. 데이터 수집·analysis.json은 `/research`와 동일 자산 공용, 산출 포맷·도표·검증만 별도. 상세: `## Word 리포트 파이프라인` 섹션.

## Development Setup

필수 의존성 (최초 1회):
```bash
pip install finance-datareader   # STEP 1.7 5년 연말 종가 정확 조회용 (WebSearch 추정 금지)
pip install yfinance             # US 종목 forward estimates, 52주/PBR/BPS fallback
playwright install chromium      # generate_all.py HTML->PDF 변환용
```

`FinanceDataReader`가 없으면 `/research` STEP 1.7이 ImportError로 실패하고 역사 밴드가 추정치로 돌아가 JYP 사건이 재발한다.

**환경변수 설정 (v4.11 자동 로드):** `kis_api.py` / `dart_api.py` 가 import 시점에 **자동으로 `.env` 탐색 로드**한다. 탐색 순서:
1. `scripts/../.env` (프로젝트 루트)
2. `scripts/../../.env` (상위 폴더, 예: `C:\Users\hsh\Desktop\vibecoding\.env`)
3. `scripts/../../../.env` (상위상위)

**우선순위**: shell 에서 이미 export 된 환경변수가 있으면 그것이 우선. 따라서 `source <(grep ...)` 명령은 **더 이상 필수가 아니다** -- `python scripts/kis_api.py` 실행만으로 자동 로드.

**상위 폴더 `.env` 한 곳만 관리하는 구조**가 권장된다 (여러 프로젝트 공용). 프로젝트 폴더 `.env`는 불필요하며 삭제해도 무방.

**KIS_BASE_URL 중요**: 실전 계좌는 `https://openapi.koreainvestment.com:9443`, 모의투자는 `https://openapivts.koreainvestment.com:29443`. **실전에서만 Peer PER/PBR 정상 반환** (모의투자는 PER/PBR/EPS/BPS 모두 0 반환하여 Peer 비교 불가 -- SK하이닉스 v1 사고 원인).

## Key Commands

```bash
# 전체 스킬 실행 (Claude Code 슬래시 커맨드)
/research {종목명 또는 티커}      # PDF 리포트
/wf-report {종목명 또는 티커}     # 위닝펀드 Word(.docx) 리포트 (도표 하이브리드)

# 리포트 생성 (analysis JSON -> 단일 상세 PDF, Navy/Gold v3, v5.0 12섹션 자동 감지)
python scripts/generate_all.py scripts/analysis_{종목명}.json

# Word 리포트 빌드 (/wf-report 경로: 계획 -> 생성 -> 검증)
python scripts/wf_chart_planner.py {종목명} scripts/analysis_{종목명}.json
python scripts/generate_word_wf.py {종목명} scripts/analysis_{종목명}.json data/{종목명}/chart_plan.json
python scripts/verify_docx.py {종목명}

# 사전 차단 검증 (v5.4 신설, STEP 4 직후 의무)
python scripts/preflight_check.py {종목명}

# 마크다운 검토 게이트 (v4.21 신설, PDF 전 사용자 검토)
python scripts/analysis_to_md.py {종목명}

# 재무 데이터 자동 요약 - 한국 (KIS+DART+FnGuide 통합)
python scripts/financial_summary.py {종목명} {종목코드}

# FnGuide 5년 실적 + 3년 컨센 (KR 종목 전용, v5.4 신설)
python -c "import sys; sys.path.insert(0, 'scripts'); from fnguide_data import get_financial_data, get_consensus_estimates; import json; d = {'financial': get_financial_data('{종목코드}'), 'consensus_estimates': get_consensus_estimates('{종목코드}')}; print(json.dumps(d, ensure_ascii=False, indent=2, default=str))"

# 재무 데이터 자동 요약 - 미국 (SEC EDGAR + KIS + yfinance)
python scripts/financial_summary_us.py {TICKER} [EXCD]
# EXCD: NAS(나스닥, 기본), NYS(뉴욕), AMS(아멕스). 주요 NYSE 종목은 자동 감지.

# 5Y PER/PBR 밴드 + Beta + Peer 병렬 (STEP 1.5)
python scripts/fdr_band.py {종목명} {종목코드}
python scripts/volatility_beta.py {종목명} {종목코드}
python scripts/peer_snapshot.py {종목명} {업종키}  # semicon/auto/retail/finance 등

# 검증 3종 병렬 (STEP 6, KR/US 자동 분기)
python scripts/verify_numbers.py {종목명}    # KR
python scripts/verify_numbers_us.py {TICKER} # US (B12~B15 추가)
python scripts/verify_style.py {종목명}      # C1~C20 (KR/US 공통)
python scripts/verify_facts.py {종목명}      # D1~D6 (KR/US 공통)

# 사업보고서 핵심 인용 추출
python scripts/report_extractor.py data/{종목명}/data_dart_reports.json

# 스킬 코드 블록 또는 scripts/* 변경 후 문법 체크
python -c "import py_compile; py_compile.compile('scripts/generate_all.py', doraise=True)"

# PDF 페이지 + 빈 페이지 점검 (v5.4 규칙 12 -- 호텔신라 38p 사고 후)
python -c "import fitz; doc = fitz.open('output/{종목명}/report_{종목명}_상세.pdf'); print(f'페이지: {len(doc)}p')"
```

`scripts/*.py` 중 `dcf_calculator.py`, `nav_calculator.py`, `industry_kpi.py`는 CLI가 아닌 **import 전용**이다. `kis_api.py`/`dart_api.py`/`sec_edgar.py`는 래퍼 라이브러리이며 직접 실행하지 않는다.

## Architecture

```
데이터 수집 (병렬)          분석/검증              리포트 생성 (v3)
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────────┐
│ dart_api.py      │    │ financial_       │    │ generate_all.py      │
│  → 재무제표 3년   │───→│  summary.py      │───→│  → 단일 상세 PDF      │
│  → 사업보고서 5개  │    │  (자동 정리+검증)  │    │  (Navy/Gold v3)      │
│                  │    │                  │    │  HTML→PDF (Playwright) │
│ kis_api.py       │    │ report_          │    │                      │
│  → 현재가/수급    │───→│  extractor.py    │    │ 마크다운 풀 파싱       │
│  → 일봉 120일    │    │  (인용 문장 추출)  │    │ 이모지 자동 strip      │
│                  │    │                  │    │ 자동 품질 검증 9개      │
│ sec_edgar.py     │    │ dcf_calculator   │    │                      │
│  → US 재무제표    │    │ nav_calculator   │    │                      │
│  → 10-K/10-Q    │    │ industry_kpi     │    │                      │
└─────────────────┘    └──────────────────┘    └──────────────────────┘
```

**v3 변경사항 (2026-04):** 이전 3개 파일 (상세PDF + 요약PDF + 대시보드HTML)에서 **단일 상세 PDF**로 통합. Word/docx 기반에서 HTML/CSS Navy/Gold 디자인으로 전환. 21섹션 자연 흐름 + Cover/Executive/Final Call 풀 페이지.

## Data Flow

```
한글 입력 -> KR 종목: DART + KIS API -> data/{종목명}/
영문 입력 -> US 종목: SEC EDGAR + KIS 해외 + yfinance -> data/{TICKER}/

data/{종목명}/                         data/{TICKER}/
├── data_dart_financials.json          ├── data_sec.json (XBRL 재무+10-K/10-Q 본문)
├── data_dart_reports.json             ├── data_kis_us.json (현재가, 일봉)
├── data_kis.json                      └── financial_summary.json (SEC+KIS+yfinance 통합)
├── data_kis_financials.json
├── financial_summary.json
└── report_quotes.json

scripts/analysis_{종목명}.json -> generate_all.py -> output/{종목명}/
```

## API Configuration

API 키는 `.env` 파일에서 환경변수로 관리 (하드코딩 fallback 제거됨, 미설정 시 경고):
- `DART_API_KEY` -- DART 전자공시 API
- `KIS_APP_KEY`, `KIS_APP_SECRET` -- 한국투자증권 OpenAPI (KR + US 해외주식 모두 사용)
- `KIS_BASE_URL` -- 기본: `https://openapivts.koreainvestment.com:29443` (모의투자)
- yfinance는 API 키 불필요 (US 종목 forward estimates/52주/PBR fallback용)

## ⚠️ KIS API 반환 스키마 — 한글 키 사용

`kis_api.py`의 래퍼 함수는 **한글 키**로 dict을 반환한다. KIS 원시 API의 영문 필드명(`stck_prpr`, `hts_avls`, `per` 소문자 등)은 래퍼 내부에서만 쓰이고, 사용자 코드는 한글로 접근해야 한다. 이 규칙을 몰라서 JYP v1에서 Peer 시총·PER이 전부 0으로 저장되는 사고 발생.

```python
# get_current_price(code) 반환 키 (모두 한글)
# 현재가(원), 전일대비(원), 등락률(%), 거래량(주), 거래대금(원), 시가(원), 고가(원), 저가(원),
# 52주최고(원), 52주최저(원), 시가총액(억원), PER(배), PBR(배), EPS(원), BPS(원)

# get_daily_price(code, days) → list[dict]  (키 한글)
# 날짜, 시가(원), 고가(원), 저가(원), 종가(원), 거래량(주)

# get_investor_trend(code, days) → dict
# 외국인_순매수(주식수), 기관_순매수(주식수), 개인_순매수(주식수), detail:[{date, 외국인(주), 기관(주), 개인(주)}, ...]
# ⚠️ 단위는 **주식수(주)**. 거래대금 원하면 × 현재가로 변환.
# 예: -41,367,064 = -4,137만주 × 216,000원 = -8.94조원 상당 순매도
```

**절대 금지:**
- `px.get("per", 0)` (소문자) / `px.get("stck_prpr", 0)` — 항상 0 반환
- `investor_trend.외국인_순매수`를 원/백만원 단위로 읽기 — 주식수 단위다

**올바름:** `px.get("PER", 0)` / `px.get("현재가", 0)` / `px.get("시가총액", 0)`.

**투자자 매매 수급 맥락화 공식** (s17에 반영):
```python
외국인_20일_거래대금 = abs(외국인_순매수) × 현재가   # 원 단위
일평균_거래대금 = 외국인_20일_거래대금 / 20         # 원/일
유동주식_대비_비중 = 외국인_순매수 / 발행주식수 × 100  # %
```
이 공식 없이 "주식수" 숫자를 원 단위로 자의 해석하면 삼성전자 v4.9 사고처럼 **수급 서사가 10배 이상 왜곡**되며 report-critic도 같은 오류를 공유하게 된다.

## 변수 명명 및 임시 파일 규칙 (재발 방지)

**변수 shadowing 금지** — `/research` 스킬 내 코드 블록에서:
- `stock_name` = 본 종목 (예: `"JYP"`) — 파일 경로에 쓰인다
- `stock_code` = 6자리 종목코드 (예: `"035900"`)
- `peer_name` / `peer_code` = Peer 루프 변수 — 절대 `name` / `code` 로 쓰지 말 것
- 사고 사례: `for name, code in peer_codes.items():` → 루프 후 `name`이 마지막 Peer 이름으로 덮여서 `data/{name}/_peer_snapshot.json` 가 잘못된 폴더에 저장됨

**임시 Grep 덤프 파일은 반드시 `data/{종목명}/` 하위** — STEP 2.5에서 사업보고서 섹션을 파일로 덤프할 때:
```python
# O 올바름
out_path = f'data/{stock_name}/_tmp_r{idx}_{short}.txt'

# X 잘못 (프로젝트 루트 오염 → 다음 /research 실행 시 다른 종목과 혼입)
out_path = f'_tmp_r{idx}_{short}.txt'
```

**Grep 경로 지정 필수** — `Grep pattern="지역별" path="data/{종목명}" glob="_tmp_*.txt"`. path 생략하면 루트의 잔재 덤프가 섞인다.

**콘솔 출력/경고 메시지에 em-dash(`—`), 기타 특수 유니코드 금지** — Windows cp949 콘솔에서 `UnicodeEncodeError` 발생. 하이픈 `-` 또는 `--` 사용. 이모지도 동일 사유로 금지 (PDF 본문은 예외로 `★☆` 별점만 허용).

## Key Scripts

| Script | Purpose |
|---|---|
| `dart_api.py` | DART API 래퍼. `get_corp_code()`, `get_consolidated_statements()`, `get_all_reports()` |
| `kis_api.py` | 한투 API 래퍼. 18req/sec 제한. `get_current_price()`, `get_investor_trend()`, `get_daily_price()` |
| `sec_edgar.py` | SEC EDGAR 래퍼. US 종목 재무제표 + 10-K/10-Q |
| `financial_summary.py` | KR: DART/KIS 원본 -> 손익+재무상태+현금흐름+비율 자동 정리. 이상치 경고 |
| `financial_summary_us.py` | US: SEC EDGAR XBRL + KIS 해외주식 + yfinance -> 동일 포맷 재무 요약. Forward PE/EPS/타겟 포함 |
| `generate_all.py` | analysis.json → **단일 상세 PDF** (Navy/Gold v3, HTML→PDF). 마크다운 파싱 + 이모지 strip + 자동 품질 검증 9개 |
| `verify_numbers.py` | **KR 종목 전용** B1~B11 수치 정합성 자동 검증 (시총/현재가/PER/PBR/EPS/52주/수급/순현금/EBITDA/EPS/신용등급/R/R/Wisereport) |
| `verify_numbers_us.py` | **US 종목 전용** (v4.15 신설) B1~B15 자동 검증 (위 KR 항목 + Stock Split 자동 감지 + GAAP/Non-GAAP 분리 + EPS×주식=NI 산술 일관성 + DCF vs Base 50%+ 괴리 경고). **B17 (v4.17 신설)**: 본문 FCF/순부채/시총 변종 자동 감지 (3종+ 고유값 등장 시 WARN, 시점 라벨 수동 확인 권고) |
| `verify_style.py` | 서술 품질 **C1~C20** (총점 100). C1~C6: 불릿/용어풀이/소제목/톤/시사점/자연어비중. C7~C10: 라벨형 소제목/영문 직역/100자+ 문장/위트 인용. **C11~C20**: C11 `한 줄 평가:` 콜론 뒤 ≤30자, C13 결론 선행 박스, C14 벤치마크 비교 5건+, C15 5단 메커니즘(`→` 카운트), C19 좋은 패턴(수치+델타+출처, `→`·`+X% YoY` 30건+). **목표는 톤 의존**: 위닝펀드 장식 톤 95+ / 참고-리포트 톤(`/wf-report` 2026-06 권장) 85±. C10 위트인용·C13 한줄평가 등은 장식이라 참고-리포트 톤에선 빠짐(정상). KR/US 공통 |
| `verify_facts.py` | 팩트 체크 D1~D4 (사업보고서 인용 실존/외부 출처/증권사 목표가/Peer 테이블) -- KR/US 공통 |
| `report_extractor.py` | 사업보고서 → 핵심 인용문 + 전년대비 변화점 자동 추출 |
| `dcf_calculator.py` | FCF 기반 DCF 3시나리오 + 민감도 테이블 |
| `nav_calculator.py` | 지주회사/리츠 NAV 계산 |
| `industry_kpi.py` | 업종별 추가 검색 키워드 + 필수 분석 항목 (16개 섹터 매트릭스) |
| `preflight_check.py` | **(v5.4 신설)** STEP 4 직후 사전 차단 8개: em-dash 자동 치환 / JSON control char fix / Peer KIS 1:1 검증 / 컨센 일치성 / ASCII 트리 / PER 시점 / forward_per 정합 / opinion 정합 |
| `fnguide_data.py` | **(v5.4 신설)** KR 종목 FnGuide SVD_Main 5년 연간 실적 + 3년 컨센 추정 + 분기 실측 (`pd.read_html` 직접, Chrome MCP 불필요). 풍산 v1 \"매출/OP 0원\" 사고 차단 |
| `analysis_to_md.py` | **(v4.21 신설)** STEP 4.5 마크다운 검토 게이트. 12섹션 + Executive Summary Card 자동 검증 + 사용자 friendly 리뷰 가능 |
| `wisereport_scraper.py` | Chrome MCP 실패 시 Playwright 백업 (Wisereport 컨센 추이) |
| `fdr_band.py` | FDR (FinanceDataReader) 5년 PER/PBR 밴드 + z-score 자동 산출 |
| `volatility_beta.py` | Beta (KOSPI200/KOSDAQ150 회귀) + σ_annual + R² 정식 산출 |
| `peer_snapshot.py` | KR Peer KIS API 실시간 시총/PER/PBR 일괄 조회 (JYP v1 추정 사고 차단) |
| `wf_charts.py` | **(/wf-report 전용, import)** generic 도표 12 아키타입 라이브러리. `render(archetype, data, None, out_dir, name)` |
| `wf_chart_planner.py` | **(/wf-report)** analysis.json → `data/{종목}/chart_plan.json` (섹션 카탈로그 + 본문 키워드 하이브리드). `[OK]`=데이터 준비, `[제안]`=본문 근거로 채울 특수 도표 |
| `generate_word_wf.py` | **(/wf-report)** analysis.json + chart_plan.json → `output/{종목}/report_{종목}.docx`. 마크다운 풀파싱 + 도표 소제목 매칭 삽입. `_EMOJI` strip은 `→`·`★☆` 보존(2026-06 패치) |
| `verify_docx.py` | **(/wf-report)** Word 전용 D1~D6 (도표 이미지 수 == 준비 도표 / 캡션 / 출처선 / 이모지 잔재 / 표지 / 섹션 헤더). `★☆` 별점 허용 |

**STEP 6 검증 자동 분기 규칙 (v4.15)**:
- `data/{종목명}/data_kis.json` 존재 → KR 종목 → `verify_numbers.py`
- `data/{TICKER}/data_kis_us.json` 존재 → US 종목 → `verify_numbers_us.py`
- 잘못된 스크립트 사용 시 \"data 파일 없음\" 에러로 자동 검증 무력화 → NFLX/PANW v1 14건 결함 사고 재발 위험.

## generate_all.py 자동 검증 항목

generate_all.py 실행 시 아래를 자동 검증하며, [ERROR]는 생성 중단, [WARN]은 경고 출력:
1. EPS 교차검증 (현재가/PER vs JSON)
2. 사업보고서 인용 건수
3. "왜?" 분석 키워드 수 (< 5 경고)
4. R/R vs BUY 일치성
5. 현재가 0원 체크
6. **시총 KIS vs JSON 교차검증** (2배+ 차이 시 생성 중단)
7. 재무 테이블 이상값 (이익률 100%+, PER 5000+)
8. Bear/Base/Bull 순서 검증
9. 배당수익률 20%+ 체크
10. **Peer 테이블 정확성** (`_peer_snapshot.json`과 교차 대조, 30%+ 차이 시 ERROR) — JYP v1 사고 방지
11. **역사 밴드 정확성** (`_per_band.json` 존재 + current_per가 JSON과 5% 이내 일치)

KIS 파일 읽기 실패 시 이제 경고를 남긴다 (과거: 조용히 pass). Peer/역사밴드 파일이 없으면 STEP 1.7/2.3을 건너뛴 것으로 간주하고 경고.

## Word 리포트 파이프라인 (`/wf-report`, 2026-06 도입)

`/research`(PDF)와 **데이터 수집·`analysis.json`을 공용**으로 쓰되 산출만 Word로 분기하는 두 번째 경로. 스킬 정의는 `.claude/commands/wf-report.md`. 전체 흐름:

```
(공용) financial_summary/fnguide/fdr_band/peer_snapshot/volatility_beta + DART 정독
  → analysis.json (정규 12키 + alias, /research와 동일 스키마)
  → wf_chart_planner.py  → chart_plan.json (도표 약 10종 계획, [제안]은 본문 근거로 수동 채움)
  → generate_word_wf.py  → output/{종목}/report_{종목}.docx (meta.section_order 7섹션 렌더, 도표 소제목 매칭 삽입)
  → verify_docx.py + verify_numbers.py + verify_style.py (3종, 목표 0 FAIL / 6-6 / style 85±)
  → 시각 QA: docx→pdf(docx2pdf/soffice)→png(fitz)  → (핵심 포지션) report-critic 서브에이전트
```

**작성 컨벤션 (2026-06 대개편 -- 전체 디테일은 스킬 정의 `.claude/commands/wf-report.md` 가 단일 출처):**
- **idempotent 빌더 `scripts/_build_{종목}.py`**: dict 구성 → **alias 키 재생성**(v5.0 키 스킴 분열 대응) → `os.replace` 단일 원자 dump. critic/검증 정정도 빌더 Edit 후 재실행(손 JSON 금지).
- **위닝펀드 7섹션 구조**: 요약 → 산업분석 → 기업분석 → 투자포인트 → 재무분석 → 리스크 → 밸류에이션. 내부는 v5.0 12키로 작성하되 빌더에서 보조섹션을 호스트에 **병합**(경영전략→기업 / 실적·컨센+수급→재무 / 액션→밸류 / ESG 제외)하고 **`meta.section_order`** 로 렌더 순서 지정(`generate_word_wf` 가 읽음, **미지정 시 12키 CANON** 이라 다른 리포트 무영향). 병합으로 미렌더되는 섹션의 차트는 호스트로 재매핑(s10·s11→s06, s12→s07).
- **참고-리포트 톤 (장식 절제, 2026-06 톤 전환 -- 기존 "입체화 의무" 폐기)**: 위닝펀드 장식(★채점표·`### 한 줄 평가:`·`시사점:` 라벨·`> 위트 인용`)을 **제거**하고, 정독한 증권사 리포트(교보·삼성)식 **평서 산문 + 데이터 표**로 쓴다. 분석 틀(비교·산정·점검 표)은 유지하되 강도 열은 ★ 대신 텍스트(매우 강함/강함/보통/약함). **verify_style 목표는 톤 의존 -- 참고-리포트 톤 85± 가 정상**(장식 쓰면 95+). 점수 위해 장식을 도로 넣지 말 것(numbers·docx 만 0 FAIL 필수).
- **밸류에이션 = 알고리즘 자체 산출**: 브로커 목표가 복붙 금지. 그 회사 애널리스트가 쓰는 방법의 *원리*를 이해해(지주=SOTP / 단일사업=정상화 EPS×Target PER / 사이클=정상화 EPS·EV/EBITDA / 자산=NAV / 적자·성장=DCF·Forward), 입력값만 넣으면 재현되는 단계 계산 + **감도분석**으로 직접 도출(Python 산술 검증, verify B12). near-term Forward PER이 비싸면 솔직히 인정(EPS 부풀려 "저평가" 만들지 말 것 -- 순이익이 이자보상배율 등 자기 서술과 산술 모순 금지).
- **broker명 본문 제거**: "X증권에 따르면/(삼성)/(교보)" 등 특정 broker 인용 제거(일반 "증권사"는 허용). per-broker 목표가 표 대신 범위/티어 집계, 컨센은 `financial_summary.json` 현행값으로 갱신(**stale 주의** -- 3개월 전 목표가·단일 브로커 EPS 금지).
- **정독 의무 (작성 전)**: 산업 3+·기업 3+ 애널리스트 리포트를 `fitz` 로 텍스트+차트 PNG 정독 + **DART 전자공시 사업보고서 전수 정독**(1차 출처). ⚠️`get_all_reports` 요약본은 15,000자 truncate + 「I. 회사의 개요」(연혁·자본금·주식총수) 누락 → 전수 정독은 `download_report_document`+`html_to_text` 로 **전문**을 받아 「I. 회사의 개요」+「II. 사업의 내용」의 **모든 소제목**(지역별 매출·부문별 손익/자산·생산능력/가동률·주주환원/자사주소각·시장점유율·주요계약)을 읽는다. 서사·수치·밸류 방법을 **재구성**(전재 금지, 인용 박스는 원문 grep 매칭 후 100% 복사). **내용 성격으로 유동 배치**(리포트 종류로 섹션 고정 ❌). 데이터 시점은 발간일이 아니라 **작성 당일 `WebSearch` 로 갱신**.

**렌더 함정 (2026-06 root fix 완료):**
- `generate_word_wf._EMOJI` 와 `verify_docx._EMOJI` 가 과거 **`→`(U+2190~21FF)와 `★☆`(U+2605~6)를 strip** → `500→750`이 `500750`으로 병합되고 해자표 ★ 강도 열이 공백이 되던 사고. 두 regex에서 carve-out 완료. **`→`·`★☆` 적극 사용 가능**하며 `→`는 verify_style C15/C19가 카운트하는 글자다 (ASCII `->`는 미카운트, 쓰지 말 것).
- **순현금 착시**: 결제 자회사 연결(예: 헥토파이낸셜) 종목은 연결 순현금에 정산 예수금·소수주주 귀속분이 섞임. "순현금 > 시총" 단정 금지, **SOTP + 예수금 caveat**로 보수 처리. 별도 상장 자회사 보유 시 SOTP(지분 시장가 + 본업 + 별도순현금)가 단일 PER보다 정확.

## analysis.json 구조

```json
{
  "meta": {"stock_name", "stock_code", "market", "country", "industry", "date", "currency", "tagline"},
  "price": {"current", "market_cap", "market_cap_num", "shares_outstanding", "per", "pbr", "eps", "bps", "forward_per", "forward_eps", ...},
  "opinion": {"rating", "type", "portfolio_role", "target_bear", "target_base", "target_bull", "risk_reward"},
  "segments": [{"name", "pct", "outlook"}],
  "financials": {"headers", "rows", "source"},
  "quarterly": {"headers", "rows", "year", "note"},
  "supply": {"foreign", "institution", "individual", "days", "comment"},
  "peers": [{"name", "market_cap", "per", "pbr", "note", "highlight"}],
  "catalysts": [{"date", "event", "impact"}],
  "sections": { /* v5.0 12섹션 또는 v4 21섹션 -- generate_all.py 자동 감지 */ }
}
```

**v5.0 12섹션 키** (2026-04 신설, generate_all.py auto-detect):
```
s01_opinion_thesis / s02_thesis_catalysts / s03_company_overview /
s04_industry_competition / s05_management_fieldcheck / s06_financial /
s07_valuation / s08_esg / s09_scenarios_risks / s10_earnings_consensus /
s11_supply_shareholder / s12_action_plan
```

**v4 21섹션 키** (하위 호환): s01_opinion ~ s21_reliability.

`market_cap_num`은 **억 단위** 정수. KIS API의 `시가총액` 필드와 반드시 일치해야 함. `shares_outstanding`은 v5.4 규칙으로 시총/현재가 통일 의무 (한미반도체 critic 결함 #2 사고 차단).

## ⚠️ v5.0 키 스킴 분열 + alias 키 필수 (2026-05 세션 실증, 3회 반복 함정)

**코드베이스에 v5.0 섹션 키가 두 종류로 갈려 있다.** 이걸 모르면 B/C/D·preflight가 거짓 FAIL을 내고 PDF 섹션이 비거나 점수가 깎인다.

- **`generate_all.py` (실제 PDF 생성기 = 정본)**: `_SECTION_TITLES_DETAILED_V5` 의 정규 12키만 렌더 — `s01_opinion_thesis / s02_thesis_catalysts / s03_company_overview / s04_industry_competition / s05_management_fieldcheck / s06_financial / s07_valuation / s08_esg / s09_scenarios_risks / s10_earnings_consensus / s11_supply_shareholder / s12_action_plan`. **analysis.json sections는 반드시 이 키로 작성.**
- **`verify_style.py` / `verify_facts.py` / `analysis_to_md.py` / `verify_numbers.py`(B6·B21)**: 구 v5.1 스킴(`s07_financial_analysis`, `s08_valuation`/`s09_valuation`, `s10_scenarios_risks`, `s11_earnings_consensus`, `s08_financial`, `s02_investment_points`, `s04_industry`, `s01_opinion`, `s13_thesis`, `s14_short_thesis`)을 읽는다. 정규 키만 있으면 이 스크립트들이 섹션을 못 찾아 C 점수 폭락·D6/B6 거짓 FAIL.

**해결 (의무)**: STEP 4 단일 Write 시 정규 12키 + **동일 내용 alias 키**를 함께 넣는다. `generate_all.py`는 정규 키만 순회하므로 alias 키는 PDF에 중복 렌더되지 않는다(안전). 표준 alias 매핑:
```python
s['s08_financial']=s['s06_financial']; s['s09_valuation']=s['s07_valuation']
s['s10_scenarios_risks']=s['s09_scenarios_risks']
s['s11_earnings_consensus']=s['s10_earnings_consensus']+'\n\n'+s['s11_supply_shareholder']
s['s02_investment_points']=s['s02_thesis_catalysts']; s['s04_industry']=s['s04_industry_competition']
s['s01_opinion']=s['s01_opinion_thesis']
# s13_thesis / s14_short_thesis 는 정규 12키에 없으므로 별도 작성 (수치+시사점+짧은 소제목 채워 C5/C7 통과)
```
critic 정정 후에도 정규 섹션을 수정했으면 **alias를 반드시 재생성**(stale alias = 검증이 옛 본문을 봄).

## v5.0 리포트 작성 실전 함정 (2026-05 세션 검증)

- **preflight C6 (PER 시점 키워드)**: `\bPER\s*\d` 패턴이 ±30자 내 시점 키워드(`후행/TTM/Forward/12M/연간/업종/2026E/5Y/Target/평균/컨센/실측`) 없으면 FAIL. **`선행`은 키워드 목록에 없다 → "선행 PER"는 반드시 "Forward PER"로** 쓸 것. 표 헤더·소제목의 "PER 5" 같은 표기도 "후행 PER 5"로.
- **preflight C7 (forward_per 정합)**: `price.forward_per` 값이 본문에 **문자 그대로** 등장해야 함. 본문이 "15.9"면 `forward_per`도 `15.9`(14.48→14.5처럼 반올림 일치)로 맞출 것.
- **verify_numbers B6 (순현금)**: `financial_summary.json`의 `net_debt`(현금성+단기금융자산−차입금, 포괄 기준)를 본다. FnGuide `cash`(현금성만)와 다르다. s06에 **financial_summary 기준 순현금을 "약 N조"로 `순현금` 단어 근처**에 명시(예: "순현금 약 4,982억(약 0.5조)").
- **`financial_summary.py` print_summary TypeError(NoneType avg_eps_forward)는 무해** — JSON은 크래시 직전 이미 dump됨. 무시하고 진행.
- **데이터 폴더명 == `meta.stock_name`**: `generate_all.py`는 데이터 경로를 `meta.stock_name`으로 유도하고, verify_*는 CLI 인자를 쓴다. 둘이 다르면(예: stock_name "와이지엔터테인먼트" vs 폴더 `data/와이지엔터/`) generate_all 내부 Peer/밴드 교차검증이 조용히 우회되어 거짓 WARN. 폴더명을 meta.stock_name과 맞추거나 데이터 복사.
- **KIS_BASE_URL 모의(`openapivts:29443`)라도 `get_current_price`가 실측 PER/PBR/EPS를 반환할 때가 있다** — CLAUDE.md 상단 "모의는 0 반환" 경고가 항상 참은 아님. 수집 직후 1종목 테스트로 0 여부 실제 확인 후 판단.
- **임시 스크립트 컨벤션**: 수집은 `scripts/_collect_{종목}.py`, critic 정정은 `scripts/_fix_{종목}_v6.py`(idempotent, 정확 문자열 치환 + alias 재생성 + json.dump 단일 원자 쓰기). 기존 `_fix_*.py` 다수가 이미 커밋돼 있어 컨벤션 일관.
- **기존 종목 재실행**: `data/{종목}/`·`scripts/analysis_{종목}.json`이 7일+ 경과면 v5.4 규칙 8로 전면 재수집(DART/FDR/Wisereport/Peer). 특히 분기 실적 발표(통상 5·8·11·2월 중순) 직후면 1Q/분기 반영이 재작성의 핵심 가치.

## DART 재무제표 주의사항

- `extract_key_metrics()`는 **필터링 없이 전체 항목을 저장**함 (127개+)
- 회사마다 필드명이 다를 수 있음 (예: "영업이익(손실)" vs "영업이익(손익)" vs 필드 없음)
- 영업이익이 없는 경우 매출총이익 - 판관비로 역산
- "영업수익" ≠ "영업이익" — 부분매칭 주의
- `financial_summary.py`가 자동으로 정리하므로, DART 원본을 직접 파싱하지 말 것

## SEC EDGAR XBRL 주의사항 (US 종목)

- **10-Q 손익/현금흐름은 YTD 누적으로 보고됨** -- Q2 = 1~6월 누적, Q3 = 1~9월 누적. 독립 분기 = 현재 누적 - 전 분기 누적으로 역산 필수. `financial_summary_us.py`가 자동 처리.
- **같은 회사가 시기별로 다른 XBRL 태그 사용** -- 예: Tesla는 2017까지 `DepreciationDepletionAndAmortization`, 이후 `Depreciation`. `sec_edgar.py`의 extract_financials()는 모든 후보 태그를 병합(첫 태그 우선, 빈 연도만 후순위 채움).
- **KIS 해외주식 API는 국내 대비 반환 필드 부족** -- PBR/BPS/52주 고저가 0으로 반환될 수 있음. `financial_summary_us.py`가 yfinance로 자동 fallback.
- **회계연도(Fiscal Year) 주의** -- Apple(9월), Microsoft(6월) 등 비표준 FY 기업은 `period[:4]` 연도 추출 시 데이터 혼입 가능. 현재 Tesla/NVIDIA 등 12월 결산 기업은 정상.
- US 재무 데이터 단위는 **raw USD** (억원이 아님). 리포트에서 $B/$M 변환 필요.

## /research 리포트 언어 규칙

**KR/US 종목 무관하게 리포트(analysis.json sections s01~s21)는 반드시 한글로 작성한다.** 독자가 한국 개인 투자자이므로 영문 리포트는 금지. 고유명사(Tesla, BYD, Megapack), 재무 약어(OPM, EPS, EBITDA), 통화($)는 원문 유지. segments/catalysts/peers 서술 필드도 한글. TSLA v1에서 21섹션 전체를 영어로 작성하는 사고 발생 -- 이 규칙으로 재발 방지.

## /research 스킬 실행 흐름 (v4.3 -- 작성 단일 + 검증 서브에이전트)

**작성은 메인 에이전트 단독, 검증만 `report-critic` 서브에이전트.** 메인 에이전트가 21섹션을 순차 작성하고, STEP 6 2~3회차에서 `report-critic` 서브에이전트를 호출하여 Fresh context 가혹 비평을 받는다. 과거 v3 6-서브에이전트 실험(작성 분업)은 비용만 4~5배 증가하고 품질 개선이 미미하여 폐기되었으나 (상세: `.claude/agents/README.md`), v4.3의 `report-critic`은 **작성이 아닌 검증 역할**이므로 v3와 다른 맥락이다. 단일 비평 에이전트는 자기 일관성 편향을 구조적으로 제거하는 이점이 명확하므로 도입됨.

```
STEP 0:   역할 부여 (월가 시니어 애널리스트)
STEP 1:   데이터 수집 (KIS 7 엔드포인트 + DART 사업보고서 + 웹 검색 병렬)
STEP 1.5: financial_summary.py 자동 정리
STEP 1.6: 변동성·베타 계산 (120일 일봉)
STEP 1.7: 역사적 밸류에이션 밴드 — FDR 5년 연말 종가 정확 조회 (WebSearch 추정 금지, _per_band.json)
STEP 2:   데이터 검증 (EPS 교차, 확정/추정 구분)
STEP 2.3: Peer 시총/PER/PBR KIS API 실시간 일괄 조회 (추정 금지, _peer_snapshot.json)
STEP 2.5 (KR): 사업보고서 정독 — 10개 필수 Grep 패턴 (지역별 매출/M/S/판매대수/ASP/신용등급 등)
STEP 2.5-US (US, v4.17): SEC 10-K/10-Q 본문 정독 — 10개 필수 Grep (reportable segments/Net revenue by segment/Geographic/market share/customer/foundry/R&D/CapEx/backlog/M&A)
STEP 3:   심층 분석 — Phase 1(이해) → Phase 2(판단) → Phase 3(확신)
STEP 3.5: 분석 메모 출력 (JSON 쓰기 전 필수)
STEP 4:   analysis.json 작성 — s02/s03/s04 필수 구조 엄수
           (s02 4줄 구조 / s03 10개 필수 요소 / s04 8개 필수 요소)
STEP 5:   generate_all.py 실행 + 자동 검증
STEP 5.5: 수치 더블체크 (KIS/DART 원본과 1:1 대조)
STEP 6:   자체 평가 + 수정 × **무조건 3회 반복 (조건부 종료 금지)**
           1회차 = 메인 에이전트 형식 누락 체크리스트 (8개 항목)
           2회차 = **`report-critic` 서브에이전트 호출** (Fresh context 가혹 비평)
                   → .claude/agents/report-critic.md 에 정의된 월가 시니어 페르소나
                   → 호출 프롬프트: 파일 경로 + "최고의 애널리스트 관점에서 냉정하고 객관적으로 평가해줘. 더 수정할 내용 없어?"
           3회차 = 같은 `report-critic` 서브에이전트 재호출 (2회차 수정 반영 후)
```

**v4 성능 (기아 수준 원본):** 시간 ~15-20분, 토큰 ~100-120K, 비용 ~$1.5-2 (Opus).

**v4.2 성능 (대한항공 실측, 자연어 비평 추가 후):** 시간 ~20-25분, 토큰 ~130-160K, 비용 ~$5-7 (Opus) / $1-1.5 (Sonnet). 자연어 비평이 체크리스트보다 **더 깊이 결함을 잡는 만큼 수정 토큰도 증가** — 이는 품질 향상의 정당한 비용이며, 효율 악화는 의도된 trade-off. 품질-효율 공짜 점심 없음.

**v4의 핵심 개선:** s02/s03/s04 약점의 진짜 원인은 에이전트 구조가 아니라 **사업보고서 [0] 주요_계약 섹션의 지역별 매출/M/S 테이블을 Grep하지 않은 것**이었다. STEP 2.5의 10개 필수 Grep 패턴이 이 문제를 해결한다.

**v4.1 개선 (2026-04, JYP 사건 후):** Peer 시총/PER/PBR를 추정 또는 웹 검색치로 쓰는 실수(JYP v1: HYBE/SM/YG 3개 전부 틀림) 및 5년 연말 주가 추정 실수를 방지하기 위해 **STEP 1.7 FDR 필수** + **STEP 2.3 Peer KIS 실시간 필수**를 추가. STEP 6은 점수 무관 **무조건 3회 반복**으로 강제하고, Peer/역사 밴드 정확성 체크 블록(B/C)을 신설.

**v4.2 개선 (2026-04, 대한항공 사건 후):** 체크리스트 3회 반복이 대한항공 v1에서 **결함 0개** 발견에 그친 반면, 사용자의 "최고의 애널리스트 관점에서 냉정하고 객관적으로 평가해줘. 더 수정할 내용 없어?" **한 문장 도전**이 **5개 치명적 결함**을 발견(별도 vs 연결 OPM 미분리, 글로벌 FSC PER 날조 SIA 12→8.96/Cathay 10→7.58, SOTP 부재, DCF Terminal g 2.0 공격성, 2027E EPS +70% 공격성). **체크리스트가 LLM의 자가검증 능력을 오히려 억누른다**는 구조적 결함이 드러남. STEP 6를 재설계: 1회차 체크리스트는 38개 → **8개로 축소**(코드 validator 중복 제거, 질적 평가는 자연어로 이전), 2~3회차는 **순수 자연어 한 문장**. 가이드/관점 리스트/프레임워크를 추가하면 다시 체크리스트 모드로 전환되므로 **"찾아야 할 5가지" 같은 항목을 절대 추가하지 말 것**.

**v4.3 개선 (2026-04, 서브에이전트 도입):** v4.2의 "한 문장 자연어 비평"을 메인 에이전트가 자기 리포트에 적용할 때 **자기 일관성 편향**으로 효과가 줄어드는 문제 발견. 해결책: 2~3회차를 **메인 에이전트 자가비평 → `report-critic` 서브에이전트 호출**로 전환. 서브에이전트는 리포트 작성 컨텍스트를 갖지 않으므로 **Fresh context**로 독립 판단 가능. 이는 "사용자가 매번 '더 수정할 내용 없어?'라고 물어야 발견되던 결함을 구조적으로 자동화"한 것. 서브에이전트 정의: `.claude/agents/report-critic.md` — 월가 시니어 페르소나 + "가이드 추가 금지" 원칙 + 강제 발굴 프로토콜. 호출 프롬프트는 **파일 경로 + 한 문장 질문**만 포함하고 시스템 프롬프트는 에이전트 파일에 맡긴다.

## STEP 6 자가검증 철학 — 3층 역할 분담 (v4.3)

LLM 리포트 자가검증은 **3층 분담**으로 작동하며, 각 층이 다른 종류의 결함을 잡는다:

| 층 | 무엇을 잡나 | 방법 | 강점 |
|---|---|---|---|
| **1. 코드 `generate_all.py` validator (11개)** | 수치 정합성 (시총 10배, Peer snapshot, PER band, EPS, R/R, Bear-Base-Bull 순서, 재무 이상값) | 자동 ERROR/WARN | 기계적 확실성 |
| **2. 1회차 메인 체크리스트 (8개)** | 형식 누락 (빠진 Q1~Q3 프로토콜, 빠진 테이블, 부족한 인용) | 사람 이진 체크 | 빠르게 "있는지/없는지" 스캔 |
| **3. 2~3회차 `report-critic` 서브에이전트** | 질적 평가 (수치 정확성, 가정 공격성, 논거 깊이, 숨은 모순, 놓친 각도) | Fresh context 자유 탐색 | **작성자 편향 없는 독립 판단** |

**각 층이 다른 층을 방해하지 않는다.** 코드 validator가 하는 것을 체크리스트가 반복하지 않고, 체크리스트가 하는 "형식 체크"를 서브에이전트가 반복하지 않는다.

**왜 서브에이전트인가** — 메인 에이전트가 자기 리포트를 비평하면 작성 과정에서 형성된 자기 일관성 편향 때문에 결함을 못 찾는다. 대한항공 v1 실증: 메인 체크리스트 3회 = 결함 0개. 이와 대조적으로 이번 세션에서 `code-reviewer` 서브에이전트로 스킬 자체를 리뷰했을 때 4개 CRITICAL + 3개 HIGH + 2개 MEDIUM 발견. 같은 LLM이지만 Fresh context면 독립 판단 가능. **서브에이전트는 "사용자 개입 의존성"을 구조적으로 제거**한다.

**가장 중요한 원칙**: 서브에이전트 호출 프롬프트에 **절대 가이드를 추가하지 말 것**. "5가지 관점을 찾아라", "거짓 수치/공격 가정/놓친 각도를 체크하라" 같은 것을 넣는 순간 서브에이전트도 체크리스트 모드로 전환된다. 호출 프롬프트는 **파일 경로 + "최고의 애널리스트 관점에서 냉정하고 객관적으로 평가해줘. 더 수정할 내용 없어?"** 한 문장만 유지한다. 페르소나/원칙/강제 발굴 프로토콜은 모두 `.claude/agents/report-critic.md` 시스템 프롬프트에 이미 정의되어 있으므로 호출 시 반복할 필요 없다.

**사용 모드 권장 (종목 중요도별)**:
- 핵심 포지션 (10%+ 투자): 전체 Opus + 4회차까지 사용자 도전, $6~8
- 일반 포지션 (3~10%): Opus 기본 3회 + 2~3회차 자연어, $4~6
- 워치리스트 탐색: Sonnet + 1회차 체크리스트만, $0.7~1
- 재실행 업데이트: Sonnet + 부분 갱신, $0.5~0.8

## v4.16 톤 변환 7대 규칙 (2026-04, NFLX 영문 직역체 사고 후)

**문제 진단**: NFLX/PANW v1이 "영문 컨센 노트 한글 직역체"로 작성되어 위닝펀드/임소정/최정욱 톤과 명백히 달랐다. 약어 폭격 + $X.XB 영문 표기 + 4줄 불릿 폭격으로 한국 독자가 첫 페이지에서 길을 잃음.

**7대 절대 규칙** (모든 섹션 강제 적용, 상세는 `.claude/commands/research.md` v4.16 섹션):
1. **소제목 한 줄 위트** (12~15자): "광고는 더블링, 안전마진은 제로" / "황제주는 같이 왔다" / "1Q는 진짜, 2Q가 변수"
2. **결론 선행** (임소정 패턴): 섹션 시작 직후 "한 줄 평가" 박스 의무
3. **수치 한국 독자 친화**: "$1.5B" → "15억 달러" / "$3T" → "3조 달러"
4. **약어 한글 우선**: OPM → 영업이익률, FCF → 잉여현금흐름, NRR → 순보유율
5. **메커니즘 설명** (박상욱 5단): 트렌드 → 병목 → 메커니즘 → 해결책 → 수혜 (클리셰 금지)
6. **단정 톤** ("~다"/"~이다"): "~것으로 보인다/추정된다" 금지
7. **위트성 마무리 인용** (`>`): s01/s13/s14 결론 섹션 모두 강제 (v4.18 격상)

**시리즈 톤 진화 (C 점수 추이)**: AMD 73 → NFLX v3 79 → 한화에어로 85 → MSFT 87 → 대한항공 v2 92. v4.16~v4.19 누적 효과로 시리즈 최고점 도달.

## v5.4 절대 규칙 13~19 (2026-05, GS리테일 + 한미반도체 작업 중 사용자 명시 지적)

| 규칙 | 핵심 |
|---|---|
| **13** | s03/s04/s09 사업보고서 1차 출처 + s03 \"기업 분석\" 명칭 + 일반 독자 친화 5요소 + 인용 박스 ≤ 2건 |
| **14** | critic 결과 자동 수정 의무 + AskUserQuestion 옵션 던지기 절대 금지 (v4.3 \"사용자 개입 구조적 제거\" 위반 차단) |
| **15** | 애널리스트 리포트 = \"정보 바탕 자기 서술\" (broker 멘션 본문 노출 최소화, 사업보고서와 동일 풀어쓰기 패턴) |
| **16** | 데이터 시점 한계 명시 의무 (모든 수치/통계에 발표 시점 + 30일+ 경과 시 \"현재 시점 변화 가능\" 명시) |
| **17** | 매체 + 핵심 자료/지표 통합 매트릭스 (12섹션 × 1차/2차/3차 출처 + 의무 분석 항목) |
| **18** | 종목 특수 시그널 grep 의무 4개 + 종목 유형별 양식 자동 분기 7개 (지주/적자/순현금/저베타/사이클/Hybrid/단일) |
| **19** | 분기보고서 [1][2][3] 본문 + Fnguide 분기 실측 1:1 대조 의무 (한미반도체 4Q25 -59% QoQ 사고 차단) |

상세는 `.claude/commands/research.md` v5.4 절대 규칙 13~19 섹션 참조.

## 27개 섹터 매트릭스 (research.md STEP 1-2 + s09)

**반도체 5개**: 메모리 / 파운드리 / **장비 (한미반도체/AMAT/ASML)** / **소부장 (동진쎄미켐/솔브레인)** / **후공정 (하나마이크론)**
**자동차 2개**: 완성차 (현대차/기아/TSLA) / 부품
**바이오 2개**: 제약 / CDMO
**2차전지 2개**: 셀 / 소재
**금융 2개**: 은행 / 보험
**소재 2개**: 화학 / 철강
**인프라 3개**: 에너지/유틸리티 / 건설/부동산 / 리츠
**미디어 2개**: 엔터 (K-POP) / 게임 / 미디어 (OTT)
**방산/조선 2개**: 방산 / 조선
**IT 2개**: IT/플랫폼 (네이버/카카오) / 통신
**유통 3개**: 소비재/유통 (GS리테일/CJ제일제당) / 항공/물류 / **이커머스 (쿠팡)**

각 섹터별 사업보고서 위험요인 종류 + WebSearch 모멘텀 쿼리 (M1~M4 + 섹터별 2~3개) + 섹터 특화 grep 키워드 매트릭스가 research.md에 정의됨.

## v4.15 / v4.17 / v4.18 / v4.19 사고 정정 누적 (2026-04)

**v4.15 (NFLX/PANW 14건 결함 사고)**: 미국 종목용 `verify_numbers_us.py` 신설. B1~B15 (시총/현재가/PER/52주 + Stock Split 자동 감지 + GAAP/Non-GAAP 분리 + EPS×주식=NI 산술 + DCF 괴리 50%+ 경고). 14건 결함 중 8건 자동 차단. 종목 분기는 `data/{종목명}/data_kis.json` 존재 → KR / `data/{TICKER}/data_kis_us.json` 존재 → US.

**v4.17 (AMD "SEC 4 segments" 거짓 진술 사고)**: 미국 종목용 **STEP 2.5-US 신설**. SEC 10-K/10-Q 본문을 `data/{TICKER}/_sec_*.txt`로 덤프하고 10개 필수 Grep을 단일 메시지 병렬 실행. Reportable segments는 **본문 직접 인용 의무**(`> SEC 10-K (filed YYYY-MM-DD): "We have N reportable segments: ..."`)로 작성 시점 사고 차단.

**v4.18 (한화에어로 D1 가짜 인용 4건 사고)**: 사업보고서/SEC 인용 박스(`>`) 작성 전 **원문 grep 매칭 의무화**. 한화에어로 v1: "자사주 매입/소각, 현금배당 등 주주환원정책..." 인용이 사업보고서에 자사주/소각/주주환원 키워드 0회로 판정 → 가짜 인용 확정. 작성 프로토콜:
1. 인용문 핵심 키워드 5개+ 추출 (조사/접속사 제외)
2. 각 키워드를 `_tmp_*.txt` (KR) 또는 `_sec_*.txt` (US)에서 grep -- **한 키워드라도 0건이면 인용 박스 폐기**
3. 원문 100% 복사 (의역/윤문 금지, 어미 추가도 금지)
4. 출처 표기: `> 사업보고서 III. 사업의 내용 (YYYY/MM 공시): "..."`

추가로 `verify_style.py` 강화:
- **C7 라벨+세부 결합형 자동 감지**: "포인트 1. K방산 수주잔고 30.99조..." (53자) 같은 라벨+세부 결합 30자+는 위트 한 줄(15자) + 본문 첫 줄 부제로 분리 권장
- **C10 위트 인용 박스 의무 격상**: s01/s13/s14 결론 섹션 모두 강제 (한화에어로 v1 s01/s14 누락 사고)

`verify_numbers_us.py` **B17 추가**: 본문 FCF/순부채/시총이 3종+ 고유값으로 등장 시 WARN (시점 라벨 수동 확인). FAIL 자동 차단은 시계열 데이터 false positive 위험 때문에 WARN으로 정착.

**v4.19 (대한항공 v2 첫 Write 실패 사고)**: Claude Code Write tool은 기존 파일 존재 시 "File has not been read yet" 에러로 거부하는데, 이를 메인 에이전트가 놓치면 v1이 그대로 남고 PDF/검증/critic 모두 v1을 본다. **규칙**: 기존 `scripts/analysis_{종목명}.json` 존재 시 Write 직전 Read 1회 의무 (offset=1, limit=5도 충분). Write 직후 본문 분량 + opinion.rating + target_base 검증 한 줄 명령으로 v1 잔재 즉시 차단.

## PDF 타이포그래피 (v4.3 — Pretendard)

`generate_all.py`의 `_DETAILED_V3_CSS`는 **CSS 변수 기반 폰트 시스템**을 사용한다. 맑은 고딕 시스템 폰트에서 Pretendard 웹폰트로 이전한 이유: (1) 한국 디자인 업계 사실상 표준, (2) tabular-nums 자동 정렬로 재무 테이블 가독성 향상, (3) pretendardvariable-dynamic-subset 덕에 PDF 파일 크기 -38% 감소(임베드 글리프 최소화).

```css
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css');

:root {
    --font-body: 'Pretendard Variable', 'Pretendard', -apple-system, system-ui, 'Malgun Gothic', sans-serif;
    --font-heading: Georgia, 'Times New Roman', 'Pretendard Variable', serif;
    --font-mono: 'JetBrains Mono', Consolas, monospace;
}

html, body {
    font-family: var(--font-body);
    font-feature-settings: 'tnum' 1, 'kern' 1;  /* 숫자 정렬 + 커닝 */
    font-size: 10pt;      /* Pretendard 최적 (맑은 고딕 9.5pt 대비 +0.5) */
    line-height: 1.65;    /* 1.6 → 1.65 (자간 개선 맞춤) */
    text-rendering: optimizeLegibility;
}
```

**디자인 철학 유지**: 한글 본문·UI = Pretendard (현대적 산세리프) / 영문 헤딩·대제목 = Georgia (NYT 세리프 스타일). 11곳 font-family가 모두 CSS 변수로 교체됐으며, 폰트 시스템 변경 시 `:root` 블록만 수정하면 전체 리포트에 전파된다.

**Playwright Chromium**이 렌더링 시 웹폰트를 자동 로드하므로 로컬 폰트 설치 불필요. CDN은 jsdelivr (Pretendard 공식).

## 커버 페이지 레이아웃 (v4.14 -- 한화에어로 겹침·잘림 사고 후 재조정)

`generate_all.py` 의 `.full-bleed.cover` CSS는 Dashboard(핵심지표/컨센서스/수익률) + pick-box(3-Target 스펙트럼 + Current + R/R) + cover-body(회사명/tagline) + cover-footer 4개 요소가 A4 한 페이지에 들어가도록 절대 위치 좌표로 배치된다. 두산·한화에어로스페이스 리포트에서 pick-badge rating 문자열 잘림 + 천 단위 숫자 줄바꿈 + Peer 테이블 페이지 경계 잘림 사고를 수정하면서 v4.14 좌표 재조정.

**v4.14 최종 좌표 (A4 297mm 기준, bottom = 페이지 하단부터 거리)**:

| 요소 | bottom | 높이 제약 | 설명 |
|---|---|---|---|
| cover-body (회사명+tagline) | (flow) | ~45mm | margin-top 10mm, h1 36pt, tagline 12pt |
| **Dashboard** | **48mm** | `max-height: 30mm` (overflow hidden) | `dash-block font 6.2pt / line-height 1.25` |
| **pick-box** | **10mm** | `min-height: 22mm / max-height: 32mm` | Current/R/R 표시 여유 확보 |
| cover-footer | 2mm | ~6mm | font 5.5pt |

**Dashboard ↔ pick-box 간격** ≥ **6mm** (48 − (10+32) = 6). pick-box max-height 32mm 내에 HOLD 배지 + BEAR/BASE/BULL + Current + R/R 가 들어감.

**v4.14 핵심 변경 (v4.7 대비)**:
- **pick-badge**: `font-size: 16pt → 11pt`, `white-space: normal`, padding 축소 -- "HOLD with downside bias" 같은 긴 rating 문자열 잘림 방지 (단 **rating 자체는 "HOLD/BUY/SELL" 1~3단어로 유지**)
- **target-cell .t-val**: `font-size: 12pt → 9.5pt (base 16→12pt)`, `white-space: nowrap` -- "1,000,000원" 줄바꿈 방지
- **pick-box max-height**: `25mm → 32mm` -- Current/R/R 라인 포함 여유 확보
- **Dashboard**: `max-height: 30mm` + `overflow: hidden` 강제, `dash-row white-space: nowrap` -- "(조원)" 같은 줄바꿈 방지
- **h1.stock-title**: `40pt → 36pt`, cover-body margin-top `12mm → 10mm` -- 상단 여유 축소로 Dashboard 공간 확보

**서로 연결된 크기 제약**: 이 값 중 하나라도 증가시키면 겹침 재발 -- 변경 시 모든 블록 세로 합 재계산 필수.

**사고 재발 방지 원칙 (v4.14 확장)**:
- Dashboard bottom **48mm 유지**. pick-box max-height 32mm 초과 금지
- **pick-badge 내부 rating 문자열은 1~3단어 짧게** (analysis.json `opinion.rating` = "HOLD"/"BUY"/"SELL", 상세는 `opinion.type` 에)
- **target-cell .t-val nowrap 절대 해제 금지** (숫자 줄바꿈 원인)
- **peers 배열 최대 6개 (본 종목+5), 연결 자회사 제외** -- 페이지 2 Peer 테이블 경계 잘림 방지
- **각 peer.note 25자 이하** -- Peer 셀 높이 증가 방지
- 새 종목 리포트 생성 후 **페이지 1 + 페이지 2 모두 육안 확인 필수** (`fitz`로 PNG 추출하여 확인)

## Windows 환경 주의

- 플랫폼: Windows 11, bash 셸 사용 (Unix 스타일, `/dev/null` not `NUL`)
- 파일 경로에 한글 포함 → 따옴표 필수 (`cd "주식 ai 리서치 리포트 에이전트"`)
- 한글 인코딩 사고 방지를 위해 스크립트 최상단에 UTF-8 강제:
  ```python
  import sys, io
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
  ```
- cp949 관련 특수문자/이모지 금지 규칙은 상단 "변수 명명 및 임시 파일 규칙" 참조.
