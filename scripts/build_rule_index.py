"""build_rule_index.py -- 스킬 파일의 규칙 인덱스를 자동 생성한다.

배경(2026-09): research.md 가 24만자 / 규칙 헤딩 102개까지 불었다.
US 분리(_research_us.md)는 원인이 아니었다 -- research.md 에 남은 US 내용은
4.6%(11,230자)뿐이다. 부피의 정체는 17개 버전 블록의 누적 규칙과
코드 블록 28.3%(67,705자)다.

안전하게 삭제 가능한 순수 이력·예시는 3.7%(9,161자)뿐이라 **삭제로는 못 줄인다.**
그래서 줄이는 대신 **찾을 수 있게** 만든다. 규칙 헤딩을 훑어 버전 역순 인덱스를
파일 상단에 심는다. 에이전트가 24만자를 다 읽지 않고 필요한 규칙으로 점프한다.

멱등: 기존 인덱스 블록을 찾아 통째로 교체한다.
사용: python scripts/build_rule_index.py [--check]
"""
import io
import pathlib
import re
import sys

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BEGIN = '<!-- RULE-INDEX:BEGIN (build_rule_index.py 가 생성 -- 직접 고치지 말 것) -->'
END = '<!-- RULE-INDEX:END -->'
TARGETS = ['.claude/commands/research.md', '.claude/commands/wf-report.md']
_RULE = re.compile(r'^#{2,4}\s*[\U0001F534\U0001F525]')     # 🔴 🔥


def _vkey(v):
    if v == '-':
        return (-1,)
    return tuple(int(x) for x in v.split('.'))


def collect(lines):
    out = []
    for i, l in enumerate(lines, 1):
        if not _RULE.match(l):
            continue
        t = re.sub(r'^#+\s*[\U0001F534\U0001F525]\s*', '', l).strip()
        t = re.sub(r'\s*\(20\d\d[-.]\d\d[^)]*\)', '', t)      # 날짜 괄호 제거
        m = re.search(r'v(\d+\.\d+)', t)
        out.append((i, m.group(1) if m else '-', t))
    return out


def render(rules, total_chars):
    by = {}
    for i, v, t in rules:
        by.setdefault(v, []).append((i, t))
    vs = sorted(by, key=_vkey, reverse=True)
    L = [BEGIN, '',
         '## 📇 규칙 인덱스 (자동 생성)',
         '',
         f'이 파일은 {total_chars:,}자 / 규칙 {len(rules)}개다. 전부 읽지 말고 '
         f'필요한 규칙으로 바로 간다.',
         '**버전이 높은 규칙이 낮은 규칙을 이긴다** (바로 위 우선순위표 참조).',
         '']
    for v in vs:
        label = f'v{v}' if v != '-' else '버전 표기 없음'
        L.append(f'**{label}**')
        for i, t in by[v]:
            short = re.sub(r'^v\d+\.\d+\s*(규칙\s*\d+\s*)?--?\s*', '', t)
            L.append(f'- (줄 {i}) {short[:78]}')
        L.append('')
    L += [END, '']
    return '\n'.join(L)


def main(check=False):
    rc = 0
    for f in TARGETS:
        P = pathlib.Path(f)
        if not P.exists():
            print(f'[SKIP] {f} 없음')
            continue
        s = P.read_text(encoding='utf-8')
        body = s
        if BEGIN in s and END in s:
            body = s[:s.index(BEGIN)] + s[s.index(END) + len(END):].lstrip('\n')
        lines = body.splitlines()
        rules = collect(lines)
        idx = render(rules, len(body))
        if check:
            print(f'  {P.name}: 규칙 {len(rules)}개 / {len(body):,}자')
            continue
        # 우선순위표 바로 뒤(없으면 첫 H1 뒤)에 삽입
        anchor = body.find('### 새 리포트를 쓸 때 실제로 확인하는 게이트')
        if anchor >= 0:
            nxt = body.find('\n## ', anchor)
            pos = nxt + 1 if nxt > 0 else len(body)
        else:
            m = re.search(r'^# .*$', body, re.M)
            pos = m.end() + 1 if m else 0
        # 인덱스가 삽입되면 그 아래 내용이 밀린다 -> 줄 번호를 다시 계산한다.
        # (1차 렌더로 인덱스 줄 수를 알아낸 뒤 삽입 지점 아래 규칙만 shift)
        head_lines = body[:pos].count('\n')
        shift = idx.count('\n') + 2
        shifted = [(i + shift if i > head_lines else i, v, t) for i, v, t in rules]
        idx = render(shifted, len(body))
        out = body[:pos] + '\n' + idx + '\n' + body[pos:]
        if not out.endswith('\n'):
            out += '\n'
        P.write_text(out, encoding='utf-8')
        print(f'[OK] {P.name}: 규칙 {len(rules)}개 인덱스 삽입 '
              f'({len(body):,} -> {len(out):,}자)')
    return rc


if __name__ == '__main__':
    raise SystemExit(main(check='--check' in sys.argv))
