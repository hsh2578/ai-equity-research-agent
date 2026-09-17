# /research-ta 분석가 brief 규약 (모든 ta-*-analyst 공통)

`scripts/ta_coverage_check.py` 가 이 형식을 기계적으로 읽는다. 형식이 틀리면 리포트 게이트가 FAIL 한다.

## 왜 이 형식인가

`/research` 는 받아 둔 뉴스·공시를 리포트에 넣지 못했다. 한 에이전트가 모든 자료를 한 맥락에서 읽고 쓰면
자료가 많을수록 훑고 지나간다. `/research-ta` 는 분석가가 자기 자료만 끝까지 읽고 **항목 단위로** 보고하고,
작성자는 항목마다 "어디에 반영했는지 / 왜 뺐는지"를 남긴다. 그래서 항목에는 ID 가 필요하다.

## 파일

`data/{종목}/ta/brief_{call_id}.md` -- call_id 는 `ta/agent_plan.json` 의 값(`fundamentals#2` 는 `brief_fundamentals-2.md`).

## 구조

```markdown
# {역할} brief -- {종목} ({작성일})

## 한 줄 결론
(이 자료 묶음에서 투자 판단에 가장 중요한 것 1~2문장)

## 항목
| ID | 필수 | 내용 | 수치·날짜 | 출처 | 조건·단서·반대 증거 | 반영할 섹션 |
|---|---|---|---|---|---|---|
| N01 | Y | ... | ... | data/에프에스티/ta/news.json#N0012 | ... | s02_thesis_catalysts |

## 자료 한계
(수집 실패·미수집·기간 한계를 manifest/출력의 status 그대로. 추정으로 메우지 않는다)
```

## 규칙

1. **ID**: 역할 접두 + 두 자리 번호. 접두는 news `N`, fundamentals `F`, sellside `SS`, industry `I`, macro `MA`, market `T`.
   분할 호출(`fundamentals#2`)은 번호를 이어서 쓴다(`F21`부터 등) -- 같은 ID 가 두 brief 에 있으면 FAIL.
   메인이 호출할 때 시작 번호를 알려준다.
2. **필수 = Y 는 적게**. 결론을 바꿀 수 있는 항목만 Y. 나머지는 N.
   - news: |D0 초과수익| 상위 5개 그룹의 원인 후보, 최근 90일 주요사항보고서
   - fundamentals: 직전 보고서 대비 사업 서술이 바뀐 곳(`dart_diff` kind=text) 중 매출·수익성·고객·생산능력·위험에 닿는 것
   - 그 밖의 역할: 투자포인트·리스크·밸류에이션 가정을 바꾸는 것
   작성자는 Y 항목을 전부 본문 반영 또는 제외 사유로 처리해야 한다. Y 가 많으면 리포트가 사건 목록이 된다.
3. **출처는 파일:줄 또는 파일#ID 또는 저장된 웹 자료 경로**. 원문 인용은 그 파일에서 grep 으로 찾을 수 있는 문자열 그대로.
   웹에서 가져온 자료는 `ta/web_sources/NN.md` 로 저장한 뒤 그 경로를 단다.
4. **조건·단서·반대 증거 열은 비우지 않는다**. 없으면 "확인한 반대 증거 없음 (확인 범위: ...)".
   요약만 받은 작성자가 뉘앙스를 잃지 않게 하는 칸이다.
5. **추정 금지**. 자료에 없으면 "미수집" 또는 "자료 없음". 수집 실패와 0건을 구분한다(`status` 값 그대로 옮긴다).
6. **초과수익은 상관이다**. "뉴스 때문에 올랐다"가 아니라 "뉴스가 난 날 시장 대비 +N%"로 쓴다.
   `type=reaction`(특징주·급등 기사)은 원인 후보로 쓰지 않는다.
7. **계산하지 않는다**. 비율·레버리지·밸류에이션 수치는 `ta/calc_ledger.json` 에 있는 값만 인용하고, 없으면 "장부에 없음".
9. **industry brief 는 항목마다 출처 종류 열을 둔다**: `협회·정부 통계 | 산업 리서치(SEMI·SNE·TrendForce·IDC) | 고객사·경쟁사 공개자료(10-K/10-Q·기업설명회) | 회사 설명(IR 자료·인터뷰)`. **뉴스는 종류로 인정하지 않는다** -- IR협의회 22편에서 뉴스는 재료의 2% 다(`docs/research-ta/kirs-construction.md`). 입력 파일: `ta/trade_stats.json`, `ta/customer_docs/*.md`, `ta/company_voice.md`.
8. 반영할 섹션 값은 정규 12키 중 하나: `s01_opinion_thesis s02_thesis_catalysts s03_company_overview s04_industry_competition s05_management_fieldcheck s06_financial s07_valuation s08_esg(=기술적 분석) s09_scenarios_risks s10_earnings_consensus s11_supply_shareholder s12_action_plan`.
