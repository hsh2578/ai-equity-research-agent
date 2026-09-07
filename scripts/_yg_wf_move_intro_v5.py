"""
위닝펀드 18-1 YG v5:
1. Slide 3 (Introduction) -> 맨 마지막으로 이동
2. Slide 2 (Index) 페이지 번호 업데이트
3. 본문 박스 paragraph 간격 압축 (오버플로우 해결)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pptx import Presentation
from pptx.util import Pt, Emu
from pathlib import Path

SRC = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\18-1_와이지엔터테인먼트_기업분석리포트.pptx')


def move_slide(prs, old_idx, new_idx):
    """슬라이드 위치 이동"""
    xml_slides = prs.slides._sldIdLst
    slides = list(xml_slides)
    target = slides[old_idx]
    xml_slides.remove(target)
    if new_idx >= len(slides) - 1:
        xml_slides.append(target)
    else:
        xml_slides.insert(new_idx, target)


def replace_para_text(para, new_text):
    if not para.runs:
        return False
    para.runs[0].text = new_text
    for r in para.runs[1:]:
        r.text = ''
    return True


def compress_body_paragraphs(slide, body_shape_indices):
    """본문 박스의 paragraph 간격 압축"""
    for idx in body_shape_indices:
        if idx >= len(slide.shapes):
            continue
        sh = list(slide.shapes)[idx]
        if not sh.has_text_frame:
            continue
        for para in sh.text_frame.paragraphs:
            para.space_before = Pt(0)
            para.space_after = Pt(2)
            para.line_spacing = 1.15


def main():
    p = Presentation(str(SRC))
    n = len(p.slides)
    print(f'Before: {n} slides')

    # 1. Slide 3 (idx 2, Introduction) -> 맨 마지막
    move_slide(p, 2, n - 1)
    print(f'Moved Slide 3 (Introduction) -> last position (Slide {n})')

    # 2. Slide 2 Index 페이지 번호 업데이트
    #    원래: shape[9]=04 / [10]=06 / [11]=09 / [12]=12 / [13]=03 / [14]=13 / [15]=15
    #    Introduction 빠지면 산업분석부터 한 칸씩 앞당겨짐 (Introduction은 마지막=16)
    index_slide = p.slides[1]
    page_updates = {
        9:  '03',  # 산업분석   (04 -> 03)
        10: '05',  # 기업분석   (06 -> 05)
        11: '08',  # 투자포인트 (09 -> 08)
        12: '11',  # 리스크     (12 -> 11)
        13: '16',  # Introduction (03 -> 16, 맨 마지막)
        14: '12',  # 재무분석   (13 -> 12)
        15: '14',  # 밸류에이션 (15 -> 14)
    }
    shapes = list(index_slide.shapes)
    for sh_idx, new_num in page_updates.items():
        if sh_idx >= len(shapes):
            continue
        sh = shapes[sh_idx]
        if sh.has_text_frame and len(sh.text_frame.paragraphs) > 0:
            old = ''.join(r.text for r in sh.text_frame.paragraphs[0].runs).strip()
            replace_para_text(sh.text_frame.paragraphs[0], new_num)
            print(f'  Index shape[{sh_idx}]: {old} -> {new_num}')

    # 3. 본문 박스 paragraph 간격 압축 (Slide 4~14 = 산업/기업/투자/리스크/재무/밸류)
    # 이동 후 새 인덱스: Slide 4(산업1), 5(산업2), 6(기업1), 7(기업2), 8(기업3),
    #                    9(투자1), 10(투자2), 11(투자3), 12(리스크), 13(재무1), 14(재무2),
    #                    15(밸류), 16(Introduction)
    # 본문 박스 인덱스는 보통 [1] [2]
    target_slides = list(range(3, 15))  # idx 3 ~ 14 = Slide 4~15
    for sidx in target_slides:
        slide = p.slides[sidx]
        compress_body_paragraphs(slide, [1, 2])
    print(f'\nCompressed body paragraphs in slides 4-15 (line_spacing 1.15, space_after 2pt)')

    p.save(str(SRC))
    print(f'\nSaved: {SRC.name}')
    print(f'After: {len(p.slides)} slides (Introduction moved to end)')


if __name__ == '__main__':
    main()
