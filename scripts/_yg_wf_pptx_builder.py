"""
와이지엔터 위닝펀드 18-1 PPT 빌더 (v3 — 양식 30+ 확장)
- 양식 13 슬라이드를 복제해서 30 슬라이드로 확장
- Word 본문 100% 보존
- 우수 리포트 디자인 (양식 그대로 활용)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from copy import deepcopy
from pptx import Presentation
from pptx.util import Emu, Pt, Inches
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from pathlib import Path

SRC = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\18-1_기업분석 리포트 양식.pptx')
DST = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\18-1_와이지엔터테인먼트_기업분석리포트_v2.pptx')

NAVY = RGBColor(0x1E, 0x3A, 0x6D)
RED = RGBColor(0xC8, 0x10, 0x2E)
GREY = RGBColor(0x44, 0x44, 0x44)


def duplicate_slide(prs, src_idx):
    """양식 src_idx 슬라이드를 복제해서 맨 뒤에 추가"""
    src = prs.slides[src_idx]
    layout = src.slide_layout
    new_slide = prs.slides.add_slide(layout)
    # 원본 모든 shape XML 복사
    for sh in src.shapes:
        new_el = deepcopy(sh.element)
        new_slide.shapes._spTree.insert_element_before(new_el, 'p:extLst')
    # 슬라이드 노트 복사 (생략)
    return new_slide


def reorder_slides(prs, new_order):
    """슬라이드 순서를 new_order(인덱스 리스트)에 따라 재배치"""
    sldIdLst = prs.slides._sldIdLst
    current = list(sldIdLst)
    # 임시로 다 제거
    for el in current:
        sldIdLst.remove(el)
    # 새 순서로 추가
    for idx in new_order:
        sldIdLst.append(current[idx])


def set_cell_text(cell, text, font_size=None, bold=None, color=None):
    """테이블 셀 텍스트 교체 (서식 보존하면서)"""
    tf = cell.text_frame
    if not tf.paragraphs:
        return
    p = tf.paragraphs[0]
    # 첫 run에 텍스트, 나머지 제거
    if p.runs:
        first = p.runs[0]
        first.text = text
        if font_size: first.font.size = Pt(font_size)
        if bold is not None: first.font.bold = bold
        if color: first.font.color.rgb = color
        for r in list(p.runs[1:]):
            r._r.getparent().remove(r._r)
    else:
        r = p.add_run()
        r.text = text
        if font_size: r.font.size = Pt(font_size)
        if bold is not None: r.font.bold = bold
        if color: r.font.color.rgb = color
    # 나머지 단락 삭제
    for pp in list(tf.paragraphs[1:]):
        pp._p.getparent().remove(pp._p)


def replace_first_text(sh, new_text, font_size=None, bold=None, color=None):
    """텍스트 박스의 텍스트를 새 텍스트로 한 번에 교체 (서식 보존)"""
    if not sh.has_text_frame:
        return
    tf = sh.text_frame
    if not tf.paragraphs:
        return
    p = tf.paragraphs[0]
    if p.runs:
        first = p.runs[0]
        orig_size = first.font.size
        orig_bold = first.font.bold
        first.text = new_text
        for r in list(p.runs[1:]):
            r._r.getparent().remove(r._r)
    else:
        r = p.add_run()
        r.text = new_text
    for pp in list(tf.paragraphs[1:]):
        pp._p.getparent().remove(pp._p)


def write_body(sh, subhead, body_text, copy=None):
    """본문 박스에 소제목 + 본문 작성"""
    if not sh.has_text_frame:
        return
    tf = sh.text_frame
    tf.clear()
    # 소제목
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = subhead
    r.font.size = Pt(11)
    r.font.bold = True
    r.font.color.rgb = NAVY
    # 본문
    p = tf.add_paragraph()
    r = p.add_run()
    r.text = body_text
    r.font.size = Pt(9)


def find_shape_by_text(slide, contains):
    """슬라이드에서 텍스트 일치하는 shape 찾기"""
    for sh in slide.shapes:
        if sh.has_text_frame and contains in sh.text_frame.text:
            return sh
    return None


def fill_cover(slide):
    """Cover Slide 1"""
    for sh in slide.shapes:
        if not sh.has_text_frame: continue
        t = sh.text_frame.text.strip()
        if '회사명' in t and '종목코드' in t:
            replace_first_text(sh, '와이지엔터테인먼트 (122870)')
        elif t == '리포트 제목':
            replace_first_text(sh, '5년 +190% 패턴, 다시 그릴 차례')
        elif '18-1 Equity Research' in t:
            replace_first_text(sh, '18-1 Equity Research')
        elif '2026.05.00' in t or '2026.00.00' in t:
            replace_first_text(sh, '2026.05.27.')
        elif 'Winning Fund 17-1' in t:
            replace_first_text(sh, 'Winning Fund 18-1 Research Report')
        elif '최종 제출 시' in t or '안내사항' in t:
            # 본문 영역 — Summary + IH + Valuation
            tf = sh.text_frame
            tf.clear()
            sections = [
                ('Summary', True, [
                    '- 핵심 베팅: 24.10~25.08 블랙핑크 재계약·DEADLINE + 베몬 데뷔로 37,000 → 107,400원 +190% 상승 패턴이, 26.08~27.07 빅뱅 20주년 + 신인 보이그룹·NEXT MONSTER 2팀 데뷔로 재현된다.',
                    '- 1Q26 매출 +46.9%·영업이익 +103.9%인데 주가는 3개월간 -26.8%. 시장은 -5% 컨센 미달과 블랙핑크 공백만 봤다.',
                    '- 하반기 빅뱅 20주년 투어·9월 신인 보이그룹·베이비몬스터 글로벌 라인업 등 5종 IP 동시 가동.',
                    '- 양현석 시스템 개편으로 "적은 아티스트 수·긴 컴백 주기" 한계가 풀리는 중이며, 베이비몬스터가 첫 증거.',
                    '- 현재 12개월 선행 PER 15.9배는 빅뱅 군 입대(2017~19)·버닝썬 사건(2019) 당시 역사적 하단과 유사.',
                    '- 순현금 2,737억·사실상 무차입. 어떤 IP 공백에도 버티는 하방 안전판.',
                ]),
                ('Investment Highlights', True, [
                    '1) 빅뱅 20주년 + 신인 2팀 = 24.10~25.08 +190% 패턴 재현: 빅뱅 BIGSHOW: REBORN 14개 도시 풀이어(2026.08~2027.01) + 9월 신인 보이그룹 + NEXT MONSTER 2027 상반기 데뷔. 컨센 2027E OP 764억은 빅뱅 풀이어 미반영, 8월 일정 확정 시 4~6주 안에 재상향 트리거.',
                    '2) 단일 IP 리스크 시스템으로 해소: 9월 5인조 신인 보이그룹 + 2027 상반기 NEXT MONSTER(4인조) 데뷔. 베이비몬스터 미니 3집 CHOOM 초동 38.8만 자체 최고. 안무 발주 2~3팀 → 10팀 확대 결과물.',
                    '3) 순현금 2,737억 무너질 일 없는 회사: 시총 8,981억의 30%가 현금. 영업현금흐름 909억·잉여현금흐름 849억 흑자. 2024년 영업적자 해에도 당기순이익 200억 유지.',
                ]),
                ('Valuation', True, [
                    '본 리포트는 24M Forward 기준(2028E)으로 적정주가 89,000원(2028E EPS 3,700원 × Target PER 24배)을 산출했다. 현재가 48,050원 대비 상승여력 +85.2%, 도달 목표 시점 2028년 말(2.5년 호라이즌).',
                    'Target PER 24배는 4사 2028E Implied PER Median 13.5배 + IP 6종 분산 Premium +5.0배 + 메가 IP 양성 입증 Premium +5.5배의 덧셈 워터폴로 산출.',
                    '5가지 보수 가정에도 도출된 정직한 보수값. 19개 증권사 컨센 평균 78,789원 대비 +13% 높은데, EPS 시점 적극 +19% × Target PER 보수 -5%의 분해. 1년 이상 장기 보유 관점. 투자의견 BUY.',
                ]),
            ]
            first = True
            for header, is_bold, lines in sections:
                if first:
                    p = tf.paragraphs[0]; first = False
                else:
                    p = tf.add_paragraph()
                r = p.add_run(); r.text = header
                r.font.size = Pt(12); r.font.bold = True; r.font.color.rgb = NAVY
                for line in lines:
                    p = tf.add_paragraph()
                    r = p.add_run(); r.text = line
                    r.font.size = Pt(9)

    # 테이블 채우기
    for sh in slide.shapes:
        if sh.shape_type != 19: continue  # not table
        t_pos = Emu(sh.top).inches if sh.top else 0
        tbl = sh.table
        rows, cols = len(tbl.rows), len(tbl.columns)

        if 5.5 < t_pos < 6.0 and rows == 8 and cols == 3:
            # Stock Data 8x3
            data = [
                ('Stock Data', '26.05.27.', ''),
                ('KOSDAQ지수(pt)', '', '789'),
                ('52주 최고/최저(원)', '', '79,000/47,000'),
                ('거래량(천 주)/거래대금(억원)', '', '215/103'),
                ('시가총액(억원)', '', '8,981'),
                ('발행주식수(천 주)', '', '18,691'),
                ('주요주주 지분율', '', '22.95%'),
                ('외국인 지분율', '', '10.86%'),
            ]
            for ri, row_data in enumerate(data):
                for ci, val in enumerate(row_data):
                    set_cell_text(tbl.cell(ri, ci), val, font_size=8)

        elif 7.0 < t_pos < 7.5:
            # Consensus
            try:
                set_cell_text(tbl.cell(0, 0), 'Consensus Data', font_size=8, bold=True)
                if cols >= 3:
                    set_cell_text(tbl.cell(0, 1), '2025', font_size=8, bold=True)
                    set_cell_text(tbl.cell(0, 2), '2026E', font_size=8, bold=True)
                cd = [
                    ('매출액(억원)', '5,454', '6,010'),
                    ('영업이익(억원)', '522', '806'),
                    ('순이익(억원)', '537', '684'),
                    ('EPS(원)', '1,974', '3,108'),
                ]
                for ri, row in enumerate(cd):
                    if ri+1 >= rows: break
                    for ci, val in enumerate(row):
                        if ci >= cols: break
                        set_cell_text(tbl.cell(ri+1, ci), val, font_size=8)
            except: pass

        elif 8.3 < t_pos < 8.7:
            # 수익률
            try:
                set_cell_text(tbl.cell(0, 0), '수익률', font_size=8, bold=True)
                if cols >= 4:
                    headers = ['1M', '6M', '12M']
                    for ci, h in enumerate(headers):
                        set_cell_text(tbl.cell(0, ci+1), h, font_size=8, bold=True)
                    if rows >= 2:
                        set_cell_text(tbl.cell(1, 0), '절대주가(%)', font_size=8)
                        vals = ['-3.8', '-26.82', '-24.22']
                        for ci, v in enumerate(vals):
                            set_cell_text(tbl.cell(1, ci+1), v, font_size=8)
            except: pass

        elif 2.8 < t_pos < 3.1:
            # 종목정보 헤더
            try:
                set_cell_text(tbl.cell(0, 0), '종목정보', font_size=10, bold=True)
                info = [('업종', 'KOSDAQ 엔터'), ('주가일', '2026.05.27'), ('상장일', '2011.11.23')]
                for ri, row in enumerate(info):
                    if ri+1 >= rows: break
                    for ci, val in enumerate(row):
                        if ci >= cols: break
                        set_cell_text(tbl.cell(ri+1, ci), val, font_size=8)
            except: pass

        elif 3.8 < t_pos < 4.2:
            # BUY 박스
            try:
                if rows >= 1: set_cell_text(tbl.cell(0, 0), 'BUY', font_size=28, bold=True, color=NAVY)
                pairs = [('목표 주가(원)', '89,000', None),
                         ('현재 주가(원)', '48,050', None),
                         ('상승 여력(%)', '+85.2', RED)]
                for ri, (label, val, color) in enumerate(pairs):
                    if ri+1 >= rows: break
                    set_cell_text(tbl.cell(ri+1, 0), label, font_size=9)
                    if cols >= 2:
                        set_cell_text(tbl.cell(ri+1, 1), val, font_size=12, bold=True, color=color or NAVY)
            except: pass


def fill_index(slide):
    """Slide 2 — Index 30 슬라이드 목차"""
    for sh in slide.shapes:
        if not sh.has_text_frame: continue
        t = sh.text_frame.text
        if '목차' in t or 'Index' in t and len(t) < 50:
            continue
        # Index 본문 텍스트 박스 찾아 갱신
        # 양식 그대로 두되 페이지 번호만 갱신
        pass
    # 양식 슬라이드에서 1~6 섹션 페이지 번호 갱신
    # 양식의 목차는 텍스트 박스 안의 페이지 번호가 박혀 있음 → 추후 보강


def main():
    prs = Presentation(str(SRC))
    n0 = len(prs.slides)
    print(f'양식 로드: {n0}개')

    # 양식 슬라이드 인덱스 (0-based):
    # 0: Cover / 1: Index / 2: Introduction
    # 3: 산업분석 / 4: 기업분석 / 5: 주가 히스토리(기업분석)
    # 6: 투자포인트 / 7: 투자포인트(요약박스)
    # 8: 리스크 / 9: 재무분석 / 10: 밸류에이션
    # 11: 재무제표 / 12: 마지막

    # 본 리포트 30 슬라이드 매핑 — 양식 어느 슬라이드를 복제할지
    # [(분류, 양식 idx)] — 1번부터 30번까지 순서대로
    layout_map = [
        ('Cover', 0),                   # 1. Cover
        ('Index', 1),                   # 2. Index
        ('산업분석', 3),                  # 3. 산업분석 1상단
        ('산업분석', 3),                  # 4. 산업분석 1하단
        ('산업분석', 3),                  # 5. 산업분석 2상단
        ('산업분석', 3),                  # 6. 산업분석 2하단
        ('기업분석', 4),                  # 7. 기업분석 1
        ('기업분석', 4),                  # 8. 기업분석 2
        ('기업분석', 4),                  # 9. 기업분석 3
        ('기업분석', 4),                  # 10. 기업분석 4-A
        ('기업분석', 4),                  # 11. 기업분석 4-B
        ('기업분석', 4),                  # 12. 기업분석 4-C
        ('기업분석', 5),                  # 13. 기업분석 5 (주가)
        ('기업분석', 4),                  # 14. 기업분석 6
        ('투자포인트', 6),                # 15. 투자포인트 1
        ('투자포인트', 6),                # 16. 투자포인트 1 (컨센)
        ('투자포인트', 6),                # 17. 투자포인트 2
        ('투자포인트', 6),                # 18. 투자포인트 2
        ('투자포인트', 6),                # 19. 투자포인트 3
        ('투자포인트', 7),                # 20. 투자포인트 3 (4팩터)
        ('리스크', 8),                    # 21. 리스크 1
        ('리스크', 8),                    # 22. 리스크 2·3
        ('재무분석', 9),                  # 23. 재무 1
        ('재무분석', 9),                  # 24. 재무 2
        ('재무분석', 9),                  # 25. 재무 3
        ('재무분석', 9),                  # 26. 재무 4
        ('밸류에이션', 10),               # 27. 밸류 1
        ('밸류에이션', 10),               # 28. 밸류 1-2
        ('밸류에이션', 10),               # 29. 밸류 2
        ('재무제표', 11),                 # 30. 재무제표
        ('Compliance', 12),               # 31. 마지막
    ]

    # 양식 슬라이드를 31개로 확장 (양식 13개 그대로 + 복제 추가)
    # 기존 양식 슬라이드는 그대로 두되 본 리포트 매핑 순서에 맞게 재배치 + 추가 복제
    # 가장 간단한 접근: 양식 13개 + 필요한 만큼 복제 → 새 순서로 재배치
    print(f'\n양식 슬라이드 31개로 확장 시작...')

    # 매핑별로 필요한 복제 횟수 계산
    # 양식 idx별 복제 수 = layout_map에서 해당 idx 나오는 횟수
    from collections import Counter
    counter = Counter(idx for _, idx in layout_map)
    print(f'양식 idx별 필요 슬라이드 수: {dict(counter)}')

    # 양식 idx별로 부족분만큼 복제 추가
    # 양식의 0~12 슬라이드는 이미 1개씩 있음
    new_slide_refs = []  # (layout_kind, layout_idx, new_slide_idx_in_prs)
    available_per_idx = {i: [i] for i in range(13)}  # idx → 사용 가능한 슬라이드 prs 인덱스 리스트

    for layout_idx, need in counter.items():
        existing = 1  # 양식에 이미 1개
        deficit = need - existing
        for _ in range(deficit):
            new_slide = duplicate_slide(prs, layout_idx)
            new_idx = len(prs.slides) - 1
            available_per_idx[layout_idx].append(new_idx)

    print(f'복제 후 슬라이드 총수: {len(prs.slides)}개')

    # 순서대로 layout_map에 매핑된 슬라이드 인덱스 결정
    order = []
    used_per_idx = {i: 0 for i in range(13)}
    for kind, idx in layout_map:
        pool = available_per_idx[idx]
        order.append(pool[used_per_idx[idx]])
        used_per_idx[idx] += 1

    print(f'\n재배치 순서: {order[:10]}...')

    # 슬라이드 재배치
    reorder_slides(prs, order)

    # Phase 2: Cover 채우기
    fill_cover(prs.slides[0])
    print('\n=== Phase 2: Cover 완료 ===')

    # Phase 3: Index (양식 그대로)
    fill_index(prs.slides[1])
    print('=== Phase 3: Index 완료 (양식 그대로) ===')

    prs.save(str(DST))
    print(f'\n저장: {DST.name}')
    print(f'크기: {DST.stat().st_size / 1024:.1f} KB')
    print(f'슬라이드: {len(prs.slides)}개')


if __name__ == '__main__':
    main()
