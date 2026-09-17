"""analysis json -> 블라인드 판정용 평문 (발간사·로고·리포트명 없이 section_order 순서, 제목만).
usage: ta_judge_export.py <analysis.json> <out.txt>"""
import json, re, sys
d = json.load(open(sys.argv[1], encoding='utf-8'))
m, s = d['meta'], d['sections']
out = []
for k in m['section_order']:
    t = m.get('section_titles', {}).get(k, k)
    body = re.sub(r'\[\[/?MARGIN\]\]', '', s.get(k, ''))
    out.append(f'==== {t} ====\n\n{body.strip()}\n')
open(sys.argv[2], 'w', encoding='utf-8').write('\n'.join(out))
print(sys.argv[2], sum(len(x) for x in out))
