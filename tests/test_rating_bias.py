"""등급·목표가 편향 점검 (rating_distribution) + 컨센 괴리 설명 의무 (gap5).

배경(2026-09-09): 사용자가 "BUY 가 나오는 종목이 있어"라고 물었다.
세어 보니 v5.14 이후 8건 중 SELL 62%, 그 이전 29건은 7% 였다.
더 깊이 보니 등급보다 **목표주가**가 먼저 기울었다 -- 컨센 대비 중앙값이
v5.8 까지 -7.7%, v5.9 이후 -25%. 30종목 중 컨센을 넘는 목표가는 5건뿐이다.

검증기에도 비대칭이 있었다: **BUY 전용 게이트 2개, SELL 전용 0개.**
gap2(BUY 가 컨센을 그대로 따라가면 지적)는 취지가 옳아 두고,
**방향 무관한 gap5**를 새로 뒀다 -- 컨센과 15% 이상 벌어지면 이유를 대라.
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

# verify_facts / rating_distribution 이 import 시점에 sys.stdout 을 바꾼다 -- 먼저 import
from verify_facts import consensus_gap_explained          # noqa: E402
from rating_distribution import era_of, warnings_for      # noqa: E402

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_passed = 0
_failed = []


def eq(got, want, label):
    global _passed
    if got == want:
        _passed += 1
    else:
        _failed.append((label, want, got))


# ---------- 컨센 괴리 설명 감지 ----------
eq(consensus_gap_explained('증권사 컨센서스 목표주가는 190,000원대다'), True,
   "'컨센서스 목표'를 적으면 설명한 것으로 본다")
eq(consensus_gap_explained('애널리스트 평균 목표주가 $275.08 은 현재가를 밑돈다'), True,
   "US 표현('애널리스트 평균')도 인정한다")
eq(consensus_gap_explained('우리 Base 는 152,000원이다'), False,
   "**우리 숫자만 적고 컨센을 안 적으면 설명이 아니다**")
eq(consensus_gap_explained(''), False, "빈 본문은 설명 없음")

# ---------- 버전대 분류 ----------
eq(era_of('2026-09-09'), 'v5.14+  (1차 출처·6축)', "9/8 이후는 v5.14+")
eq(era_of('2026-07-01'), 'v5.9~13 (수상작 논증)', "6~8월은 v5.9~13")
eq(era_of('2026-04-10'), 'v4.x~5.8', "4~5월은 v4.x~5.8")
eq(era_of(''), 'v4.x~5.8', "날짜가 비면 가장 오래된 구간")

# ---------- 쏠림 경고 ----------
def mk(ratings, gaps=None):
    gaps = gaps if gaps is not None else [None] * len(ratings)
    return [{'name': f'X{i}', 'date': '2026-09-09', 'rating': r, 'gap': g}
            for i, (r, g) in enumerate(zip(ratings, gaps))]


eq(len(warnings_for(mk(['SELL'] * 6 + ['BUY']))), 1,
   "**한 등급이 75% 넘게 몰리면 경고**")
eq(warnings_for(mk(['BUY', 'HOLD', 'SELL', 'BUY', 'HOLD', 'SELL'])), [],
   "고르게 섞이면 경고 없음")
eq(warnings_for(mk(['SELL'] * 4)), [],
   "표본이 5 미만이면 경고하지 않는다 (작은 수로 단정하지 않는다)")

w = warnings_for(mk(['BUY'] * 3 + ['HOLD'] * 3,
                    [-30.0, -28.0, -26.0, -27.0, -31.0, -29.0]))
eq(len(w), 2, "**중앙값 -25% 초과 + 전부 컨센 아래 = 경고 2건**")

w2 = warnings_for(mk(['BUY'] * 3 + ['HOLD'] * 3,
                     [-30.0, -28.0, -26.0, -27.0, -31.0, +5.0]))
eq(len(w2), 1, "한 건이라도 컨센을 넘으면 '전부 아래' 경고는 빠진다")

eq(warnings_for(mk(['BUY'] * 3 + ['HOLD'] * 3,
                   [-5.0, 3.0, -8.0, 2.0, -6.0, 4.0])), [],
   "컨센 근처면 경고 없음")

print('=' * 66)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  등급·목표가 편향 점검: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
