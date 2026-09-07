"""
peer_snapshot (KR) CLI 파싱 가드 테스트 (TDD -- 구현보다 먼저 작성됨)

peer_snapshot_us.py 초판은 `args[args.index('--peers') + 1]` 을 직접 읽어
'--peers' 가 마지막 인자면 IndexError 로 죽었다. KR 판에는 --peers 자체가
없어서 대신 `sys.argv[2]` 를 무조건 업종키로 읽었다. 그래서
`python scripts/peer_snapshot.py 풍산 --peers` 같은 호출이 업종키 '--peers'
로 해석돼 "Peer 목록 없음" 이라는 엉뚱한 메시지로 끝났다.

decision_log.flag_value 와 같은 규칙(값 없음/다음 토큰이 또 다른 플래그면
default)으로 파싱하고, 위치 인자는 ':' 유무로 업종키와 name:code 를 가른다.

실행: python tests/test_peer_snapshot.py
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from peer_snapshot import parse_args, resolve_peers, PEER_TEMPLATES   # noqa: E402

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


# --- 기존 사용법 회귀 (깨지면 안 된다) ---
eq(parse_args(['풍산']), ('풍산', 'default', []), "종목명만")
eq(parse_args(['풍산', 'semicon']), ('풍산', 'semicon', []), "종목명 + 업종키")
eq(parse_args(['JYP', 'kpop', 'HYBE:352820']),
   ('JYP', 'kpop', ['HYBE:352820']), "종목명 + 업종키 + name:code")
eq(parse_args(['JYP', 'kpop', 'HYBE:352820', 'SM:041510']),
   ('JYP', 'kpop', ['HYBE:352820', 'SM:041510']), "name:code 여러 개")

# 업종키 없이 name:code 만 줘도 동작해야 한다 (기존엔 첫 name:code 가 업종키로 먹혔다)
eq(parse_args(['풍산', '고려아연:010130']),
   ('풍산', 'default', ['고려아연:010130']), "업종키 생략하고 name:code 만")

# --- 플래그가 마지막 인자여도 IndexError 가 나지 않는다 ---
eq(parse_args(['풍산', '--peers']), ('풍산', 'default', []),
   "--peers 가 마지막 인자여도 죽지 않는다")
eq(parse_args(['풍산', 'semicon', '--peers']), ('풍산', 'semicon', []),
   "업종키 뒤 --peers 만 있어도 죽지 않는다")
eq(parse_args(['풍산', '--peers', '--verbose']), ('풍산', 'default', []),
   "--peers 뒤가 또 다른 플래그면 값 없음으로 처리")

# --- --peers CSV 지원 (US 판과 같은 형식) ---
eq(parse_args(['풍산', '--peers', '고려아연:010130,LS:006260']),
   ('풍산', 'default', ['고려아연:010130', 'LS:006260']), "--peers CSV 파싱")
eq(parse_args(['풍산', 'semicon', '--peers', '고려아연:010130']),
   ('풍산', 'semicon', ['고려아연:010130']), "업종키와 --peers 동시 사용")
eq(parse_args(['풍산', '--peers', ' 고려아연:010130 , LS:006260 ']),
   ('풍산', 'default', ['고려아연:010130', 'LS:006260']), "CSV 공백 제거")

# --peers 값은 위치 인자로 다시 세지 않는다 (업종키로 오인 금지)
eq(parse_args(['풍산', '--peers', '고려아연:010130', 'retail']),
   ('풍산', 'retail', ['고려아연:010130']), "--peers 값 소비 후 남은 위치 인자가 업종키")

# --- 인자가 아예 없거나 첫 인자가 플래그면 종목명 없음 ---
eq(parse_args([]), (None, 'default', []), "빈 인자")
eq(parse_args(['--peers', 'A:1']), (None, 'default', ['A:1']), "첫 인자가 플래그면 종목명 None")

# --- resolve_peers: 템플릿 + 추가 peer 병합 ---
peers = resolve_peers('kpop', [])
eq(peers, dict(PEER_TEMPLATES['kpop']), "업종 템플릿 그대로")
peers = resolve_peers('kpop', ['큐브:182360'])
eq(peers.get('큐브'), '182360', "추가 peer 병합")
eq(len(peers), len(PEER_TEMPLATES['kpop']) + 1, "템플릿을 덮어쓰지 않고 추가")
eq(resolve_peers('default', []), {}, "default 업종키는 빈 목록")
eq(resolve_peers('없는업종', ['A:1']), {'A': '1'}, "모르는 업종키여도 추가 peer 는 산다")
eq(resolve_peers('kpop', ['HYBE:999999'])['HYBE'], '999999', "같은 이름이면 인자가 우선")

print(f"\n{'=' * 60}")
print(f"  peer_snapshot CLI 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
