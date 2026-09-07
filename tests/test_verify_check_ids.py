"""
검증기 체크 ID 충돌 테스트 (TDD -- 구현보다 먼저 작성됨)

배경 -- '조용한 무력화' 결함.
verify_numbers_us.py 에 v5.5 로 추가한 `('B13 분기 누락', ...)` 이 기존
`('B13 GAAP/Non-GAAP', ...)` 와 id 가 겹쳤다. 한 번의 실행에서 서로 다른 두
검증이 같은 B13 으로 출력되면, 로그를 grep 하거나 리포트에 "B13 PASS" 라고
적을 때 어느 검증이 통과한 것인지 알 수 없다. 검증기 자체가 검증되지 않으면
PASS 는 아무 의미가 없다 (B13 이 몇 달간 죽어 있었던 그 전력).

같은 검증의 하위 항목이 id 를 공유하는 것(B17 'FCF 본문 변종' /
'순부채 본문 변종' / '시총 본문 변종')은 정상이다. 그래서 "라벨끼리 공통
단어가 하나도 없으면 서로 다른 검증" 이라는 기준으로 판정한다.

실행: python tests/test_verify_check_ids.py
"""
import sys
import os
import io
import re
import collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, '..'))

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


# f'B4 {label}' 처럼 f-string 으로 만드는 id 도 잡는다
_APPEND = re.compile(r"\(\s*f?'(B\d+)([^']*)'\s*,")


def check_ids(path):
    """소스에서 results.append(('B<n> 라벨', ...)) 를 긁어 id -> 라벨집합."""
    src = open(path, encoding='utf-8').read()
    ids = collections.defaultdict(set)
    for num, label in _APPEND.findall(src):
        ids[num].add(label.strip())
    return ids


def collisions(ids):
    """라벨끼리 공통 단어가 하나도 없는 id = 서로 다른 검증의 id 충돌.

    f'B8 {label}' 처럼 런타임에 채워지는 라벨은 무엇과도 비교할 수 없으니 제외한다
    (B8 은 'B8 EPS' 와 f'B8 {label}' 이 같은 EPS 검증의 두 출력 경로다).
    """
    bad = []
    for num, labels in ids.items():
        labels = {l for l in labels if '{' not in l}
        if len(labels) < 2:
            continue
        common = None
        for lab in labels:
            toks = set(lab.replace('/', ' ').split())
            common = toks if common is None else (common & toks)
        if not common:
            bad.append((num, sorted(labels)))
    return sorted(bad)


# --- US 검증기: B13 충돌이 없어야 한다 ---
us = check_ids(os.path.join(_ROOT, 'scripts', 'verify_numbers_us.py'))
eq(collisions(us), [], "verify_numbers_us.py 에 서로 다른 검증의 id 충돌 없음")

# 분기 누락 검증은 B20 으로 이사했고, B13 은 GAAP/Non-GAAP 전용이다
truthy(any('분기 누락' in l for l in us.get('B20', set())),
       "US 분기 누락 검증은 B20")
falsy(any('분기 누락' in l for l in us.get('B13', set())),
      "B13 에는 더 이상 분기 누락 검증이 없다")
truthy(any('GAAP' in l for l in us.get('B13', set())),
       "B13 은 GAAP/Non-GAAP 전용으로 남는다")

# B20 은 US 파일 안에서 다른 검증과 겹치지 않아야 한다
eq(len(us.get('B20', set())), 1, "B20 라벨은 하나뿐")

# --- KR 검증기: 회귀 없음 (수정 대상 아님) ---
kr = check_ids(os.path.join(_ROOT, 'scripts', 'verify_numbers.py'))
eq(collisions(kr), [], "verify_numbers.py 에 id 충돌 없음 (회귀 확인)")

# --- docstring 검증 항목 목록도 실제 id 와 맞아야 한다 ---
us_src = open(os.path.join(_ROOT, 'scripts', 'verify_numbers_us.py'), encoding='utf-8').read()
doc = us_src.split('"""')[1]
truthy('B20' in doc, "docstring 검증 항목 목록에 B20 이 등재됨")
truthy(re.search(r'B13\s+GAAP', doc), "docstring 의 B13 은 GAAP/Non-GAAP")
falsy(re.search(r'B13[^\n]*분기', doc), "docstring 에 'B13 분기' 표기가 남아있지 않음")

# docstring 에 적힌 B 번호는 전부 코드에 실재해야 한다 (죽은 문서 방지)
doc_ids = set(re.findall(r'^-\s*(B\d+)\s', doc, re.M))
missing = sorted(doc_ids - set(us), key=lambda x: int(x[1:]))
eq(missing, [], "docstring 에만 있고 코드에 없는 검증 id 없음")


print(f"\n{'=' * 60}")
print(f"  verify 체크 ID 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
