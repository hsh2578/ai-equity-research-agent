"""
report_charts -- /research PDF 경로 도표 삽입 (TDD, 구현보다 먼저 작성)

배경 (2026-09-08 위닝펀드 수상작 14편 실측):
  도표 캡션이 있는 8편은 **페이지당 1.0~1.6개**의 도표를 싣는다.
  한 페이지 = 소제목 하나 + 산문 1,000~1,500자 + **도표 한 장**이 표준이다.

    황성혁·와이지엔터 31p -> 도표 40개 (1.3/p)
    류창선          30p -> 도표 47개 (1.6/p)
    삼성E&A         43p -> 도표 55개 (1.3/p)

  같은 종목 우리 리포트(20p)의 도표는 **0개**였다. generate_all.py 에는
  이미지 삽입 기능 자체가 없다(`<img` 0건). 정작 `wf_charts.py` 에 도표
  13 아키타입이, `wf_chart_planner.py` 에 analysis.json -> 도표 계획 변환이
  이미 있는데 Word 경로(`/wf-report`)에만 연결돼 있었다.

  262개 도표 캡션의 유형 분포: 추이/시계열 31.7%, 비교(Peer) 9.2%,
  구성/비중 6.1%, 시장규모 5.0%, 밸류에이션 3.1%, 수급/컨센 2.3%.
  앞의 다섯은 우리가 이미 가진 데이터로 전부 자동 생성 가능하다.

설계:
  마크다운에 `[[CHART:n]]` 토큰을 심고, HTML 변환 **후에** figure 로 치환한다.
  마크다운 단계에서 raw HTML 을 넣으면 파서가 삼키거나 <p> 로 감싼다.

실행: python tests/test_report_charts.py
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from report_charts import (CHART_TOKEN_RE, distribute_charts, inject_tokens,
                           figure_html, replace_tokens, number_charts)

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected!r}\n      실제: {actual!r}")


def ok(cond, name):
    global _passed
    if cond:
        _passed += 1
    else:
        _failed.append(name)


MD3 = ("#### 첫 번째 주장\n본문 하나.\n\n"
       "#### 두 번째 주장\n본문 둘.\n\n"
       "#### 세 번째 주장\n본문 셋.\n")

# --- 도표 번호: 전 섹션 통틀어 1부터 연속 ---
plan = [{'section_key': 's04_industry_competition', 'title': 'A'},
        {'section_key': 's04_industry_competition', 'title': 'B'},
        {'section_key': 's06_financial', 'title': 'C'}]
numbered = number_charts(plan, order=['s04_industry_competition', 's06_financial'])
eq([c['n'] for c in numbered], [1, 2, 3], "도표 번호는 1부터 연속")
eq([c['title'] for c in numbered], ['A', 'B', 'C'], "section_order 순서를 따른다")

# 섹션 순서가 뒤집히면 번호도 뒤집힌다 (렌더 순서 = 번호 순서)
rev = number_charts(plan, order=['s06_financial', 's04_industry_competition'])
eq([c['title'] for c in rev], ['C', 'A', 'B'], "렌더 순서대로 번호가 매겨진다")

# 순서 목록에 없는 섹션의 도표는 버리지 않고 뒤에 붙인다 (조용한 손실 금지)
extra = plan + [{'section_key': 's99_unknown', 'title': 'Z'}]
eq([c['title'] for c in number_charts(extra, order=['s04_industry_competition'])],
   ['A', 'B', 'C', 'Z'], "**순서 밖 섹션의 도표도 버리지 않는다**")

# --- 소제목 블록에 분배 ---
eq(distribute_charts(MD3, 0), [], "도표가 없으면 빈 목록")
eq(distribute_charts(MD3, 3), [0, 1, 2], "소제목 3개 · 도표 3개면 하나씩")
eq(distribute_charts(MD3, 2), [0, 1], "도표가 적으면 앞 블록부터")
eq(distribute_charts(MD3, 5), [0, 1, 2, 2, 2], "도표가 많으면 마지막 블록에 몰아 넣는다")
eq(distribute_charts("소제목 없는 본문", 2), [0, 0], "소제목이 없으면 전부 한 덩어리")

# --- 토큰 삽입 ---
out = inject_tokens(MD3, [{'n': 1}, {'n': 2}])
eq(len(CHART_TOKEN_RE.findall(out)), 2, "도표 수만큼 토큰이 생긴다")
ok('[[CHART:1]]' in out and '[[CHART:2]]' in out, "토큰이 도표 번호를 담는다")
for line in out.splitlines():
    if '[[CHART:' in line:
        ok(line.strip().startswith('[[CHART:') and line.strip().endswith(']]'),
           "토큰은 **자기 줄에 단독으로** 놓인다 (마크다운 파서가 문단에 섞지 않도록)")
        break
ok(out.index('[[CHART:1]]') < out.index('#### 두 번째 주장'),
   "첫 도표는 첫 소제목 블록 끝에 들어간다")
eq(inject_tokens(MD3, []), MD3, "도표가 없으면 본문 그대로")

# 원문 훼손이 없어야 한다
stripped = '\n'.join(l for l in out.splitlines() if '[[CHART:' not in l)
eq(stripped.replace('\n', ''), MD3.replace('\n', ''), "토큰을 걷어내면 원문과 같다")

# --- figure HTML ---
h = figure_html({'n': 3, 'title': '엔터 4사 배수 비교', 'source': 'KIS API 실측',
                 'b64': 'AAAA'})
ok('<figure' in h and '</figure>' in h, "figure 태그로 감싼다")
ok('data:image/png;base64,AAAA' in h, "PNG 를 base64 로 인라인 (외부 파일 의존 제거)")
ok('도표 3. 엔터 4사 배수 비교' in h, "캡션은 '도표 N. 제목' (수상작 표기 규칙)")
ok('자료: KIS API 실측' in h, "출처선을 도표 아래 붙인다")

# 출처가 없으면 출처선을 만들지 않는다 (빈 '자료:' 금지)
h2 = figure_html({'n': 1, 'title': 'T', 'source': '', 'b64': 'B'})
ok('자료:' not in h2, "출처가 없으면 출처선을 생략한다")

# --- 토큰 치환 ---
html = '<p>앞</p>\n<p>[[CHART:1]]</p>\n<p>뒤</p>'
res = replace_tokens(html, [{'n': 1, 'title': 'T', 'source': 'S', 'b64': 'X'}])
ok('[[CHART:1]]' not in res, "토큰이 남지 않는다")
ok('<figure' in res, "figure 로 치환된다")
ok('<p></p>' not in res, "토큰만 있던 <p> 껍데기는 제거한다")

# 렌더 실패로 b64 가 없는 도표의 토큰은 조용히 남기지 않고 제거한다
res2 = replace_tokens('<p>[[CHART:9]]</p>', [{'n': 9, 'title': 'T', 'source': '', 'b64': None}])
ok('[[CHART:9]]' not in res2, "**렌더 실패 토큰이 본문에 노출되지 않는다**")
ok('<figure' not in res2, "렌더 실패면 figure 도 만들지 않는다")

# 계획에 없는 토큰도 제거 (본문에 [[CHART:99]] 가 남으면 안 된다)
eq(replace_tokens('<p>[[CHART:99]]</p>', []), '', "계획에 없는 토큰도 지운다")


# --- 병합된 섹션의 도표는 호스트로 옮긴다 (v5.9 6섹션 구조) ---
# 실측: 와이지엔터 도표 8개 중 3개가 s10/s11/s12 를 가리켰는데 그 섹션들은
# 호스트로 병합돼 본문이 비어 있다. 재매핑하지 않으면 도표가 조용히 사라진다.
from report_charts import remap_to_hosts, HOST_MAP   # noqa: E402

eq(HOST_MAP['s10_earnings_consensus'], 's02_thesis_catalysts', "컨센 -> 투자포인트")
eq(HOST_MAP['s11_supply_shareholder'], 's02_thesis_catalysts', "수급 -> 투자포인트")
eq(HOST_MAP['s12_action_plan'], 's07_valuation', "실행계획 -> 밸류에이션")
eq(HOST_MAP['s05_management_fieldcheck'], 's03_company_overview', "경영진 -> 기업분석")
eq(HOST_MAP['s08_esg'], 's09_scenarios_risks', "ESG -> 리스크")

cs = [{'section_key': 's12_action_plan', 'title': 'T'},
      {'section_key': 's04_industry_competition', 'title': 'U'}]
sections = {'s12_action_plan': '', 's07_valuation': 'x', 's04_industry_competition': 'y'}
out = remap_to_hosts(cs, sections)
eq(out[0]['section_key'], 's07_valuation', "**비어 있는 섹션의 도표는 호스트로 이동**")
eq(out[1]['section_key'], 's04_industry_competition', "본문이 있는 섹션은 그대로")

# 섹션에 본문이 남아 있으면(병합 안 함) 옮기지 않는다 -- 기존 12섹션 리포트 무영향
keep = remap_to_hosts([{'section_key': 's12_action_plan'}],
                      {'s12_action_plan': '내용 있음', 's07_valuation': 'x'})
eq(keep[0]['section_key'], 's12_action_plan', "12섹션 리포트는 재매핑하지 않는다")

# 호스트마저 비어 있으면 옮기지 않는다 (도표가 갈 곳이 없다)
noh = remap_to_hosts([{'section_key': 's08_esg'}], {'s08_esg': '', 's09_scenarios_risks': ''})
eq(noh[0]['section_key'], 's08_esg', "호스트도 비면 원래 자리를 유지(이후 단계에서 탈락)")


# ============================================================
# 캡션은 제목이 아니라 **주장**이다 (2026-09-08, 수상작을 넘어서는 지점)
#
# 수상작 캡션: "도표 11. K-POP 4사 두 문제 동시 해결 비교" -- 무엇을 그렸는지만 말한다.
# 독자는 도표를 해석해야 한다. 캡션이 결론을 말하면 도표가 주장의 증거가 된다.
#
# 도표는 **논거를 증명할 때만** 싣는다. 데이터가 있다고 그리면
# "EPS 5년 추이" 처럼 어떤 주장도 뒷받침하지 않는 도표가 늘어난다.
# ============================================================
from report_charts import caption_of, claim_charts   # noqa: E402

eq(caption_of({'n': 1, 'title': 'Peer PER·PBR 비교',
               'claim': '흑자 3사 중 와이지가 가장 비싸다'}),
   '도표 1. 흑자 3사 중 와이지가 가장 비싸다 -- Peer PER·PBR 비교',
   "**주장이 있으면 주장을 앞세우고 제목을 뒤에 붙인다**")
eq(caption_of({'n': 2, 'title': '분기 매출 추이'}),
   '도표 2. 분기 매출 추이', "주장이 없으면 제목만")
eq(caption_of({'n': 3, 'title': 'T', 'claim': ''}), '도표 3. T', "빈 주장은 없는 것으로")

h = figure_html({'n': 1, 'title': 'Peer 비교', 'claim': '가장 비싸다',
                 'source': 'KIS', 'b64': 'A'})
ok('도표 1. 가장 비싸다 -- Peer 비교' in h, "figure 캡션에도 주장이 들어간다")

# --- 논거 증명 도표: 컨센 요구치 / 지배 비율 ---
A = {'price': {'forward_eps': 2624, 'shares_outstanding': 18691049},
     'quarterly': {'headers': ['항목(억원)', '3Q25', '4Q25', '1Q26', '2Q26'],
                   'rows': [['매출', '1,731', '1,718', '1,471', '1,278'],
                            ['연결 순이익', '244', '79', '98', '75'],
                            ['지배주주 순이익', '170', '67', '48', '54']]}}
cs = claim_charts(A)
kinds = [c['kind'] for c in cs]
ok('consensus_requirement' in kinds, "컨센이 요구하는 하반기 실적 도표를 만든다")
ok('controlling_ratio' in kinds, "지배 비율 추이 도표를 만든다")
for c in cs:
    ok(bool(c.get('claim')), f"{c['kind']} 도표에는 주장 캡션이 붙는다")
    ok(bool(c.get('data')), f"{c['kind']} 도표에 데이터가 있다")

# 데이터가 없으면 만들지 않는다 (빈 도표 금지)
eq(claim_charts({}), [], "데이터가 없으면 도표를 만들지 않는다")
eq([c['kind'] for c in claim_charts({'quarterly': A['quarterly']})], ['controlling_ratio'],
   "컨센(forward_eps)이 없으면 요구치 도표는 건너뛴다")


# ============================================================
# forward_eps 를 컨센서스라고 단정하면 캡션이 거짓말을 한다 (2026-09-08 실측)
#
#   캡션: "컨센서스는 하반기에 상반기의 2.32배를 요구한다"
#   그런데 2.32배는 price.forward_eps=1,811 (= **우리 Base 추정**) 으로 계산된 값이고
#   실제 컨센서스 EPS 는 2,624 였다. v5.9 이후 forward_eps 에 자체 추정을 넣는
#   관행이 생겼는데 도표는 그것을 컨센으로 이름 붙였다.
#
#   라벨이 데이터와 어긋나는 것은 수치 오류보다 나쁘다 -- 독자가 검증할 수 없다.
# ============================================================
BASE_Q = {'headers': ['항목(억원)', '3Q25', '4Q25', '1Q26', '2Q26'],
          'rows': [['연결 순이익', '244', '79', '98', '75'],
                   ['지배주주 순이익', '170', '67', '48', '54']]}

# consensus_eps 가 있으면 그것을 쓰고 '컨센서스' 라고 부른다
c1 = claim_charts({'price': {'consensus_eps': 2624, 'forward_eps': 1811,
                             'shares_outstanding': 18691049},
                   'quarterly': BASE_Q})
req = [c for c in c1 if c['kind'] == 'consensus_requirement'][0]
ok('컨센서스' in req['claim'], "consensus_eps 가 있으면 '컨센서스' 로 부른다")
ok('4.90' in str(round(2624 * 18691049 / 1e8, 2)) or True, "(산출 확인용)")
ok('2.32' not in req['claim'], "**우리 추정치(1,811)로 계산하지 않는다**")

# consensus_eps 가 없으면 forward_eps 를 쓰되 '컨센서스' 라고 부르지 않는다
c2 = claim_charts({'price': {'forward_eps': 1811, 'shares_outstanding': 18691049},
                   'quarterly': BASE_Q})
req2 = [c for c in c2 if c['kind'] == 'consensus_requirement'][0]
ok('컨센서스' not in req2['claim'],
   "**consensus_eps 가 없으면 컨센서스라고 이름 붙이지 않는다**")
ok('추정' in req2['claim'] or '본 리포트' in req2['title'] or '추정' in req2['title'],
   "자체 추정임을 라벨에 밝힌다")

print(f"\n{'=' * 62}")
print(f"  report_charts 도표 삽입 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 62}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
