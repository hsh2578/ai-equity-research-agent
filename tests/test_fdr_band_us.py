"""
fdr_band_us 밴드 산출 테스트 (TDD -- 구현보다 먼저 작성됨)

코드리뷰 지적 2건을 고정한다.

(a) 진행 중인 당해년도가 밴드에 섞였다.
    hist.groupby(year).tail(1) 은 오늘 종가를 그 해의 '연말 종가'로 만든다.
    financial_summary 에 그 해 부분 실적이 있으면 close/eps 가 가짜 배수가 되고,
    그 시계열로 per_mean 과 변동계수(NOISY_CV)를 잰다.

(b) 오늘의 shares 로 과거 각 연도의 total_equity 를 나눠 BPS 를 만들었다.
    자사주 매입/증자/액면분할이 있었던 기업은 역사 BPS 와 PBR 밴드 전체가 틀린다.
    -> 연도별 발행주식수를 쓰고, 없으면 산출을 거부하고 warnings 에 남긴다.
       (틀린 숫자보다 '없다'가 낫다 -- 프로젝트 원칙)

실행: python tests/test_fdr_band_us.py
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from fdr_band_us import (          # noqa: E402
    confirmed_year_closes,
    year_shares,
    year_bps,
    build_series,
    BASIS_RANGE,
)

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected!r}\n      실제: {actual!r}")


def near(actual, expected, name, tol=1e-6):
    global _passed
    if actual is not None and abs(actual - expected) <= tol:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected!r}(+-{tol})\n      실제: {actual!r}")


def truthy(actual, name):
    eq(bool(actual), True, name)


def falsy(actual, name):
    eq(bool(actual), False, name)


# ---------------------------------------------------------------- (a)
# 1. 진행 중인 당해년도는 연말 종가가 존재하지 않으므로 밴드에서 뺀다
rows = [(2022, 10.0), (2023, 12.0), (2024, 15.0), (2025, 20.0)]
closes, excluded = confirmed_year_closes(rows, 2025)
eq(sorted(closes), [2022, 2023, 2024], "당해년도(2025) 제외한 확정 연도만")
eq(excluded, [2025], "제외 연도 보고")
near(closes[2024], 15.0, "확정 연도 종가 보존")

closes2, excluded2 = confirmed_year_closes(rows, 2026)
eq(sorted(closes2), [2022, 2023, 2024, 2025], "당해년도가 데이터에 없으면 전부 확정")
eq(excluded2, [], "제외 연도 없음")

# 2. 오염 시나리오: 당해년도 부분 실적 + 오늘 종가 -> 가짜 PER 이 시계열에 들어가면 안 된다
fin_partial = {
    '2022': {'eps': 1.0, 'net_income': 100.0, 'shares_outstanding': 100.0, 'total_equity': 500.0},
    '2023': {'eps': 1.2, 'net_income': 120.0, 'shares_outstanding': 100.0, 'total_equity': 600.0},
    '2024': {'eps': 1.5, 'net_income': 150.0, 'shares_outstanding': 100.0, 'total_equity': 700.0},
    # 2025 는 3분기까지 부분 실적 -> EPS 가 연간의 1/4 -> close/eps 가 4배 부풀려진다
    '2025': {'eps': 0.4, 'net_income': 40.0, 'shares_outstanding': 100.0, 'total_equity': 720.0},
}
res = build_series(closes, fin_partial, ref_shares=100.0)
eq(sorted(res['detail']), ['2022', '2023', '2024'], "부분 실적 당해년도는 detail 에서 제외")
eq(len(res['per_series']), 3, "PER 표본에 당해년도 미포함")
truthy(all(p < 20 for p in res['per_series']), "가짜 배수(50배)가 시계열에 섞이지 않는다")

# ---------------------------------------------------------------- (b)
# 3. BPS 는 그 연도의 발행주식수로 나눈다 (오늘 주식수 아님)
fin_buyback = {
    # 자사주 매입으로 주식수가 100 -> 50 으로 줄어든 기업
    '2022': {'eps': 1.0, 'net_income': 100.0, 'shares_outstanding': 100.0, 'total_equity': 1000.0},
    '2023': {'eps': 1.2, 'net_income': 90.0, 'shares_outstanding': 75.0, 'total_equity': 900.0},
    '2024': {'eps': 1.5, 'net_income': 75.0, 'shares_outstanding': 50.0, 'total_equity': 800.0},
}
res = build_series(closes, fin_buyback, ref_shares=50.0)
near(res['detail']['2022']['bps'], 10.0, "2022 BPS = 1000/100 (그 해 주식수)")
near(res['detail']['2023']['bps'], 12.0, "2023 BPS = 900/75")
near(res['detail']['2024']['bps'], 16.0, "2024 BPS = 800/50")
near(res['detail']['2022']['pbr'], 1.0, "2022 PBR = 10/10 (오늘 주식수로 나눈 0.5 가 아니다)")

near(year_bps({'total_equity': 1000.0, 'shares_outstanding': 100.0}), 10.0, "year_bps 역산")
near(year_bps({'bps': 7.5, 'total_equity': 1000.0, 'shares_outstanding': 100.0}), 7.5,
     "bps 필드가 있으면 그것을 우선")
eq(year_bps({'total_equity': 1000.0}), None, "주식수 없으면 BPS 없음")
eq(year_shares({'shares_outstanding': 0}), None, "주식수 0 은 무효")

# 4. 연도별 주식수를 못 구하면 PBR 밴드를 만들지 않고 warnings 에 남긴다
fin_noshares = {
    '2022': {'eps': 1.0, 'net_income': 100.0, 'total_equity': 1000.0},
    '2023': {'eps': 1.2, 'net_income': 120.0, 'total_equity': 1100.0},
    '2024': {'eps': 1.5, 'net_income': 150.0, 'total_equity': 1200.0},
}
res = build_series(closes, fin_noshares, ref_shares=100.0)
eq(res['pbr_series'], [], "주식수 없으면 PBR 시계열은 비어 있다 (추정 금지)")
eq(len(res['per_series']), 3, "PER 은 EPS 만으로 계산되므로 영향 없음")
truthy(any('주식수' in n for n in res['notes']), "PBR 미산출 사유를 notes 에 명시")
eq([r.get('bps') for r in res['detail'].values()], [None, None, None],
   "오늘 주식수로 역산한 가짜 BPS 를 넣지 않는다")

# 5. 액면분할 등으로 주당 기준이 섞인 연도는 통째로 제외한다
#    (NFLX 실측: 2021~2023 은 분할 전 주식수, 2024~ 는 분할 후. 종가는 전부 분할 반영)
fin_split = {
    '2022': {'eps': 9.95, 'net_income': 4491.0, 'shares_outstanding': 445.0, 'total_equity': 20777.0},
    '2023': {'eps': 1.20, 'net_income': 5408.0, 'shares_outstanding': 432.0, 'total_equity': 20588.0},
    '2024': {'eps': 1.98, 'net_income': 8711.0, 'shares_outstanding': 4277.0, 'total_equity': 24743.0},
}
res = build_series(closes, fin_split, ref_shares=4222.0)
eq(sorted(res['detail']), ['2024'], "주당 기준이 다른 연도(분할 미반영)는 제외")
truthy(any('2022' in s for s in res['skipped']), "제외 연도가 skipped 에 기록")
truthy(any('기준' in v for v in res['skipped'].values()), "제외 사유 명시")
eq(len(res['per_series']), 1, "기준 불일치 연도는 PER 표본에서도 빠진다")
truthy(BASIS_RANGE >= 2, "기준 허용 배수는 실제 자사주/증자를 죽이지 않을 만큼 넉넉")

# 6. NI/EPS 로 역산한 주식수가 보고 주식수와 크게 다르면 그 해 PER 만 버린다
fin_epsbad = {
    '2022': {'eps': 1.0, 'net_income': 100.0, 'shares_outstanding': 100.0, 'total_equity': 1000.0},
    '2023': {'eps': 1.2, 'net_income': 120.0, 'shares_outstanding': 100.0, 'total_equity': 1000.0},
    # eps 가 10배 기준으로 보고됨 -> NI/EPS = 1000주 vs 보고 100주
    '2024': {'eps': 0.15, 'net_income': 150.0, 'shares_outstanding': 100.0, 'total_equity': 1000.0},
}
res = build_series(closes, fin_epsbad, ref_shares=100.0)
eq(len(res['per_series']), 2, "EPS 기준 불일치 연도는 PER 표본 제외")
eq(res['detail']['2024'].get('per'), None, "해당 연도 PER 은 비운다")
near(res['detail']['2024']['pbr'], 1.5, "EPS 만 문제이므로 PBR 은 살린다")
truthy(any('EPS' in n for n in res['notes']), "EPS 기준 불일치를 notes 에 명시")

# 7. 자사주 매입 정도의 주식수 변동(2배 이내)은 정상으로 통과시킨다
fin_ok = {
    '2022': {'eps': 1.0, 'net_income': 100.0, 'shares_outstanding': 100.0, 'total_equity': 1000.0},
    '2023': {'eps': 1.2, 'net_income': 90.0, 'shares_outstanding': 75.0, 'total_equity': 900.0},
    '2024': {'eps': 1.5, 'net_income': 75.0, 'shares_outstanding': 50.0, 'total_equity': 800.0},
}
res = build_series(closes, fin_ok, ref_shares=50.0)
eq(res['skipped'], {}, "정상 자사주 매입 기업은 어떤 연도도 버리지 않는다")

# 8. ref_shares 를 못 구해도 동작한다 (연도 간 기준 검증만 생략)
res = build_series(closes, fin_buyback, ref_shares=None)
eq(len(res['per_series']), 3, "ref_shares 없이도 PER 산출")
near(res['detail']['2022']['bps'], 10.0, "ref_shares 없이도 연도별 BPS")

print(f"\n{'=' * 60}")
print(f"  fdr_band_us 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
