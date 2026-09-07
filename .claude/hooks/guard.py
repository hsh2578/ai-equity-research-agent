"""
반복 사고 물리 차단 hook (v5.5 신설)

CLAUDE.md 의 "절대 금지" 규칙들은 지금까지 **문서상 규칙**이었고, 그래서 반복 위반됐다.
문서는 읽히지 않을 수 있지만 hook 은 반드시 실행된다.

차단 대상 3가지 (전부 실제로 사고를 낸 것들):

1. **KIS 래퍼 영문 소문자 키** -- `px.get("per")`, `px.get("stck_prpr")`
   kis_api.py 래퍼는 한글 키로 반환한다. 소문자 영문 키는 항상 0/None 을 돌려준다.
   JYP v1 에서 Peer 시총·PER 이 전부 0 으로 저장된 사고의 직접 원인.

2. **프로젝트 루트에 임시 덤프 쓰기** -- `_tmp_*.txt` 를 `data/{종목}/` 밖에 쓰면
   다음 /research 실행 때 다른 종목 잔재가 Grep 에 섞인다.

3. **콘솔 출력에 em-dash / 이모지** -- Windows cp949 콘솔에서 UnicodeEncodeError.
   (PDF 본문의 별점은 예외이므로 print/f-string 안만 본다)

동작: PreToolUse(Write|Edit) 에서 exit 2 로 차단하고 사유를 stderr 로 알린다.
오탐이 의심되면 이 파일의 패턴을 고치거나 settings.local.json 에서 hook 을 끈다.
"""
import sys
import io
import os
import json
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 1. KIS 소문자 키 (래퍼는 한글 키 반환)
KIS_LOWER = re.compile(
    r'''\.get\(\s*['"](?:per|pbr|eps|bps|stck_prpr|hts_avls|stck_hgpr|stck_lwpr|'''
    r'''prdy_ctrt|acml_vol|acml_tr_pbmn)['"]''')

KIS_HINT = {
    'per': 'PER', 'pbr': 'PBR', 'eps': 'EPS', 'bps': 'BPS',
    'stck_prpr': '현재가', 'hts_avls': '시가총액',
    'stck_hgpr': '고가', 'stck_lwpr': '저가',
    'prdy_ctrt': '등락률', 'acml_vol': '거래량', 'acml_tr_pbmn': '거래대금',
}

# 2. 루트 임시 덤프
ROOT_DUMP = re.compile(r'''^_(?:tmp|sec|dart)_[^/\\]*\.(?:txt|json)$''')

# 3. 콘솔 출력 특수문자 (cp949 미지원)
BAD_CHARS = {'—': 'em-dash(—)', '–': 'en-dash(–)', '‘': '‘',
             '’': '’', '“': '“', '”': '”'}
PRINT_LINE = re.compile(r'^\s*(?:print\(|.*\bprint\(|\s*f?["\'])')


def block(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def check_python_source(text, where):
    problems = []

    m = KIS_LOWER.search(text)
    if m:
        key = re.search(r"['\"]([a-z_]+)['\"]", m.group(0)).group(1)
        ko = KIS_HINT.get(key, '한글 키')
        problems.append(
            f"KIS 래퍼 소문자 키 `{m.group(0)}` 발견.\n"
            f"  kis_api.py 의 get_current_price() 는 **한글 키**로 반환한다.\n"
            f"  `.get('{key}')` 는 항상 0/None 을 돌려준다 -> `.get('{ko}')` 로 고칠 것.\n"
            f"  (JYP v1 에서 Peer 시총/PER 이 전부 0 으로 저장된 사고의 원인)")

    # print / 콘솔 문자열 안의 em-dash 류
    for i, line in enumerate(text.splitlines(), 1):
        if 'print(' not in line and 'stderr' not in line:
            continue
        for ch, name in BAD_CHARS.items():
            if ch in line:
                problems.append(
                    f"{i}행 콘솔 출력에 {name} 사용. Windows cp949 에서 "
                    f"UnicodeEncodeError 가 난다. 하이픈 '-' 또는 '--' 로 바꿀 것.\n"
                    f"  > {line.strip()[:90]}")
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

    # 규칙 2: 루트 임시 덤프
    if tool == 'Write' and ROOT_DUMP.match(base):
        norm = path.replace('\\', '/')
        # 'data/' 가 경로 세그먼트로 들어 있으면 정상 (절대/상대 경로 모두 허용)
        if 'data/' not in norm:
            block(
                f"[guard] 프로젝트 루트에 임시 덤프 `{base}` 쓰기 차단.\n\n"
                f"  임시 덤프는 반드시 `data/{{종목명}}/` 하위에 쓴다.\n"
                f"  루트에 쌓이면 다음 /research 실행 때 다른 종목 잔재가 Grep 에 섞인다.\n"
                f"  예: data/한국콜마/{base}")

    # 규칙 1,3: 파이썬 소스
    if not path.endswith('.py'):
        sys.exit(0)
    norm_py = path.replace('\\', '/')
    # 이 hook 자신과 테스트 파일은 검사하지 않는다.
    # 테스트는 "차단돼야 하는 패턴"을 픽스처로 포함해야 하므로 검사하면 자기 자신을 막는다.
    if '.claude/hooks' in norm_py or '/tests/' in norm_py or norm_py.startswith('tests/'):
        sys.exit(0)

    if tool == 'Write':
        check_python_source(ti.get('content', ''), base)
    elif tool == 'Edit':
        check_python_source(ti.get('new_string', ''), base)

    sys.exit(0)


if __name__ == '__main__':
    main()
