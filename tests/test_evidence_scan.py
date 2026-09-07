"""
evidence_scan CLI/필터 테스트 (TDD -- 구현보다 먼저 작성됨)

코드리뷰 지적: docstring 에 `--min-quote 2` 사용 예시가 있는데 인자가 아무 일도
하지 않았다 (main(stock, min_quote=1) 이 min_quote 를 쓰지 않음). 또 `--min-quote`
가 마지막 인자면 IndexError.

여기서 고정하는 계약:
  1. min_quote = 유형별 최소 인용 수. 그 미만인 유형은 결과에서 통째로 뺀다.
  2. **반증(counter)에는 적용하지 않는다.** 이 스크립트의 존재 이유가 반증 수집이고
     (docstring 참조), 반증은 1건이라도 값이 있다. 실측 증거/실격 신호만 거른다.
  3. `--min-quote` 가 마지막 인자여도 IndexError 대신 기본값.

실행: python tests/test_evidence_scan.py
"""
import sys
import os
import io
import json
import tempfile
import shutil
import contextlib

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from evidence_scan import flag_value, parse_min_quote, filter_min_quote, main  # noqa: E402

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


# --- 1. flag_value: 마지막 인자여도 IndexError 를 내지 않는다 ---
eq(flag_value(['종목', '--min-quote', '2'], '--min-quote'), '2', "정상 값 추출")
eq(flag_value(['종목', '--min-quote'], '--min-quote', '1'), '1',
   "flag 가 마지막 -> default (IndexError 아님)")
eq(flag_value(['종목', '--min-quote', '--verbose'], '--min-quote', '1'), '1',
   "다음 토큰이 또 다른 flag -> default")
eq(flag_value(['종목'], '--min-quote', '1'), '1', "flag 없음 -> default")

# --- 2. parse_min_quote: 항상 1 이상의 int ---
eq(parse_min_quote(['종목', '--min-quote', '2']), 2, "숫자 파싱")
eq(parse_min_quote(['종목', '--min-quote']), 1, "값 없으면 기본 1")
eq(parse_min_quote(['종목']), 1, "flag 없으면 기본 1")
eq(parse_min_quote(['종목', '--min-quote', 'abc']), 1, "숫자가 아니면 기본 1")
eq(parse_min_quote(['종목', '--min-quote', '0']), 1, "0/음수는 1 로 보정")

# --- 3. filter_min_quote: 유형별 건수 미달이면 통째로 제거 ---
hits = [
    {'type': '가동률', 'quote': 'a'},
    {'type': '가동률', 'quote': 'b'},
    {'type': '수주잔고', 'quote': 'c'},
]
eq([h['type'] for h in filter_min_quote(hits, 1)], ['가동률', '가동률', '수주잔고'],
   "min_quote=1 은 기존 동작과 동일 (아무것도 안 뺀다)")
eq([h['type'] for h in filter_min_quote(hits, 2)], ['가동률', '가동률'],
   "min_quote=2 -> 1건짜리 유형 제거")
eq(filter_min_quote(hits, 3), [], "min_quote=3 -> 전부 제거")

# --- 4. main() end-to-end: min_quote 가 실제로 결과 JSON 을 바꾼다 ---
cwd = os.getcwd()
tmp = tempfile.mkdtemp(prefix='evscan_test_')
try:
    os.chdir(tmp)
    os.makedirs('data/테스트종목', exist_ok=True)
    # dedupe 가 앞 60자로 유사 인용을 지우므로 히트끼리 충분히 떨어뜨린다 (CTX=130)
    filler = ("본 보고서는 당사의 사업 현황과 재무 상태를 설명하기 위해 작성되었으며 "
              "관련 법령에 따라 공시되는 자료임을 밝힌다. ") * 3
    text = (
        filler
        + "당사 주력 공장의 가동률은 2025년 98% 수준을 유지하고 있다.\n"
        + filler
        + "2026년 상반기 기준 가동률 95%로 사실상 풀 캐파 가동이 지속되고 있다.\n"
        + filler
        + "수주잔고는 2026년 6월 말 기준 3조원으로 집계되었다.\n"
        + filler
        + "다만 경쟁사 증설 완료로 공급이 안정화되어 2026년에는 수급 완화가 나타났다.\n"
    )
    with open('data/테스트종목/_dart_FULL_사업보고서.txt', 'w', encoding='utf-8') as f:
        f.write(text)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main('테스트종목', min_quote=1)
    eq(rc, 0, "정상 종료")
    d1 = json.load(open('data/테스트종목/_evidence_scan.json', encoding='utf-8'))
    types1 = sorted({h['type'] for h in d1['evidence']})
    truthy('수주잔고' in types1, "min_quote=1 이면 1건짜리 유형도 남는다")
    truthy('가동률' in types1, "2건짜리 유형은 당연히 남는다")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main('테스트종목', min_quote=2)
    d2 = json.load(open('data/테스트종목/_evidence_scan.json', encoding='utf-8'))
    types2 = sorted({h['type'] for h in d2['evidence']})
    eq('수주잔고' in types2, False, "min_quote=2 이면 1건짜리 유형은 빠진다")
    truthy('가동률' in types2, "2건 이상인 유형은 남는다")
    eq(d2.get('min_quote'), 2, "적용한 min_quote 를 결과에 기록")

    # 반증은 min_quote 와 무관하게 보존된다 (이 스크립트의 존재 이유)
    truthy(d1['counter'], "min_quote=1 에서 반증 존재")
    eq([h['type'] for h in d2['counter']], [h['type'] for h in d1['counter']],
       "min_quote 를 올려도 반증은 그대로 남는다")
finally:
    os.chdir(cwd)
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{'=' * 60}")
print(f"  evidence_scan 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
