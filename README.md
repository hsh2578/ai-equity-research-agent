# AI Equity Research Agent · 주식 AI 리서치 리포트 에이전트

> **종목명 한 줄 입력 → 기관급 증권 리서치 리포트(PDF) 자동 생성.**
> 데이터 수집·교차검증·심층분석·밸류에이션·디자인·팩트체크까지 사람 개입 없이 전 과정 자동화.

<p>
<img alt="Python" src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white">
<img alt="LLM Agent" src="https://img.shields.io/badge/LLM-Multi--step%20Agent-7C3AED">
<img alt="Data" src="https://img.shields.io/badge/Data-DART%20%7C%20KIS%20%7C%20SEC%20EDGAR%20%7C%20FnGuide-0E7C5B">
<img alt="Output" src="https://img.shields.io/badge/Output-Institutional%20PDF%2019~60p-1A2B4C">
</p>

한국·미국 상장사를 대상으로 **CFA Institute 리서치 표준 + IB 실무(DCF·SOTP·NAV) + 국내 베스트 애널리스트 리포트 패턴**을 결합한 12섹션 구조의 리포트를 생성합니다. 단순 요약이 아니라, 1차 출처(전자공시·SEC 원문) 정독 → 가설 수립 → 밸류에이션 → 리스크 → 액션 플랜으로 이어지는 **애널리스트의 사고 흐름 자체를 자동화**한 것이 핵심입니다.

---

## 📊 샘플 리포트 (먼저 보기)

에이전트가 **사람 후편집 없이 자동 생성한 원본**입니다. → **[`samples/` 폴더 전체 보기](samples/)**

| 종목 | 시장 | 섹터 | 분량 | 링크 |
|------|------|------|------|------|
| 기아 | KOSPI | 완성차 | **60p** | [PDF](samples/01_기아_자동차_KR.pdf) |
| 삼성전자 | KOSPI | 반도체(메모리) | 19p | [PDF](samples/02_삼성전자_반도체_KR.pdf) |
| 에코프로 | KOSDAQ | 2차전지 소재 | 46p | [PDF](samples/03_에코프로_2차전지_KR.pdf) |
| 한미반도체 | KOSPI | 반도체 장비(HBM) | 36p | [PDF](samples/04_한미반도체_반도체장비_KR_v5.4.pdf) |
| Netflix | NASDAQ | OTT/미디어 | 31p | [PDF](samples/05_Netflix_OTT_US.pdf) |

---

## 프로젝트 개요

증권사 RA(Research Assistant)의 반복 업무 — 전자공시·SEC 원문 정독, 재무 3개년 정리, Peer 비교, 밸류에이션 밴드 산출, 컨센서스 대조, 초안 작성, 수치 검증 — 를 LLM 멀티스텝 에이전트로 자동화한 개인 프로젝트입니다.

| 항목 | 내용 |
|------|------|
| **입력** | 종목명 또는 티커 한 줄 (예: `삼성전자`, `TSLA`) |
| **출력** | Navy/Gold 팔레트 기관급 단일 PDF (19~60p, 12섹션) + 검증 로그 |
| **소요** | 약 15~25분 / 리포트 (완전 자동) |
| **커버리지** | 한국(KOSPI/KOSDAQ) + 미국(NYSE/NASDAQ), 27개 섹터 매트릭스 |

## 핵심 차별점

**1. 멀티소스 1차 데이터 + 교차검증**
DART(전자공시)·한국투자증권 OpenAPI·SEC EDGAR(XBRL)·FnGuide·FinanceDataReader를 병렬 수집하고, 시가총액·EPS·PER·Peer·밸류에이션 밴드를 **소스 간 1:1 대조**합니다. 추정·웹검색 수치를 1차 데이터로 위장하지 않도록 강제하는 게이트가 내장되어 있습니다.

**2. 금융 도메인 깊이**
FCF 기반 DCF 3시나리오 + 민감도 테이블, 지주사/리츠 NAV(SOTP), 5년 PER/PBR 밴드 + z-score, KOSPI200/KOSDAQ150 회귀 베타, 섹터별 KPI 매트릭스(반도체 후공정·완성차 ASP·은행 NIM 등)를 종목 유형에 따라 자동 분기 적용합니다.

**3. 할루시네이션 방지 설계**
인용 박스는 **원문 grep 매칭을 통과해야만** 본문에 삽입됩니다(가짜 인용 자동 폐기). 수치는 코드 검증기가 기계적으로 ERROR/WARN을 발생시키고, 작성과 분리된 **독립 비평 서브에이전트**가 Fresh context로 가혹 검토합니다. 금융 리포트에서 가장 치명적인 *그럴듯한 거짓*을 구조적으로 차단합니다.

**4. 실전 결함 → 자동 회귀 테스트 전환**
운영 중 발견된 모든 결함(수급 단위 오독, Peer 추정치 혼입, 시점 라벨 누락 등)을 일회성 수정으로 끝내지 않고 `preflight_check.py` / `verify_*.py`의 **자동 검증 규칙으로 영구 편입**했습니다. 동일 결함 재발률 0을 목표로 한 회귀 방지 체계입니다.

## 시스템 아키텍처

```
  데이터 수집 (병렬)              분석 / 검증                  리포트 생성
┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│ dart_api.py  (KR 공시) │   │ financial_summary.py  │   │ generate_all.py       │
│ kis_api.py   (시세·수급)│──▶│  손익·재무·현금흐름 정규화 │──▶│  HTML/CSS → PDF        │
│ sec_edgar.py (US XBRL) │   │ dcf_calculator.py     │   │  Navy/Gold · Pretendard│
│ fnguide_data.py(컨센)  │   │ nav_calculator.py     │   │  자동 품질검증 11종     │
│ fdr_band.py  (밸류밴드) │   │ industry_kpi.py       │   │                       │
│ volatility_beta.py(β)  │   │ report_extractor.py   │   │ preflight_check.py     │
│ peer_snapshot.py(Peer) │   │  (1차 출처 인용 추출)   │   │  (사전 차단 게이트)     │
└──────────────────────┘   └──────────────────────┘   └──────────────────────┘
        │                                                          │
        └──────────── analysis_{종목}.json (구조화 분석 산출물) ──────┘
```

## AI 에이전트 워크플로우

리포트 **작성은 메인 에이전트 단독**, **검증은 독립 서브에이전트**가 담당하는 분리 구조입니다.

```
STEP 0   역할 부여 (월가 시니어 애널리스트 페르소나)
STEP 1   데이터 수집 (KIS 7 엔드포인트 + DART 사업보고서 + 웹검색 병렬)
STEP 1.5 재무 자동 정규화 / 변동성·베타 / 5년 밸류에이션 밴드(실측 종가)
STEP 2   데이터 검증 (EPS 교차, 확정/추정 구분) + Peer 실시간 일괄 조회
STEP 2.5 1차 출처 정독 (사업보고서 / SEC 10-K·10-Q 10개 필수 grep 패턴)
STEP 3   심층 분석 (이해 → 판단 → 확신 3단계)
STEP 4   analysis.json 작성 (12섹션 구조 강제)
STEP 5   PDF 생성 + 자동 품질검증 11종
STEP 6   3층 자가검증 × 무조건 3회 반복
```

### 신뢰성: 3층 자가검증

| 층 | 무엇을 잡나 | 방법 |
|----|-------------|------|
| **1. 코드 검증기 (11종)** | 수치 정합성 (시총 10배 오류, Peer 괴리, EPS, R/R, 재무 이상값) | 기계적 ERROR/WARN |
| **2. 형식 체크리스트 (8종)** | 누락 (빠진 테이블·인용·프로토콜) | 이진 스캔 |
| **3. `report-critic` 서브에이전트** | 질적 결함 (가정 공격성, 논거 깊이, 숨은 모순, 놓친 각도) | **Fresh context 독립 비평** |

> 작성자가 자기 리포트를 검증하면 자기일관성 편향으로 결함을 놓칩니다. 작성 컨텍스트를 갖지 않는 별도 서브에이전트를 호출해 **편향을 구조적으로 제거**한 것이 이 설계의 핵심입니다.

## 기술 스택

- **언어/런타임**: Python 3.11+
- **AI**: LLM 멀티스텝 에이전트 + 독립 검증 서브에이전트 (프롬프트 엔지니어링 / 워크플로우 설계)
- **데이터**: DART OpenAPI, 한국투자증권 OpenAPI, SEC EDGAR XBRL, FnGuide, FinanceDataReader, yfinance
- **금융 모델링**: DCF(FCF 3시나리오·민감도), NAV/SOTP, PER/PBR 밴드·z-score, CAPM 베타 회귀
- **리포트 엔진**: HTML/CSS → PDF (Playwright/Chromium), Pretendard 타이포그래피, tabular-nums 재무 테이블
- **품질**: preflight/verify 자동 게이트, 회귀 방지 검증 규칙

## 실행 방법

```bash
# 의존성
pip install finance-datareader yfinance
playwright install chromium

# 환경변수 (.env.example 참고 — 실제 키는 커밋되지 않음)
cp .env.example .env   # DART / KIS 키 입력

# 리포트 생성 (Claude Code 슬래시 커맨드)
/research 삼성전자
/research TSLA

# 분석 JSON → PDF 단독 실행
python scripts/generate_all.py scripts/analysis_삼성전자.json
```

> **API 키 보안**: 모든 키는 환경변수(`.env`)로만 로드되며 코드에 하드코딩이 없습니다. `.env`·수집 데이터·생성물·토큰 캐시는 `.gitignore`로 전면 차단되어 본 저장소에 포함되지 않습니다.

## 프로젝트 구조

```
.
├── .claude/
│   ├── commands/research.md     # 에이전트 워크플로우 정의 (STEP 0~6)
│   └── agents/report-critic.md  # 독립 검증 서브에이전트 페르소나
├── scripts/
│   ├── dart_api.py / kis_api.py / sec_edgar.py / fnguide_data.py   # 데이터 수집
│   ├── financial_summary*.py    # 재무 정규화 (KR/US)
│   ├── dcf_calculator.py / nav_calculator.py / industry_kpi.py     # 금융 모델
│   ├── fdr_band.py / volatility_beta.py / peer_snapshot.py         # 밸류에이션
│   ├── generate_all.py          # PDF 생성 엔진 + 자동 품질검증 11종
│   ├── preflight_check.py       # 사전 차단 게이트
│   ├── verify_numbers*.py / verify_style.py / verify_facts.py      # 검증 3종
│   └── analysis_*.json          # 구조화 분석 산출물 예시
├── samples/                     # 자동 생성 리포트 PDF 5종
├── CLAUDE.md                    # 아키텍처·운영 규칙·회귀 방지 이력 (상세)
└── .env.example                 # 환경변수 템플릿 (키 미포함)
```

## 한계 및 면책

- 본 결과물은 **리서치 자동화 도구의 산출물이며 투자 자문이 아닙니다.**
- 리포트의 모든 수치는 **데이터 수집 시점**을 본문에 명시하며, 시점 경과에 따라 현재 사실과 다를 수 있습니다.
- LLM 기반 분석은 검증 게이트로 신뢰성을 보강했으나 오류 가능성이 0은 아닙니다. 1차 출처(전자공시·SEC) 교차 확인을 전제로 합니다.
- 외부 참고자료·제3자 리포트는 저작권상 본 저장소에 포함하지 않았습니다.

---

<sub>본 저장소는 포트폴리오 목적의 개인 프로젝트입니다. DART/KIS/SEC EDGAR 등 데이터 출처의 이용약관을 준수합니다.</sub>
