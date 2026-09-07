"""
v10 — 워드 본문 박스 1:1 PPT (38장)
- 박스 35개를 1슬라이드씩 (워드 본문 그대로, 글자 줄임 없음)
- 본문 박스 동적 H (짧음 H=4.20 / 중간 H=5.00 / 긴 H=8.50, 도표 없음)
- 도표 H=5.30 (양식 3.26 대비 +63%, v9 6.50 대비 -18%)
"""
import sys, io, json, shutil, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from copy import deepcopy
from pptx import Presentation
from pptx.util import Emu, Pt, Inches
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from pathlib import Path

NAVY = RGBColor(0x1E, 0x3A, 0x6D)
RED = RGBColor(0xC8, 0x10, 0x2E)
GREY = RGBColor(0x44, 0x44, 0x44)

SRC = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\18-1_기업분석 리포트 양식_clean.pptx')
DST = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\18-1_와이지엔터테인먼트_기업분석리포트_v10.pptx')
BOXES_JSON = Path('scripts/_yg_v10_boxes.json')

# v10 좌표 (본문 분량별 동적)
COPY_L, COPY_T, COPY_W = 0.40, 0.85, 1.40
BODY_L, BODY_W = 1.87, 5.92


def get_layout(body_chars):
    """본문 글자 수에 따라 layout 동적 결정"""
    if body_chars < 700:
        # 짧음: 본문 H=2.50, 도표 H=6.00 (도표 크게)
        return dict(body_h=2.50, chart_t=3.85, chart_h=6.50, caption_t=3.55, source_t=10.55, has_chart=True)
    elif body_chars < 1500:
        # 중간: 본문 H=4.20, 도표 H=5.30
        return dict(body_h=4.20, chart_t=5.55, chart_h=4.80, caption_t=5.25, source_t=10.55, has_chart=True)
    elif body_chars < 2500:
        # 긴: 본문 H=5.50, 도표 H=4.00
        return dict(body_h=5.50, chart_t=6.85, chart_h=3.50, caption_t=6.55, source_t=10.55, has_chart=True)
    else:
        # 매우 긴 (2500자+): 본문 H=9.50, 도표 없음
        return dict(body_h=9.50, chart_t=0, chart_h=0, caption_t=0, source_t=0, has_chart=False)


def add_blank_slide_from_template(dst, src_slide):
    layout = src_slide.slide_layout
    new_slide = dst.slides.add_slide(layout)
    for sh in src_slide.shapes:
        new_el = deepcopy(sh.element)
        new_slide.shapes._spTree.insert_element_before(new_el, 'p:extLst')
    return new_slide


def set_text(tf, text, font_size=None, bold=None, color=None):
    tf.clear()
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = text
    if font_size: r.font.size = Pt(font_size)
    if bold is not None: r.font.bold = bold
    if color: r.font.color.rgb = color


def write_body(tf, head, body, font_size=9):
    """소제목 11pt Navy bold + 본문 9pt 회색"""
    tf.clear()
    tf.word_wrap = True
    p = tf.paragraphs[0]
    if head:
        r = p.add_run(); r.text = head
        r.font.size = Pt(11); r.font.bold = True; r.font.color.rgb = NAVY
    paragraphs = body.split('\n')
    first = (not head)
    for line in paragraphs:
        if not line.strip(): continue
        if first:
            p2 = tf.paragraphs[0]
            r2 = p2.add_run() if p2.runs else p2.add_run()
            r2.text = line
            first = False
        else:
            p2 = tf.add_paragraph()
            r2 = p2.add_run(); r2.text = line
        r2.font.size = Pt(font_size); r2.font.color.rgb = GREY


def reposition_and_clear(slide, layout):
    """양식 본문 박스 위치/크기 조정 + 하단 박스 제거"""
    to_remove = []
    body_top = None
    copy_top = None
    for sh in slide.shapes:
        if not sh.has_text_frame: continue
        l = Emu(sh.left).inches if sh.left else 0
        t = Emu(sh.top).inches if sh.top else 0
        w = Emu(sh.width).inches if sh.width else 0
        txt = sh.text_frame.text

        if l >= 1.5 and 0.5 < t < 2.5 and w > 4.0:
            body_top = sh
        elif l >= 1.5 and 5.0 < t < 7.0 and w > 4.0:
            to_remove.append(sh)
        elif l < 1.5 and 0.8 < t < 1.8 and ('요약 제목' in txt or len(txt.strip()) < 30):
            copy_top = sh
        elif l < 1.5 and 5.5 < t < 6.3:
            to_remove.append(sh)

    if body_top:
        body_top.left = Inches(BODY_L)
        body_top.top = Inches(COPY_T)
        body_top.width = Inches(BODY_W)
        body_top.height = Inches(layout['body_h'])
    if copy_top:
        copy_top.left = Inches(COPY_L)
        copy_top.top = Inches(COPY_T)
        copy_top.width = Inches(COPY_W)
        copy_top.height = Inches(1.5)

    for sh in to_remove:
        sh._element.getparent().remove(sh._element)

    return body_top, copy_top


def remove_unused(slide):
    """양식 GROUP(도표 placeholder) + 도표 영역 LINE 제거"""
    to_remove = []
    for sh in slide.shapes:
        l = Emu(sh.left).inches if sh.left else 0
        t = Emu(sh.top).inches if sh.top else 0
        w = Emu(sh.width).inches if sh.width else 0
        if sh.shape_type == 6 and l < 1.0 and w > 5.0:
            to_remove.append(sh)
        elif sh.shape_type == 9 and 2.30 < t < 11.10:
            to_remove.append(sh)
    for sh in to_remove:
        sh._element.getparent().remove(sh._element)


def fill_box_slide(slide, header, copy_text, box_title, body, body_chars):
    """박스 1개 슬라이드 채우기"""
    layout = get_layout(body_chars)
    remove_unused(slide)
    body_top, copy_top = reposition_and_clear(slide, layout)

    # 헤더
    for sh in slide.shapes:
        if not sh.has_text_frame: continue
        l = Emu(sh.left).inches if sh.left else 0
        t = Emu(sh.top).inches if sh.top else 0
        if t < 0.5 and l < 1.0 and sh.text_frame.text.strip():
            set_text(sh.text_frame, header, font_size=18, bold=True, color=NAVY)

    # 좌측 카피
    if copy_top and copy_text:
        set_text(copy_top.text_frame, copy_text, font_size=10, bold=True, color=GREY)

    # 본문 (소제목 = 박스 제목)
    if body_top:
        # 본문 길이에 따라 폰트 크기 자동 조절
        font_size = 9 if body_chars < 1500 else 8.5 if body_chars < 2500 else 8
        write_body(body_top.text_frame, box_title, body, font_size=font_size)


def update_page_no(prs):
    for i, slide in enumerate(prs.slides):
        for sh in slide.shapes:
            if not sh.has_text_frame: continue
            t = sh.text_frame.text.strip()
            l = Emu(sh.left).inches if sh.left else 0
            top = Emu(sh.top).inches if sh.top else 0
            if l > 7 and top > 11 and ('|' in t or t.strip().isdigit()):
                set_text(sh.text_frame, f'|   {i+1}', font_size=9, color=GREY)


def set_cell(cell, text, font_size=None, bold=None, color=None):
    tf = cell.text_frame
    if not tf.paragraphs: return
    p = tf.paragraphs[0]
    if p.runs:
        first = p.runs[0]
        first.text = text
        if font_size: first.font.size = Pt(font_size)
        if bold is not None: first.font.bold = bold
        if color: first.font.color.rgb = color
        for r in list(p.runs[1:]): r._r.getparent().remove(r._r)
    else:
        r = p.add_run(); r.text = text
        if font_size: r.font.size = Pt(font_size)
        if bold is not None: r.font.bold = bold
        if color: r.font.color.rgb = color
    for pp in list(tf.paragraphs[1:]): pp._p.getparent().remove(pp._p)


# Cover (워드 박스 0,1,2 통합)
def fill_cover(slide, cover_boxes):
    """cover_boxes = [Summary box, Highlight box, Valuation box]"""
    for sh in slide.shapes:
        if not sh.has_text_frame: continue
        t = sh.text_frame.text.strip()
        if '회사명' in t and '종목코드' in t:
            set_text(sh.text_frame, '와이지엔터테인먼트 (122870)', font_size=28, bold=True, color=NAVY)
        elif t == '리포트 제목':
            set_text(sh.text_frame, '5년 +190% 패턴, 다시 그릴 차례', font_size=16, color=GREY)
        elif '18-1 Equity Research' in t:
            set_text(sh.text_frame, '18-1 Equity Research', font_size=9)
        elif '2026.05.00' in t or '2026.00.00' in t:
            set_text(sh.text_frame, '2026.05.27.', font_size=9)
        elif 'Winning Fund 17-1' in t:
            set_text(sh.text_frame, 'Winning Fund 18-1 Research Report', font_size=9)
        elif '최종 제출 시' in t or '안내사항' in t:
            tf = sh.text_frame; tf.clear()
            first = True
            for box in cover_boxes:
                title = box['box_title'].split(' ', 1)[0]  # "Summary 6줄" → "Summary"
                if first: p = tf.paragraphs[0]; first = False
                else: p = tf.add_paragraph()
                r = p.add_run(); r.text = title
                r.font.size = Pt(12); r.font.bold = True; r.font.color.rgb = NAVY
                # body (각 sub의 body 합쳐)
                body = '\n'.join(s['body'] for s in box['subs'])
                for line in body.split('\n'):
                    if not line.strip(): continue
                    p = tf.add_paragraph()
                    r = p.add_run(); r.text = line
                    r.font.size = Pt(8); r.font.color.rgb = GREY

    # 테이블 (양식 그대로)
    for sh in slide.shapes:
        if sh.shape_type != 19: continue
        t_pos = Emu(sh.top).inches if sh.top else 0
        tbl = sh.table
        rows, cols = len(tbl.rows), len(tbl.columns)
        if 5.5 < t_pos < 6.0 and rows == 8 and cols == 3:
            data = [
                ('Stock Data', '26.05.27.', ''), ('KOSDAQ지수(pt)', '', '789'),
                ('52주 최고/최저(원)', '', '79,000/47,000'),
                ('거래량(천주)/거래대금(억)', '', '215/103'),
                ('시가총액(억원)', '', '8,981'),
                ('발행주식수(천 주)', '', '18,691'),
                ('주요주주 지분율', '', '22.95%'),
                ('외국인 지분율', '', '10.86%'),
            ]
            for ri, row in enumerate(data):
                for ci, val in enumerate(row):
                    set_cell(tbl.cell(ri, ci), val, font_size=8)
        elif 7.0 < t_pos < 7.5:
            try:
                set_cell(tbl.cell(0, 0), 'Consensus Data', font_size=8, bold=True)
                if cols >= 3:
                    set_cell(tbl.cell(0, 1), '2025', font_size=8, bold=True)
                    set_cell(tbl.cell(0, 2), '2026E', font_size=8, bold=True)
                cd = [('매출액(억원)', '5,454', '6,010'), ('영업이익(억원)', '522', '806'),
                      ('순이익(억원)', '537', '684'), ('EPS(원)', '1,974', '3,108')]
                for ri, row in enumerate(cd):
                    if ri+1 >= rows: break
                    for ci, val in enumerate(row):
                        if ci >= cols: break
                        set_cell(tbl.cell(ri+1, ci), val, font_size=8)
            except: pass
        elif 8.3 < t_pos < 8.7:
            try:
                set_cell(tbl.cell(0, 0), '수익률', font_size=8, bold=True)
                if cols >= 4:
                    for ci, h in enumerate(['1M', '6M', '12M']):
                        set_cell(tbl.cell(0, ci+1), h, font_size=8, bold=True)
                    if rows >= 2:
                        set_cell(tbl.cell(1, 0), '절대주가(%)', font_size=8)
                        for ci, v in enumerate(['-3.8', '-26.82', '-24.22']):
                            set_cell(tbl.cell(1, ci+1), v, font_size=8)
            except: pass
        elif 2.8 < t_pos < 3.1:
            try:
                set_cell(tbl.cell(0, 0), '종목정보', font_size=10, bold=True, color=NAVY)
                info = [('업종', 'KOSDAQ / 엔터'), ('주가 (5/27)', '48,050원'), ('상장일', '2011.11.23')]
                for ri, row in enumerate(info):
                    if ri+1 >= rows: break
                    for ci, val in enumerate(row):
                        if ci >= cols: break
                        set_cell(tbl.cell(ri+1, ci), val, font_size=8)
            except: pass
        elif 3.8 < t_pos < 4.2:
            try:
                if rows >= 1: set_cell(tbl.cell(0, 0), 'BUY', font_size=28, bold=True, color=NAVY)
                pairs = [('목표 주가(원)', '89,000', NAVY), ('현재 주가(원)', '48,050', None),
                         ('상승 여력(%)', '+85.2', RED)]
                for ri, (lbl, val, c) in enumerate(pairs):
                    if ri+1 >= rows: break
                    set_cell(tbl.cell(ri+1, 0), lbl, font_size=9)
                    if cols >= 2:
                        set_cell(tbl.cell(ri+1, 1), val, font_size=12, bold=True, color=c or NAVY)
            except: pass


# 카테고리 → 양식 idx
CAT_TEMPLATE = {
    '산업': 3,
    '기업': 4,
    '기업-주가': 5,
    '투자': 6,
    '리스크': 8,
    '재무': 9,
    '밸류': 10,
}


def categorize(slide_num):
    """워드 슬라이드 번호 → 카테고리"""
    n = int(slide_num) if slide_num.isdigit() else 0
    if 3 <= n <= 6: return '산업'
    if 7 <= n <= 12: return '기업'
    if n == 13: return '기업-주가'  # 5년 주가
    if n == 14: return '기업'
    if 15 <= n <= 19: return '투자'
    if 20 <= n <= 21: return '리스크'
    if 22 <= n <= 25: return '재무'
    if 26 <= n <= 28: return '밸류'
    return '기업'


def short_copy(box_title):
    """박스 제목 → 좌측 카피 (12~16자)"""
    t = box_title.split('—')[0].split(':')[0].strip()
    if len(t) > 16:
        t = t[:14] + '...'
    # 2줄로 분리 시도
    if len(t) > 10:
        mid = len(t) // 2
        # 공백 근처에서 분리
        for off in [0, 1, -1, 2, -2]:
            if mid + off < len(t) and t[mid + off] == ' ':
                return t[:mid+off] + '\n' + t[mid+off+1:]
    return t


CATEGORY_HEADER = {
    '산업': '산업분석 Industry Overview',
    '기업': '기업분석 Company Overview',
    '기업-주가': '기업분석 Company Overview',
    '투자': '투자포인트 Investment Highlights',
    '리스크': '리스크 Risk',
    '재무': '재무분석 Financial Overview',
    '밸류': '밸류에이션 Valuation',
}


def main():
    print('=== v10 빌드 (워드 본문 1:1) ===\n')

    with open(BOXES_JSON, encoding='utf-8') as f:
        boxes = json.load(f)
    print(f'박스 로드: {len(boxes)}개')

    # Cover 박스 분리 (slide_num == '1')
    cover_boxes = [b for b in boxes if b['slide_num'] == '1']
    body_boxes = [b for b in boxes if b['slide_num'] not in ('1', '2', '29')]
    print(f'  Cover: {len(cover_boxes)} / 본문: {len(body_boxes)} / 재무제표: 1')

    # 양식 로드
    src = Presentation(str(SRC))

    # dst 초기화
    tmp = tempfile.NamedTemporaryFile(suffix='.pptx', delete=False); tmp.close()
    shutil.copy(SRC, tmp.name)
    dst = Presentation(tmp.name)
    sldIdLst = dst.slides._sldIdLst
    while len(list(sldIdLst)) > 0:
        sld = list(sldIdLst)[0]
        rId = sld.get(qn('r:id'))
        dst.part.drop_rel(rId)
        sldIdLst.remove(sld)
    print(f'dst 초기화 완료\n')

    # 1. Cover (양식 idx 0)
    add_blank_slide_from_template(dst, src.slides[0])
    print(f'Slide 1 Cover')

    # 2. Index (양식 idx 1)
    add_blank_slide_from_template(dst, src.slides[1])
    print(f'Slide 2 Index')

    # 3~. 본문 박스 35개 1:1
    print(f'\n=== 본문 박스 1:1 슬라이드 ===')
    for i, box in enumerate(body_boxes):
        cat = categorize(box['slide_num'])
        tmpl_idx = CAT_TEMPLATE[cat]
        src_slide = src.slides[tmpl_idx]
        add_blank_slide_from_template(dst, src_slide)
        print(f'  Slide {i+3}: 박스 {box["slide_num"]}-{box["box_no"]} ({cat}) {box["box_title"][:30]}')

    # N+1. 재무제표 (양식 idx 11)
    add_blank_slide_from_template(dst, src.slides[11])
    print(f'\nSlide {len(body_boxes)+3} 재무제표')

    total = len(dst.slides)
    print(f'\n빌드 완료: {total}장')

    # === 본문 채우기 ===
    print(f'\n=== Cover 채우기 ===')
    fill_cover(dst.slides[0], cover_boxes)

    print(f'\n=== 본문 슬라이드 채우기 ===')
    for i, box in enumerate(body_boxes):
        slide_idx = i + 2  # Cover=0, Index=1
        slide = dst.slides[slide_idx]
        cat = categorize(box['slide_num'])
        header = CATEGORY_HEADER[cat]
        copy = short_copy(box['box_title'])
        body = '\n'.join(s['body'] for s in box['subs'])
        body_chars = len(body)
        fill_box_slide(slide, header, copy, box['box_title'], body, body_chars)
        print(f'  Slide {slide_idx+1:2}: {box["box_title"][:35]} ({body_chars}자)')

    # 페이지 번호
    update_page_no(dst)

    dst.save(str(DST))
    print(f'\n저장: {DST.name}')
    print(f'크기: {DST.stat().st_size / 1024:.1f} KB / {total}장')


if __name__ == '__main__':
    main()
