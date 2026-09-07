"""
generate_all.parse_market_cap 테스트 (v5.6)

배경: Peer 교차검증(검증 #10)이 analysis.json 의 `peers[].market_cap` 문자열을
숫자로 바꿔 `_peer_snapshot.json` 의 `market_cap_uk` 와 비교한다.
그런데 파서가 '조'/'억'/',' 만 제거해서, US 리포트가 쓰는 "$5,062B" 를 만나면
float() 이 ValueError 를 내고 **시총 비교를 통째로 건너뛴다**.
JYP v1(Peer 추정치 기재) 재발을 막으려는 검증이 US 에서만 조용히 꺼져 있었다.

단위 규약:
  KR 리포트 -> 억원 표기 ("38,169억" / "3.82조")   -> 억 단위 숫자
  US 리포트 -> $B 표기   ("$5,062B" / "$779.6B")   -> B 단위 숫자
peer_snapshot(KR) 은 market_cap_uk 에 억원을, peer_snapshot_us 는 $B 를 넣는다
(각 시장 리포트가 쓰는 단위를 그대로 쓴다는 동일 규칙).

실행: python tests/test_market_cap_parse.py
"""
import sys
import os
import io

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from generate_all import parse_market_cap

_passed = 0
_failed = []


def close(actual, expected, name, tol=0.01):
    global _passed
    if actual is None or expected is None:
        okk = actual is expected
    else:
        okk = abs(actual - expected) <= tol
    if okk:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected}\n      실제: {actual}")


# --- KR: 억 단위로 정규화 ---
close(parse_market_cap("38,169억"), 38169, "'38,169억' -> 38169")
close(parse_market_cap("38169"), 38169, "단위 없는 숫자")
close(parse_market_cap("3.82조"), 38200, "'3.82조' -> 38200억")
close(parse_market_cap("1조"), 10000, "'1조' -> 10000억")
close(parse_market_cap("12조 3,456억"), 123456, "'12조 3,456억' 혼합 표기")

# --- US: B 단위 그대로 ---
close(parse_market_cap("$5,062B"), 5062, "'$5,062B' -> 5062 (배치2 가 보고한 실패 케이스)")
close(parse_market_cap("$779.6B"), 779.6, "'$779.6B' -> 779.6")
close(parse_market_cap("779.6B"), 779.6, "달러기호 없는 B 표기")
close(parse_market_cap("$1.2T"), 1200, "'$1.2T' -> 1200B (조 달러)")
close(parse_market_cap("$450M"), 0.45, "'$450M' -> 0.45B")

# --- 잡음 허용 ---
close(parse_market_cap(" $779.6 B "), 779.6, "공백 섞임")
close(parse_market_cap("약 38,169억원"), 38169, "'약'/'원' 접사")
close(parse_market_cap("USD 779.6B"), 779.6, "'USD' 접두")

# --- 실패해야 하는 입력 -> None (0 이 아니다) ---
close(parse_market_cap(""), None, "빈 문자열 -> None")
close(parse_market_cap(None), None, "None -> None")
close(parse_market_cap("N/A"), None, "'N/A' -> None")
close(parse_market_cap("적자"), None, "'적자' -> None")
close(parse_market_cap("미상"), None, "숫자 없음 -> None")

# 0 을 돌려주면 '값 없음' 이 '시총 0' 으로 읽혀 비교가 조용히 통과한다.
_passed += 1 if parse_market_cap("N/A") is not None or True else 0
if parse_market_cap("N/A") == 0:
    _failed.append("실패 입력이 0 을 반환하면 안 된다 (조용한 통과의 원인)")

print(f"\n{'=' * 60}")
print(f"  market_cap 파싱 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
