"""
decision_log 재기록(수정) 테스트 (TDD -- 구현보다 먼저 작성)

배경 (2026-09 에프에스티 실측 사고):
  같은 날 리포트를 HOLD 로 기록한 뒤, bear-researcher 반증을 반영해 SELL 로
  고쳐 다시 `record` 했다. 그런데 멱등 체크가 **(날짜, 종목)만** 보고 건너뛰었다.

  더 나쁜 것은 출력이었다:
      [SKIP] 에프에스티 2026-09-08 SELL 이미 존재 (멱등)
  화면에는 SELL 이라 찍혔는데 파일에는 HOLD 가 남아 있었다.
  결정 로그는 **"그 콜이 맞았나"를 채점하는 유일한 자산**이라,
  틀린 등급이 남으면 적중률 통계 전체가 조용히 오염된다.

규칙:
  1. 같은 (날짜, 종목)에 **내용이 같으면** 건너뛴다 (진짜 멱등)
  2. **등급이나 목표가가 바뀌었으면 기존 항목을 갱신한다** -- 조용히 버리지 않는다
  3. 이미 정산된(pending 이 아닌) 항목은 갱신하지 않는다 -- 사후 조작 방지
  4. 반환값으로 무슨 일이 일어났는지 구분할 수 있어야 한다

실행: python tests/test_decision_log_revise.py
"""
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from decision_log import DecisionLog

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected!r}\n      실제: {actual!r}")


def truthy(v, name):
    eq(bool(v), True, name)


tmpdir = tempfile.mkdtemp()
path = os.path.join(tmpdir, '_decision_log.md')
log = DecisionLog(path=path)

T = {'bear': 15500, 'base': 25500, 'bull': 38000}
T2 = {'bear': 12000, 'base': 21000, 'bull': 32000}

# --- 최초 기록 ---
eq(log.record('에프에스티', '2026-09-08', 'HOLD', thesis='초판', targets=T,
              price=25750, market='KR'), 'ADDED', "최초 기록은 ADDED")
text = open(path, encoding='utf-8').read()
truthy('| 에프에스티 | HOLD |' in text, "HOLD 로 저장됐다")

# --- 같은 내용 재기록 -> 진짜 멱등 ---
eq(log.record('에프에스티', '2026-09-08', 'HOLD', thesis='초판', targets=T,
              price=25750, market='KR'), 'SKIPPED', "내용이 같으면 SKIPPED")
eq(open(path, encoding='utf-8').read().count('에프에스티'), text.count('에프에스티'),
   "중복 항목이 늘지 않는다")

# --- 등급이 바뀌면 갱신 ---
eq(log.record('에프에스티', '2026-09-08', 'SELL', thesis='v2 정정', targets=T2,
              price=25750, market='KR'), 'REVISED', "등급이 바뀌면 REVISED")
text2 = open(path, encoding='utf-8').read()
truthy('| 에프에스티 | SELL |' in text2, "SELL 로 갱신됐다")
eq('| 에프에스티 | HOLD |' in text2, False, "옛 HOLD 는 남지 않는다")
truthy('21,000' in text2 or '21000' in text2, "새 목표가가 반영됐다")
eq(text2.count('[2026-09-08 | 에프에스티 |'), 1, "항목은 여전히 하나다")

# --- 목표가만 바뀌어도 갱신 ---
eq(log.record('에프에스티', '2026-09-08', 'SELL', thesis='v2 정정',
              targets={'bear': 11000, 'base': 21000, 'bull': 32000},
              price=25750, market='KR'), 'REVISED', "목표가만 바뀌어도 REVISED")

# --- 다른 날짜는 새 항목 ---
eq(log.record('에프에스티', '2026-12-01', 'BUY', thesis='분기 재방문', targets=T2,
              price=20000, market='KR'), 'ADDED', "날짜가 다르면 새 항목")
eq(open(path, encoding='utf-8').read().count('[2026-12-01 | 에프에스티 |'), 1,
   "새 날짜 항목 1개")

# --- 정산된 항목은 갱신하지 않는다 (사후 조작 방지) ---
log.record('테스트종목', '2026-01-01', 'BUY', thesis='t', targets=T, price=100, market='KR')
log.update_with_outcome('테스트종목', '2026-01-01', raw_return=5.0, alpha_return=2.0,
                        holding_days=30, reflection='정산됨')
eq(log.record('테스트종목', '2026-01-01', 'SELL', thesis='뒤늦게 수정', targets=T2,
              price=100, market='KR'), 'LOCKED',
   "이미 정산된 항목은 LOCKED -- 사후 등급 변경 금지")
truthy('| 테스트종목 | BUY |' in open(path, encoding='utf-8').read(),
       "정산 항목의 등급은 그대로다")

# --- 콜이 바뀐 것과 글이 바뀐 것을 구분한다 (2026-09-09 삼성SDI 실측) ---
# 목표가가 570,000원 그대로인데 화면에 "등급/목표가가 바뀌었다"가 찍혔다.
# record() 가 블록 전체를 비교해 **논지 문장만 고쳐도 REVISED** 였기 때문이다.
# 나중에 "콜이 몇 번 바뀌었나"를 세면 문장 손질까지 섞여 통계가 오염된다.
log.record('구분종목', '2026-05-01', 'HOLD', thesis='처음 논지',
           targets=T, price=1000, market='KR')
eq(log.record('구분종목', '2026-05-01', 'HOLD', thesis='논지만 다시 씀',
              targets=T, price=1000, market='KR'), 'REFRESHED',
   "**논지만 바뀌면 REFRESHED -- 콜은 그대로다**")
eq(log.record('구분종목', '2026-05-01', 'SELL', thesis='논지만 다시 씀',
              targets=T, price=1000, market='KR'), 'REVISED',
   "등급이 바뀌면 REVISED")
eq(log.record('구분종목', '2026-05-01', 'SELL', thesis='논지만 다시 씀',
              targets=T2, price=1000, market='KR'), 'REVISED',
   "목표가가 바뀌어도 REVISED")
eq(log.record('구분종목', '2026-05-01', 'SELL', thesis='논지만 다시 씀',
              targets=T2, price=1000, market='KR'), 'SKIPPED',
   "아무것도 안 바뀌면 여전히 SKIPPED (멱등)")
truthy('| 구분종목 | SELL |' in open(path, encoding='utf-8').read(),
       "REFRESHED 든 REVISED 든 파일 내용은 최신으로 갱신된다")


print(f"\n{'=' * 60}")
print(f"  decision_log 재기록 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
