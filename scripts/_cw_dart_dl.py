# -*- coding: utf-8 -*-
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'scripts')
from dart_api import download_report_document, html_to_text
D='data/씨에스윈드'
targets = [('사업보고서2025','20260318001110'), ('반기보고서2026H1','20260814001500'), ('분기보고서1Q26','20260515001165')]
for name, rno in targets:
    files = download_report_document(rno)
    if not files:
        print(f'[FAIL] {name}'); continue
    total=[]
    for fn, content in files.items():
        try:
            txt = html_to_text(content) if isinstance(content,str) else html_to_text(content.decode('utf-8','ignore'))
        except Exception as e:
            txt = f'[ERR {e}]'
        total.append(f'\n\n========== FILE: {fn} ==========\n{txt}')
    out = ''.join(total)
    p = f'{D}/_dart_FULL_{name}.txt'
    open(p,'w',encoding='utf-8').write(out)
    print(f'[OK] {name}: files={len(files)} chars={len(out)} -> {p}')
