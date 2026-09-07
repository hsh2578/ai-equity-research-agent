"""
fdr_band (KR) 밴드 산출 가드 테스트 (TDD -- 구현보다 먼저 작성됨)

US 판(fdr_band_us.py) 에만 있던 v5.5/v5.6 가드를 KR 로 이식한 것을 고정한다.
KR 은 FinanceDataReader 연말 종가 + KIS 재무비율(EPS/BPS) 을 쓰므로 US 와
데이터 출처가 다르다. 특히:

  - KR financial_summary 는 **연도별 발행주식수를 주지 않는다**.
    대신 그 해 EPS/BPS 가 이미 원 단위로 들어온다. BPS 필드가 있으면 그것이
    정답이고, 없을 때만 자기자본(억원) / 그 해 주식수 로 역산한다.
    그 해 주식수는 순이익(억원)*1e8 / EPS(원) 로 얻는다 -- 둘 다 같은 해
    공시값이므로 '오늘 주식수' 를 쓰는 US 초판의 사고가 재발하지 않는다.
  - 주식수를 끝내 못 구하면 BPS/PBR 을 산출하지 않고 사유를 notes 에 남긴다.
    (틀린 숫자보다 '없다'가 낫다 -- 프로젝트 원칙)

가드 4종:
  (1) 표본 3개 미만이면 밴드/z-score 산출 거부
  (2) 변동계수(std/mean) > 0.6 이면 per_band_valid=False + 경고
      -- 풍산/OCI홀딩스처럼 사이클 바닥에서 PER 이 튀는 종목이 실제로 걸린다
  (3) 진행 중인 당해년도 제외 (달력연도가 끝난 해만 연말 종가)
  (4) 연도별 주식수 기준 불일치(액면분할 등) 연도 제외

실행: python tests/test_fdr_band.py
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from fdr_band import (          # noqa: E402
    confirmed_year_closes,
    year_shares,
    year_bps,
    build_series,
    band_stats,
    EOK,
    MIN_SAMPLES,
    NOISY_CV,
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


# ---------------------------------------------------------------- (3) 당해년도
# FDR DataReader 는 오늘까지의 일봉을 주므로 groupby(year).tail(1) 이
# '2026 연말 종가 = 오늘 종가' 를 만든다. 실제 data/풍산/_per_band.json 의
# closes 에 2026: 96500 이 그렇게 들어가 있었다.
rows = [(2022, 30000), (2023, 39200), (2024, 49950), (2025, 106500), (2026, 96500)]
closes, excluded = confirmed_year_closes(rows, 2026)
eq(sorted(closes), [2022, 2023, 2024, 2025], "진행 중인 당해년도(2026) 제외")
eq(excluded, [2026], "제외 연도 보고")
eq(closes[2025], 106500, "확정 연도 종가 보존")
truthy(all(isinstance(v, int) for v in closes.values()), "KR 종가는 원 단위 정수")

closes2, excluded2 = confirmed_year_closes(rows, 2027)
eq(sorted(closes2), [2022, 2023, 2024, 2025, 2026], "당해년도가 데이터에 없으면 전부 확정")
eq(excluded2, [], "제외 연도 없음")

# 당해년도 부분 실적이 밴드에 못 들어간다
fin_partial = {
    '2023': {'eps': 5582.0, 'bps': 71975.0, 'net_income': 1564},
    '2024': {'eps': 8423.0, 'bps': 80518.0, 'net_income': 2360},
    '2025': {'eps': 5251.0, 'bps': 84137.0, 'net_income': 1472},
    # 2026 은 반기 누적 -> EPS 가 연간의 절반 -> close/eps 가 2배 부풀려진다
    '2026': {'eps': 2100.0, 'bps': 86000.0, 'net_income': 590},
}
res = build_series(closes, fin_partial)
eq(sorted(res['detail']), ['2023', '2024', '2025'], "부분 실적 당해년도는 detail 에서 제외")
eq(len(res['per_series']), 3, "PER 표본에 당해년도 미포함")
falsy(any(p > 40 for p in res['per_series']), "가짜 배수(46배)가 시계열에 섞이지 않는다")

# ---------------------------------------------------------------- BPS/주식수
# KIS 재무비율이 준 bps 필드가 있으면 그것이 정답
near(year_bps({'bps': 60099.0, 'total_equity': 16856, 'eps': 8682.0, 'net_income': 2434}),
     60099.0, "bps 필드가 있으면 그것을 우선")
# bps 가 없으면 자기자본(억원) / 그 해 **명시** 주식수
near(year_bps({'total_equity': 16856, 'shares_outstanding': 28_030_000}),
     16856 * EOK / 28_030_000, "bps 없으면 그 해 명시 주식수로 역산")
eq(year_bps({'total_equity': 16856}), None, "주식수를 못 구하면 BPS 없음 (추정 금지)")
eq(year_bps({}), None, "빈 연도는 BPS 없음")

near(year_shares({'shares_outstanding': 28030000, 'net_income': 2434, 'eps': 8682.0}),
     28030000.0, "명시 주식수를 그대로 쓴다")
eq(year_shares({'shares_outstanding': 0}), None, "주식수 0 은 무효")
# 순이익/EPS 역산은 하지 않는다. KR 은 연결 순이익(비지배 포함)을 지배주주 EPS 로
# 나누는 꼴이라 지주사/저마진 연도가 통째로 어긋난다 (실측: 두산 4.2배, 에스엠 0.04배).
eq(year_shares({'net_income': 2434, 'eps': 8682.0}), None,
   "순이익/EPS 역산 주식수를 만들지 않는다")
eq(year_bps({'total_equity': 16856, 'net_income': 2434, 'eps': 8682.0}), None,
   "역산 주식수로 BPS 를 만들지 않는다")

# 4. bps 도 없고 역산도 못 하면 PBR 밴드를 만들지 않고 warnings 에 남긴다
fin_noshares = {
    '2023': {'eps': 5582.0, 'total_equity': 19660},
    '2024': {'eps': 8423.0, 'total_equity': 21993},
    '2025': {'eps': 5251.0, 'total_equity': 22981},
}
res = build_series(closes, fin_noshares)
eq(res['pbr_series'], [], "주식수 없으면 PBR 시계열은 비어 있다 (추정 금지)")
eq(len(res['per_series']), 3, "PER 은 EPS 만으로 계산되므로 영향 없음")
truthy(any('주식수' in n for n in res['notes']), "PBR 미산출 사유를 notes 에 명시")
eq([r.get('bps') for r in res['detail'].values()], [None, None, None],
   "오늘 주식수로 역산한 가짜 BPS 를 넣지 않는다")

# ---------------------------------------------------------------- (4) 기준 불일치
# 액면분할: FDR 종가는 수정주가(분할 반영)인데 KIS 재무비율 EPS/BPS 는
# 분할 전 기준으로 남아 있으면 배수가 통째로 틀린다.
fin_split = {
    '2023': {'eps': 5582.0, 'bps': 71975.0, 'net_income': 1564,
             'shares_outstanding': 2_800_000},     # 분할 전 기준 (10배 적음)
    '2024': {'eps': 8423.0, 'bps': 80518.0, 'net_income': 2360,
             'shares_outstanding': 28_000_000},
    '2025': {'eps': 5251.0, 'bps': 84137.0, 'net_income': 1472,
             'shares_outstanding': 28_030_000},
}
res = build_series(closes, fin_split, ref_shares=28_030_000)
eq(sorted(res['detail']), ['2024', '2025'], "주당 기준이 다른 연도는 제외")
truthy(any('2023' in s for s in res['skipped']), "제외 연도가 skipped 에 기록")
truthy(any('기준' in v for v in res['skipped'].values()), "제외 사유 명시")
eq(len(res['per_series']), 2, "기준 불일치 연도는 PER 표본에서도 빠진다")
truthy(BASIS_RANGE >= 2, "허용 배수는 실제 자사주 소각/증자를 죽이지 않을 만큼 넉넉")

# 자사주 소각 정도(2배 이내)는 정상 통과
fin_buyback = {
    '2023': {'eps': 5582.0, 'bps': 71975.0, 'net_income': 1564, 'shares_outstanding': 28_000_000},
    '2024': {'eps': 8423.0, 'bps': 80518.0, 'net_income': 2360, 'shares_outstanding': 24_000_000},
    '2025': {'eps': 5251.0, 'bps': 84137.0, 'net_income': 1472, 'shares_outstanding': 20_000_000},
}
res = build_series(closes, fin_buyback, ref_shares=20_000_000)
eq(res['skipped'], {}, "정상 자사주 소각 기업은 어떤 연도도 버리지 않는다")
eq(len(res['per_series']), 3, "정상 기업은 표본 보존")

# 회귀: 명시 주식수가 없으면 기준 판정 자체를 하지 않는다.
# (KR 실데이터 -- 에스엠 2024 순이익 8억/EPS 778원. 역산하면 ref 대비 0.04배라
#  연도가 통째로 지워지고, PER 97배가 사라져 노이즈 밴드가 valid 로 뒤집혔다.)
fin_sm = {
    '2023': {'eps': 3664.0, 'bps': 30825.0, 'net_income': 827, 'total_equity': 9094},
    '2024': {'eps': 778.0, 'bps': 29037.0, 'net_income': 8, 'total_equity': 8291},
    '2025': {'eps': 15126.0, 'bps': 43793.0, 'net_income': 3594, 'total_equity': 13587},
}
sm_closes = {2023: 92100, 2024: 75600, 2025: 135000}   # 에스엠 실측 연말 종가
res = build_series(sm_closes, fin_sm, ref_shares=22_894_737)
eq(res['skipped'], {}, "저마진 연도를 기준 불일치로 오판해 버리지 않는다")
eq(len(res['per_series']), 3, "분산이 큰 연도가 조용히 지워지지 않는다")
eq(res['detail']['2024']['per'], 97.17, "PER 97배 이상치가 시계열에 남는다")
mean, std, valid, notes = band_stats(res['per_series'], 'PER')
eq(valid, False, "이상치가 남아 있으므로 CV 가드가 밴드를 무효로 판정한다")

# ref_shares 없이도 동작 (연도 간 기준 검증만 생략)
res = build_series(closes, fin_buyback, ref_shares=None)
eq(len(res['per_series']), 3, "ref_shares 없이도 PER 산출")
near(res['detail']['2023']['bps'], 71975.0, "ref_shares 없이도 BPS 보존")

# ---------------------------------------------------------------- (1)(2) 통계
# 표본 3개 미만 -> 산출 거부
mean, std, valid, notes = band_stats([12.0, 15.0], 'PER')
eq((mean, std, valid), (0.0, 0.0, False), f"표본 {MIN_SAMPLES}개 미만이면 밴드 거부")
truthy(any('표본' in n for n in notes), "표본 부족 사유를 남긴다")
truthy(any('5년 평균' in n for n in notes), "리포트에서 금지할 표현을 사유에 적시")

mean, std, valid, notes = band_stats([], 'PBR')
eq(valid, False, "빈 시계열은 무효")

# 변동계수 초과 -> 무효 (풍산 실측 시계열)
mean, std, valid, notes = band_stats([3.59, 5.38, 7.02, 5.93, 20.28], 'PER')
truthy(mean > 0, "무효여도 mean 자체는 계산해 둔다 (연도별 값 제시용)")
eq(valid, False, "변동계수 0.6 초과 시계열은 무효 (풍산 PER)")
truthy(any('변동계수' in n for n in notes), "변동계수 사유를 남긴다")

# OCI홀딩스 실측 -- 적자 직후 PER 34,062 배
mean, std, valid, notes = band_stats([1.74, 2.95, 11.75, 34062.5], 'PER')
eq(valid, False, "적자 전환 종목의 폭주 PER 은 무효")

# 정상 시계열 -> 유효
mean, std, valid, notes = band_stats([10.0, 11.0, 12.0, 13.0, 14.0], 'PER')
near(mean, 12.0, "정상 시계열 평균")
eq(valid, True, "변동계수 0.6 이내면 유효")
eq(notes, [], "유효하면 경고 없음")

# 임계값 자체가 US 판과 같은 값으로 이식됐는지
eq(MIN_SAMPLES, 3, "최소 표본 3개")
near(NOISY_CV, 0.6, "변동계수 임계 0.6")

print(f"\n{'=' * 60}")
print(f"  fdr_band (KR) 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
