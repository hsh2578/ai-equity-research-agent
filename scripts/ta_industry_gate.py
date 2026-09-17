# -*- coding: utf-8 -*-
"""IR협의회 구성 게이트 G1~G6 (docs/research-ta/kirs-construction.md 7절).

G1 산업현황 분량 >= 본문 20% (IR협의회 24%)          G4 요약 한 줄 3개: (1)실적 수치 (2)회사 밖 실명 (3)시점
G2 산업현황 회사 밖 문단 >= 90% (IR협의회 96%)        G5 밸류는 밴드+Peer 본문, s01·s02 에 SOTP/시나리오/DCF 없음
G3 산업현황 출처 종류 >= 3 (협회·정부·산업리서치·고객사)  G6 산업현황 뉴스 인용 <= 2 (IR협의회 뉴스 재료 2%)

usage: python scripts/ta_industry_gate.py {종목명} [--analysis path]   (0 FAIL 필수)
"""
import io
import json
import re
import sys

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SRC = re.compile(r'협회|통계청|관세청|USITC|SEMI|SNE|TrendForce|트렌드포스|IDC|Omdia|WSTS|10-K|10-Q|컨퍼런스콜|IR 자료|기업설명회|산업부|농림|식약처')
NEWS = re.compile(r'보도|기사')
MARGIN = re.compile(r'^> \*\*한 줄:\*\*\s*(.+)$', re.M)
NUM = re.compile(r'\d[\d,.]*\s*(억원|%|배|원)')
TIME = re.compile(r'20\d\d|[1-4]Q|분기|상반기|하반기|연내|내년')
NAME = re.compile(r'[A-Z][A-Za-z]{2,}|전자|하이닉스|리서치|테크|케미칼|머티리얼|화학|반도체|삼성|SK|LG|현대|TSMC|ASML')
VAL = re.compile(r'SOTP|시나리오|DCF|Bull|Bear')


def _body(a):
    s = a['sections']
    return {k: s.get(k, '') for k in a['meta']['section_order'] if k in s}


def outside_ratio(text, name):
    """종목명 또는 '동사' 가 나오는 문단은 회사 안. 나머지 비율."""
    paras = [p for p in re.split(r'\n\s*\n', text) if p.strip()]
    if not paras:
        return 0.0
    inside = sum(1 for p in paras if name in p or '동사' in p)
    return round(1 - inside / len(paras), 2)


def check(a):
    b = _body(a)
    name = a['meta']['stock_name']
    s04 = b.get('s04_industry_competition', '')
    s01 = b.get('s01_opinion_thesis', '')
    s07 = b.get('s07_valuation', '')
    s02 = b.get('s02_thesis_catalysts', '')
    tot = sum(len(v) for v in b.values()) or 1
    out = []
    share = len(s04) / tot
    out.append({'id': 'G1', 'status': 'PASS' if share >= 0.20 else 'FAIL', 'value': f'{share:.0%}', 'note': '산업현황 분량 >= 20% (IR협의회 24%)'})
    r = outside_ratio(s04, name)
    out.append({'id': 'G2', 'status': 'PASS' if r >= 0.9 else 'FAIL', 'value': f'{r:.0%}', 'note': '산업현황 회사 밖 문단 >= 90% (IR협의회 96%)'})
    kinds = set(m.group(0).lower() for m in SRC.finditer(s04))
    out.append({'id': 'G3', 'status': 'PASS' if len(kinds) >= 3 else 'FAIL', 'value': ','.join(sorted(kinds)) or '-', 'note': '협회·정부·산업리서치·고객사 공개자료 3종+'})
    m = MARGIN.findall(s01)
    ok4 = len(m) >= 3 and bool(NUM.search(m[0])) and bool(NAME.search(m[1])) and bool(TIME.search(m[2]))
    out.append({'id': 'G4', 'status': 'PASS' if ok4 else 'FAIL', 'value': f'{len(m)}개', 'note': '요약 한 줄 3개: (1)실적 수치 (2)회사 밖 실명 (3)시점'})
    ok5 = bool(re.search(r'밴드|Peer|비교기업', s07)) and not VAL.search(s01 + s02)
    out.append({'id': 'G5', 'status': 'PASS' if ok5 else 'FAIL', 'value': 'ok' if ok5 else 'SOTP/시나리오가 s01·s02 에 있음', 'note': '밸류는 밴드+Peer 본문, 시나리오는 판단 블록'})
    n6 = len(NEWS.findall(s04))
    out.append({'id': 'G6', 'status': 'PASS' if n6 <= 2 else 'FAIL', 'value': str(n6), 'note': '산업현황의 뉴스 인용 <= 2 (IR협의회 뉴스 2%)'})
    return out


def main(argv=None):
    a = argv or sys.argv[1:]
    stock = a[0]
    p = a[a.index('--analysis') + 1] if '--analysis' in a else f'scripts/analysis_{stock}_ta.json'
    with open(p, encoding='utf-8') as f:
        res = check(json.load(f))
    for r in res:
        print(f"  [{'v' if r['status'] == 'PASS' else 'x'} {r['id']}] {r['status']:4s} {r['value']:22s} {r['note']}")
    fails = sum(1 for r in res if r['status'] == 'FAIL')
    print(f'[industry_gate] FAIL {fails}건')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
