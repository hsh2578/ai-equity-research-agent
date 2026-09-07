"""
rs_table -> fetch_quote 인자 전달 테스트

실행: python tests/test_rs_table.py

배경 -- 벤치마크 인자가 fetch_quote 로 전달되지 않았다.
run_window 가 `[python, fetch_quote, *codes, bench, "--start", ...]` 로 벤치마크를
**또 하나의 종목코드**로 넘기고 --bench 는 주지 않아, fetch_quote 의 기본값
"KOSPI" 로 조용히 폴백했다. `rs_table.py 247540 --bench KOSDAQ` 는 화면에
"벤치마크 KOSDAQ" 를 찍으면서 실제 상대강도는 KOSPI 기준으로 계산했고,
그 잘못된 시계열에 ±100/-50 판정 임계값이 적용됐다.
"""
import sys
import os
import io
import json
import types

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'scripts', 'broker'))

import rs_table as R

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected}\n      실제: {actual}")


def truthy(actual, name):
    eq(bool(actual), True, name)


def falsy(actual, name):
    eq(bool(actual), False, name)


captured = []


class _FakeRun:
    """subprocess.run 대역 -- 커맨드만 잡고 빈 JSON 을 돌려준다."""

    def __init__(self, payload='[]'):
        self.payload = payload

    def __call__(self, cmd, **kw):
        captured.append(list(cmd))
        return types.SimpleNamespace(returncode=0, stdout=self.payload, stderr='')


_orig_run = R.subprocess.run
R.subprocess.run = _FakeRun(json.dumps(
    [{"code": "247540", "return_pct": 12.0, "relative_strength_pp": 3.0}]))

try:
    captured.clear()
    rows = R.run_window(['247540', '066970'], 'KOSDAQ', '2026-01-01', '2026-09-08')
    cmd = captured[0]

    truthy('--bench' in cmd, "--bench 플래그가 fetch_quote 로 전달된다")
    if '--bench' in cmd:
        eq(cmd[cmd.index('--bench') + 1], 'KOSDAQ', "--bench 값이 요청한 벤치마크와 같다")

    # 위치 인자(codes) 부분만 뜯어본다: [python, fetch_quote.py, <codes...>, --옵션...]
    positional = []
    for tok in cmd[2:]:
        if str(tok).startswith('--'):
            break
        positional.append(tok)
    eq(positional, ['247540', '066970'], "벤치마크가 종목코드 위치 인자에 섞이지 않는다")
    truthy('--start' in cmd and '--end' in cmd, "--start/--end 는 그대로 전달")
    eq(cmd[cmd.index('--start') + 1], '2026-01-01', "--start 값 유지")
    eq(cmd[cmd.index('--end') + 1], '2026-09-08', "--end 값 유지")
    eq(rows, [{"code": "247540", "return_pct": 12.0, "relative_strength_pp": 3.0}],
       "정상 응답 파싱 회귀")

    # 기본 벤치마크(KOSPI)도 명시 전달되어야 한다 (fetch_quote 기본값 의존 금지)
    captured.clear()
    R.run_window(['005930'], 'KOSPI', '2026-01-01', '2026-09-08')
    cmd2 = captured[0]
    truthy('--bench' in cmd2 and cmd2[cmd2.index('--bench') + 1] == 'KOSPI',
           "기본 KOSPI 도 --bench 로 명시 전달")

    # build() 를 통해도 벤치마크가 3개 구간 전부에 전달된다
    captured.clear()
    R.build(['247540'], 'KOSDAQ', '2026-09-08', {'247540': '테스트'})
    eq(len(captured), 3, "build() 는 3M/12M/24M 세 구간을 조회")
    truthy(all('--bench' in c and c[c.index('--bench') + 1] == 'KOSDAQ' for c in captured),
           "build() 세 구간 모두 --bench KOSDAQ 전달")
finally:
    R.subprocess.run = _orig_run


# --- verdict 회귀 (판정 임계값은 손대지 않는다) ---
eq(R.verdict({'12M_rs': 234.0, '24M_rs': 300.0}), '이미상승', "verdict 이미상승 (RS > +100)")
eq(R.verdict({'12M_rs': -60.0, '24M_rs': -70.0}), '미반영', "verdict 미반영 (RS < -50)")
eq(R.verdict({'12M_rs': 10.0, '24M_rs': -5.0}), '중립', "verdict 중립")
eq(R.verdict({}), '데이터없음', "verdict 데이터없음")

print(f"\n{'=' * 60}")
print(f"  rs_table 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
