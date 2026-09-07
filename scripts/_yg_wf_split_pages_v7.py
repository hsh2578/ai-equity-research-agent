"""
위닝펀드 18-1 YG v7 — 페이지 분리:
각 본문 슬라이드(3~14)를 2 페이지로 분리.
- 첫 페이지: 박스 1 + 도표 1 + 좌측 카피 상단 (박스 2/도표 2/카피 하단 제거)
- 둘째 페이지: 박스 2 + 도표 2 + 좌측 카피 하단 (박스 1/도표 1/카피 상단 제거)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import copy
from pptx import Presentation
from pptx.util import Emu
from pathlib import Path

SRC = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\18-1_와이지엔터테인먼트_기업분석리포트.pptx')


def duplicate_slide(prs, src_idx):
    """슬라이드 복제 후 맨 끝에 추가, 새 슬라이드 객체 반환"""
    src = prs.slides[src_idx]
    new_slide = prs.slides.add_slide(src.slide_layout)
    # 기존 add_slide가 추가한 placeholder 제거 (깨끗한 슬라이드 만들기)
    for sh in list(new_slide.shapes):
        sp = sh._element
        sp.getparent().remove(sp)
    # 원본의 모든 shape 복제
    for shape in src.shapes:
        new_el = copy.deepcopy(shape.element)
        new_slide.shapes._spTree.insert_element_before(new_el, 'p:extLst')
    return new_slide


def move_slide_to(prs, current_idx, target_idx):
    """슬라이드를 다른 위치로 이동"""
    xml = prs.slides._sldIdLst
    slides = list(xml)
    elem = slides[current_idx]
    xml.remove(elem)
    if target_idx >= len(slides) - 1:
        xml.append(elem)
    else:
        xml.insert(target_idx, elem)


def remove_shape(shape):
    sp = shape._element
    sp.getparent().remove(sp)


def split_slide(prs, src_idx):
    """src_idx 슬라이드를 2 페이지로 분리.
    원본은 박스 1+도표 1만 / 복제본은 박스 2+도표 2만 남김.
    복제본을 원본 바로 뒤로 이동."""

    n_before = len(prs.slides)

    # 1) 복제 → 맨 끝
    new_slide = duplicate_slide(prs, src_idx)
    # new_slide는 맨 끝 (idx = n_before)

    # 2) 새 슬라이드를 원본 바로 뒤로 이동
    move_slide_to(prs, n_before, src_idx + 1)

    # 3) 원본 슬라이드에서 하단 요소 (박스 2, 도표 2, 좌측 카피 하단) 제거
    orig = prs.slides[src_idx]
    orig_shapes = list(orig.shapes)

    # shape 위치 기반 분류 (T 좌표가 5"보다 큰 것 = 하단)
    to_remove_orig = []
    for sh in orig_shapes:
        if sh.top is None:
            continue
        t_inch = Emu(sh.top).inches
        # 카테고리 헤더 (T < 0.5") 보존
        # 페이지 번호/로고 (T > 11") 보존
        if t_inch > 11.0 or t_inch < 0.5:
            continue
        # 하단 박스/도표/카피 (T >= 5") 제거
        if t_inch >= 5.0:
            to_remove_orig.append(sh)

    for sh in to_remove_orig:
        remove_shape(sh)

    # 4) 복제 슬라이드에서 상단 요소 (박스 1, 도표 1, 좌측 카피 상단) 제거
    dup = prs.slides[src_idx + 1]
    dup_shapes = list(dup.shapes)

    to_remove_dup_top = []
    to_move_dup = []  # 하단 → 상단 이동할 shape (박스 2, 도표 2, 카피 하단)
    for sh in dup_shapes:
        if sh.top is None:
            continue
        t_inch = Emu(sh.top).inches
        if t_inch > 11.0 or t_inch < 0.5:
            continue
        if t_inch < 5.0:
            # 상단 요소 제거
            to_remove_dup_top.append(sh)
        else:
            # 하단 요소 → 상단으로 이동
            to_move_dup.append(sh)

    for sh in to_remove_dup_top:
        remove_shape(sh)

    # 5) 복제 슬라이드의 하단 요소들을 상단으로 이동 (T -= 5.0")
    for sh in to_move_dup:
        cur_top = Emu(sh.top).inches
        new_top_inch = cur_top - 5.03  # 하단 시작(T 5.81)을 상단 시작(T 0.78) 위치로
        sh.top = Emu(int(new_top_inch * 914400))

    return new_slide


def main():
    p = Presentation(str(SRC))
    n_before = len(p.slides)
    print(f'Before: {n_before} slides')

    # 본문 슬라이드 인덱스 (Slide 3~14 = idx 2~13)
    # Cover(0), Index(1), 본문 12장(2~13), 재무제표(14)
    # 처음부터 인덱스가 변경되므로 뒤에서부터 작업
    # idx 13 → 12 → 11 → ... → 2 순서

    body_indices = list(range(13, 1, -1))  # [13, 12, ..., 2]
    for idx in body_indices:
        split_slide(p, idx)
        print(f'  Split slide idx {idx} -> 2 pages')

    p.save(str(SRC))
    n_after = len(p.slides)
    print(f'\nAfter: {n_after} slides (was {n_before})')
    print(f'Saved: {SRC.name}')


if __name__ == '__main__':
    main()
