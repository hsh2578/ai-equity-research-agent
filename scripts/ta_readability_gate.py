# -*- coding: utf-8 -*-
"""가독성 게이트 R1~R4 (/research-ta, 2026-09-18 사용자 지적 "내용을 이해하기 어렵다").

기존 검증기는 전부 "숫자를 더 넣어라" 방향이라 반대 방향 검사가 없으면 글이 산식으로 채워진다.
R1 요약 첫 블록의 액션 플랜 표 -- 선택(사용자 결정 2026-09-18: 초판 형식이 낫다, 없으면 SKIP)      R3 용어 박스 -- 선택(없으면 SKIP, 두면 8개+ 아니면 WARN)
R2 본문 문장당 숫자 <= 1.5개 (표·마진노트·인용 제외)                 R4 같은 금액 표기가 5회+ 반복되면 WARN (판정 ⑥ 근거)

usage: python scripts/ta_readability_gate.py {종목명} [--analysis path]   (전 항목 WARN/SKIP -- 강제 없음, 밀도·반복 참고용)
"""
import io
import json
import re
import sys
from collections import Counter

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

NUM = re.compile(r'\d[\d,]*(?:\.\d+)?')
MONEY = re.compile(r'\d{1,3}(?:,\d{3})+억원|\d+\.\d억원')
MAX_NUM_PER_SENT = 2.5   # 기준선 미확정 -- IR협의회 PDF 텍스트는 표·차트 숫자가 산문에 섞여 측정 불가(실측 5~9). CJ 초판 3.26. WARN 만 낸다
MIN_GLOSS = 8
REPEAT_WARN = 5
MIN_SENT = 6


def prose_sentences(text):
    """표·마진노트·인용·소제목을 뺀 본문 문장."""
    out = []
    for para in re.split(r'\n\s*\n', text):
        p = para.strip()
        if not p or p.startswith('|') or p.startswith('>') or p.startswith('#'):
            continue
        p = re.sub(r'\n(?!\n)', ' ', p)
        out += [s for s in re.split(r'(?<=다\.)\s+', p) if len(s) >= MIN_SENT]
    return out


def action_table(s01):
    for para in re.split(r'\n\s*\n', s01):
        if para.strip().startswith('|') and '언제' in para and '확인' in para and ('안 되면' in para or '아니면' in para):
            return True
    return False


def glossary_count(s01):
    m = re.search(r'####\s*용어[^\n]*\n(.*)', s01, re.S)
    if not m:
        return 0
    return len(re.findall(r'^- \*\*[^*]+\*\*\s*:', m.group(1), re.M))


def check(a):
    s = a['sections']
    order = a['meta'].get('section_order') or list(s)
    s01 = s.get('s01_opinion_thesis', '')
    body = [s.get(k, '') for k in order if k in s]
    sents = [x for t in body for x in prose_sentences(t)]
    nps = sum(len(NUM.findall(x)) for x in sents) / len(sents) if sents else 0.0
    rep = Counter(m for t in body for m in MONEY.findall(t))
    heavy = [(k, v) for k, v in rep.most_common() if v >= REPEAT_WARN]
    g = glossary_count(s01)
    out = [
        {'id': 'R1', 'status': 'PASS' if action_table(s01) else 'SKIP', 'value': '있음' if action_table(s01) else '없음',
         'note': '요약 첫 블록에 액션 플랜 표 (언제 / 무엇을 확인 / 되면 / 안 되면)'},
        {'id': 'R2', 'status': 'PASS' if nps <= MAX_NUM_PER_SENT else 'WARN', 'value': f'{nps:.2f}개/문장 ({len(sents)}문장)',
         'note': f'본문 문장당 숫자 <= {MAX_NUM_PER_SENT} (표·마진노트·인용 제외, 기준선 미확정이라 WARN)'},
        {'id': 'R3', 'status': 'PASS' if g >= MIN_GLOSS else ('SKIP' if g == 0 else 'WARN'), 'value': f'{g}개', 'note': f'용어 박스는 선택(사용자 결정 2026-09-18: 없는 쪽이 낫다). 두면 {MIN_GLOSS}개+'},
        {'id': 'R4', 'status': 'WARN' if heavy else 'PASS', 'value': ', '.join(f'{k} x{v}' for k, v in heavy[:4]) or '-',
         'note': f'같은 금액 표기 {REPEAT_WARN}회+ 반복 (요약·투자포인트·리스크·재무가 같은 사실을 되풀이하는 신호)'},
    ]
    return out


def main(argv=None):
    a = argv or sys.argv[1:]
    stock = a[0]
    p = a[a.index('--analysis') + 1] if '--analysis' in a else f'scripts/analysis_{stock}_ta.json'
    with open(p, encoding='utf-8') as f:
        res = check(json.load(f))
    for r in res:
        icon = 'v' if r['status'] == 'PASS' else ('!' if r['status'] == 'WARN' else 'x')
        print(f"  [{icon} {r['id']}] {r['status']:4s} {r['value']:28s} {r['note']}")
    fails = sum(1 for r in res if r['status'] == 'FAIL')
    print(f'[readability_gate] FAIL {fails}건')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
