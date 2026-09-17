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

## STEP 0 -- 준비
```bash
python scripts/source_health.py
python -c "import sys; sys.path.insert(0,'scripts'); import ta_common as t; print(t.resolve_stock('{종목명}'))"
```
기존 `/research` STEP 1 수집물이 7일 넘었거나 없으면 먼저 갱신한다(v5.4 규칙 8):
`financial_summary.py`(KIS 500 이면 `_run_with_real_kis.py`) · `collect_dart_full.py` · `collect_dart_filings.py` · `dart_quarterly.py` ·
`wisereport_consensus.py` · `fdr_band.py` · `volatility_beta.py` · `peer_snapshot.py`(업종키 결과를 눈으로 확인, v5.18 규칙 3) · `price_cycles.py` · `driver_scan.py` · `evidence_scan.py`

## STEP 1 -- 신규 수집 (결정론)
업종 category·키워드는 `ta/dart/business.txt` 의 1~2장을 보고 정한다(`ta_dart_diff` 를 먼저 돌린다).
```bash
python scripts/ta_dart_diff.py {종목명}
python scripts/ta_collect_news.py {종목명}
python scripts/ta_event_study.py {종목명}
python scripts/ta_calendar.py {종목명}
python scripts/ta_market_data.py {종목명}
python scripts/ta_board_flow.py {종목명}
python scripts/ta_collect_reports.py {종목명} --industry-category {업종} --keywords {제품,전방,경쟁사}
python scripts/macro_data.py ...   # KR 스냅샷을 data/{종목명}/ta/macro.json 으로 저장
python scripts/ta_trade_stats.py {종목명}          # ta/trade_query.json (HS 4~10자리·국가 ISO2·months) 를 먼저 쓴다 -- 사업보고서 II장 제품·수출 지역
python scripts/ta_customer_docs.py {종목명}        # ta/customers.json [{name, kind: US|KR, ticker(US), keywords}] -- 고객사·장비사·경쟁사 10-K/10-Q·기업설명회
python scripts/ta_news_body.py {종목명}            # 뉴스 API 는 요약 150자만 준다 -- 기사 URL 을 열어 본문 확보(네이버 #dic_area / trafilatura)
python scripts/ta_kind_ir.py {종목명}              # KIND IR자료실에서 기업설명회 발표자료 PDF (DART 공시는 개최 안내문뿐)
python scripts/ta_company_voice.py {종목명} --irtv # IR 발표자료 + 발언 기사(전문 기준) + IRTV 자막 -> ta/company_voice.md
python scripts/ta_plan_agents.py {종목명}
```
IR협의회 22편 재료 비중은 DART 26 / 자체 추정 26 / 회사 설명 18 / 협회·정부 12 / 고객사·경쟁사 8 / **뉴스 2** (%) 다
(`docs/research-ta/kirs-construction.md`). 뉴스는 재료가 아니라 사건 표기다. 위 다섯이 협회·정부·고객사·회사 설명 재료의 대체재다.
에프에스티 실측: 관세청 8시리즈 / 램리서치 24·삼성전자 12 인용 / 뉴스 본문 48/57 / KIND IR 발표자료 3건(각 22p) / 발언 기사 8건.
각 스크립트 뒤에 `ta/manifest.json` 의 status 를 본다. **failed 는 넘어가지 말고 원인을 확인**한다(조용한 실패 패턴).
`ta/agent_plan.json` 의 calls 가 분석가 호출 목록이다. **인원은 종목마다 다르다.**

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

### 절대 규칙 13 -- 첫 페이지에서 행동할 수 있어야 한다 (가독성, 2026-09-18 사용자 지적 "이해하기 어려워 제미나이에게 물어본다")

기존 검증기는 전부 "숫자를 더 넣어라" 방향이라 반대쪽 검사가 없으면 글이 산식으로 채워진다(CJ프레시웨이: 문장당 숫자 3.3개, 판정 ⑥ 패배).
- **s01 맨 앞 `#### 한 장 요약 -- 결론부터`**: 결론 한 줄(등급·목표가·기대가치) / 이유 세 줄(숫자 최소, 말로) / **액션 플랜 표**(`| 언제 | 무엇을 확인한다 | 확인되면 | 안 되면 |`, 3행 안팎, 날짜형 판정 지점) / 맞는 투자자·안 맞는 투자자 한 줄. 기존 `> **한 줄:**` 3개는 그 뒤에 그대로 둔다(G4 순서).
- **s01 맨 끝 `#### 용어 -- 이 리포트에서 처음 보는 말`**: 8~10개, `- **용어**: 한 줄 풀이`. 산업 게이트 G1 은 이 블록을 분모에서 뺀다.
- 본문에서 같은 사실(단기차입 581→1,426, 11/26 콜 등)을 네 섹션이 되풀이하지 않는다 -- 요약·투자포인트·리스크·재무 중 **한 곳이 숫자를 갖고 나머지는 가리킨다**. `ta_readability_gate` R4 가 5회+ 반복을 경고한다.
- 게이트: `python scripts/ta_readability_gate.py {종목명}` R1 액션 표 / R3 용어 박스 0 FAIL, R2 문장당 숫자·R4 반복은 WARN(기준선 미확정).

## STEP 6 -- 작성 (메인 단독 -- 에프에스티 A/B 블라인드 판정 메인 6 / 에이전트 2 로 확정)
작성 에이전트 4 + humanizer + 편집자 1 조합(B)은 ②회사 밖·⑤리스크·⑥읽힘 세 축에서 위치를 바꿔도 졌다(마진노트 중복·600자 문단·요약 블록화, 본문 4.8만자).
B 가 낸 가치는 작성이 아니라 **검토**에서 나왔다(원자료 오류 3건, brief 오류 2건 발견) -> 에이전트는 critic·편집 검토로 쓴다.
섹션은 `data/{종목명}/ta/sections/*.md` 에 `{{플레이스홀더}}` 로 쓰고 빌더가 장부·시세·수급 값을 채운다(종가·장부가 바뀌면 재빌드만). 조사는 `{{a}}를` 처럼 붙이면 빌더가 받침에 맞춘다(에프에스티 빌더 `render()` 참고).
`scripts/_build_{종목명}_ta.py` → `scripts/analysis_{종목명}_ta.json`. **`meta.stock_name` 은 `{종목명}` 그대로**(데이터 경로).
- s01 첫 4개 산문 문단 합계 ≤ 1,100자(커버 카드). `peers` 는 배수 산정 대상과 같은 5사, `_peer_snapshot.json` 을 그날 갱신(모의 500 이면 `_run_with_real_kis.py`). `opinion.risk_reward` 는 짧게(레일 폭).
- ORDER(v5.21) 에 `s08_esg` 를 리스크 앞에 끼운다. alias 키 재생성(CLAUDE.md "v5.0 키 스킴 분열").
- 작성하면서 `data/{종목명}/ta/coverage_map.json` 을 채운다: brief 의 필수(Y) ID 마다 `{"section", "quote"}`(본문에 실제로 넣은 문장 20자+) 또는 `{"excluded": "사유"}`.
- 투자자 적합성(요약 끝), 위험 시나리오 표의 '관찰 지표·대응 트리거' 열, 기준 단위 선언(요약 첫머리).

## STEP 7 -- 검증
```bash
python scripts/ta_coverage_check.py {종목명}          # 반영 게이트 (0 FAIL)
# ⚠️ financial_summary.json 의 financials['{올해}'] 열은 매출·순이익만 반기 실측이고 ocf/capex/net_debt/비율은 Wisereport 연간 컨센(2026E)이다.
#    빌더의 반기 열(H1)에 그 열을 쓰지 말고 반기보고서 현금흐름표에서 직접 읽는다 (CJ프레시웨이 critic 1회차: OCF +1,233 -> 실제 -363).
python scripts/ta_readability_gate.py {종목명}        # 절대 규칙 13: 액션 표·용어 박스 0 FAIL, 숫자 밀도·반복은 WARN
python scripts/ta_calc_ledger.py check {종목명}       # 본문 지표값 = 장부 (0 FAIL). WARN 은 반기·부문·타사·기준선 등 장부 밖 표기 -- 출처를 눈으로 확인하고 넘어간다. 반기 값은 '상반기/1H26' 을, 타사 값은 회사명을 30자 안에 적는다
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
