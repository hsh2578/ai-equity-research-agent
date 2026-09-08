"""Peer 이름 매칭 -- 부분문자열 관계인 두 종목이 같은 표에 있을 때.

배경(2026-09-09 피에스케이홀딩스): verify_facts D4 가
`real_name in name or name in real_name` 로 매칭해서, 리포트의 '피에스케이'가
스냅샷의 '피에스케이홀딩스'에 먼저 붙었다. PER 46.28 을 34.45 와 비교해
멀쩡한 표가 FAIL 로 떨어졌다.

corp_name_resolver 를 만들게 한 것과 같은 종류의 문제이며,
**부분문자열 관계인 종목은 한국 시장에 흔하다**
(LS / LS일렉트릭, 한화 / 한화에어로스페이스, CJ / CJ제일제당 ...).
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

# verify_facts 가 import 시점에 sys.stdout 을 자기 wrapper 로 바꾼다.
# 먼저 감싸 두면 그쪽이 교체하면서 이쪽 버퍼가 닫혀 ValueError 가 난다 -- 순서를 지킨다.
from verify_facts import _match_peer, check_d4_peer_table   # noqa: E402

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


SNAP = {
    '피에스케이홀딩스': {'per': 34.45, 'pbr': 6.24},
    '한미반도체': {'per': 109.49, 'pbr': 33.59},
    '피에스케이': {'per': 46.28, 'pbr': 6.75},
}

# ---------- 실측 오탐 케이스 ----------
eq(_match_peer(SNAP, '피에스케이')['per'], 46.28,
   "**'피에스케이'는 '피에스케이홀딩스'가 아니라 자기 자신에 붙는다**")
eq(_match_peer(SNAP, '피에스케이홀딩스')['per'], 34.45,
   "'피에스케이홀딩스'도 정확히 자기 자신에 붙는다")

# ---------- 정규화 ----------
eq(_match_peer({'LG 이노텍': {'per': 1}}, 'LG이노텍')['per'], 1,
   "공백 차이는 흡수한다")
eq(_match_peer({'에스케이(주)': {'per': 2}}, '에스케이')['per'], 2,
   "괄호 표기는 흡수한다")

# ---------- 부분 일치는 길이 차가 가장 작은 것 ----------
eq(_match_peer({'한화': {'per': 1}, '한화에어로스페이스': {'per': 2}},
               '한화에어로')['per'], 2,
   "부분 일치가 여럿이면 이름 길이가 가장 가까운 쪽")

# ---------- 방어 ----------
eq(_match_peer(SNAP, ''), None, "빈 이름은 매칭하지 않는다")
eq(_match_peer(SNAP, '삼성전자'), None, "없는 종목은 None")
eq(_match_peer({}, '피에스케이'), None, "빈 스냅샷도 안전")

# ---------- D4 전체 경로 ----------
analysis = {'peers': [
    {'name': '피에스케이홀딩스', 'per': 34.45},
    {'name': '피에스케이', 'per': 46.28},
]}
res = check_d4_peer_table(analysis, SNAP)
eq(res['fails'], [], "**두 종목이 같은 표에 있어도 D4 는 FAIL 을 내지 않는다**")

analysis_bad = {'peers': [{'name': '피에스케이', 'per': 99.0}]}
eq(len(check_d4_peer_table(analysis_bad, SNAP)['fails']), 1,
   "진짜로 값이 다르면 여전히 잡는다")

print('=' * 62)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  Peer 이름 매칭: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 62)
sys.exit(1 if _failed else 0)
