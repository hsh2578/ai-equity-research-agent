"""
verify_style C21 재정의 + C23/C24 신설 -- 위닝펀드 수상작 12편 실측 기준 (TDD)

배경 (2026-09-08, 수상작 12편 페이지 배분 실측):

    섹션        수상작   우리(와이지엔터 v6)
    산업         26%          5.6%
    기업         19%          7.7%
    투자포인트    17%         14.3%
    ------------------------------
    스토리 합    62%         27.6%
    재무         12%         11.9%   <- 문제가 아니었다

  기존 C21(스토리/재무+밸류 >= 1.5배)은 겨눈 곳이 틀렸다. 재무 비중은 수상작과
  거의 같았고, 진짜 원인은 **수상작에 존재하지도 않는 섹션 5개**
  (ESG·실행계획·수급·경영진·컨센)가 본문의 32% 를 먹은 것이었다.
  분모를 재무로 잡으면 그 32% 가 보이지 않는다. -> **본문 전체 대비 비중**으로 바꾼다.

  기준 55% 는 임의값이 아니라 수상작 실측 62% 에서 7%p 여유를 둔 값이다.

C23 (소제목 단위 주장):
  수상작은 **한 페이지 = 한 소제목 = 1,000~1,500자 + 도표 1장**이다.
  본인 수상작(와이지엔터 31p)의 소제목은 "엔터 4사 -39%, 컨센은 +6%",
  "주가는 라인업이 비면 빠지고, 차면 오른다" 처럼 그 페이지가 증명할 명제 하나다.
  한 소제목 아래 1,800자가 넘으면 주장이 뭉쳐 있다는 뜻이다.

C24 (산업분석의 종목 착지):
  수상작 산업분석은 매 소제목이 본 종목으로 착지한다.
  실측 인용(p4 끝): "와이지엔터테인먼트도 이 세 흐름에서 벗어나 있지 않으며,
  4사 중 가장 낮은 PER 16배는 세 가지 외부 요인이 한꺼번에 누른 결과다."
  종목명이 한 번도 안 나오는 산업 소제목은 남의 산업 리포트다.

실행: python tests/test_verify_style_wf.py
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from verify_style import (check_c21_story_weight, check_c23_heading_blocks,
                          check_c24_industry_anchor, split_heading_blocks,
                          STORY_SHARE_MIN, HEADING_MAX)

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected!r}\n      실제: {actual!r}")


def close(actual, expected, name, tol=1.0):
    global _passed
    if actual is not None and abs(actual - expected) <= tol:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected}\n      실제: {actual}")


# ============ C21: 본문 전체 대비 스토리 비중 ============
eq(STORY_SHARE_MIN, 55, "기준 55% (수상작 실측 62% 에서 7%p 여유)")

# 와이지엔터 v6 실측 재현 (정규 12키, 자수)
YG = {'s01_opinion_thesis': 1655, 's02_thesis_catalysts': 6605,
      's03_company_overview': 3564, 's04_industry_competition': 2584,
      's05_management_fieldcheck': 1983, 's06_financial': 5485,
      's07_valuation': 5281, 's08_esg': 1615, 's09_scenarios_risks': 4314,
      's10_earnings_consensus': 4238, 's11_supply_shareholder': 2705,
      's12_action_plan': 6134}
yg = {k: 'x' * v for k, v in YG.items()}
share, ok = check_c21_story_weight(yg)
close(share, 27.6, "와이지엔터 v6 실측 27.6%")
eq(ok, False, "27.6% 는 FAIL")

# 위닝펀드 구조로 재편하면 통과한다 (통과 경로가 실제로 존재하는지 확인)
WF = {'s01_opinion_thesis': 1600, 's02_thesis_catalysts': 7500,
      's03_company_overview': 8500, 's04_industry_competition': 11500,
      's05_management_fieldcheck': 0, 's06_financial': 5300,
      's07_valuation': 7000, 's08_esg': 0, 's09_scenarios_risks': 4400,
      's10_earnings_consensus': 0, 's11_supply_shareholder': 0,
      's12_action_plan': 0}
share2, ok2 = check_c21_story_weight({k: 'x' * v for k, v in WF.items()})
close(share2, 60.0, "6섹션 재편 시 약 60%", 2.0)
eq(ok2, True, "재편하면 통과 -- **통과 경로가 존재한다**")

# alias 키만 있는 리포트도 읽는다 (verify_style 은 구 v5.1 스킴을 읽어 왔다)
alias_only = {'s02_investment_points': 'x' * 7500, 's03_company_overview': 'x' * 8500,
              's04_industry': 'x' * 11500, 's08_financial': 'x' * 5300,
              's09_valuation': 'x' * 7000, 's10_scenarios_risks': 'x' * 4400,
              's01_opinion': 'x' * 1600}
share3, ok3 = check_c21_story_weight(alias_only)
close(share3, 60.0, "alias 키만 있어도 동일하게 계산", 2.0)

# 정규 + alias 가 함께 있어도 **이중 계산하지 않는다**
both = dict(yg)
both['s08_financial'] = both['s06_financial']       # 표준 alias 재생성 상태
both['s04_industry'] = both['s04_industry_competition']
share4, _ = check_c21_story_weight(both)
close(share4, 27.6, "**alias 를 이중 계산하지 않는다** (정규 우선)")

eq(check_c21_story_weight({}), (None, None), "본문이 없으면 판정 불가")

# ============ C23: 소제목 블록 분량 ============
eq(HEADING_MAX, 1800, "소제목 블록 상한 1,800자 (수상작 페이지당 1,000~1,500자)")

md = ("#### 엔터 4사 -39%, 컨센은 +6%\n" + "가" * 900 +
      "\n#### 멀티플이 깎인 세 가지 이유\n" + "나" * 800)
blocks = split_heading_blocks(md)
eq(len(blocks), 2, "#### 소제목으로 블록 분리")
eq(blocks[0][0], "엔터 4사 -39%, 컨센은 +6%", "소제목 텍스트 추출")

eq(check_c23_heading_blocks({'s04_industry_competition': md}), [],
   "900자 블록은 통과")

fat = "#### 하나로 뭉친 소제목\n" + "다" * 2500
over = check_c23_heading_blocks({'s04_industry_competition': fat})
eq(len(over), 1, "2,500자 블록은 적발")
eq(over[0][1], "하나로 뭉친 소제목", "적발된 소제목명")

# 소제목이 아예 없으면 섹션 전체가 한 덩어리다 -- 길면 적발한다
eq(len(check_c23_heading_blocks({'s04_industry_competition': "라" * 2500})), 1,
   "소제목 없는 긴 섹션도 적발 (페이지 단위 주장이 아니다)")
eq(check_c23_heading_blocks({'s04_industry_competition': "라" * 900}), [],
   "소제목 없어도 짧으면 통과")

# 표는 분량에서 뺀다 (도표는 페이지에 같이 들어간다)
tbl = "#### 소제목\n" + "마" * 900 + "\n" + ("| a | b |\n" * 200)
eq(check_c23_heading_blocks({'s04_industry_competition': tbl}), [],
   "표 행은 소제목 분량에서 제외")

# 재무/밸류는 대상이 아니다 (수상작도 표 중심이다)
eq(check_c23_heading_blocks({'s06_financial': fat}), [],
   "C23 은 스토리 3섹션만 본다")

# ============ C24: 산업분석의 종목 착지 ============
land = ("#### 멀티플이 깎인 세 가지 이유\n" + "가" * 600 +
        "\n와이지엔터테인먼트도 이 세 흐름에서 벗어나 있지 않다.\n"
        "#### 회복 트리거 4가지\n" + "나" * 600 + "\n와이지엔터는 이 중 둘을 갖췄다.")
eq(check_c24_industry_anchor(land, '와이지엔터'), [],
   "모든 소제목이 종목으로 착지하면 통과")

nolan = ("#### 시장 규모와 성장률\n" + "가" * 600 +
         "\n#### 회복 트리거 4가지\n" + "나" * 600 + "\n와이지엔터는 이 중 둘을 갖췄다.")
miss = check_c24_industry_anchor(nolan, '와이지엔터')
eq(miss, ["시장 규모와 성장률"], "**종목명이 없는 산업 소제목을 적발**")

# 짧은 블록(도입 문단 등)은 봐준다
eq(check_c24_industry_anchor("#### 도입\n짧은 안내문이다.", '와이지엔터'), [],
   "200자 미만 블록은 착지 의무 없음")

eq(check_c24_industry_anchor('', '와이지엔터'), [], "빈 섹션")
eq(check_c24_industry_anchor("가" * 600, ''), [], "종목명이 없으면 판정하지 않는다")


# ============ C21 가드: 스키마가 다르면 PASS 가 아니라 판정 불가 ============
# 실측 사고 (2026-09-08): 구 v4 리포트에 C21 을 돌렸더니
#   삼성SDI 83.3% PASS / 한화에어로 54.4% -- 둘 다 **거짓값**이었다.
# CANON12 로 못 잡는 섹션(s05_competition, s09_risk, s16_consensus ...)이
# 분모에서 통째로 빠져 비중이 부풀려졌다. 삼성SDI 는 5,588자가 분모 밖이었다.
# 결측을 0 으로 때우면 게이트가 죽는다는 v5.6 규칙 5 의 재발이다.

from verify_style import UNCOUNTED_MAX      # noqa: E402

eq(UNCOUNTED_MAX, 10, "분모 밖 본문이 10% 를 넘으면 판정하지 않는다")

sdi = {'s01_opinion': 'x' * 598, 's02_investment_points': 'x' * 924,
       's03_company_overview': 'x' * 770, 's04_industry': 'x' * 1279,
       's05_competition': 'x' * 477, 's07_financial': 'x' * 864,
       's08_valuation': 'x' * 869, 's09_risk': 'x' * 1330,
       's11_catalysts': 'x' * 593, 's13_thesis': 'x' * 494,
       's14_short_thesis': 'x' * 624, 's15_beat_miss': 'x' * 337}
eq(check_c21_story_weight(sdi), (None, None),
   "**삼성SDI 구 스키마는 83.3% PASS 가 아니라 판정 불가**")

hae = {k: 'x' * n for k, n in [
    ('s01_opinion', 1614), ('s02_investment_points', 2823), ('s03_company_overview', 3372),
    ('s04_industry', 3201), ('s05_competition', 1160), ('s06_moat', 650),
    ('s07_management', 630), ('s08_financial', 3365), ('s09_valuation', 2908),
    ('s10_macro', 503), ('s11_catalysts', 741), ('s12_scenarios', 1197),
    ('s13_thesis', 1889), ('s14_short_thesis', 1086), ('s15_beat_miss', 818),
    ('s16_consensus', 1423), ('s17_supply', 683), ('s18_shareholder_return', 972),
    ('s19_trust_worry_watch', 829), ('s20_action_plan', 798), ('s21_reliability', 1750)]}
eq(check_c21_story_weight(hae), (None, None),
   "**한화에어로 v4 21섹션도 판정 불가** (54.4% 는 거짓값이었다)")

ok_extra = dict({k: 'x' * v for k, v in WF.items()},
                s13_thesis='x' * 1500, s14_short_thesis='x' * 1500)
_sh, _o = check_c21_story_weight(ok_extra)
eq(_o, True, "s13_thesis/s14_short_thesis 는 판정을 막지 않는다")

_sh2, _o2 = check_c21_story_weight(yg)
eq(_o2, False, "정상 v5 리포트(와이지엔터)는 계속 판정된다")


# ============ 병합으로 비운 섹션이 alias 로 되살아나면 안 된다 ============
# 실측(2026-09-08 와이지엔터 v7): s10_earnings_consensus 를 s02 로 병합하고 ''로
# 비웠는데, alias(s11_earnings_consensus)가 남아 있어 fallback 이 그 내용을
# 분모에 **다시** 넣었다. 스토리 비중이 56.9% -> 49.9% 로 잘못 계산됐다.
#
# 규칙: 정규 키가 dict 에 **존재하면** 그 값이 최종이다(빈 문자열 = 병합 완료).
#       alias 는 정규 키가 아예 **없을 때만** 본다.

merged = {'s01_opinion_thesis': 'x' * 600, 's02_thesis_catalysts': 'x' * 2800,
          's03_company_overview': 'x' * 3200, 's04_industry_competition': 'x' * 5100,
          's06_financial': 'x' * 2300, 's07_valuation': 'x' * 3500,
          's09_scenarios_risks': 'x' * 1900,
          's05_management_fieldcheck': '', 's08_esg': '',
          's10_earnings_consensus': '', 's11_supply_shareholder': '',
          's12_action_plan': '',
          # 표준 alias 재생성 상태
          's02_investment_points': 'x' * 2800, 's04_industry': 'x' * 5100,
          's08_financial': 'x' * 2300, 's09_valuation': 'x' * 3500,
          's11_earnings_consensus': 'x' * 2800}
_m, _mok = check_c21_story_weight(merged)
close(_m, 56.9, "**비운 정규 키는 alias 로 되살리지 않는다** (56.9%)", 0.5)
eq(_mok, True, "병합 구조가 정상 판정된다")

# 정규 키가 아예 없으면 alias 로 읽는 기존 동작은 유지
eq('s04_industry_competition' in alias_only, False, "(전제) 정규 키 부재")
_a, _ = check_c21_story_weight(alias_only)
close(_a, 60.0, "정규 키가 없으면 alias 로 읽는다 (기존 동작 유지)", 2.0)

# ============================================================
# C25 (v5.11) -- 문단마다 결론 한 줄 (마진 노트)
#
# 실측: 위닝펀드 수상작 14편 중 **12편**이 본문 옆 여백에 그 문단의 결론을
# 한 줄로 단다. "실질은 EPC 기업인"(DL이앤씨) / "①AI 투자→ ②PCB"(이수페타시스)
# / "계속된 매출 성장과 수주잔고 -> 성장 사이클 유지"(한화에어로).
#
# 레이아웃 장식이 아니라 **글쓰기 규율**이다. 한 문단의 결론을 한 줄로 못 쓰면
# 그 문단에는 논지가 없다. 우리 리포트는 0개였다.
# ============================================================
from verify_style import check_c25_margin_notes, MARGIN_PREFIX, MARGIN_MAX   # noqa: E402

eq(MARGIN_PREFIX, '> **한 줄:**', "마진 노트 표기는 '> **한 줄:**'")
eq(MARGIN_MAX, 40, "한 줄은 40자 이내 (수상작 실측 10~35자)")

_good = "\n".join([
    "#### 순현금은 늘었는데 주주 몫은 줄었다",
    "> **한 줄:** 연결 이익의 31%가 비지배지분으로 나간다",
    "",
    "본문이다.",
    "#### 두 번째 주장",
    "> **한 줄:** 하반기가 전부다",
    "",
    "본문이다.",
])
eq(check_c25_margin_notes({'s04_industry_competition': _good}), [],
   "모든 블록에 한 줄이 있으면 통과")

_bad = "\n".join(["#### 첫 주장", "본문이다.", "",
                  "#### 둘째 주장", "> **한 줄:** 있다", "", "본문."])
eq(check_c25_margin_notes({'s04_industry_competition': _bad}),
   [('s04_industry_competition', '첫 주장')], "**한 줄이 없는 블록을 적발**")

_long = "\n".join(["#### 주장", "> **한 줄:** " + "가" * 60, "", "본문."])
eq(len(check_c25_margin_notes({'s04_industry_competition': _long})), 1,
   "40자를 넘으면 적발 (요약이 아니다)")

eq(check_c25_margin_notes({'s06_financial': _bad}), [],
   "C25 는 스토리 3섹션만 본다 (재무·밸류는 표 중심이라 면제)")
eq(check_c25_margin_notes({}), [], "빈 dict")
eq(check_c25_margin_notes({'s04_industry_competition': ''}), [], "빈 섹션")

print()
print('=' * 62)
print(f'  C21 재정의 + C23/C24/C25 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 62)
for f in _failed:
    print(f'  [FAIL] {f}')
sys.exit(1 if _failed else 0)
