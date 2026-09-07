"""
위닝펀드 18-1 YG v10 — 분리 후 정리:
COM으로 복제된 27 슬라이드에서 shape 정리.
- 원본 슬라이드 (짝수 idx 2,4,6,...,24): 하단 요소 (T >= 5) 제거. 박스 1 H 늘리고 도표 1 위치 내림.
- 복제 슬라이드 (홀수 idx 3,5,7,...,25): 상단 요소 (T < 5) 제거. 하단 요소를 위로 이동 (T -= 5.03). 박스 H 늘리고 도표 위치 내림.

Cover(0), Index(1), 재무제표(26)는 건드리지 않음.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pptx import Presentation
from pptx.util import Emu
from pathlib import Path

SRC = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\18-1_와이지엔터테인먼트_기업분석리포트.pptx')


def inches_to_emu(x):
    return Emu(int(x * 914400))


def remove_shape(shape):
    sp = shape._element
    sp.getparent().remove(sp)


def main():
    p = Presentation(str(SRC))
    n = len(p.slides)
    print(f'Total slides: {n}')

    # 본문 슬라이드 idx 2~25 (Cover=0, Index=1, 재무제표=26 제외)
    for idx in range(2, n - 1):
        slide = p.slides[idx]
        is_clone = ((idx - 2) % 2 == 1)  # idx 3,5,7,... = 복제
        marker = 'clone' if is_clone else 'orig'

        shapes = list(slide.shapes)
        removed = 0
        moved = 0

        for sh in shapes:
            if sh.top is None:
                continue
            t_inch = Emu(sh.top).inches
            # 헤더(T<0.5) / 푸터(T>11) 보존
            if t_inch > 11.0 or t_inch < 0.5:
                continue
            if is_clone:
                # 복제 슬라이드: 상단 요소 (T < 5) 제거, 하단 요소는 위로 이동
                if t_inch < 5.0:
                    remove_shape(sh)
                    removed += 1
                else:
                    # 하단 → 상단으로 5.03" 위로 이동
                    sh.top = Emu(int((t_inch - 5.03) * 914400))
                    moved += 1
            else:
                # 원본 슬라이드: 하단 요소 (T >= 5) 제거
                if t_inch >= 5.0:
                    remove_shape(sh)
                    removed += 1

        # 박스 H 늘림 + 도표 위치 내림 (각 슬라이드의 남은 shape 중)
        for sh in list(slide.shapes):
            if sh.top is None or sh.height is None:
                continue
            t_inch = Emu(sh.top).inches
            h_inch = Emu(sh.height).inches
            w_inch = Emu(sh.width).inches if sh.width else 0
            # 본문 박스: T < 2.5, W > 5, H < 3 (텍스트 박스)
            if sh.has_text_frame and t_inch < 2.5 and w_inch > 5 and h_inch < 3:
                sh.height = inches_to_emu(4.0)
                sh.text_frame.word_wrap = True
            # 도표: Picture, T 2~5, W>3, H>2
            elif sh.shape_type == 13 and 2.0 < t_inch < 6.0 and w_inch > 3 and h_inch > 2:
                sh.top = inches_to_emu(5.0)

        print(f'[Slide {idx+1}] {marker}: removed={removed}, moved={moved}, '
              f'shapes_now={len(list(slide.shapes))}')

    p.save(str(SRC))
    print(f'\nSaved: {SRC.name}')


if __name__ == '__main__':
    main()
