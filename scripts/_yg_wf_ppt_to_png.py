"""
PowerPoint COM으로 pptx -> 슬라이드별 PNG 추출 (Windows + PowerPoint 필요)
시각 검수용
"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import win32com.client
from pathlib import Path

SRC = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\18-1_와이지엔터테인먼트_기업분석리포트.pptx')
OUT = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\_slide_pngs')
OUT.mkdir(exist_ok=True)

ppt = win32com.client.Dispatch('PowerPoint.Application')
ppt.Visible = 1  # 0이면 안 보임. 일부 버전은 1 필수
try:
    pres = ppt.Presentations.Open(str(SRC), WithWindow=False)
except Exception:
    pres = ppt.Presentations.Open(str(SRC))

print(f'Slides: {pres.Slides.Count}')
for i in range(1, pres.Slides.Count + 1):
    slide = pres.Slides(i)
    out_path = OUT / f'slide_{i:02d}.png'
    # Export(FileName, FilterName, ScaleWidth, ScaleHeight)
    slide.Export(str(out_path), 'PNG', 992, 1403)  # A4 비율 약 0.707
    print(f'  Saved {out_path.name}')

pres.Close()
ppt.Quit()
print('Done.')
