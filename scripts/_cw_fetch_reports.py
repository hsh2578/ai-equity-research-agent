# -*- coding: utf-8 -*-
import sys, io, os, re, json, urllib.parse, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

OUT = 'data/씨에스윈드/reports'
os.makedirs(OUT, exist_ok=True)
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'

def fetch(url, dest):
    subprocess.run(['curl','-sL','-A',UA,url,'-o',dest], check=False)
    return dest

def parse_list(html):
    rows = []
    # each row: date, title, broker, writer, downpdf link
    for m in re.finditer(r'<tr[^>]*>(.*?)</tr>', html, re.S):
        blk = m.group(1)
        idx = re.search(r'downpdf\?report_idx=(\d+)', blk)
        if not idx: continue
        tds = re.findall(r'<td[^>]*>(.*?)</td>', blk, re.S)
        clean = [re.sub(r'<[^>]+>', ' ', t) for t in tds]
        clean = [re.sub(r'\s+', ' ', c).strip() for c in clean]
        rows.append({'idx': idx.group(1), 'cells': [c for c in clean if c]})
    return rows

queries = [
    ('CO_cw',  'report_type=CO&search_text=' + urllib.parse.quote('씨에스윈드'), '2025-08-01'),
    ('IN_wind','report_type=IN&search_text=' + urllib.parse.quote('풍력'), '2025-06-01'),
    ('IN_re',  'report_type=IN&search_text=' + urllib.parse.quote('재생에너지'), '2025-06-01'),
    ('IN_ene', 'report_type=IN&search_text=' + urllib.parse.quote('신재생'), '2025-06-01'),
]
manifest = {}
for tag, q, sdate in queries:
    url = f'http://consensus.hankyung.com/analysis/list?sdate={sdate}&edate=2026-08-14&{q}'
    p = fetch(url, f'{OUT}/_list_{tag}.html')
    html = open(p, encoding='utf-8', errors='ignore').read()
    rows = parse_list(html)
    manifest[tag] = rows
    print(f'=== {tag} : {len(rows)} rows')
    for r in rows[:25]:
        print('  ', r['idx'], ' | '.join(r['cells'])[:150])
json.dump(manifest, open(f'{OUT}/_manifest.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
