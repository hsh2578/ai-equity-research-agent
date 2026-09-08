"""
verify_numbers (KR) B23 밴드 유효성 게이트 테스트 (TDD -- 구현보다 먼저 작성됨)

US 판 verify_numbers_us.py 의 B19 를 KR 로 이식한 것을 고정한다.
_per_band.json 의 per_band_valid / pbr_band_valid 가 False 인데 본문이
"5년 평균", "역사적 평균", "밴드 상단/하단", "z-score", 시그마 같은 표현으로
단정하면 FAIL. 밴드가 노이즈인데 "역사적 저평가" 라고 쓰는 것이 이 프로젝트가
반복해서 낸 사고다(AMD PER 56 -> 278 -> 121, 풍산/OCI홀딩스 사이클 바닥).

검증 id 는 KR 에서 이미 B1~B22 가 쓰이고 있으므로 **B23** 이다.
(tests/test_verify_check_ids.py 가 id 충돌을 자동으로 잡는다)

실행: python tests/test_verify_band_gate.py
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from verify_numbers import (   # noqa: E402
    band_gate, band_claims_in, BAND_CLAIM_WORDS, BAND_DISCLAIMERS,
)

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected!r}\n      실제: {actual!r}")


def truthy(actual, name):
    eq(bool(actual), True, name)


def falsy(actual, name):
    eq(bool(actual), False, name)


CLAIM = ('밸류에이션은 5년 평균 PER 8.4배 대비 현재 20.3배로 밴드 상단에 있다. '
        'z-score 는 +1.9σ 수준이다.')
PLAIN = ('연도별 후행 PER 은 2021년 3.6배, 2022년 5.4배, 2023년 7.0배, '
         '2024년 5.9배, 2025년 20.3배로 사이클에 따라 크게 흔들린다.')

# --- 파일이 없거나 구버전이면 SKIP (거짓 FAIL 금지) ---
status, detail = band_gate(None, CLAIM)
eq(status, 'SKIP', "_per_band.json 이 없으면 SKIP")

status, detail = band_gate({'per_series': [1, 2, 3]}, CLAIM)
eq(status, 'SKIP', "per_band_valid 키가 없는 구버전 밴드는 SKIP")
truthy('fdr_band' in detail, "구버전이면 재실행을 안내한다")

# --- 유효한 밴드면 밴드 표현을 써도 통과 ---
band_ok = {'per_band_valid': True, 'pbr_band_valid': True}
status, detail = band_gate(band_ok, CLAIM)
eq(status, 'PASS', "유효한 밴드는 밴드 표현 허용")

# --- 무효 밴드 + 밴드 표현 = FAIL ---
band_bad = {'per_band_valid': False, 'pbr_band_valid': True,
            'warnings': ['PER 변동계수 0.72 (>0.6)']}
status, detail = band_gate(band_bad, CLAIM)
eq(status, 'FAIL', "PER 밴드 무효인데 '5년 평균' 단정 -> FAIL")
truthy('5년 평균' in detail, "적발된 표현을 사유에 적시")

# --- 무효 밴드 + 밴드 표현 없음 = PASS ---
status, detail = band_gate(band_bad, PLAIN)
eq(status, 'PASS', "무효 밴드라도 연도별 값만 제시하면 통과")

# --- PBR 밴드만 무효인 경우도 잡는다 ---
band_pbr_bad = {'per_band_valid': True, 'pbr_band_valid': False}
status, detail = band_gate(band_pbr_bad, 'PBR 은 5년 평균 대비 밴드 하단이다.')
eq(status, 'FAIL', "PBR 밴드 무효인데 밴드 표현 -> FAIL")
truthy('PBR' in detail, "어느 밴드가 무효인지 사유에 명시")

# --- 표본 부족(밴드 산출 거부)도 무효로 취급 ---
band_few = {'per_band_valid': False, 'pbr_band_valid': False,
            'warnings': ['PER 표본 2개 (<3) - 밴드/z-score 산출 거부']}
status, detail = band_gate(band_few, '역사적 평균 PER 대비 저평가다.')
eq(status, 'FAIL', "표본 부족 밴드도 밴드 표현 금지")

# --- 표현 사전 ---
eq(band_claims_in(PLAIN), [], "밴드 표현이 없으면 빈 목록")
truthy('5년 평균' in band_claims_in(CLAIM), "'5년 평균' 감지")
truthy('밴드 상단' in band_claims_in(CLAIM), "'밴드 상단' 감지")
truthy('z-score' in band_claims_in(CLAIM), "'z-score' 감지")
truthy('σ' in band_claims_in('현재 +1.9σ'), "시그마 표기 감지")
for w in ['5년 평균', '역사적 평균', '밴드 상단', '밴드 하단', 'z-score', 'σ']:
    truthy(w in BAND_CLAIM_WORDS, f"US B19 와 같은 표현 '{w}' 를 사전에 포함")

# --- 저자가 스스로 밴드를 무효 선언한 문장은 단정이 아니다 (한국콜마 실측 문장) ---
DISCLAIMED = ('후행 PER은 30.52배다. 5년 평균 74.39배는 2022년 순손실 구간의 왜곡 때문에 '
              '의미가 없으므로 비교 기준으로 쓰지 않는다.')
eq(band_claims_in(DISCLAIMED), [], "무효 선언과 함께 쓴 '5년 평균' 은 단정이 아니다")
status, detail = band_gate(band_bad, DISCLAIMED)
eq(status, 'PASS', "밴드를 못 쓴다고 밝힌 리포트는 통과 (정직한 문장을 지우게 만들지 않는다)")

# 같은 표현을 다른 곳에서 단정으로 쓰면 여전히 FAIL
_FILLER = ' 부문별 매출은 국내 55%, 중국 20%, 북미 15% 로 구성되며 화장품 ODM 비중이 높다.' * 2
MIXED = DISCLAIMED + _FILLER + ' 한편 현재 주가는 5년 평균 대비 30% 저평가 구간이다.'
truthy('5년 평균' in band_claims_in(MIXED), "무효 선언 없는 등장이 하나라도 있으면 단정으로 센다")
eq(band_gate(band_bad, MIXED)[0], 'FAIL', "혼재 시 FAIL")
truthy(BAND_DISCLAIMERS, "무효 선언 사전이 비어 있지 않다")


# ============================================================
# 지표별 판정 (2026-09-08 와이지엔터 v7 실측 후 추가)
#
# PER 밴드는 유효한데(표본 5개, 변동계수 0.44) PBR 밴드가 무효(표본 0개)라는
# 이유로 **PER 서술까지 FAIL** 이 났다:
#     [FAIL] B23  PBR 밴드 무효인데 본문이 밴드 표현 사용: ['5년 평균', 'σ']
# 본문이 쓴 것은 "5년 평균 후행 PER 28.60배", "z = -0.49σ" 로 전부 PER 이었다.
#
# KR 종목은 PBR 표본이 얇은 경우가 흔해 이 거짓 FAIL 이 사실상 모든 리포트에
# 걸린다. 거짓 FAIL 이 반복되면 게이트를 무시하게 되고 진짜 FAIL 도 함께 묻힌다.
# 고침: 무효 지표의 **이름이 밴드 표현 근처에 있을 때만** FAIL.
# ============================================================

PER_OK = {'per_band_valid': True, 'pbr_band_valid': False,
          'warnings': ['PBR 표본 0개 (<3) - 밴드/z-score 산출 거부']}
BOTH_OK = {'per_band_valid': True, 'pbr_band_valid': True, 'warnings': []}
PER_BAD = {'per_band_valid': False, 'pbr_band_valid': True,
           'warnings': ['PER 변동계수 0.71 (>0.6)']}

_yg = ("5년 평균 후행 PER 28.60배, 현재 후행 PER 22.39배로 z = -0.49σ다. "
       "Target PER 은 28.60배에서 25% 할인한 21.5배를 쓴다.")
eq(band_gate(PER_OK, _yg)[0], 'PASS',
   "**PER 밴드가 유효하면 PBR 무효가 PER 서술을 막지 않는다**")

_bad = "PBR 은 5년 평균 2.4배 대비 현재 1.60배로 역사적 하단이다."
eq(band_gate(PER_OK, _bad)[0], 'FAIL', "PBR 무효인데 PBR 5년 평균을 쓰면 FAIL")

eq(band_gate(PER_BAD, "5년 평균 PER 28.6배 대비 현재는 싸다")[0], 'FAIL',
   "PER 무효인데 PER 5년 평균을 쓰면 FAIL")
eq(band_gate(PER_BAD, _yg)[0], 'FAIL', "PER 무효면 와이지 본문도 FAIL")

eq(band_gate(BOTH_OK, _bad)[0], 'PASS', "둘 다 유효하면 PASS")

eq(band_gate(PER_OK, "역사적 밴드 하단이다. 5년 평균 대비 크게 낮다.")[0], 'FAIL',
   "어느 지표인지 안 밝힌 밴드 단정은 FAIL (지표를 명시하게 만든다)")

eq(band_gate(PER_OK, "PBR 5년 평균은 표본 부족으로 무효라 쓰지 않는다.")[0], 'PASS',
   "무효를 스스로 밝힌 문장은 계속 통과")

# --- 연도 표기를 밴드 단정으로 오인하지 않는다 (2026-09-08 실측) ---
# "국내 오프라인 음악 공연 유료 관람 횟수는 2024년 평균 3.5회에서 **2025년 평균**
#  5.4회로 증가했고" -- 여기서 '2025년 평균' 안의 '5년 평균' 이 매칭돼
# 산업 통계 인용이 밴드 단정으로 잡혔다. 앞 글자가 숫자면 연도 표기다.
eq(band_claims_in("2025년 평균 5.4회로 증가했다"), [], "'2025년 평균'은 밴드 단정이 아니다")
eq(band_claims_in("2024년 평균 3.5회에서 2025년 평균 5.4회"), [], "연도 두 번도 마찬가지")
eq(band_claims_in("5년 평균 PER 28.6배 대비 싸다"), ['5년 평균'],
   "**진짜 '5년 평균' 은 계속 잡는다**")
eq(band_claims_in("최근 5년 평균 대비 낮다"), ['5년 평균'], "앞이 공백이면 밴드 단정")

# ============================================================
# B24 -- opinion 의 3-시나리오 목표가가 본문에 실제로 있는가
#
# 실측 사고(2026-09-08 한화에어로): 목표주가를 1,260,000 -> 1,320,000 으로
# 올릴 때 opinion/s01/s07 만 고치고 **s09 시나리오 표와 감도·실행계획이
# 옛 값(820,000 / 1,650,000)에 남았다.** 커버 스펙트럼과 본문이 서로 다른
# 숫자를 말하는 상태로 PDF 가 나갔다.
#
# 커버는 opinion 을 읽고 본문은 sections 를 읽으므로 둘이 갈라진다.
# 사람이 매번 3개 값을 전 섹션에서 찾아 고치는 것은 재발이 보장된 방식이다.
# ============================================================
from verify_numbers import check_b24_targets_in_body   # noqa: E402

_sec = {'s07_valuation': 'Base 1,320,000원 x ... Bear 850,000원 ... Bull 1,790,000원'}
_op = {'target_bear': 850000, 'target_base': 1320000, 'target_bull': 1790000}
eq(check_b24_targets_in_body(_op, _sec), [], "세 값이 모두 본문에 있으면 통과")

_sec2 = {'s07_valuation': 'Base 1,320,000원만 있다'}
miss = check_b24_targets_in_body(_op, _sec2)
eq(sorted(miss), ['Bear 850,000', 'Bull 1,790,000'],
   "**본문에 없는 목표가를 적발** (커버와 본문 불일치)")

# 콤마 없는 표기도 인정한다
eq(check_b24_targets_in_body({'target_base': 39000},
                             {'s': '목표주가 39000원'}), [], "콤마 없는 표기 허용")
# 값이 0/None 이면 판정하지 않는다
eq(check_b24_targets_in_body({'target_base': 0, 'target_bear': None}, {'s': ''}), [],
   "값이 없으면 판정 대상이 아니다")
eq(check_b24_targets_in_body({}, {'s': 'x'}), [], "opinion 이 비면 빈 목록")

print(f"\n{'=' * 60}")
print(f"  verify_numbers B23 밴드 게이트 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
