# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

주식 AI 리서치 리포트 자동 생성 시스템. DART(한국 전자공시), 한국투자증권 OpenAPI, SEC EDGAR(미국)에서 재무제표·사업보고서·시세를 수집하고, 21개 섹션의 증권사 수준 리포트를 자동 생성한다.

## Development Setup

필수 의존성 (최초 1회):
```bash
pip install finance-datareader   # STEP 1.7 5년 연말 종가 정확 조회용 (WebSearch 추정 금지)
pip install yfinance             # US 종목 forward estimates, 52주/PBR/BPS fallback
playwright install chromium      # generate_all.py HTML->PDF 변환용
```

`FinanceDataReader`가 없으면 `/research` STEP 1.7이 ImportError로 실패하고 역사 밴드가 추정치로 돌아가 JYP 사건이 재발한다.

**환경변수 설정:** API 키는 `.env` 파일에서 관리 (`.gitignore`에 등록됨). `.env.example`을 복사하여 사용:
```bash
cp .env.example .env
# .env 파일에 DART_API_KEY, KIS_APP_KEY, KIS_APP_SECRET 입력
```
bash 세션에서 로드: `source <(grep -v '^#' .env | grep '=' | sed 's/^/export /')`

## Key Commands

```bash
# 리포트 생성 (analysis JSON -> 단일 상세 PDF, Navy/Gold v3 디자인)
python scripts/generate_all.py scripts/analysis_{종목명}.json

# 재무 데이터 자동 요약 - 한국
python scripts/financial_summary.py {종목명} {종목코드}

# 재무 데이터 자동 요약 - 미국 (SEC EDGAR + KIS + yfinance)
python scripts/financial_summary_us.py {TICKER} [EXCD]
# EXCD: NAS(나스닥, 기본), NYS(뉴욕), AMS(아멕스). 주요 NYSE 종목은 자동 감지.

# 사업보고서 핵심 인용 추출
python scripts/report_extractor.py data/{종목명}/data_dart_reports.json

# 스킬 코드 블록 또는 scripts/* 변경 후 문법 체크
python -c "import py_compile; py_compile.compile('scripts/generate_all.py', doraise=True)"

# 전체 스킬 실행 (Claude Code 슬래시 커맨드)
/research {종목명 또는 티커}
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
# 현재가, 전일대비, 등락률, 거래량, 거래대금, 시가, 고가, 저가,
# 52주최고, 52주최저, 시가총액(억), PER, PBR, EPS, BPS

# get_daily_price(code, days) → list[dict]  (키 한글)
# 날짜, 시가, 고가, 저가, 종가, 거래량
```

**절대 금지:** `px.get("per", 0)` (소문자) / `px.get("stck_prpr", 0)` — 항상 0 반환.
**올바름:** `px.get("PER", 0)` / `px.get("현재가", 0)` / `px.get("시가총액", 0)`.

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
| `report_extractor.py` | 사업보고서 → 핵심 인용문 + 전년대비 변화점 자동 추출 |
| `dcf_calculator.py` | FCF 기반 DCF 3시나리오 + 민감도 테이블 |
| `nav_calculator.py` | 지주회사/리츠 NAV 계산 |
| `industry_kpi.py` | 업종별 추가 검색 키워드 + 필수 분석 항목 |

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

## analysis.json 구조

```json
{
  "meta": {"stock_name", "stock_code", "market", "country", "industry", "date", "currency"},
  "price": {"current", "market_cap", "market_cap_num", "per", "pbr", "eps", "bps", ...},
  "opinion": {"rating", "target_bear", "target_base", "target_bull", "risk_reward"},
  "segments": [{"name", "pct", "outlook"}],
  "financials": {"headers", "rows", "source"},
  "peers": [{"name", "market_cap", "per", "pbr", "note"}],
  "catalysts": [{"date", "event", "impact"}],
  "sections": {"s01_opinion" ~ "s21_reliability"}
}
```

`market_cap_num`은 **억 단위** 정수. KIS API의 `시가총액` 필드와 반드시 일치해야 함.

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
STEP 2.5: 사업보고서 정독 — 10개 필수 Grep 패턴 (지역별 매출/M/S/판매대수/ASP/신용등급 등)
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

## 커버 페이지 레이아웃 (v4.7 -- 겹침 방지 좌표)

`generate_all.py` 의 `.full-bleed.cover` CSS는 Dashboard(핵심지표/컨센서스/수익률) + pick-box(3-Target 스펙트럼) + cover-body(회사명/tagline) + cover-footer 4개 요소가 A4 한 페이지에 들어가도록 절대 위치 좌표로 배치된다. v4.7에서 삼성전자 리포트 렌더링 시 Dashboard와 pick-box가 1mm 간격으로 붙어서 겹침이 발생한 사고를 수정하면서 좌표가 재조정되었다.

**최종 좌표 (A4 297mm 기준, bottom 값 = 페이지 하단부터의 거리)**:

| 요소 | bottom | 예상 높이 | 예상 top |
|---|---|---|---|
| cover-body (회사명+tagline) | (flow) | ~50mm | 12mm (margin-top) |
| **Dashboard** | **48mm** | ~32mm | ~217mm |
| **pick-box** | **8mm** | **~18mm** (min-height) | ~271mm |
| cover-footer | 2mm | ~6mm | ~289mm |

**Dashboard ↔ pick-box 간격 ≥ 24mm** 확보 (이전 1mm → 24mm).

**서로 연결된 크기 제약**: Dashboard 내부 폰트 6.5~6.8pt / line-height 1.35 / padding 2.5mm, 3-Target 스펙트럼 t-val 12pt(Base 16pt) / padding 0.8mm 2mm, h1.stock-title 40pt, tagline 14pt / max-width 130mm. 이 값 중 하나라도 증가시키면 겹침 재발 가능 -- 변경 시 모든 블록 세로 합 재계산 필수.

**사고 재발 방지 원칙**:
- Dashboard는 **절대 bottom 48mm 아래로 내리지 말 것** (행 수가 많은 종목에서 pick-box 침범)
- pick-box min-height: 18mm 는 3-Target 스펙트럼 최소 높이 기반이며 축소 불가
- 새 종목 리포트 생성 후 **페이지 1 육안 확인 필수**. Dashboard와 pick-box가 붙어있으면 Dashboard bottom 값을 50mm 이상으로 추가 상향

## Windows 환경 주의

- 플랫폼: Windows 11, bash 셸 사용 (Unix 스타일, `/dev/null` not `NUL`)
- 파일 경로에 한글 포함 → 따옴표 필수 (`cd "주식 ai 리서치 리포트 에이전트"`)
- 한글 인코딩 사고 방지를 위해 스크립트 최상단에 UTF-8 강제:
  ```python
  import sys, io
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
  ```
- cp949 관련 특수문자/이모지 금지 규칙은 상단 "변수 명명 및 임시 파일 규칙" 참조.
