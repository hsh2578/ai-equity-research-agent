"""
반복 사고 물리 차단 hook (v5.5)

CLAUDE.md 의 "절대 금지" 규칙들은 지금까지 **문서상 규칙**이었고, 그래서 반복 위반됐다.
문서는 읽히지 않을 수 있지만 hook 은 반드시 실행된다.

차단 대상 3가지 (전부 실제로 사고를 낸 것들):

1. **KIS 래퍼 결과에 영문 소문자 키** -- `px.get("per")`, `px.get("stck_prpr")`
   kis_api.py 래퍼는 한글 키로 반환한다. 소문자 영문 키는 항상 0/None 을 돌려준다.
   JYP v1 에서 Peer 시총·PER 이 전부 0 으로 저장된 사고의 직접 원인.

2. **프로젝트 루트에 임시 덤프 쓰기** -- `_tmp_*.txt` 를 `data/{종목}/` 밖에 쓰면
   다음 /research 실행 때 다른 종목 잔재가 Grep 에 섞인다.

3. **콘솔 출력에 em-dash / 스마트 따옴표** -- Windows cp949 콘솔에서 UnicodeEncodeError.

## v5.5 리뷰 반영 -- 초판의 치명적 오탐

초판은 `.get('per'|'eps'|...)` 를 **무조건** 잡았다. 그런데 소문자 영문 키를 쓰는 것이
**정상인** 자료구조가 이 프로젝트에 훨씬 많다:

  - `financial_summary.json['kis']`  -> current_price / per / pbr / eps / bps (영문 소문자)
  - `financial_summary.json['financials'][연도]` -> revenue / op_income / eps / bps
  - yfinance `info`                  -> trailingPE / forwardPE / ...
  - DART 재무제표 행                  -> eps 등

한글 키를 쓰는 것은 **kis_api.py 래퍼 함수의 반환값뿐**이다. 그래서 초판은
financial_summary.py / fdr_band.py / analysis_to_md.py / build_snapshot.py /
fdr_band_us.py 의 정상 코드를 전부 차단했고, "`.get('EPS')` 로 고치라"는
**틀린 지시**까지 냈다 (그대로 고치면 그 코드들이 조용히 망가진다).

현재 규칙: **KIS 래퍼 함수의 반환값에 직접 소문자 키를 쓸 때만** 차단한다.
  (a) `get_current_price(...).get("per")` 처럼 호출에 바로 체이닝하거나
  (b) `px = get_current_price(...)` 로 받은 그 변수에 `.get("per")` 를 쓸 때

또 em-dash 검사가 물리 라인 단위라 여러 줄로 쓴 `print(...)` 를 놓쳤다.
지금은 호출 span 을 이어붙여 검사한다.
"""
import sys
import io
import os
import json
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# --- 1. KIS 래퍼 ---------------------------------------------------------
# 한글 키로 반환하는 kis_api.py 래퍼 함수들
KIS_FUNCS = ('get_current_price', 'get_daily_price', 'get_investor_trend',
             'get_us_current_price', 'get_us_daily_price')

# 이 키들을 소문자로 쓰면 항상 0/None 이 나온다 -> 대응 한글 키
KIS_HINT = {
    'per': 'PER', 'pbr': 'PBR', 'eps': 'EPS', 'bps': 'BPS',
    'stck_prpr': '현재가', 'hts_avls': '시가총액',
    'stck_hgpr': '고가', 'stck_lwpr': '저가', 'prdy_ctrt': '등락률',
    'acml_vol': '거래량', 'acml_tr_pbmn': '거래대금',
    'frgn_ntby_qty': '외국인_순매수', 'orgn_ntby_qty': '기관_순매수',
}
_KEYS = '|'.join(sorted(KIS_HINT, key=len, reverse=True))

# (a) 호출에 바로 체이닝:  get_current_price(...).get("per")
_CHAINED = re.compile(
    rf'(?:{"|".join(KIS_FUNCS)})\s*\([^()]*\)\s*\.get\(\s*[\'"]({_KEYS})[\'"]')

# KIS 래퍼 반환을 받은 변수:  px = get_current_price(code)
_ASSIGN = re.compile(rf'^\s*([A-Za-z_]\w*)\s*=\s*(?:{"|".join(KIS_FUNCS)})\s*\(', re.M)

# --- 2. 루트 임시 덤프 ----------------------------------------------------
ROOT_DUMP = re.compile(r'^_(?:tmp|sec|dart)_[^/\\]*\.(?:txt|json)$')

# --- 3. 콘솔 출력 특수문자 (cp949 미지원) ---------------------------------
BAD_CHARS = {'—': 'em-dash', '–': 'en-dash',
             '‘': '여는 홑따옴표', '’': '닫는 홑따옴표',
             '“': '여는 겹따옴표', '”': '닫는 겹따옴표'}

# print( / sys.stderr 로 시작하는 호출 span 을 괄호 균형까지 이어붙여 잡는다.
_PRINT_START = re.compile(r'\b(?:print|sys\.stderr\.write|stderr\.write)\s*\(')


def block(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def kis_lowercase_hits(text):
    """KIS 래퍼 반환값에 소문자 키를 쓴 곳만 (키, 문맥) 으로 반환."""
    hits = []
    for m in _CHAINED.finditer(text):
        hits.append((m.group(1), m.group(0)))

    kis_vars = {m.group(1) for m in _ASSIGN.finditer(text)}
    for var in kis_vars:
        pat = re.compile(rf'\b{re.escape(var)}\s*\.get\(\s*[\'"]({_KEYS})[\'"]')
        for m in pat.finditer(text):
            hits.append((m.group(1), m.group(0)))
    return hits


def print_spans(text):
    """print(...) / stderr.write(...) 호출 본문을 괄호 균형까지 잘라 돌려준다.

    물리 라인 단위로 보면 여러 줄로 쓴 print 안의 em-dash 를 놓친다 (v5.5 리뷰 지적).
    """
    spans = []
    for m in _PRINT_START.finditer(text):
        i = m.end() - 1            # 여는 괄호 위치
        depth, j, n = 0, i, len(text)
        while j < n:
            c = text[j]
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        start_line = text.count('\n', 0, m.start()) + 1
        spans.append((start_line, text[m.start():min(j + 1, n)]))
    return spans


def check_python_source(text, where):
    problems = []

    for key, ctx in kis_lowercase_hits(text):
        ko = KIS_HINT.get(key, '한글 키')
        problems.append(
            f"KIS 래퍼 반환값에 소문자 키 `{ctx.strip()}` 사용.\n"
            f"  kis_api.py 의 {'/'.join(KIS_FUNCS[:2])}() 는 **한글 키**로 반환한다.\n"
            f"  `.get('{key}')` 는 항상 0/None 을 돌려준다 -> `.get('{ko}')` 로 고칠 것.\n"
            f"  (JYP v1 에서 Peer 시총/PER 이 전부 0 으로 저장된 사고의 원인)\n"
            f"  주의: financial_summary.json / yfinance info / DART 행은 소문자 영문 키가"
            f" 정상이므로 그쪽은 고치지 말 것.")
        break                       # 한 건만 보고하면 충분하다

    for lineno, span in print_spans(text):
        for ch, name in BAD_CHARS.items():
            if ch in span:
                flat = ' '.join(span.split())[:110]
                problems.append(
                    f"{lineno}행 콘솔 출력에 {name}({ch}) 사용. Windows cp949 에서 "
                    f"UnicodeEncodeError 가 난다. 하이픈 '-' 또는 '--' 로 바꿀 것.\n"
                    f"  > {flat}")
                break

    if problems:
        block(f"[guard] {where} 차단:\n\n" + "\n\n".join(f"- {p}" for p in problems)
              + "\n\n수정 후 다시 시도할 것.")


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)          # 입력을 못 읽으면 통과 (hook 이 작업을 막지 않게)

    tool = payload.get('tool_name', '')
    ti = payload.get('tool_input', {}) or {}
    path = ti.get('file_path') or ''
    base = os.path.basename(path)
    norm = path.replace('\\', '/')

    # 규칙 2: 루트 임시 덤프
    if tool == 'Write' and ROOT_DUMP.match(base) and 'data/' not in norm:
        block(
            f"[guard] 프로젝트 루트에 임시 덤프 `{base}` 쓰기 차단.\n\n"
            f"  임시 덤프는 반드시 `data/{{종목명}}/` 하위에 쓴다.\n"
            f"  루트에 쌓이면 다음 /research 실행 때 다른 종목 잔재가 Grep 에 섞인다.\n"
            f"  예: data/한국콜마/{base}")

    if not path.endswith('.py'):
        sys.exit(0)
    # 이 hook 자신과 테스트 파일은 검사하지 않는다.
    # 테스트는 "차단돼야 하는 패턴"을 픽스처로 포함해야 한다.
    if '.claude/hooks' in norm or '/tests/' in norm or norm.startswith('tests/'):
        sys.exit(0)

    if tool == 'Write':
        check_python_source(ti.get('content', ''), base)
    elif tool == 'Edit':
        check_python_source(ti.get('new_string', ''), base)

    sys.exit(0)


if __name__ == '__main__':
    main()
