"""
dart_quarterly 테스트 (TDD -- 구현보다 먼저 작성)

배경: FnGuide 는 최근 4분기만 준다. 그래서 두산 1Q25 를 "소급 불가" 로 판단했는데,
DART 는 연도별 분기보고서를 그대로 제공한다. 사용자 지적으로 확인했다.

DART 재무제표 API 의 금액 컬럼 의미 (실측으로 확정):
  thstrm_amount      = **당분기 3개월** (standalone)
  thstrm_add_amount  = **누적** (1분기보고서에서는 3개월과 같다)
  사업보고서(11011) 는 thstrm_amount 가 **연간 전체**이고 누적 컬럼이 비어 있다.

따라서 4분기 = 연간 - 3분기 누적 으로 역산한다.
검산: 4개 분기 합 == 연간 (두산 2025 실측에서 10,627억으로 정확히 일치)

실행: python tests/test_dart_quarterly.py
"""
import sys
import os
import io

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from dart_quarterly import (pick_account, amount, derive_quarters,
                            checksum, to_uk, compare_with_report)

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
    if actual is not None and expected is not None and abs(actual - expected) <= tol:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected}\n      실제: {actual}")


def truthy(a, name):
    eq(bool(a), True, name)


# --- amount: 문자열 금액 파싱 ---
eq(amount({'thstrm_amount': '4298676000000'}, 'thstrm_amount'), 4298676000000, "정수 문자열")
eq(amount({'thstrm_amount': '-123'}, 'thstrm_amount'), -123, "음수")
eq(amount({'thstrm_amount': '1,234'}, 'thstrm_amount'), 1234, "콤마 포함")
eq(amount({'thstrm_amount': ''}, 'thstrm_amount'), None, "빈 문자열 -> None")
eq(amount({'thstrm_amount': '-'}, 'thstrm_amount'), None, "하이픈 -> None")
eq(amount({}, 'thstrm_amount'), None, "키 없음 -> None")
eq(amount({'thstrm_add_amount': ''}, 'thstrm_add_amount'), None, "사업보고서의 빈 누적 컬럼")

# --- pick_account: 손익계산서에서 계정 찾기 ---
items = [
    {'account_nm': '매출액', 'sj_div': 'IS', 'thstrm_amount': '100'},
    {'account_nm': '매출액', 'sj_div': 'CIS', 'thstrm_amount': '999'},   # 포괄손익 -- 제외
    {'account_nm': '영업이익', 'sj_div': 'IS', 'thstrm_amount': '10'},
    {'account_nm': '자산총계', 'sj_div': 'BS', 'thstrm_amount': '500'},
]
eq(amount(pick_account(items, ('매출액', '영업수익')), 'thstrm_amount'), 100, "IS 의 매출액만 고른다")
eq(amount(pick_account(items, ('영업이익',)), 'thstrm_amount'), 10, "영업이익")
eq(pick_account(items, ('없는계정',)), None, "없으면 None")
eq(amount(pick_account(items, ('영업수익', '매출액')), 'thstrm_amount'), 100,
   "별칭 목록 중 존재하는 것을 찾는다")

# --- CIS 전용 제출사 (에코프로 실측: IS 0개, CIS 26개) ---
# 많은 회사가 손익계산서와 포괄손익계산서를 분리하지 않고 CIS 하나로 제출한다.
# IS 만 보면 전 계정이 None 이 되어 '실적 없음' 으로 조용히 통과한다.
cis_only = [
    {'account_nm': '매출액', 'sj_div': 'CIS', 'thstrm_amount': '777'},
    {'account_nm': '영업이익', 'sj_div': 'CIS', 'thstrm_amount': '77'},
    {'account_nm': '자산총계', 'sj_div': 'BS', 'thstrm_amount': '5'},
]
eq(amount(pick_account(cis_only, ('매출액',)), 'thstrm_amount'), 777,
   "CIS 만 있는 제출사도 읽는다 (에코프로 사고)")
eq(amount(pick_account(cis_only, ('영업이익',)), 'thstrm_amount'), 77, "CIS 영업이익")
eq(pick_account(cis_only, ('자산총계',)), None, "BS 계정은 여전히 제외")

# IS 와 CIS 가 둘 다 있으면 IS 를 우선한다 (중복 계상 방지)
both = [
    {'account_nm': '매출액', 'sj_div': 'CIS', 'thstrm_amount': '999'},
    {'account_nm': '매출액', 'sj_div': 'IS', 'thstrm_amount': '100'},
]
eq(amount(pick_account(both, ('매출액',)), 'thstrm_amount'), 100, "IS 를 CIS 보다 우선")

# --- derive_quarters: 두산 2025 실측값 (억원 아닌 원 단위) ---
raw = {
    '1Q': {'rev_q': 4298676000000, 'rev_cum': 4298676000000,
           'op_q': 198460000000, 'op_cum': 198460000000},
    '2Q': {'rev_q': 5346439000000, 'rev_cum': 9645115000000,
           'op_q': 357778000000, 'op_cum': 556238000000},
    '3Q': {'rev_q': 4452365000000, 'rev_cum': 14097480000000,
           'op_q': 231269000000, 'op_cum': 787507000000},
    'FY': {'rev_q': 19784138000000, 'rev_cum': None,
           'op_q': 1062715000000, 'op_cum': None},
}
q = derive_quarters(raw)
close(to_uk(q['4Q']['rev']), 56866.58, "4Q 매출 = 연간 - 3Q누적", 1.0)
close(to_uk(q['4Q']['op']), 2752.08, "4Q 영업이익 = 연간 - 3Q누적", 1.0)
close(to_uk(q['1Q']['op']), 1984.60, "1Q 영업이익 (누락됐던 분기)", 1.0)
close(to_uk(q['2Q']['op']), 3577.78, "2Q 영업이익", 1.0)
close(to_uk(q['3Q']['op']), 2312.69, "3Q 영업이익 -- FnGuide 2025/09 와 일치", 1.0)

# --- checksum: 4분기 합 == 연간 ---
ok, detail = checksum(q, raw['FY'])
truthy(ok, f"두산 2025 검산 통과 ({detail})")

bad = {k: dict(v) for k, v in q.items()}
bad['2Q']['op'] = bad['2Q']['op'] + 500_000_000_000     # 5,000억 오염
ok2, _ = checksum(bad, raw['FY'])
eq(ok2, False, "합이 어긋나면 검산 실패로 잡는다")

# --- to_uk: 원 -> 억원 ---
close(to_uk(100_000_000), 1.0, "1억원 -> 1")
eq(to_uk(None), None, "None -> None")

# --- compare_with_report: 리포트 값과 실측 대조 (v5.4 규칙 19) ---
report_rows = {'영업이익': ['약 2,500', '약 2,700', '약 2,500', '약 3,800 (NH추정)']}
report_headers = ['분기(억원)', '2Q25', '3Q25', '4Q25 A', '1Q26 E']
diffs = compare_with_report(q, 2025, report_headers, report_rows, tol_pct=10)
labels = {d['quarter'] for d in diffs}
truthy('2Q25' in labels, "2Q25 불일치 적발 (리포트 2,500 vs 실측 3,578)")
truthy('3Q25' in labels, "3Q25 불일치 적발")
eq(any(d['quarter'] == '1Q26' for d in diffs), False,
   "추정치(1Q26 E)는 대조 대상에서 제외")

d2 = [d for d in diffs if d['quarter'] == '2Q25'][0]
close(d2['actual'], 3577.78, "적발된 실측값", 1.0)
close(d2['reported'], 2500.0, "적발된 리포트값", 1.0)
truthy(abs(d2['diff_pct']) > 25, "2Q25 오차가 25% 를 넘는다")

# 값이 맞으면 적발하지 않는다
good_rows = {'영업이익': ['3,578', '2,313', '2,752', '약 3,800 (NH추정)']}
eq(compare_with_report(q, 2025, report_headers, good_rows, tol_pct=10), [],
   "실측과 같으면 불일치 0건")

print(f"\n{'=' * 60}")
print(f"  dart_quarterly 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
