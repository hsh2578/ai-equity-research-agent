"""
wf_charts.peer_multiples 결측 Peer 렌더 테스트

실행: python tests/test_wf_charts.py

배경 -- 적자 Peer 한 곳이 Word 빌드 전체를 중단시켰다.
wf_chart_planner.b_peer_multiples 는 `_num(p.get('per'))` 로 PER 를 채우는데
'적자' / 'N/A' peer 에는 None 이 들어간다(generate_all.py 가 peer PER 의 '적자' 를
명시적으로 처리하므로 실재하는 값이다). 그 None 리스트가 그대로 ax.bar 로 넘어가
TypeError: unsupported operand type(s) for +: 'int' and 'NoneType' 가 났고,
generate_word_wf.py 가 render() 를 try/except 없이 부르기 때문에 .docx 생성이 통째로 죽었다.

기대 동작: 결측 Peer 는 막대를 그리지 않고 '적자'/'N/A' 라벨만 표기, 나머지는 정상 렌더.
"""
import sys
import os
import io
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import wf_charts as W

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected}\n      실제: {actual}")


def renders(data, name):
    """render 가 예외 없이 png 를 만들면 통과."""
    global _passed
    try:
        with tempfile.TemporaryDirectory() as td:
            path = W.peer_multiples(data, 'Peer PER/PBR 비교', td, name='t_peer')
            if os.path.exists(path) and os.path.getsize(path) > 0:
                _passed += 1
            else:
                _failed.append(f"{name}\n      PNG 미생성: {path}")
    except Exception as exc:
        _failed.append(f"{name}\n      예외: {type(exc).__name__}: {exc}")


# --- 정상 (회귀) ---
renders({'names': ['본종목', 'A사', 'B사'], 'per': [12.5, 18.0, 9.4],
         'pbr': [1.2, 2.1, 0.8], 'highlight_idx': 0},
        "정상 Peer 3사 -- 기존 동작 회귀")

# --- 적자 Peer 1곳 (실제 사고 재현) ---
renders({'names': ['본종목', '적자피어', 'B사'], 'per': [12.5, None, 9.4],
         'pbr': [1.2, 0.8, 0.8], 'highlight_idx': 0,
         'per_labels': [None, '적자', None]},
        "적자 Peer 1곳 (PER=None) -- Word 빌드 중단 사고 재현")

# --- PER/PBR 양쪽에 결측 ---
renders({'names': ['본종목', '적자피어', 'B사'], 'per': [12.5, None, 9.4],
         'pbr': [1.2, None, 0.8], 'highlight_idx': 0,
         'per_labels': [None, '적자', None], 'pbr_labels': [None, 'N/A', None]},
        "PER·PBR 양쪽 결측")

# --- 결측이 다수 (라벨 없는 경우 포함) ---
renders({'names': ['본종목', 'A사', 'B사', 'C사'], 'per': [None, 15.0, None, None],
         'pbr': [1.0, None, None, 0.7], 'highlight_idx': 1},
        "결측 다수 + per_labels 미제공 (하위호환)")

# --- PER 전부 결측 (전 업종 적자) -- 죽지 않아야 한다 ---
renders({'names': ['본종목', 'A사', 'B사'], 'per': [None, None, None],
         'pbr': [1.0, 1.4, 0.7], 'highlight_idx': 0},
        "PER 전부 결측 (전 업종 적자) -- 축만 그리고 생존")

# --- pbr 자체가 없는 하위호환 케이스 ---
renders({'names': ['본종목', 'A사'], 'per': [10.0, 12.0], 'highlight_idx': 0},
        "pbr 키 부재 (하위호환)")

# --- 음수 PER 이 섞인 경우 (일부 리포트가 적자를 -12 로 적는다) ---
renders({'names': ['본종목', 'A사', 'B사'], 'per': [10.0, -12.0, None],
         'pbr': [1.0, 0.9, 0.8], 'highlight_idx': 0},
        "음수 PER 혼재")

print(f"\n{'=' * 60}")
print(f"  wf_charts 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
