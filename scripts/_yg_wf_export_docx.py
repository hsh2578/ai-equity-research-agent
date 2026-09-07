"""
위닝펀드 18-1 YG 본문을 Word(.docx)로 추출 — 본문 수정용
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pptx import Presentation
from pptx.util import Emu
from docx import Document
from docx.shared import Pt, RGBColor
from pathlib import Path

SRC = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\18-1_와이지엔터테인먼트_기업분석리포트.pptx')
OUT = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\18-1_와이지엔터테인먼트_본문_편집용.docx')

NAVY = RGBColor(0x1F, 0x3A, 0x5F)
GOLD = RGBColor(0xC9, 0xA9, 0x61)
GREY = RGBColor(0x88, 0x88, 0x88)


def classify_shape(sh):
    """shape 유형 분류: header / left_copy / body_box / footer / chart / other"""
    if sh.top is None or sh.height is None:
        return 'other'
    t = Emu(sh.top).inches
    h = Emu(sh.height).inches
    w = Emu(sh.width).inches if sh.width else 0
    l = Emu(sh.left).inches if sh.left else 0

    # 푸터
    if t > 11.0:
        return 'footer'
    # 카테고리 헤더 (상단 0.19, W>4)
    if t < 0.6 and w > 3:
        return 'header'
    # 좌측 카피 (L < 1.5, W < 1.5)
    if l < 1.5 and w < 1.5 and sh.has_text_frame:
        return 'left_copy'
    # 본문 박스 (큰 W, 텍스트)
    if sh.has_text_frame and w > 5 and h > 1.0:
        return 'body_box'
    # 도표 (Picture)
    if sh.shape_type == 13 and w > 3 and h > 2:
        return 'chart'
    return 'other'


def get_text(shape):
    """shape의 paragraph 리스트 반환"""
    if not shape.has_text_frame:
        return []
    paras = []
    for para in shape.text_frame.paragraphs:
        t = ''.join(r.text for r in para.runs).strip()
        if t:
            paras.append(t)
    return paras


def main():
    p = Presentation(str(SRC))
    n = len(p.slides)

    doc = Document()

    # 문서 제목
    title = doc.add_heading('와이지엔터테인먼트 위닝펀드 18-1 본문 (편집용)', 0)
    p_intro = doc.add_paragraph()
    r = p_intro.add_run(f'전체 {n} 슬라이드 · 본문 수정 후 알려주면 PPT에 반영')
    r.italic = True
    r.font.color.rgb = GREY
    doc.add_paragraph()

    for sidx, slide in enumerate(p.slides, 1):
        # 슬라이드별 분류
        header_text = ''
        left_copies = []  # T 좌표 순
        body_boxes = []   # T 좌표 순

        for sh in slide.shapes:
            kind = classify_shape(sh)
            if kind == 'header':
                texts = get_text(sh)
                if texts:
                    header_text = texts[0]
            elif kind == 'left_copy':
                texts = get_text(sh)
                if texts:
                    t_val = Emu(sh.top).inches if sh.top else 99
                    left_copies.append((t_val, ' '.join(texts)))
            elif kind == 'body_box':
                texts = get_text(sh)
                if texts:
                    t_val = Emu(sh.top).inches if sh.top else 99
                    body_boxes.append((t_val, texts))

        # 순서대로 정렬
        left_copies.sort(key=lambda x: x[0])
        body_boxes.sort(key=lambda x: x[0])

        # 슬라이드 헤더
        h2 = doc.add_heading(f'Slide {sidx} — {header_text}', 1)

        # 좌측 카피
        for _, lc in left_copies:
            p_lc = doc.add_paragraph()
            r = p_lc.add_run(f'[좌측 카피] {lc}')
            r.bold = True
            r.font.color.rgb = GOLD

        # 본문 박스
        for box_idx, (_, paras) in enumerate(body_boxes, 1):
            if not paras:
                continue
            # 첫 paragraph = 헤더, 나머지 = 본문 단락
            h3 = doc.add_heading(f'박스 {box_idx}: {paras[0]}', 2)
            for body_para in paras[1:]:
                p_body = doc.add_paragraph(body_para)
                p_body.paragraph_format.space_after = Pt(6)

        doc.add_paragraph()  # 슬라이드 간 간격

    doc.save(str(OUT))
    print(f'Saved: {OUT}')
    print(f'File size: {OUT.stat().st_size / 1024:.1f} KB')


if __name__ == '__main__':
    main()
