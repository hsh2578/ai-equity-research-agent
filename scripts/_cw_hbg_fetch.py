# -*- coding: utf-8 -*-
"""2026 반기보고서(rcept 20260814001500) 본문을 DART 뷰어 경로로 수집.
document.xml API 가 당일 공시분을 아직 서비스하지 않아 viewer.do 로 우회."""
import sys, io, os, re, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'scripts')
from dart_api import html_to_text

RCP = '20260814001500'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
D = 'data/씨에스윈드'
h = open(f'{D}/_hbg_main.html', encoding='utf-8', errors='ignore').read()
nodes = re.findall(
    r"node\d+\['text'\]\s*=\s*\"(.*?)\";.*?node\d+\['dcmNo'\]\s*=\s*\"(\d+)\";"
    r".*?node\d+\['eleId'\]\s*=\s*\"(\d*)\";.*?node\d+\['offset'\]\s*=\s*\"(\d*)\";"
    r".*?node\d+\['length'\]\s*=\s*\"(\d*)\";.*?node\d+\['dtd'\]\s*=\s*\"(.*?)\";", h, re.S)

WANT = ['II. 사업의 내용', '3. 연결재무제표 주석', 'I. 회사의 개요']
out = []
seen = set()
for text, dcm, ele, off, ln, dtd in nodes:
    if not any(text.strip().startswith(w) for w in WANT):
        continue
    key = (dcm, ele)
    if key in seen:
        continue
    seen.add(key)
    url = (f'https://dart.fss.or.kr/report/viewer.do?rcpNo={RCP}&dcmNo={dcm}'
           f'&eleId={ele}&offset={off}&length={ln}&dtd={dtd}')
    tmp = f'{D}/_hbg_part_{ele}.html'
    subprocess.run(['curl', '-sL', '-A', UA, url, '-o', tmp], check=False)
    raw = open(tmp, encoding='utf-8', errors='ignore').read()
    txt = html_to_text(raw)
    print(f'  [{text.strip()[:30]}] eleId={ele} html={len(raw):,} text={len(txt):,}')
    out.append(f'\n\n########## {text.strip()} ##########\n{txt}')

open(f'{D}/_dart_FULL_반기2026.txt', 'w', encoding='utf-8').write(''.join(out))
print(f'[OK] _dart_FULL_반기2026.txt  {sum(len(o) for o in out):,}자')
