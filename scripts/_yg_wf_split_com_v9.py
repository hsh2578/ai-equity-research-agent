"""
위닝펀드 18-1 YG v9 — PowerPoint COM으로 슬라이드 분리:
1. COM으로 본문 슬라이드(3~14) 12장 Duplicate (이미지 포함 완전 복제)
2. python-pptx로 각 슬라이드 shape 제거 + 위치 조정
"""
import sys, io, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import win32com.client
from pathlib import Path

SRC = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\18-1_와이지엔터테인먼트_기업분석리포트.pptx')


def main():
    ppt = win32com.client.Dispatch('PowerPoint.Application')
    ppt.Visible = 1
    pres = ppt.Presentations.Open(str(SRC), WithWindow=False)
    n_before = pres.Slides.Count
    print(f'Before: {n_before} slides')

    # 본문 슬라이드: Slide 3~14 (1-indexed). 뒤에서부터 복제해야 인덱스 꼬임 없음.
    body_indices_1based = list(range(14, 2, -1))  # [14, 13, ..., 3]
    for idx in body_indices_1based:
        src = pres.Slides(idx)
        src.Duplicate()  # 복제 후 같은 위치 + 1에 새 슬라이드 자동 추가
        time.sleep(0.1)
        print(f'  Duplicated slide {idx}')

    pres.Save()
    n_after = pres.Slides.Count
    print(f'After: {n_after} slides')
    pres.Close()
    ppt.Quit()
    print('Done.')


if __name__ == '__main__':
    main()
