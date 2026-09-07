"""
guard hook 테스트 (v5.5)

hook 은 조용히 실패하면 아무도 모른다 (막아야 할 것을 통과시켜도 로그가 안 남는다).
그래서 차단/통과 양쪽을 전부 고정한다.

주의: 이 파일은 "차단돼야 하는 패턴"을 픽스처로 포함하므로 guard 가 tests/ 를
검사 대상에서 제외한다. 제외 규칙이 깨지면 이 파일 자체를 저장할 수 없게 된다.

v5.5 리뷰 반영: 초판 KIS_LOWER 정규식이 **모든** `.get('eps')` 를 잡아
financial_summary.py / fdr_band.py / analysis_to_md.py / build_snapshot.py /
fdr_band_us.py 의 정상 코드를 차단했다. 그 5곳을 회귀 케이스로 고정한다.
(KIS 래퍼만 한글 키를 쓴다. financial_summary.json / yfinance / DART 행은
 소문자 영문 키가 정상이다.)

실행: python tests/run_all.py  또는  python tests/test_guard_hook.py
"""
import sys
import os
import io
import json
import subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, '.claude', 'hooks', 'guard.py')

BLOCK, PASS = 2, 0
Q = chr(34)
LOWER_PER = Q + 'per' + Q          # 픽스처를 리터럴로 두지 않기 위해 조립
LOWER_EPS = Q + 'eps' + Q


def w(path, content):
    return {"tool_name": "Write", "tool_input": {"file_path": path, "content": content}}


def e(path, new):
    return {"tool_name": "Edit", "tool_input": {"file_path": path, "new_string": new}}


CASES = [
    # ---------- KIS 래퍼 결과에 소문자 키를 쓰면 차단 ----------
    ("KIS 래퍼 결과 변수에 소문자 키",
     w('scripts/_t.py', f'from kis_api import get_current_price\n'
                        f'px = get_current_price(code)\n'
                        f'v = px.get({LOWER_PER}, 0)\n'), BLOCK),
    ("KIS 래퍼 호출에 바로 체이닝",
     w('scripts/_t.py', f'v = get_current_price(code).get({LOWER_PER})\n'), BLOCK),
    ("KIS 원시 필드명 stck_prpr",
     w('scripts/_t.py', 'px = get_current_price(c)\n'
                        'v = px.get("stck_' + 'prpr")\n'), BLOCK),
    ("Edit 로 들어와도 차단",
     e('scripts/_t.py', 'price = get_current_price(c)\n'
                        'a = price.get("p' + 'br")\n'), BLOCK),
    ("KIS 래퍼 + 한글 키는 통과",
     w('scripts/_t.py', 'px = get_current_price(code)\n'
                        'v = px.get("PER", 0)\n'), PASS),

    # ---------- 리뷰에서 나온 실제 오탐 5곳 (전부 통과해야 한다) ----------
    ("오탐회귀: financial_summary.py DART 행",
     w('scripts/financial_summary.py',
       f'row = statements[i]\nd["eps"] = to_float(row.get({LOWER_EPS}))\n'), PASS),
    ("오탐회귀: fdr_band.py financials 연도블록",
     w('scripts/fdr_band.py',
       f'yf = fin.get(str(y), {{}})\neps = yf.get({LOWER_EPS})\nbps = yf.get("bps")\n'), PASS),
    ("오탐회귀: analysis_to_md.py",
     w('scripts/analysis_to_md.py',
       f'p = data.get("price", {{}})\nper = p.get({LOWER_PER})\n'), PASS),
    ("오탐회귀: build_snapshot.py financial_summary['kis'] 영문키",
     w('scripts/build_snapshot.py',
       f'k = (self.fs or {{}}).get("kis") or {{}}\nv = k.get({LOWER_EPS})\n'), PASS),
    ("오탐회귀: fdr_band_us.py SEC financials",
     w('scripts/fdr_band_us.py',
       f'yd = fin.get(str(y))\neps = yd.get({LOWER_EPS})\n'), PASS),
    ("오탐회귀: yfinance info 는 소문자가 정상",
     w('scripts/_t.py', 'info = t.info or {}\nv = info.get("trailingPE")\n'
                        f'x = info.get({LOWER_EPS})\n'), PASS),

    # ---------- 루트 임시 덤프 ----------
    ("루트 임시덤프 차단", w('_tmp_r1.txt', 'x'), BLOCK),
    ("data 하위 임시덤프 통과", w('data/한국콜마/_tmp_r1.txt', 'x'), PASS),
    ("절대경로 data 하위 통과", w('C:/proj/data/AMD/_sec_10k.txt', 'x'), PASS),

    # ---------- 콘솔 출력 특수문자 ----------
    ("print 한 줄 em-dash 차단", w('scripts/_t.py', 'print("a \u2014 b")'), BLOCK),
    ("print 여러 줄 em-dash 차단 (리뷰 지적)",
     w('scripts/_t.py', 'print(\n    f"긴 설명 \u2014 이어지는 문장"\n)\n'), BLOCK),
    ("stderr 여러 줄 em-dash 차단",
     w('scripts/_t.py', 'print(\n    "요약 \u2014 끝",\n    file=sys.stderr,\n)\n'), BLOCK),
    ("print 하이픈 통과", w('scripts/_t.py', 'print("a -- b")'), PASS),
    ("주석의 em-dash 는 통과 (콘솔 출력 아님)",
     w('scripts/_t.py', '# 이 주석에는 \u2014 가 있어도 콘솔에 안 나간다\nx = 1\n'), PASS),
    ("문자열 상수의 em-dash 는 통과 (출력 아님)",
     w('scripts/_t.py', 'TITLE = "보고서 \u2014 요약"\n'), PASS),

    # ---------- 검사 제외 ----------
    ("md 파일은 검사 안 함", w('doc.md', f'px.get({LOWER_PER})'), PASS),
    ("guard 자기 자신은 통과", w('.claude/hooks/guard.py', f'px.get({LOWER_PER})'), PASS),
    ("tests/ 는 검사 제외 (픽스처 보호)", w('tests/test_x.py', f'px.get({LOWER_PER})'), PASS),
    ("깨진 입력은 통과 (작업을 막지 않는다)", None, PASS),
]

passed, failed = 0, []
for name, payload, expect in CASES:
    stdin = 'not-json' if payload is None else json.dumps(payload)
    r = subprocess.run([sys.executable, HOOK], input=stdin,
                       capture_output=True, text=True, encoding='utf-8')
    if r.returncode == expect:
        passed += 1
    else:
        failed.append(f"{name}: exit={r.returncode} (기대 {expect})\n      "
                      f"{(r.stderr or '').strip()[:180]}")

print(f"\n{'=' * 60}")
print(f"  guard hook 테스트: {passed}개 통과 / {len(failed)}개 실패")
print(f"{'=' * 60}")
for f in failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if failed else 0)
