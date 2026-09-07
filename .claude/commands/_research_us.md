# 미국 종목 리서치 파이프라인 (v5.5)

`/research {TICKER}` 로 **영문 티커**가 들어왔을 때 이 파일을 따른다.
`research.md` 는 공통 뼈대(서술 원칙 / 퀀트 프로토콜 / analysis.json 스키마 /
PDF 레이아웃 / STEP 3 분석 3-Phase)를 계속 제공하고, **데이터 수집·정독·검증만**
이 파일이 대체한다. 충돌 시 **이 파일이 우선**한다.

## 왜 분리했나

2026-09 감사 결과 미국 파이프라인이 한국 대비 명백히 얇았다.

| 항목 | KR | US (분리 전) |
|---|---|---|
| 1차 출처 정독량 | DART 전문 1.7~3.3MB/종목 | SEC 덤프 170~425KB/종목 |
| 밴드/베타/Peer | 커밋된 스크립트 3종 | **없음** -- 매 실행 인라인 임시코드 |
| 5년 실적 + 3년 컨센 | `fnguide_data.py` | **없음** (yfinance forward EPS 1개뿐) |
| 컨센 **추이** 검증 | Wisereport + B11 | **없음** |
| 분기 실측 대조 | v5.4 규칙 19 + B13 | **없음** |
| 자동 검증 | B1~B19 (18개) | 11개 |

게다가 `research.md` 에 사실과 다른 기술이 있었다 --
"FDR/베타/Peer 는 financial_summary_us.py 내에서 통합 처리" 라고 적혀 있었지만
그 파일에 밴드·Peer 코드는 존재하지 않는다. 그 결과 AMD 의 `_peer_snapshot.json` 이
$347.81 / 시총 $567B 로 stale 하게 방치돼 있었다 (실시간 $477.57 / $779.6B).

---

## STEP 0: 진입 판별

입력이 영문 티커(`AMD`, `NVDA`, `BRK.B`)면 US 경로다.
`data/{TICKER}/` 를 작업 폴더로 쓰고, `meta.country = "US"`, `meta.currency = "USD"` 로 둔다.

**리포트 본문은 KR/US 무관하게 전부 한글로 쓴다** (TSLA v1 영문 작성 사고 방지).
고유명사(Tesla, Megapack), 재무 약어(OPM, EPS, EBITDA), 통화($)만 원문 유지.

---

## STEP 1: 데이터 수집

```bash
# 1-1. SEC EDGAR 재무제표 5년 + 10-K/10-Q 본문 + 한투 해외주식 시세
python scripts/financial_summary_us.py {TICKER} [EXCD]
#   EXCD: NAS(기본) / NYS / AMS. 주요 NYSE 종목은 자동 감지.
#   -> data/{TICKER}/data_sec.json, data_kis_us.json, financial_summary.json
```

`print_summary` 의 `TypeError(NoneType avg_eps_forward)` 는 무해하다 --
JSON 은 크래시 직전에 이미 dump 된다. 무시하고 진행한다.

### 1-2. 병렬 3종 (v5.5 신설 -- 여기가 KR 대비 최대 격차였다)

**단일 메시지에 3개를 동시 호출한다.**

```bash
# 컨센서스 + 리비전 추이 (KR Wisereport 컨센 추이 + FnGuide 3년 추정의 미국판)
python scripts/us_consensus.py {TICKER}

# 5년 PER/PBR 밴드 (+ 밴드 유효성 게이트)
python scripts/fdr_band_us.py {TICKER}

# Peer 실시간 (업종키: semicon/semieq/software/security/media/auto/pharma/megacap/retail/bank)
python scripts/peer_snapshot_us.py {TICKER} {업종키}
#   업종키가 없으면: --peers "NVIDIA:NVDA,Intel:INTC,Broadcom:AVGO"
```

**`us_consensus.py` 가 주는 것** (전부 yfinance, 추가 API 키 불필요):

| 항목 | 내용 | 어디에 쓰나 |
|---|---|---|
| `eps_estimate` | 당분기/다음분기/당해/내년 EPS 컨센 (평균·최저·최고·분석가 수) | s10 컨센서스 |
| `eps_trend` | current / 7d / 30d / 60d / 90d 전 컨센 | **컨센 추이 표** |
| `eps_revisions` | 30일 상향/하향 건수 | Wisereport 에도 없는 데이터 |
| `growth_estimates` | 종목 vs 산업/섹터/지수 | s04 상대 성장 |
| `price_targets` | low/high/mean/median | s07 밸류에이션 |
| `upgrades_downgrades` | 최근 90일 등급 변경 | s10 |
| `derived.consensus_direction` | UP / DOWN / FLAT 자동 판정 | **B11 이 본문과 대조** |

실측(AMD): 내년 EPS 컨센이 90일간 13.08 -> 15.45 (**+18.2%**), 30일 순리비전 **+30건**.
이건 "시장이 이미 알고 있다"의 정량 증거이므로 Edge 서술에 직접 쓴다.

### 1-3. 밴드 유효성 게이트 (v5.5 신설)

`fdr_band_us.py` 는 표본 3개 미만이거나 **변동계수(std/mean) > 0.6** 이면
`per_band_valid: false` 와 경고를 낸다.

실측(AMD): PER 시계열이 56 -> 77 -> 278 -> 121 -> 81 로 변동계수 0.66.
평균 122.6배 / 현재 121.8배라 "5년 평균 수준"처럼 보이지만 **표준편차가 80.6이라 무의미하다.**
게다가 2022년 자일링스 인수로 BPS 가 4.59 -> 33.54 로 점프해 PBR 밴드는 구조적 단절이다.

**`per_band_valid: false` 이면 본문에서 "5년 평균 대비", z-score, 밴드 상/하단 표현을 쓰지 않는다.**
대신 연도별 PER 값을 표로 직접 제시한다. 어기면 `verify_numbers_us.py` B19 가 FAIL 을 낸다.

### 1-4. 검증된 수치 스냅샷 (필수)

```bash
python scripts/build_snapshot.py {TICKER}
```

-> `data/{TICKER}/_verified_snapshot.md`. **STEP 3 진입 전 반드시 Read 한다.**
`미수집` 으로 표기된 항목은 그 항목에 대한 수치 주장 자체가 금지된다.

---

## STEP 2.5-US: SEC 본문 정독

```bash
python - <<'PY'
import sys, json; sys.path.insert(0, 'scripts')
from sec_edgar import get_filings_text
# 10-K 최신 + 10-Q 3개를 data/{TICKER}/_sec_*.txt 로 덤프
PY
```

덤프 후 **단일 메시지에 10개 Grep 을 동시 호출**한다:

`reportable segments` / `Net revenue by segment` / `Geographic` / `market share` /
`customer concentration` / `foundry|supply agreement` / `Research and development` /
`capital expenditures` / `backlog` / `acquisition|merger`

**Reportable segments 는 본문 직접 인용 의무**다 (AMD v1 "SEC 4 segments" 거짓 진술 사고):

```
> SEC 10-K (filed YYYY-MM-DD): "We have N reportable segments: ..."
```

### 증거/반증 스캔 (v5.5 신설, KR/US 공통)

```bash
python scripts/evidence_scan.py {TICKER}
```

`_sec_*.txt` 를 훑어 **실측 증거**(수치 동반)와 **반증**(공급 충분/증설로 해소/
판가 열위/수요 둔화/양산 전)을 원문 인용 + `file:line` 으로 뽑는다.
회계 보일러플레이트와 표 조각은 자동 제외된다.

**반증이 실측 증거보다 많으면 강세 논거를 재검토한다.** 반증 0건이면 패턴이
안 걸린 것인지 정말 없는 것인지 직접 확인한다.

---

## STEP 4: analysis.json 작성 -- US 특수 규칙

공통 규칙(정규 12키 + alias 재생성, 서술 12원칙, 인용 박스 원문 grep 매칭)은
`research.md` 를 따른다. **US 에만 적용되는 것**만 여기 적는다.

1. **10-Q 는 YTD 누적이다.** Q2 = 1~6월 누적, Q3 = 1~9월 누적.
   독립 분기 = 현재 누적 − 전 분기 누적. `financial_summary_us.py` 가 자동 처리하지만,
   `quarterly` 표를 손으로 채울 때 역산 결과를 다시 확인한다.

2. **분기 라벨에 반드시 연도를 붙인다.** `Q3'25`, `1Q26` 형식.
   `Q1`, `Q2` 처럼 연도 없는 라벨은 `verify_numbers_us.py` B13 이 FAIL 을 낸다
   (어느 연도인지 특정할 수 없어 누락 검증이 불가능하다).

3. **GAAP 과 Non-GAAP 을 같은 행에 섞지 않는다.** 회사 발표 Non-GAAP EPS 와
   SEC XBRL GAAP EPS 는 다른 숫자다. 표에 어느 기준인지 명시한다 (B13/B8 검증).

4. **Stock split 이력을 확인한다.** NFLX 10:1 사고처럼 EPS 시계열 단위가 섞인다.
   B12 가 자동 감지하지만 표를 만들 때 split-adjusted 인지 명시한다.

5. **비표준 회계연도 주의.** Apple(9월), Microsoft(6월), NVIDIA(1월) 등은
   `period[:4]` 로 연도를 뽑으면 데이터가 섞인다.

6. **단위 변환.** SEC 는 raw USD 다. 본문은 "15억 달러", "3조 달러" 처럼
   **한국 독자 친화 표기**로 쓴다 ($1.5B / $3T 금지 -- v4.16 규칙 3).

7. **컨센 방향은 `_us_consensus.json` 의 `derived.consensus_direction` 과 일치해야 한다.**
   컨센이 90일 +18% 상향인데 본문이 "눈높이 하향"이라고 쓰면 B11 이 FAIL 이다.

8. **`target_base` 가 컨센 최고가를 넘으면** s07 에 초과 근거를 명시한다 (B11).

---

## STEP 6: 검증 (US)

```bash
# 단일 메시지 동시 호출
python scripts/verify_numbers_us.py {TICKER}   # B1~B19
python scripts/verify_style.py {TICKER}        # C1~C20 (KR/US 공통)
python scripts/verify_facts.py {TICKER}        # D1~D6 (KR/US 공통)
```

**B 블록 (US, v5.5 기준 19개)**

| 항목 | 내용 |
|---|---|
| B1~B4 | 시총 / 현재가 / PER / 52주 (vs yfinance) |
| B6~B8 | Net Debt / EBITDA / EPS 5년 테이블 |
| B10 | R/R 내부 일관성 |
| **B11** | **컨센 정합 4종** (v5.5): forward_eps vs 컨센 / forward_per 역산 / 리비전 방향 vs 본문 / target_base vs 컨센 상단 |
| B12 | Stock split 자동 감지 |
| **B13** | **분기 누락** (v5.5, KR 과 공용 모듈) |
| B14 | EPS x 발행주식 = 순이익 산술 |
| B15 | DCF vs Base 괴리 50%+ 경고 |
| B17 | 본문 FCF/순부채/시총 변종 감지 |
| **B19** | **밴드 유효성 게이트** (v5.5) |

**FAIL 은 무시하지 않는다.** 전부 정정 후 PDF 를 재생성한다.

### 서브에이전트 2종

```
1. bear-researcher  (STEP 4 완료 직후, 백그라운드)
   -> 반증 + 실격 조건 5가지 점검. 결과를 s09/s14 에 반영한다.

2. report-critic    (STEP 6 2~3회차)
   -> 호출 프롬프트는 파일 경로 + 한 문장만. 가이드를 추가하지 말 것.
```

---

## STEP 7: 결정 로그 기록 (v5.5 신설, 필수)

```bash
python scripts/decision_log.py record {TICKER}
```

발간 시점의 등급·목표가·논지를 `output/_decision_log.md` 에 pending 으로 남긴다.
나중에 `settle` 로 SPY 대비 alpha 를 계산해 사후 평가한다.
이 기록이 없으면 그 리포트는 영원히 채점되지 않는다.

---

## US 특유 함정 목록

- **KIS 해외주식 API 는 국내 대비 반환 필드가 부족하다.** PBR/BPS/52주가 0 으로 오면
  `financial_summary_us.py` 가 yfinance 로 fallback 한다. 0 을 그대로 쓰지 말 것.
- **같은 회사가 시기별로 다른 XBRL 태그를 쓴다.** Tesla 는 2017까지
  `DepreciationDepletionAndAmortization`, 이후 `Depreciation`.
  `sec_edgar.py` 가 후보 태그를 병합한다.
- **yfinance `info` 는 종종 필드가 비거나 rate limit 에 걸린다.** 한 종목 테스트 후 진행.
- **Peer 는 6개 이하** (본 종목 + 5). 커버 페이지 Peer 테이블 잘림 방지 (v4.14).
- **`_peer_snapshot.json` 이 오래되면 B1~B4 가 전부 FAIL 로 뜬다.** 이건 리포트 결함이
  아니라 데이터 stale 이다. 7일 넘었으면 STEP 1-2 를 재실행한다 (v5.4 규칙 8).
