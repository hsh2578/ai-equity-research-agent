# -*- coding: utf-8 -*-
import sys, io, os, re, json, urllib.parse, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
OUT='data/씨에스윈드/reports'; os.makedirs(OUT,exist_ok=True)
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
def parse_list(html):
    rows=[]
    for m in re.finditer(r'<tr[^>]*>(.*?)</tr>', html, re.S):
        blk=m.group(1)
        idx=re.search(r'downpdf\?report_idx=(\d+)', blk)
        if not idx: continue
        tds=re.findall(r'<td[^>]*>(.*?)</td>', blk, re.S)
        c=[re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',t)).strip() for t in tds]
        rows.append({'idx':idx.group(1),'cells':[x for x in c if x]})
    return rows
qs=[('CO_wind2','CO','윈드','2025-01-01'),
    ('IN_pw','IN','풍력','2024-06-01'),
    ('IN_solar','IN','태양광','2025-06-01'),
    ('IN_util','IN','유틸리티','2025-10-01'),
    ('IN_energy','IN','에너지','2025-11-01'),
    ('IN_elec','IN','전력','2025-11-01')]
man={}
for tag,rt,kw,sd in qs:
    url=f'http://consensus.hankyung.com/analysis/list?sdate={sd}&edate=2026-08-14&report_type={rt}&search_text={urllib.parse.quote(kw)}'
    subprocess.run(['curl','-sL','-A',UA,url,'-o',f'{OUT}/_l_{tag}.html'],check=False)
    rows=parse_list(open(f'{OUT}/_l_{tag}.html',encoding='utf-8',errors='ignore').read())
    man[tag]=rows
    print(f'=== {tag} ({kw}) : {len(rows)}')
    for r in rows[:30]:
        t=' | '.join(r['cells'])
        t=re.sub(r'(.{25,}?)\1+', r'\1', t)
        print('  ',r['idx'],t[:130])
json.dump(man,open(f'{OUT}/_manifest2.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
