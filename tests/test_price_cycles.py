"""
price_cycles -- 과거 주가 사이클 자동 탐지 (TDD, 구현보다 먼저 작성)

배경 (2026-09-08, 위닝펀드 수상작 정독):
  수상작의 가장 강한 논증 장치는 **과거 사이클 유비**다.

    "직전 사이클(2024.10~2025.08) 와이지 주가가 37,000원 -> 107,400원 +190%
     상승했을 때(FDR 실측), 그 핵심 트리거가 '메가 IP 그룹의 재계약과 월드투어'였다.
     본 리포트는 이번 사이클에서 그 자리를 빅뱅 20주년 월드투어가 대체한다고 본다."

  구조: (1) 과거 큰 움직임을 **실측으로 특정**하고 (2) 그때의 트리거를 밝히고
  (3) 지금의 트리거를 1:1 대응시킨다. 대응이 성립하지 않으면 그 논거는 약하다.

  우리 리포트에는 이 장치가 전무했다. "저점 대비 +104.6%" 같은 단순 수익률만 썼다.
  단순 수익률은 사이클이 아니다 -- **언제 시작해 언제 끝났는지**와 **그 구간의
  트리거가 무엇이었는지**가 있어야 유비가 성립한다.

  이 모듈은 (1)을 자동화한다. (2)(3)은 저자가 쓴다 -- 트리거 규명은 데이터가
  아니라 판단이다. 다만 저자가 지어내지 못하도록 **구간의 시작/끝/폭은 실측으로 고정**한다.

실행: python tests/test_price_cycles.py
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from price_cycles import find_cycles, MIN_MOVE_PCT

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


def ok(cond, name):
    global _passed
    if cond:
        _passed += 1
    else:
        _failed.append(name)


def series(pairs):
    return [(d, float(p)) for d, p in pairs]


eq(MIN_MOVE_PCT, 30, "30% 미만 움직임은 사이클로 세지 않는다 (노이즈)")

# --- 단순 상승 한 구간 ---
up = series([('2024-01-01', 100), ('2024-06-01', 130), ('2024-12-01', 200)])
cy = find_cycles(up)
eq(len(cy), 1, "단조 상승은 사이클 1개")
eq(cy[0]['direction'], 'up', "방향 up")
eq(cy[0]['start'], '2024-01-01', "시작일")
eq(cy[0]['end'], '2024-12-01', "종료일")
close(cy[0]['change_pct'], 100.0, "100 -> 200 은 +100%")

# --- 상승 후 하락: 두 구간으로 쪼갠다 ---
ud = series([('2024-01-01', 100), ('2024-08-01', 200), ('2025-03-01', 90)])
cy2 = find_cycles(ud)
eq(len(cy2), 2, "상승 -> 하락은 사이클 2개")
# 목록은 **최신 사이클이 먼저**다 (본문이 '직전 사이클'을 인용하므로)
eq([c['direction'] for c in cy2], ['down', 'up'], "최신(하락)이 먼저, 그 앞 구간(상승)이 뒤")
close(cy2[0]['change_pct'], -55.0, "200 -> 90 은 -55%")

# --- 작은 되돌림은 새 사이클로 세지 않는다 ---
noisy = series([('2024-01-01', 100), ('2024-03-01', 150), ('2024-04-01', 140),
                ('2024-09-01', 210)])
cy3 = find_cycles(noisy)
eq(len(cy3), 1, "**-6.7% 되돌림은 사이클을 끊지 않는다** (노이즈)")
close(cy3[0]['change_pct'], 110.0, "100 -> 210")

# --- 30% 미만 전체 움직임은 아예 사이클이 아니다 ---
flat = series([('2024-01-01', 100), ('2024-06-01', 112), ('2024-12-01', 105)])
eq(find_cycles(flat), [], "전 구간 변동이 작으면 빈 목록")

# --- 최신 사이클이 먼저 온다 (본문이 '직전 사이클'을 인용한다) ---
three = series([('2022-01-01', 100), ('2022-12-01', 200),
                ('2023-12-01', 80), ('2024-12-01', 190)])
cy4 = find_cycles(three)
ok(len(cy4) >= 3, "세 구간을 잡는다")
eq(cy4[0]['end'], '2024-12-01', "**가장 최근 사이클이 첫 번째** (직전 사이클 인용용)")

# --- 기간 라벨 ---
eq(cy4[0]['label'], '2023-12 ~ 2024-12', "라벨은 YYYY-MM ~ YYYY-MM")
ok(cy4[0]['months'] >= 11, "개월 수를 함께 준다")

# --- 방어 ---
eq(find_cycles([]), [], "빈 입력")
eq(find_cycles(series([('2024-01-01', 100)])), [], "한 점으로는 사이클이 없다")
eq(find_cycles(series([('2024-01-01', 0), ('2024-06-01', 100)])), [],
   "시작가 0 은 변동률을 만들 수 없다 -- 무한대를 만들지 않는다")


# ============================================================
# 노이즈 병합 -- 큰 움직임이 조각나 사라지는 것을 막는다
#
# 실측 사고(2026-09-08 LS일렉트릭): 주간 종가 313,000 -> 184,800 (-41.0%)
# 하락이 중간의 +16.4% 반등 때문에 -28.9% / -28.6% 로 갈려 **둘 다 30% 미달로
# 통째로 사라졌다.** 리포트는 "직전 사이클 +836% 상승" 만 말하고 그 뒤 4개월
# -36% 조정을 한 마디도 못 하게 된다. retrace(15) < min_move(30) 인 한 구조적이다.
# ============================================================
from price_cycles import find_cycles as _fc, current_position, _merge_noise  # noqa: E402

def _s(pairs):
    return [(d, float(p)) for d, p in pairs]

# LS일렉트릭 실제 모양 축약: 고점 -> 중간반등 -> 저점
_frag = _s([
    ('2026-01-04', 100000), ('2026-05-10', 313000),
    ('2026-06-14', 222500),          # -28.9% (임계 미달)
    ('2026-06-21', 259000),          # +16.4% 반등 (retrace 15% 초과 -> 피벗)
    ('2026-08-02', 184800),          # -28.6% (임계 미달)
])
_cy = _fc(_frag)
downs = [c for c in _cy if c['direction'] == 'down']
eq(len(downs), 1, "조각난 하락이 **하나로 합쳐져** 살아남는다")
eq(downs[0]['start_price'], 313000, "합쳐진 하락의 시작은 고점")
eq(downs[0]['end_price'], 184800, "합쳐진 하락의 끝은 저점")
eq(downs[0]['change_pct'], -41.0, "합치면 -41.0% -- 30% 임계를 넘는다")

# 병합이 정상 구간을 망가뜨리지 않는다
_clean = _s([('2024-01-07', 10000), ('2024-06-02', 20000), ('2024-12-01', 12000)])
eq(len(_fc(_clean)), 2, "임계를 넘는 구간은 그대로 둘 다 남는다")

# _merge_noise 단독
eq(_merge_noise([('a', 100), ('b', 105)], 30), [('a', 100), ('b', 105)],
   "피벗이 2개면 병합할 게 없다 (임계 필터는 find_cycles 가 한다)")
eq(_merge_noise([('a', 100), ('b', 200), ('c', 205)], 30), [('a', 100), ('b', 200)],
   "꼬리 구간이 임계 미달이면 끝점을 버려 앞 구간을 살린다")
eq(len(_merge_noise([('a', 100), ('b', 200), ('c', 100)], 30)), 3,
   "둘 다 임계를 넘으면 건드리지 않는다")

# current_position -- 사이클의 끝이 현재가 아니다
_cur = current_position(_s([('2026-01-04', 100000), ('2026-09-13', 200500)]),
                        [{'end': '2026-08-02', 'end_price': 184800}])
eq(_cur['price'], 200500, "현재가는 시계열의 마지막")
eq(_cur['change_pct'], 8.5, "직전 사이클 종점 대비 +8.5%")
eq(_cur['months_since'], 1, "종점 이후 1개월 경과")
eq(current_position([], [])                is None, True, "시계열이 비면 None")
eq(current_position(_s([('2026-09-13', 100)]), [])['change_pct'], None,
   "사이클이 없으면 변화율을 지어내지 않는다")

print(f"\n{'=' * 62}")
print(f"  price_cycles 과거 사이클 탐지: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 62}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
