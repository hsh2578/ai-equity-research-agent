"""
v11 - 박스 H 축소 + 도표 위치 위로:
- 본문 박스 H: 4.0" -> 2.5" (텍스트가 박스에 꽉 차게)
- 도표 T: 5.0" -> 3.4" (페이지 압축)
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

    # Cover(0), Index(1), 재무제표(마지막) 제외
    for sidx in range(2, n - 1):
        slide = p.slides[sidx]
        for sh in slide.shapes:
            if sh.top is None or sh.height is None:
                continue
            t_inch = Emu(sh.top).inches
            h_inch = Emu(sh.height).inches
            w_inch = Emu(sh.width).inches if sh.width else 0

            # 본문 박스 (T < 2.5, W > 5, H 약 4)
            if sh.has_text_frame and t_inch < 2.5 and w_inch > 5:
                sh.height = inches_to_emu(2.5)
            # 도표 (Picture, T 4~6)
            elif sh.shape_type == 13 and 3.5 < t_inch < 6.0 and w_inch > 3:
                sh.top = inches_to_emu(3.4)

    p.save(str(SRC))
    print(f'Saved: {SRC.name}')


if __name__ == '__main__':
    main()
