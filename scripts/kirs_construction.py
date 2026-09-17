"""IR협의회 리포트 문단 태그(data/_ref/kirs/_analysis/tags_*.json) 집계 -> 구성 템플릿.
usage: python scripts/kirs_construction.py  (출력: _analysis/construction.json + 콘솔 표)"""
import glob, json, collections, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
files = sorted(glob.glob('data/_ref/kirs/_analysis/tags_*.json'))
src_all, func_all, scope_all = collections.Counter(), collections.Counter(), collections.Counter()
by_sec = collections.defaultdict(lambda: {'chars': 0, 'src': collections.Counter(), 'scope': collections.Counter(), 'func': collections.Counter(), 'n': 0})
ip_nature, val_method, cues, not_inc = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
order = collections.Counter(); rows = []
def norm(t):
    t = t.replace(' ', '').lower()
    for k, v in [('valuation', '밸류에이션'), ('forecast', '실적전망'), ('요약', '요약'), ('개요', '기업개요'), ('연혁', '기업개요'), ('주주', '주주구성'), ('제품', '제품·기술'), ('기술', '제품·기술'), ('사업', '제품·기술'),
                 ('산업', '산업현황'), ('시장', '산업현황'), ('투자포인트', '투자포인트'), ('실적', '실적전망'), ('전망', '실적전망'), ('밸류', '밸류에이션'), ('가치', '밸류에이션'),
                 ('리스크', '리스크'), ('위험', '리스크'), ('재무', '재무분석'), ('주가', '주가')]:
        if k in t: return v
    return '기타'
for f in files:
    d = json.load(open(f, encoding='utf-8'))
    tot = 0; outside = 0; seq = []
    for s in d.get('sections', []):
        key = norm(s.get('title', '')); seq.append(key)
        for p in s.get('paragraphs', []):
            c = p.get('chars', 0) or 0; tot += c
            src_all[p.get('source')] += c; func_all[p.get('function')] += c; scope_all[p.get('scope')] += c
            b = by_sec[key]; b['chars'] += c; b['n'] += 1; b['src'][p.get('source')] += c; b['scope'][p.get('scope')] += c; b['func'][p.get('function')] += c
            if p.get('scope') == '회사밖': outside += c
    for i, k in enumerate(seq): order[(k, i)] += 1
    for ip in d.get('investment_points', []): ip_nature[ip.get('nature')] += 1
    v = d.get('valuation', {}); val_method[v.get('method', '')[:30]] += 1
    for c in d.get('field_visit_cues', []): cues[str(c)[:20]] += 1
    for x in d.get('not_included', []): not_inc[str(x)[:20]] += 1
    rows.append((d.get('name'), tot, round(outside / max(1, tot), 2), len(d.get('investment_points', [])), len(d.get('risks', [])), v.get('method', '')[:40], d.get('rating'), d.get('target')))
T = sum(src_all.values()) or 1
pct = lambda c: {k: round(v / max(1, sum(c.values())), 2) for k, v in c.most_common()}
out = {'n_reports': len(files), 'source_share': pct(src_all), 'function_share': pct(func_all), 'scope_share': pct(scope_all),
       'by_section': {k: {'chars_share': round(b['chars'] / T, 2), 'src': pct(b['src']), 'scope': pct(b['scope']), 'func': pct(b['func'])} for k, b in by_sec.items()},
       'section_order_votes': [(k, i, n) for (k, i), n in order.most_common(40)], 'investment_point_nature': dict(ip_nature),
       'valuation_methods': dict(val_method), 'field_visit_cues': cues.most_common(15), 'not_included': not_inc.most_common(15), 'reports': rows}
json.dump(out, open('data/_ref/kirs/_analysis/construction.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'reports {len(files)}'); print('source', out['source_share']); print('function', out['function_share']); print('scope', out['scope_share'])
for k, b in sorted(out['by_section'].items(), key=lambda x: -x[1]['chars_share']): print(f"  {k:8s} {b['chars_share']:.0%}  scope{b['scope']}  src{dict(list(b['src'].items())[:3])}")
print('IP nature', dict(ip_nature)); print('valuation', dict(val_method)); print('not_included', not_inc.most_common(8))
for r in rows: print('  ', r)
