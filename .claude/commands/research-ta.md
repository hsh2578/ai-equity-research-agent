# /research-ta {종목명} -- 애널리스트 조직 과정으로 쓰는 리서치 리포트 (실험 스킬)

> 기존 `/research` 는 그대로 둔다. 이 스킬은 **같은 리포트 양식**(IR협의회 목차 + 기술적 분석)을
> **다른 작업 방식**으로 만든다. TradingAgents(arXiv 2412.20138, 코드 be952b8) 의 조직 구조를 참고했다.
> 설계 결정의 근거: `~/.claude/plans/rosy-splashing-falcon.md`, 원본 대비 변경: `third_party/tradingagents_port/NOTICE`.

## 왜 이 스킬인가
`/research` 는 수집기와 게이트가 많아도 세 가지가 반복해서 빠졌다: **최신 뉴스, 주가를 움직인 뉴스의 호재/악재, 이미 받아 둔 전자공시 내용.**
한 에이전트가 수십 개 원자료를 한 맥락에서 읽고 쓰기 때문이다. 여기서는
① 뉴스·공시를 검색이 아니라 **전수 수집**하고 ② **자료 묶음별 분석가**가 끝까지 읽어 ID 붙은 항목으로 보고하고
③ 작성자가 항목마다 **반영/제외를 기록**하게 하고 ④ 코드가 그 기록을 검사한다.

## 절대 규칙 (이 파일에만 있는 것 -- 나머지 작성 규칙은 `/research` 현행 규칙을 따른다)
1. **리포트 양식은 `/research` v5.21~5.22 와 같다.** IR협의회 ORDER + `meta.section_titles`, 문체 게이트(verify_tone), C21 스토리 55%.
   추가 섹션 하나: `s08_esg` 자리 = **기술적 분석** (`meta.section_titles.s08_esg = "기술적 분석"`, `meta.section_labels.s08_esg = "Technical Analysis"`).
2. **본문 예산.** 새 정량 도구(RIM·역DCF·DOL/DFL·VaR·민감도·투자자 적합성)는 결론을 바꿀 때만 본문 한 문단 + 표 1개. 나머지는 해당 섹션 끝 부록 표.
   기술적 분석 섹션 ≤ 본문 6%. 투자포인트 2~3개, 미래 지향. **"숫자 도배"로 돌아가면 이 스킬은 실패다.**
3. **계산은 장부로.** 본문의 비율·레버리지·밸류 수치는 `ta/calc_ledger.json` 값만 쓴다. 머릿속 계산 금지.
4. **brief 는 색인이다.** 본문에 쓰는 주장마다 brief 가 가리킨 원문(file:line)을 직접 열어 확인한다(Grep 1회). 분업으로 뉘앙스를 잃지 않기 위해서다.
5. **초과수익은 상관이다.** "뉴스 때문에"라고 쓰지 않는다.
6. **decision_log record 하지 않는다**(파일럿 기간). 기존 `/research` 콜과 섞이면 채점이 오염된다.
7. 동시 서브에이전트 ≤ 12(프로젝트 규칙).
8. **요약(s01)·투자포인트(s02)는 사건으로 쓴다.** 보도와 주가 반응(초과수익), 수시공시, 정기보고서 문구 변화, 실적 사실. 밸류 산식·배수·역산은 s07 에만.
   s01 의 밸류 언급은 결론 한 문단까지. 측정: 밸류 용어(배수|EBITDA|ROE|RIM|PBR|SOTP|주당가치|확률가중|내재) s01 ≤ 8회, s02 ≤ 15회, 뉴스·공시 용어보다 적어야 한다.
   에프에스티 실측: critic·리스크 토론이 산식만 고치는 방향이라 그 결과가 요약으로 흘러 s01 19회/s02 31회가 됐고 사용자가 "또 재무·밸류로 서술한다"고 잡았다.
9. **이익과 배수의 기간을 맞춘다.** 선행 이익에는 선행 배수(비교기업 컨센 이익으로 직접 계산), 후행에는 후행. 상각비 정의도 비교기업과 같은 방법.
   에프에스티 실측: 선행 EBITDA x 후행 배수가 유일하게 현재가 위의 목표주가(+10%)를 만들었고 HOLD 의 근거였다. 기간을 맞추자 SELL.
10. **요약은 ■ 3개 고정** (IR협의회 22편 전부): ① 회사가 무엇을 하고 최근 실적 사실(반기·분기 수치) ② 성장 동인 하나를 회사 밖 실명·수치로 ③ 앞으로의 일정·판단·밸류 위치 한 줄. `> **한 줄:**` 3개가 이 순서다(게이트 G4).
11. **산업현황은 회사 밖 재료로만 쓰고 마지막 한 문단에서 동사로 착지한다.** 분량 20%+, 회사 밖 문단 90%+, 출처 3종+(관세청·협회·SEMI·고객사 10-K·기업설명회), 뉴스 인용 2회 이하(G1~G3, G6). 재료는 `ta/trade_stats.json`, `ta/customer_docs/`, `ta/company_voice.md`.
12. **밸류는 밴드+Peer 로 "지금 위치"까지만 본문(s07)에, 등급·목표가·시나리오는 s07 끝 `#### 판단` 블록 하나에.** s01·s02 에는 SOTP·시나리오·DCF 를 쓰지 않는다(G5). IR협의회는 등급이 없지만 이 프로젝트는 실제 투자용이라 판단 블록을 둔다(사용자 결정 2026-09-17).

## 실행 모드 -- lite 가 기본값 후보 (2026-09-18 HD현대중공업 실측)
| | lite | full |
|---|---|---|
| 수집(STEP 0~1) | 전부 | 전부 |
| 분석가 | 산업+거시 1명(웹 검색 있는 역할만) | 자료량 배정(CJ 16명) |
| 토론·리스크 토론 | 없음 | bull/bear 4 + 리스크 3 |
| 작성 | 메인 단독 (수집물 직접 정독) | 메인 단독 (brief 색인) |
| 반영 게이트 | 산업 brief 필수 ID 만 | 전 brief 필수 ID |
| critic | 1회 + 재개 대조 | 1회 + 재개 대조 |
| 실측 | HD현대중공업: PDF 까지 50분, 에이전트 5회(분석가 1·critic 1·재토론 2·재대조 1), 약 80만 토큰 | CJ프레시웨이: 3시간+, 27회 |
근거: 에프에스티 lite 가 full 에 3:2 로 근소 열세, CJ 결정 오류를 잡은 것은 팀이 아니라 critic. 자료가 많은 대형주·핵심 포지션이면 full.
⚠️ lite 에서 critic 이 잡은 것은 **메인이 혼자 만든 밸류 산식의 기간 불일치**였다(HD: FY26E 배수 15.3 을 FY27E EPS 에 곱해 목표가 +10.6% 전부가 연도 롤포워드, KIS 롤링 12.87 미인용, RIM 63%가 영구 TV, 요구 영구 ROE 40.8%). 규칙 9 를 적어 두고도 어겼으므로 **배수 라벨에 기준연도(FY26E 선행/12개월 롤링/후행 12개월)를 반드시 붙이고, 목표가 표에 "요구 영구 ROE" 열과 자본효율 앵커 범위(잔여가치 0·g 0·ke 감도·컨센 BPS)를 함께 둔다.** 결정 수준이면 재토론(보수형+공격형) -- HD 는 둘이 같은 사실에서 SELL 405k / HOLD 520k 로 갈렸고 PM 이 493k 로 착지했다.
lite 에서 메인이 직접 하는 정독 순서: `_verified_snapshot.md` -> `event_study.json` top_moves·calendar -> 수시공시 본문(`_dart_filings.json` bodies) -> **STEP 1.5 정독(IR 덱 → 종목리포트 → 산업리포트, 원문 전부)** -> `_drivers.md`·`company_voice.md` -> 반기보고서 grep(부문·수주잔고·현금흐름·순차입금·민감도).
실측 비용에 정독을 더하면: 메인 원문 약 17만 토큰 + 판정 2회 31만(HD현대중공업 4판).
⚠️ 네이버 종목뉴스 API 는 최근 약 2개월만 준다(HD현대중공업 실측 2,121건, 7/9~. 처음 '10일치'로 보인 것은 우리 수집기의 max_pages=20 상한이었다). 그 이전 급등락일은 `ta_news_window.py` 로 채운다.

## STEP 0 -- 준비
```bash
python scripts/source_health.py
python -c "import sys; sys.path.insert(0,'scripts'); import ta_common as t; print(t.resolve_stock('{종목명}'))"
```
기존 `/research` STEP 1 수집물이 7일 넘었거나 없으면 먼저 갱신한다(v5.4 규칙 8):
`financial_summary.py`(KIS 500 이면 `_run_with_real_kis.py`) · `collect_dart_full.py` · `collect_dart_filings.py` · `dart_quarterly.py` ·
`wisereport_consensus.py` · `fdr_band.py` · `volatility_beta.py` · `peer_snapshot.py`(업종키 결과를 눈으로 확인, v5.18 규칙 3) ·
`peer_snapshot_global.py {종목} {업종키} [--peers "이름:TICKER"]`(해외 비교기업, yfinance 억원 환산 -- 국내 3사만 놓으면 배수가 어디 서는지 못 본다) · `price_cycles.py` · `driver_scan.py` · `evidence_scan.py`

## STEP 1 -- 신규 수집 (결정론)
업종 category·키워드는 `ta/dart/business.txt` 의 1~2장을 보고 정한다(`ta_dart_diff` 를 먼저 돌린다).
```bash
python scripts/ta_dart_diff.py {종목명}
python scripts/ta_collect_news.py {종목명}
python scripts/ta_event_study.py {종목명}
python scripts/ta_news_window.py {종목명}           # 네이버 종목뉴스 API 는 최근 약 2개월(HD현대중공업 실측 7/9~)만 준다. 그 이전 급등락일(event_study top_moves)의
                                                    # 재료를 Google News RSS 날짜창(d-2~d+1)으로 받아 type='window' 로 넣고 event_study 를 다시 돌린다.
                                                    # HD현대중공업 실측: 4/1 -11.8% 의 재료가 공시 제목('최대주주 소유주식 변동')이 아니라 모회사 20억달러 교환사채(교환가 54만원)였다
python scripts/ta_event_study.py {종목명}           # 창 뉴스 연결 후 재실행
python scripts/ta_calendar.py {종목명}
python scripts/ta_market_data.py {종목명}
python scripts/ta_board_flow.py {종목명}
python scripts/ta_collect_reports.py {종목명} --industry-category {업종} --keywords {제품,전방,경쟁사}
python scripts/macro_data.py ...   # KR 스냅샷을 data/{종목명}/ta/macro.json 으로 저장
python scripts/ta_trade_stats.py {종목명}          # ta/trade_query.json (HS 4~10자리·국가 ISO2·months) 를 먼저 쓴다 -- 사업보고서 II장 제품·수출 지역
python scripts/ta_customer_docs.py {종목명}        # ta/customers.json [{name, kind: US|KR, ticker(US), keywords}] -- 고객사·장비사·경쟁사 10-K/10-Q·기업설명회
python scripts/ta_news_body.py {종목명}            # 뉴스 API 는 요약 150자만 준다 -- 기사 URL 을 열어 본문 확보(네이버 #dic_area / trafilatura)
python scripts/ta_kind_ir.py {종목명}              # KIND IR자료실에서 기업설명회 발표자료 PDF (DART 공시는 개최 안내문뿐)
python scripts/ta_company_ir.py {종목명}           # 회사 홈페이지 IR 자료(분기 실적발표 덱). DART 홈페이지 -> IR 링크 자동 탐색, 등록부 docs/research-ta/ir_sites.json.
                                                    # 이미지 덱은 PNG 로 저장(HD 2Q26). 링크 패턴 3종·게시판 따라가기·세션 유지(CJ). 정독 대상 "IR 최근 2분기"의 출처
python scripts/peer_snapshot_global.py {종목명} {업종키}   # 해외 비교기업(yfinance, 억원 환산)
python scripts/ta_company_voice.py {종목명} --irtv # IR 발표자료 + 발언 기사(전문 기준) + IRTV 자막 -> ta/company_voice.md
python scripts/ta_plan_agents.py {종목명}
```
IR협의회 22편 재료 비중은 DART 26 / 자체 추정 26 / 회사 설명 18 / 협회·정부 12 / 고객사·경쟁사 8 / **뉴스 2** (%) 다
(`docs/research-ta/kirs-construction.md`). 뉴스는 재료가 아니라 사건 표기다. 위 다섯이 협회·정부·고객사·회사 설명 재료의 대체재다.
에프에스티 실측: 관세청 8시리즈 / 램리서치 24·삼성전자 12 인용 / 뉴스 본문 48/57 / KIND IR 발표자료 3건(각 22p) / 발언 기사 8건.
각 스크립트 뒤에 `ta/manifest.json` 의 status 를 본다. **failed 는 넘어가지 말고 원인을 확인**한다(조용한 실패 패턴).
`ta/agent_plan.json` 의 calls 가 분석가 호출 목록이다. **인원은 종목마다 다르다.**

## STEP 1.5 -- 정독 (메인이 원문 전부를 읽는다. 요약 대체 금지) -- v5.24, 형식은 `docs/research-ta/reading_note_format.md`
사용자 결정(2026-09-20): "종목리포트 최근 3~5개, 산업리포트 2~3개, IR자료 최근 2분기 -- 이 모든 내용을 정독해서 ... 다 읽어서 이해한 상태에서 우리 리포트를 쓰게."
초판 정독은 목표가·EPS·투자포인트 제목만 뽑는 숫자 추출이었고, 블라인드 판정(위치 교차 2회)에서 정독 뒤 판이 5축 / 옛 판 1축으로 이겼다. 차이는 숫자가 아니라 **논리의 출처와 반론**이었다.
1. **대상 고정**: 종목리포트 최근 3~5편 + 가장 긴 편 1(커버리지 개시), 산업리포트 2~3편(합 15만 토큰 초과 시 2편), 회사 IR 덱 최근 2분기(`ta_company_ir`·`ta_kind_ir`, 이미지는 PNG), IR협의회(있으면). 나머지는 밸류 방법표에 "미정독"으로만.
2. **순서**: IR 덱 → 종목 → 산업. 회사 말을 먼저 알아야 애널리스트가 무엇을 덧붙였는지 보인다. `Read` 로 파일째 올린다(HD 실측 17만 토큰, 메인 컨텍스트에 들어간다). `Read` 는 한 메시지에서 여러 편을 같이 올리고, 노트는 3~4편씩 묶어 쓴다(턴 수 14 → 4). 읽는 양은 같다. 위임·부분 읽기는 검토 뒤 취소(2026-09-20 사용자 결정).
3. **정독 직후** 편당 노트 `ta/notes/{id}.md`(다섯 질문 + 6번 자유, 원문 `파일:줄`·쪽) + `notes/_summary.md` + `notes/_valuation_methods.md`(10~12곳 방법·배수·근거·이익 연도) + `ta/questions.json`(질문 3, 증거 tier·stance·verdict) + `ta/watchlist.json`(앞으로 나올 뉴스, "이미 가격에 있는 것" 열).
4. **같은 호흡으로 s02·s04·s07 을 쓴다.** 정독과 핵심 장 작성 사이에 수집·게이트 같은 긴 작업을 두지 않는다 -- 컨텍스트 압축이 읽은 것을 지운다(이번 세션 실측: 압축 뒤 4편을 다시 읽었다). 노트가 복구 지점이다.
5. 노트 판정 기준: **노트만 읽은 사람이 저자의 논리를 반박할 수 있으면 합격**, "무엇을 말했는지"만 남았으면 불합격. 읽지 않은 것을 읽은 것처럼 적지 않는다.
6. 비용: 원문은 메인만. critic·재토론·판정에는 노트·장부·본문을 준다. 산업리포트 2편 이상을 메인이 읽었으면 산업 분석가 에이전트를 부르지 않는다.

## STEP 2 -- 분석가 팀 (병렬)
`agent_plan.json` 의 call 마다 역할 에이전트를 **한 메시지에서 병렬 호출**한다.

| role | 에이전트 | ID 접두 |
|---|---|---|
| news | `ta-news-analyst` | N |
| fundamentals | `ta-fundamentals-analyst` | F |
| sellside / sellside+industry | `ta-sellside-analyst` (병합 시 산업 규칙도 따르라고 명시) | SS |
| industry | `ta-industry-analyst` -- 입력에 `ta/trade_stats.json`, `ta/customer_docs/*.md` 를 반드시 넣는다 | I |
| macro | `ta-macro-analyst` | MA |
| market | `ta-market-analyst` | T |

호출 프롬프트에 넣을 것(그 외 가이드는 넣지 않는다): 종목명, call_id, 입력 목록(agent_plan 그대로), brief 경로, **ID 시작 번호**(분할 호출끼리 겹치지 않게 100 간격: #1 은 01, #2 는 101, #3 은 201 -- 파일럿에서 20 간격이 뉴스 분석가 25개 항목과 겹쳤다), `docs/research-ta/brief_format.md` 를 먼저 읽으라는 한 줄.

## STEP 3 -- 계산 장부 1차
`ta/assumptions.json` 을 쓴다(ke·wacc·g·ROE 전망·FCF0·순현금·주식수·현재가 + 각 `sources`). 근거는 brief·기존 ggm_check·컨센 추이에서.
```bash
python scripts/ta_calc_ledger.py compute {종목명}
```

## STEP 4 -- 강세·약세 토론
1라운드: `ta-bull` 과 `ta-bear` 병렬 → `ta/debate_bull_1.md`, `ta/debate_bear_1.md`
2라운드: 서로의 1라운드를 넘겨 병렬 반박 → `_2.md`
메인 = Research Manager: `ta/research_plan.md` -- 원본 ResearchPlan 필드(recommendation Buy/Overweight/Hold/Underweight/Sell, rationale, strategic_actions) +
투자포인트 후보 2~3개, 핵심 리스크, **시장이 틀린 지점 1개**(ta-sellside 의 '가격에 넣은 가정' vs 장부의 `reverse_dcf_implied_growth`).
**근거가 팽팽하면 Hold** -- 방향을 억지로 만들지 않는다(원본 규칙 + v5.5 규칙 6).

## STEP 5 -- 리스크 토론 → 최종 결정
`ta/decision_draft.md`(등급·Bear/Base/Bull 목표가·핵심 가정)와 `ta/rating_context.md`(`python scripts/decision_log.py context {종목명}` + `python scripts/rating_distribution.py` 요약)를 쓴다.
`ta-risk-debater` 3개 병렬(stance: aggressive / neutral / conservative) → 메인 = Portfolio Manager: `ta/decision.md` (원본 PortfolioDecision 필드: rating, executive_summary, investment_thesis, price_target, time_horizon).
목표가를 바꿨으면 assumptions 갱신 후 장부 재계산.
**결정 변경은 리스크 토론을 거친다.** critic 이 결정 수준 결함을 내면 메인이 바로 등급을 바꾸지 않고 `ta/decision_draft{N}.md`(무엇이 바뀌었고 무엇을 공격해 달라는지)를 써서 3명을 다시 부른다.
한 방향 누적(v5.19)을 막는 장치이지만 반대 오류도 넣는다 -- 에프에스티 재토론 1 은 "12개월 목표가 관행"으로 기간 불일치를 만들었고 critic 2 가 잡았다. 그래서 규칙 9 를 장부 검사로 강제한다.

### 절대 규칙 14 -- 표기 기준을 하나로 두고, 고쳤으면 전파를 grep 으로 확인한다 (2026-09-18 HD현대중공업 critic 1회 + 재대조 실측)

critic 12건 중 결정 수준 7건은 밸류 산식이었고, 재대조 잔재 4건은 전부 **s07 에서 고친 라벨이 s01·s13·s14·s09·decision.md 로 전파되지 않은 것**이었다.
- **배수·이익 라벨에 기준을 붙인다**: 후행 PER 은 **최근 12개월 지배순이익 / 현 발행주식수**(합병·증자 뒤 KIS 표시 PER 은 옛 가중평균주식수 기준이라 참고만), 선행은 "2026년 컨센 PER" 과 "12개월 롤링 PER(KIS per_12m_forward)"을 구분, PBR 헤드라인은 **최신 반기 BPS**(연말 BPS·컨센 BPS 는 병기). 목표가 표에는 "요구 영구 ROE" 열, 자본효율 앵커는 범위(잔여가치 0·g 0·ke 감도·컨센 BPS)로.
- **한 지표에 두 값이면 기준일을 붙인다**(수주 달성률 6월 103% / 9월 114%). 판정 기준은 하나(catalysts.impact 와 본문·decision 의 마진 임계값이 같아야 한다).
- **수급(`ta/flow.json`)은 20거래일 창이다.** 그보다 긴 구간(고점 이후 3개월)의 서사에 쓰지 않는다. 급등일 이틀과 20일 합계를 나눠 적는다.
- **배당은 `financial_summary.forward.dps_forward` 를 본다.** 후행 시가배당률만 쓰면 분기배당 도입 종목에서 인컴 판단이 뒤집힌다.
- **컨센 목표가 평균은 표본 컷오프(발간일)를 밝히고, 컷오프 밖의 큰 상향·하향을 한 줄 적는다.**
- **리스크 표 필수 행 둘**: "실적이 맞아도 배수가 깎이는 위험"(민감도 표가 배수 > 이익이라 말하면 그 변수에 확률·관찰지표가 있어야 한다), "수요·수주 공백이 실적보다 먼저 배수에 반영되는 경로".
- **s07 을 고쳤으면 빌드 전에 grep**: `grep -n "{{per_ttm}}\|{{pbr_now}}\|{{per_now}}" sections/s01*.md sections/s13*.md sections/s14*.md` 로 옛 플레이스홀더·라벨이 남았는지 본다. decision.md 도 같은 값으로.
  **grep 범위는 섹션 파일만이 아니다** -- 하이브 재대조 잔재 2건은 `s14_short_thesis.md`(alias 섹션)와 `assumptions.json` 의 `catalysts[].impact`(촉매 표 임계값 "68% 유지")였다. 판정 임계값·EPS·목표가를 바꿨으면 `grep -rn "옛값" sections/ decision.md assumptions.json questions.json watchlist.json` 로 다섯 파일을 한 번에 본다.
- 급락·급등일의 재료가 공시 제목뿐이면 `ta_news_window.py` 로 그 날짜 창의 뉴스를 받는다(4/1 -11.8% = 모회사 교환사채).

### ~~절대 규칙 13~~ -- 폐기 (2026-09-18 사용자 실물 검토: "CJ프레시웨이 처음 나온 게 가독성이 낫다")

Gemini 피드백을 받아 요약 맨 앞에 '한 장 요약'(결론 한 줄·이유 세 줄·액션 표·맞는 투자자)과 맨 끝에 용어 박스를 넣었는데(CJ프레시웨이 2판·HD현대중공업 1~3판),
사용자가 두 리포트를 실물로 읽고 **그 전 형식(■ 3줄 마진노트 + 산문으로 바로 시작)이 더 읽힌다**고 판정했다. 블록이 늘면서 요약이 두 번 반복됐고
표·볼드가 첫 페이지를 조각냈다. **요약은 IR협의회 형식 그대로**(규칙 10): 기준 단위 한 줄 -> `> **한 줄:**` 3개 -> 산문. 액션·판정 지점은 산문과
s07 판단 블록·리스크 표의 '대응 트리거' 열에 있다. 용어는 첫 등장 문장 안에서 괄호로 푼다.
`ta_readability_gate` 는 남겨 두되 전 항목 WARN/SKIP(문장당 숫자·같은 금액 반복은 참고 지표로만 본다).
남는 교훈 하나: 같은 사실을 네 섹션이 되풀이하지 않는다 -- 한 곳이 숫자를 갖고 나머지는 가리킨다(R4 WARN).

### 절대 규칙 15 -- 정독은 요약으로 대체하지 않는다 (2026-09-20 사용자 결정, v5.24)
서브에이전트 요약·grep 발췌·투자포인트 제목 추출은 정독이 아니다. STEP 1.5 의 대상을 메인이 원문 그대로 읽고 노트를 남긴 뒤에만 s02·s04·s07 을 쓴다.
읽은 것과 안 읽은 것을 `notes/_summary.md` 첫 줄에 적는다. 차트는 텍스트 추출본에서 사라지므로 이미지 덱은 PNG 로 본다.
HD현대중공업 실측: 이 규칙 전 판은 12곳 목표가와 EPS 만 있었고, 규칙 후 판은 IBK 의 LPG 사슬·카타르 저선가 반박, LS 의 온사이트 발전단가 3배 반론, 메리츠 Q&A 의 2027년 납기 비공시 수주, 회사 덱의 함정 마진 6.0% 가 들어갔다.

## STEP 6 -- 작성 (메인 단독 -- 에프에스티 A/B 블라인드 판정 메인 6 / 에이전트 2 로 확정)
작성 에이전트 4 + humanizer + 편집자 1 조합(B)은 ②회사 밖·⑤리스크·⑥읽힘 세 축에서 위치를 바꿔도 졌다(마진노트 중복·600자 문단·요약 블록화, 본문 4.8만자).
B 가 낸 가치는 작성이 아니라 **검토**에서 나왔다(원자료 오류 3건, brief 오류 2건 발견) -> 에이전트는 critic·편집 검토로 쓴다.
섹션은 `data/{종목명}/ta/sections/*.md` 에 `{{플레이스홀더}}` 로 쓰고 빌더가 장부·시세·수급 값을 채운다(종가·장부가 바뀌면 재빌드만). 조사는 `{{a}}를` 처럼 붙이면 빌더가 받침에 맞춘다(에프에스티 빌더 `render()` 참고).
`scripts/_build_{종목명}_ta.py` → `scripts/analysis_{종목명}_ta.json`. **`meta.stock_name` 은 `{종목명}` 그대로**(데이터 경로).
- s01 첫 3개 산문 문단 합계 ≤ 700자(커버 카드 -- 생성기가 3문단·700자까지만 싣고 넘치는 문단은 뺀다, v5.25. 4문단 1,100자 규칙은 HD·하이브 실측에서 4번째 문단이 잘리고 재무표가 사라져 폐기). `peers` 는 배수 산정 대상과 같은 5사(국내 3 + 해외 2 권장), `_peer_snapshot.json` 을 그날 갱신(모의 500 이면 `_run_with_real_kis.py`). `opinion.risk_reward` 는 짧게(레일 폭).
  해외 비교기업은 `_peer_snapshot_global.json`(D4·generate_all 이 병합해 대조). **`flags`(forward_pe_suspect·fx_missing) 가 있는 값은 본문에 쓰지 않는다** -- 가와사키重 선행 PER 4.2 실측. s07 에 해외 표 한 개 + "우리 배수가 중국·일본·유럽 사이 어디인가" 한 문단.
- ORDER(v5.21) 에 `s08_esg` 를 리스크 앞에 끼운다. alias 키 재생성(CLAUDE.md "v5.0 키 스킴 분열").
- 작성하면서 `data/{종목명}/ta/coverage_map.json` 을 채운다: brief 의 필수(Y) ID 마다 `{"section", "quote"}`(본문에 실제로 넣은 문장 20자+) 또는 `{"excluded": "사유"}`.
- 투자자 적합성(요약 끝), 위험 시나리오 표의 '관찰 지표·대응 트리거' 열, 기준 단위 선언(요약 첫머리).
- **정독 노트를 본문으로 옮기는 법(v5.24, `reading_note_format.md` 표)**: s02 는 저자들의 논리를 우리 말로(촉발→데이터→반론→반박 순서가 있으면 그대로) 쓰고 문단 끝에 **확인된 것 / 가정인 것**을 나눈다. s04 는 "왜 지금 바뀌는가"를 병목→대안→수혜 순서로 정량으로. s05 는 증권사 실측을 **회사 IR 덱**으로 출처 교체하고 회사가 사유를 안 적은 것을 적는다. s07 은 증권사 방법표 + "왜 이 배수인가"(우리 배수를 그들의 근거로 다시 계산) + 해외 비교기업 표. s09 끝에 "앞으로 나올 뉴스" 표(12행 이하씩 나눔). s10 은 IR 덱 두 분기 부문표와 영업외 헤지 양면. 결정·요약 형식은 정독으로 바꾸지 않는다(바뀌면 재토론).
- **증권사 종목리포트는 투자포인트를 표로 집계한다**(사용자 지적 2026-09-18 "투자포인트가 주요 이슈"): `ta/reports/company/*.txt` 전편의 투자포인트를 뽑아 s02 에 `| 투자포인트 | 언급 리포트(N편 중) | 우리 판단 |` 표를 둔다. 빈도가 높은 포인트가 "시장이 가격에 넣은 가정"이고, **0편이 언급한 것**(HD현대중공업: 미포 합병 기저효과·파업)이 우리가 판정 지점으로 삼을 것이다. lite 에서는 메인이 직접, 전체판에서는 ta-sellside-analyst brief 의 '시장 기대 표'가 이 역할을 한다.

## STEP 7 -- 검증
게이트는 **마지막에 한 번 전체**를 돌리고, 중간 보정 때는 깨진 검증기 하나만 다시 돌린다(하이브 실측: 12종 재실행 7회가 시간을 먹었다). 치환 스크립트의 앵커는 기억이 아니라 grep 으로 먼저 뽑는다.
```bash
python scripts/ta_coverage_check.py {종목명}          # 반영 게이트 (0 FAIL)
# ⚠️ financial_summary.json 의 financials['{올해}'] 열은 매출·순이익만 반기 실측이고 ocf/capex/net_debt/비율은 Wisereport 연간 컨센(2026E)이다.
#    빌더의 반기 열(H1)에 그 열을 쓰지 말고 반기보고서 현금흐름표에서 직접 읽는다 (CJ프레시웨이 critic 1회차: OCF +1,233 -> 실제 -363).
python scripts/ta_readability_gate.py {종목명}        # 참고용(강제 없음): 문장당 숫자·같은 금액 반복 WARN
python scripts/ta_calc_ledger.py check {종목명}       # 본문 지표값 = 장부 (0 FAIL) + 규칙 9 기간 정합: per_scenarios 마다 eps_basis/per_basis 를 적고, 다르면 period_note(본문에 적은 이유) 없이는 FAIL, 미표기는 WARN (v5.25, 하이브 실측 FY27E x 12M 선행). WARN 은 반기·부문·타사·기준선 등 장부 밖 표기 -- 출처를 눈으로 확인하고 넘어간다. 반기 값은 '상반기/1H26' 을, 타사 값은 회사명을 30자 안에 적는다
python scripts/ta_industry_gate.py {종목명}          # G1~G6 산업현황 재료·요약 ■3·밸류 분리 (0 FAIL) -- 절대 규칙 8 의 밸류 용어 카운트는 G5 가 대신한다
python scripts/preflight_check.py {종목명}_ta  ...    # 기존 게이트는 analysis 경로를 _ta 로
python scripts/verify_numbers.py / verify_style.py / verify_facts.py / verify_tone.py / verify_content.py / source_coverage.py / section_rubric.py
```
기존 검증기가 `scripts/analysis_{종목}.json` 경로를 고정으로 읽으면, 임시로 `_ta` 파일을 그 이름으로 복사해 돌린 뒤 **원본을 즉시 복원**한다(원본 백업 확인 후).
그 다음 `report-critic` **1회**(호출 프롬프트는 기존 규칙 그대로 한 문장, 가이드 추가 금지). 파일 경로에는 analysis json 과 함께 `ta/decision.md` 를 준다 -- 에프에스티 critic 2 는 결정 이력을 읽고서 목표가가 매번 현재가 +6~10% 에 붙는 앵커링을 잡았다. 지적을 반영한 뒤에는 새 critic 을 부르지 않고 **같은 에이전트를 SendMessage 로 재개해 "지적한 항목만 고쳐졌는지 원문과 대조해라"** 를 시킨다(사용자 결정 2026-09-18: 2회차는 비용 대비 효과가 작다 -- CJ프레시웨이 1회차 20만 토큰으로 22건, 그중 A급 5건이 판정·게이트·토론이 전부 놓친 것이었다). 결정 수준 지적(현금흐름 부호 같은 것)이면 반영 전에 리스크 재토론(보수형+공격형, 방향 균형)을 거친다.
**critic·토론 반영 후 s01·s02 를 다시 잰다**(절대 규칙 8). 검증 루프는 밸류를 깊게 만드는 방향이라 요약이 산식으로 채워진다. 넘으면 사건 서술로 되돌린다:
```bash
python - <<'EOF'
import json,re,sys
d=json.load(open('scripts/analysis_{종목명}_ta.json',encoding='utf-8'))['sections']
val=re.compile(r'배수|EBITDA|ROE|RIM|PBR|SOTP|목표주가|주당가치|현재가 대비|확률가중|내재'); news=re.compile(r'보도|공시했|기사|뉴스|초과수익|발주|납품|증여|가득조건')
for k,lim in (('s01_opinion_thesis',8),('s02_thesis_catalysts',15)):
    v,n=len(val.findall(d[k])),len(news.findall(d[k])); print(k,'밸류',v,'뉴스',n,'FAIL' if v>lim or v>n else 'PASS')
EOF
```

## STEP 8 -- PDF
```bash
python scripts/ta_render.py {종목명}      # output/{종목명}_ta/ 에 생성, 기존 output/{종목명}/ 은 복원
```
`output/{종목명}_ta/png/` 의 커버와 기술적 분석 페이지를 눈으로 본다(캡션 "08 · TECHNICAL ANALYSIS", 커버 불릿 3개, 빈 페이지).

## STEP 9 -- 평가 (파일럿 필수)
1. **블라인드 판정** -- IR협의회 보고서가 있으면: 두 문서를 텍스트로 뽑아 발간사·작성자·리포트명 제거 → A/B 무작위 → `ta/judge/` → `ta-report-judge`.
   ```bash
   python scripts/ta_judge_export.py scripts/analysis_{종목명}_ta.json data/{종목명}/ta/judge/arm_ta.txt
   python scripts/ta_judge_pair.py data/{종목명}/ta/judge/run1 arm_ta.txt other.txt {이른 발간일} [--swap]   # 2회, 위치 교차
   ```
   판정자 프롬프트는 run 폴더의 A.txt/B.txt/cutoff.txt 경로 + "mapping 은 열지 말 것" 만. 두 판정을 축별로 합산한다.
2. **대조군(lite)** -- 같은 종목에서 분석가·토론·리스크 에이전트 없이 메인 단독으로 STEP 1 수집물 + STEP 3 장부 + STEP 7 반영 검사만 적용한 리포트를 만든다.
   기존 `/research` 리포트 / lite / 전체 `-ta` 를 같은 판정자로 비교한다. **lite ≈ 전체면 분업은 비용만 늘린다.**
3. **제거 실험** -- 토론 전후 투자포인트·리스크 변화, 리스크 토론 전후 등급·목표가 변화를 `docs/research-ta-ablation.md` 에 수치로 기록.
4. 시간·서브에이전트 호출 수 기록.
