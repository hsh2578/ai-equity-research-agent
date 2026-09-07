# -*- coding: utf-8 -*-
"""YG DART 전수 정독용 수집: 정기보고서 목록 + 전문(FULL) 텍스트 저장"""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dart_api import (get_corp_code, get_disclosure_list, get_all_report_rcept_nos,
                      download_report_document, html_to_text)

STOCK = '와이지엔터'
OUT = f'data/{STOCK}'
os.makedirs(OUT, exist_ok=True)

corp, _code = get_corp_code('와이지엔터테인먼트')
print('corp_code =', corp)

# 1) 최근 공시 목록
try:
    dl = get_disclosure_list(corp, 100)
    items = dl.get('list', []) if isinstance(dl, dict) else dl
    print(f'[disclosures] {len(items)}건')
    keep = [{'date': it.get('rcept_dt'), 'nm': it.get('report_nm'),
             'rcept_no': it.get('rcept_no')} for it in items]
    json.dump(keep, open(f'{OUT}/_dart_disclosures.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    for k in keep[:50]:
        print(' ', k['date'], str(k['nm'])[:55], k['rcept_no'])
except Exception as e:
    print('[disclosure list ERR]', repr(e))

# 2) 정기보고서 rcept_no + 전문 저장
try:
    rc = get_all_report_rcept_nos(corp)
    print(f'\n[정기보고서] {len(rc)}건')
    json.dump(rc, open(f'{OUT}/_dart_rcept_nos.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    for r in rc:
        print(' ', r.get('rcept_dt'), r.get('report_nm'), r.get('rcept_no'))

    # 최근 4개 전문 저장 (반기/분기/사업)
    for i, r in enumerate(rc[:4]):
        rn = r.get('rcept_no')
        tag = f"{r.get('rcept_dt','')}_{r.get('type','rep')}"
        try:
            files = download_report_document(rn)  # {filename: html}
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
except Exception as e:
    print('[rcept ERR]', repr(e))
