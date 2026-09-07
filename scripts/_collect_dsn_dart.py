# -*- coding: utf-8 -*-
"""덕산네오룩스 DART 전수 정독용 수집"""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dart_api import (get_corp_code, get_all_report_rcept_nos,
                      download_report_document, html_to_text)

STOCK = '덕산네오룩스'
OUT = f'data/{STOCK}'
os.makedirs(OUT, exist_ok=True)
corp, _ = get_corp_code('덕산네오룩스')
print('corp_code =', corp)
rc = get_all_report_rcept_nos(corp)
print(f'\n[정기보고서] {len(rc)}건')
json.dump(rc, open(f'{OUT}/_dart_rcept_nos.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for r in rc:
    print(' ', r.get('rcept_dt'), r.get('report_nm'), r.get('rcept_no'))
for i, r in enumerate(rc[:3]):
    rn = r.get('rcept_no'); tag = f"{r.get('rcept_dt','')}_{r.get('type','rep')}"
    try:
        files = download_report_document(rn)
        parts = []
        for fn in sorted(files):
            parts.append(f'\n\n===== [FILE] {fn} =====\n'); parts.append(html_to_text(files[fn]))
        txt = ''.join(parts)
        p = f'{OUT}/_dart_FULL_{i}_{tag}.txt'
        open(p, 'w', encoding='utf-8').write(txt)
        print(f'  [saved] {p}  {len(txt):,}자')
    except Exception as e:
        print(f'  [ERR {rn}]', repr(e))
