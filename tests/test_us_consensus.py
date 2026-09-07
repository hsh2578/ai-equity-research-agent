"""
us_consensus CLI 인자 파싱 테스트 (TDD -- 구현보다 먼저 작성됨)

코드리뷰 지적: `--dir` 가 마지막 인자면 IndexError.
    out_dir = sys.argv[sys.argv.index('--dir') + 1]

decision_log.flag_value 와 동일한 안전 규칙으로 고정한다.

실행: python tests/test_us_consensus.py
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from us_consensus import flag_value, resolve_out_dir  # noqa: E402

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected!r}\n      실제: {actual!r}")


# --- flag_value ---
eq(flag_value(['AMD', '--dir', 'out/x'], '--dir'), 'out/x', "정상 값 추출")
eq(flag_value(['AMD', '--dir'], '--dir', 'D'), 'D', "flag 가 마지막 -> default (IndexError 아님)")
eq(flag_value(['AMD', '--dir', '--quiet'], '--dir', 'D'), 'D', "다음 토큰이 또 다른 flag -> default")
eq(flag_value(['AMD'], '--dir', 'D'), 'D', "flag 없음 -> default")

# --- resolve_out_dir: 인자가 깨져도 기본 경로로 살아난다 ---
eq(resolve_out_dir(['us_consensus.py', 'AMD', '--dir', 'data/AMD2'], 'AMD'), 'data/AMD2',
   "--dir 지정 시 그 경로")
eq(resolve_out_dir(['us_consensus.py', 'AMD', '--dir'], 'AMD'), 'data/AMD',
   "--dir 가 마지막 -> 기본 data/{TICKER} (IndexError 아님)")
eq(resolve_out_dir(['us_consensus.py', 'AMD'], 'AMD'), 'data/AMD', "--dir 없음 -> 기본 경로")

print(f"\n{'=' * 60}")
print(f"  us_consensus 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
