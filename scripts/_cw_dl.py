# -*- coding: utf-8 -*-
import sys, io, os, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
OUT='data/씨에스윈드/reports'
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
items = [
 ('CO_유진_2608','651568'), ('CO_유진_2605','649063'), ('CO_유진_2602','646971'),
 ('CO_메리츠_2502','639048'),
 ('IN_대신_전력인프라_2607','651293'), ('IN_유진_메가프로젝트_2607','650660'),
 ('IN_유진_AIDC_2607','650658'), ('IN_유진_유럽교훈_2604','648071'),
 ('IN_iM_종전에너지전환_2604','648022'), ('IN_유진_재생정책_2603','647766'),
 ('IN_유진_에너지자립_2603','647400'), ('IN_iM_에너지자립_2604','648431'),
 ('IN_한화_유틸리티전망_2512','645039'), ('IN_유진_에너지전환주가_2601','645755'),
]
import fitz
for name, idx in items:
    dest=f'{OUT}/{name}.pdf'
    if not os.path.exists(dest) or os.path.getsize(dest)<10000:
        subprocess.run(['curl','-sL','-A',UA,f'http://consensus.hankyung.com/analysis/downpdf?report_idx={idx}','-o',dest],check=False)
    sz=os.path.getsize(dest) if os.path.exists(dest) else 0
    pg='?'
    try:
        d=fitz.open(dest); pg=len(d); d.close()
    except Exception as e:
        pg=f'ERR {type(e).__name__}'
    print(f'{name:38s} {sz/1024:8.0f}KB  {pg}p')
