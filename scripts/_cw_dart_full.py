# -*- coding: utf-8 -*-
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'scripts')
from dart_api import get_all_report_rcept_nos, download_report_document, html_to_text

CORP='00670340'; D='data/씨에스윈드'
os.makedirs(D, exist_ok=True)
rl = get_all_report_rcept_nos(CORP)
print('reports found:', len(rl))
for r in rl[:12]:
    print('  ', r)
json.dump(rl, open(f'{D}/_rcept_list.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
