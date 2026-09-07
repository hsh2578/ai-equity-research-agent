# -*- coding: utf-8 -*-
"""OCI홀딩스 DART 전수 정독용 수집: 정기보고서 목록 + 전문(FULL) 텍스트 저장"""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dart_api import (get_corp_code, get_all_report_rcept_nos,
                      download_report_document, html_to_text)

STOCK = 'OCI홀딩스'
OUT = f'data/{STOCK}'
os.makedirs(OUT, exist_ok=True)

corp, _code = get_corp_code('OCI홀딩스')
print('corp_code =', corp)

rc = get_all_report_rcept_nos(corp)
print(f'\n[정기보고서] {len(rc)}건')
json.dump(rc, open(f'{OUT}/_dart_rcept_nos.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
for r in rc:
    print(' ', r.get('rcept_dt'), r.get('report_nm'), r.get('rcept_no'))

for i, r in enumerate(rc[:3]):
    rn = r.get('rcept_no')
    tag = f"{r.get('rcept_dt','')}_{r.get('type','rep')}"
    try:
        files = download_report_document(rn)
        parts = []
        for fname in sorted(files):
            parts.append(f'\n\n===== [FILE] {fname} =====\n')
            parts.append(html_to_text(files[fname]))
        txt = ''.join(parts)
        path = f'{OUT}/_dart_FULL_{i}_{tag}.txt'
        open(path, 'w', encoding='utf-8').write(txt)
        print(f'  [saved] {path}  {len(txt):,}자')
    except Exception as e:
        print(f'  [ERR {rn}]', repr(e))
