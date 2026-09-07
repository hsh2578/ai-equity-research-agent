"""
위닝펀드 18-1 YG v8 — 박스 크기 + 도표 위치 재조정 (분리 후 후처리):
페이지 분리 후 박스가 텍스트 오버플로우로 도표 침범하는 문제 해결.

각 분리 슬라이드 (idx 2~25, 즉 Slide 3~26):
- 본문 박스 H 1.88" -> 4.0"
- 도표 위치 T 2.61" -> T 5.0"
- (도표 크기는 그대로)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pptx import Presentation
from pptx.util import Emu
from pathlib import Path

SRC = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\18-1_와이지엔터테인먼트_기업분석리포트.pptx')


def inches_to_emu(x):
    return Emu(int(x * 914400))


def main():
    p = Presentation(str(SRC))
    n = len(p.slides)
    print(f'Total slides: {n}')

    # 본문 슬라이드: Slide 3~26 (idx 2~25)
    # Cover(0), Index(1), 재무제표(26 마지막) 제외
    body_indices = range(2, n - 1)

    for sidx in body_indices:
        slide = p.slides[sidx]
        # 본문 박스 (T < 2, H 작음)와 도표 (T 2~5, H > 2)를 찾기
        body_boxes = []
        charts = []
        for sh in slide.shapes:
            if sh.top is None or sh.height is None:
                continue
            t_inch = Emu(sh.top).inches
            h_inch = Emu(sh.height).inches
            w_inch = Emu(sh.width).inches if sh.width else 0
            # 본문 박스: T < 2, W > 5 (큰 텍스트 박스)
            if sh.has_text_frame and t_inch < 2.5 and w_inch > 5 and h_inch < 3:
                body_boxes.append(sh)
            # 도표: shape_type 13 (Picture), T 2~5, W > 3, H > 2
            elif sh.shape_type == 13 and 2.0 < t_inch < 6.0 and w_inch > 3 and h_inch > 2:
                charts.append(sh)

        # 본문 박스 H 1.88 -> 4.0
        for box in body_boxes:
            box.height = inches_to_emu(4.0)
            # word_wrap 활성화
            if box.has_text_frame:
                box.text_frame.word_wrap = True
        # 도표 T 2.61 -> 5.0 (그대로 두거나 살짝 내림). 도표 크기 유지.
        for chart in charts:
            chart.top = inches_to_emu(5.0)

        if body_boxes or charts:
            print(f'[Slide {sidx+1}] box={len(body_boxes)} resized H=4.0, chart={len(charts)} moved T=5.0')

    p.save(str(SRC))
    print(f'\nSaved: {SRC.name}')


if __name__ == '__main__':
    main()
