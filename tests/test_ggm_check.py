"""
ggm_check -- Target 배수를 자본효율로 정당화 (TDD, 구현보다 먼저 작성)

배경 (2026-09-08, 위닝펀드 수상작 9편 본문 정독):
  수상작은 Target 배수의 근거를 **자본효율**에 건다.

    "Target PBR 1.3배: **18%대 ROIC 가 정당화하는** 밴드 상단 소폭 돌파" (에스엘)
    "Target PER 11.5배: 글로벌 램프 Peer에 '로봇 포지션' 리레이팅"

  우리 세 리포트는 전부 "업종 평균 32.37배 대비 13.5% 할인" 같은 **임의 계수**였다.
  할인율의 근거가 서술에만 있고 숫자에 없다 -- 독자가 재현할 수 없다.

  Gordon Growth Model 은 PBR 을 ROE·성장률·자본비용 세 값으로 묶는다.

      PBR = (ROE - g) / (COE - g)

  이 식이 주는 것은 정답이 아니라 **기준선**이다. 우리 Target 이 기준선보다
  높으면 그 초과분을 설명해야 하고, 설명하지 못하면 임의 계수와 다를 바 없다.

실행: python tests/test_ggm_check.py
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from ggm_check import implied_pbr, implied_per, justify, DEFAULT_COE

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected!r}\n      실제: {actual!r}")


def close(actual, expected, name, tol=0.05):
    global _passed
    if actual is not None and abs(actual - expected) <= tol:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected}\n      실제: {actual}")


# --- GGM 기본 ---
close(implied_pbr(roe=0.226, coe=0.10, g=0.05), 3.52, "ROE 22.6% · COE 10% · g 5% -> 3.52배")
close(implied_pbr(roe=0.09, coe=0.095, g=0.03), 0.92, "ROE 9% · COE 9.5% · g 3% -> 0.92배")
close(implied_pbr(roe=0.10, coe=0.10, g=0.03), 1.00, "**ROE = COE 면 PBR 1.0배**")
eq(implied_pbr(roe=0.20, coe=0.05, g=0.05), None,
   "COE = g 이면 분모가 0 -- 값을 만들지 않는다")
eq(implied_pbr(roe=0.20, coe=0.03, g=0.05), None,
   "g > COE 는 성립하지 않는다 (무한 성장)")
eq(implied_pbr(roe=None, coe=0.10, g=0.03), None, "ROE 결측이면 None")

# ROE 가 음수면 장부가 배수를 정당화할 수 없다
eq(implied_pbr(roe=-0.05, coe=0.10, g=0.03), None, "적자(ROE<0)면 None")

# --- PER 환산: PER = PBR / ROE ---
close(implied_per(roe=0.226, coe=0.10, g=0.05), 15.6, "PBR 3.52 / ROE 0.226 = 15.6배", 0.3)
eq(implied_per(roe=None, coe=0.10, g=0.03), None, "ROE 결측")

# --- 기본 자본비용 ---
eq(DEFAULT_COE, 0.095, "기본 자본비용 9.5% (무위험 + 시장 프리미엄 통상 가정)")

# --- justify: Target 이 기준선 대비 어디인가 ---
r = justify(target_pbr=1.3, roe=0.18, coe=0.095, g=0.03)
close(r['implied_pbr'], 2.31, "ROE 18% -> 기준선 2.31배", 0.05)
eq(r['verdict'], 'DISCOUNT', "Target 1.3 < 기준선 2.31 -> 할인")
eq(r['needs_explanation'], False, "기준선보다 낮으면 별도 설명 부담이 없다")

r2 = justify(target_pbr=2.1, roe=0.09, coe=0.095, g=0.03)
close(r2['implied_pbr'], 0.92, "ROE 9% -> 기준선 0.92배", 0.05)
eq(r2['verdict'], 'PREMIUM', "Target 2.1 > 기준선 0.92 -> 프리미엄")
eq(r2['needs_explanation'], True,
   "**기준선의 1.3배를 넘으면 초과분을 설명해야 한다**")
close(r2['ratio'], 2.28, "2.1 / 0.92 = 2.28배", 0.06)

r3 = justify(target_pbr=1.0, roe=0.10, coe=0.10, g=0.03)
eq(r3['verdict'], 'INLINE', "기준선과 ±10% 이내면 INLINE")

eq(justify(target_pbr=2.0, roe=None, coe=0.095, g=0.03)['verdict'], 'UNKNOWN',
   "ROE 가 없으면 판정 불가 (PASS 로 때우지 않는다)")
eq(justify(target_pbr=None, roe=0.15, coe=0.095, g=0.03)['verdict'], 'UNKNOWN',
   "Target 이 없으면 판정 불가")


# --- 기준선의 한계를 도구가 스스로 밝힌다 ---
# 단년도 ROE 를 영구 ROE 로 쓰면 기준선이 왜곡된다.
#  · 고ROE(20%+) 기업: g=3% 가정이 지속가능성장률(ROE x 유보율)보다 훨씬 낮아
#    기준선이 **과소평가**된다 -> Target 이 프리미엄으로 보인다
#  · 회복기 기업: 바닥 ROE 를 영구값으로 쓰면 기준선이 바닥에 붙는다
# 실측(2026-09-08): 세 종목 모두 PREMIUM 이 나왔는데 삼성SDI 는 25.8배였다.
# 그 숫자를 그대로 "고평가" 로 읽으면 틀린다. caveat 로 경고한다.

c = justify(target_pbr=7.0, roe=0.24, coe=0.095, g=0.03)
ok = 'caveat' in c and c['caveat']
eq(bool(ok), True, "고ROE(24%)면 caveat 를 단다")
eq('지속가능성장' in (c.get('caveat') or ''), True, "caveat 가 이유를 말한다")

c2 = justify(target_pbr=1.0, roe=0.08, coe=0.095, g=0.03)
eq(c2.get('caveat'), None, "보통 ROE(8%)면 caveat 없음")

# 정상화 ROE 를 직접 주면 그것을 쓴다
c3 = justify(target_pbr=2.1, roe=0.035, coe=0.095, g=0.03, normalized_roe=0.09)
close(c3['implied_pbr'], 0.92, "normalized_roe 가 있으면 그것으로 기준선을 만든다", 0.05)
eq(c3['roe_used'], 0.09, "쓴 ROE 를 밝힌다")
eq(justify(target_pbr=2.1, roe=0.035, coe=0.095, g=0.03)['roe_used'], 0.035,
   "normalized_roe 가 없으면 원래 ROE")

print()
print('=' * 62)
print(f'  ggm_check Target 배수 정당화: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 62)
for f in _failed:
    print(f'  [FAIL] {f}')
sys.exit(1 if _failed else 0)
