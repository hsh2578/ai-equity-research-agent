"""
guard hook 테스트 (v5.5)

hook 은 조용히 실패하면 아무도 모른다 (막아야 할 것을 통과시켜도 로그가 안 남는다).
그래서 차단/통과 양쪽을 전부 고정한다.

주의: 이 파일은 "차단돼야 하는 패턴"을 픽스처로 포함하므로 guard 가 tests/ 를
검사 대상에서 제외한다. 제외 규칙이 깨지면 이 파일 자체를 저장할 수 없게 된다.

실행: python tests/test_guard_hook.py
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
LOWER = chr(34) + 'per' + chr(34)          # 픽스처를 리터럴로 두지 않기 위해 조립

CASES = [
    ("KIS 소문자 per 차단",
     {"tool_name": "Write", "tool_input": {"file_path": "scripts/_t.py",
                                           "content": f'x = px.get({LOWER}, 0)'}}, BLOCK),
    ("KIS 한글 PER 통과",
     {"tool_name": "Write", "tool_input": {"file_path": "scripts/_t.py",
                                           "content": 'x = px.get("PER", 0)'}}, PASS),
    ("KIS 원시필드 stck_prpr 차단",
     {"tool_name": "Write", "tool_input": {"file_path": "scripts/_t.py",
                                           "content": 'v = d.get("stck_' + 'prpr")'}}, BLOCK),
    ("KIS 소문자 pbr Edit 차단",
     {"tool_name": "Edit", "tool_input": {"file_path": "scripts/_t.py",
                                          "new_string": 'a = px.get("p' + 'br")'}}, BLOCK),
    ("루트 임시덤프 차단",
     {"tool_name": "Write", "tool_input": {"file_path": "_tmp_r1.txt", "content": "x"}}, BLOCK),
    ("data 하위 임시덤프 통과",
     {"tool_name": "Write", "tool_input": {"file_path": "data/한국콜마/_tmp_r1.txt",
                                           "content": "x"}}, PASS),
    ("절대경로 data 하위 통과",
     {"tool_name": "Write", "tool_input": {"file_path": "C:/proj/data/AMD/_sec_10k.txt",
                                           "content": "x"}}, PASS),
    ("print em-dash 차단",
     {"tool_name": "Write", "tool_input": {"file_path": "scripts/_t.py",
                                           "content": 'print("a \u2014 b")'}}, BLOCK),
    ("print 하이픈 통과",
     {"tool_name": "Write", "tool_input": {"file_path": "scripts/_t.py",
                                           "content": 'print("a -- b")'}}, PASS),
    ("md 파일은 검사 안 함",
     {"tool_name": "Write", "tool_input": {"file_path": "doc.md",
                                           "content": f'px.get({LOWER})'}}, PASS),
    ("guard 자기 자신은 통과",
     {"tool_name": "Write", "tool_input": {"file_path": ".claude/hooks/guard.py",
                                           "content": f'px.get({LOWER})'}}, PASS),
    ("tests/ 는 검사 제외 (픽스처 보호)",
     {"tool_name": "Write", "tool_input": {"file_path": "tests/test_x.py",
                                           "content": f'px.get({LOWER})'}}, PASS),
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
        failed.append(f"{name}: exit={r.returncode} (기대 {expect})\n      {r.stderr.strip()[:150]}")

print(f"\n{'=' * 60}")
print(f"  guard hook 테스트: {passed}개 통과 / {len(failed)}개 실패")
print(f"{'=' * 60}")
for f in failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if failed else 0)
