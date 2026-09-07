"""
와이지엔터 PPT v9 — 31 슬라이드 분할 빌드 (1 슬라이드 = 본문 1 + 큰 도표 1)
- v3/v8: 1 슬라이드 = 본문 2 + 도표 2 (빽빽, 본문-도표 겹침)
- v9: 본문 영역 H=2.80 + 도표 영역 H=6.50 (위닝펀드 우수 리포트 패턴)
- reorder 안 쓰고 빈 dst에 add_slide 방식 (Slide 8 캐시 버그 해소)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import shutil, tempfile
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
DST = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\18-1_와이지엔터테인먼트_기업분석리포트_v9.pptx')

# v9 새 좌표 (1 슬라이드 = 본문 1 + 도표 1)
COPY_L, COPY_T, COPY_W, COPY_H = 0.40, 0.85, 1.47, 1.20   # 좌측 카피 (위치+크기 확대)
BODY_L, BODY_T, BODY_W, BODY_H = 1.87, 0.85, 5.92, 2.80   # 본문 박스 (H 0.99 → 2.80)
CHART_L, CHART_T, CHART_W, CHART_H = 0.42, 4.25, 7.42, 6.50  # 도표 영역 H=6.50
CAPTION_T = 3.95   # 도표 캡션
SOURCE_T = 10.95   # 도표 출처


def add_blank_slide_from_template(dst, src_slide):
    """src의 layout을 가져와서 dst에 빈 슬라이드 추가 + shape 복제"""
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


def write_body(tf, subhead, body):
    """소제목(Navy 11pt bold) + 본문(8.5pt) — 본문 영역 H=2.80 활용"""
    tf.clear()
    p = tf.paragraphs[0]
    if subhead:
        r = p.add_run(); r.text = subhead
        r.font.size = Pt(11); r.font.bold = True; r.font.color.rgb = NAVY
        for line in body.split('\n'):
            p = tf.add_paragraph()
            r = p.add_run(); r.text = line
            r.font.size = Pt(9); r.font.color.rgb = GREY  # 9pt (8.5→9)
    else:
        r = p.add_run(); r.text = body
        r.font.size = Pt(9); r.font.color.rgb = GREY


def reposition_body_textbox(slide, kind):
    """양식의 상단/하단 본문 박스 중 상단만 남기고 크기 확대"""
    to_remove = []
    body_top = None
    copy_top = None
    for sh in slide.shapes:
        if not sh.has_text_frame: continue
        l = Emu(sh.left).inches if sh.left else 0
        t = Emu(sh.top).inches if sh.top else 0
        w = Emu(sh.width).inches if sh.width else 0
        txt = sh.text_frame.text

        # 본문 박스 (좌측 카피 옆 큰 박스, L>=1.5)
        if l >= 1.5 and 0.5 < t < 2.5 and w > 4.0:
            body_top = sh
        elif l >= 1.5 and 5.0 < t < 7.0 and w > 4.0:
            to_remove.append(sh)
        # 좌측 카피 (L<1.5)
        elif l < 1.5 and 0.8 < t < 1.8 and ('요약 제목' in txt or len(txt.strip()) < 30):
            copy_top = sh
        elif l < 1.5 and 5.5 < t < 6.3:
            to_remove.append(sh)

    # 본문 박스 크기 확대
    if body_top:
        body_top.left = Inches(BODY_L)
        body_top.top = Inches(BODY_T)
        body_top.width = Inches(BODY_W)
        body_top.height = Inches(BODY_H)
    if copy_top:
        copy_top.left = Inches(COPY_L)
        copy_top.top = Inches(COPY_T)
        copy_top.width = Inches(COPY_W)
        copy_top.height = Inches(COPY_H)

    # 하단 본문/카피 제거 (도표 영역과 충돌 방지)
    for sh in to_remove:
        sh._element.getparent().remove(sh._element)

    return body_top, copy_top


def fill_slide_v9(slide, header, copy_text, head, body_text):
    """v9 단일 본문 슬라이드 채우기"""
    # 1. 헤더 + 본문/카피 박스 reposition
    body_top, copy_top = reposition_body_textbox(slide, header)

    # 2. 헤더 텍스트 교체
    for sh in slide.shapes:
        if not sh.has_text_frame: continue
        l = Emu(sh.left).inches if sh.left else 0
        t = Emu(sh.top).inches if sh.top else 0
        if t < 0.5 and l < 1.0 and sh.text_frame.text.strip():
            set_text(sh.text_frame, header, font_size=18, bold=True, color=NAVY)

    # 3. 좌측 카피
    if copy_top and copy_text:
        set_text(copy_top.text_frame, copy_text, font_size=10, bold=True, color=GREY)

    # 4. 본문
    if body_top:
        write_body(body_top.text_frame, head, body_text)


def remove_unused_shapes(slide):
    """도표 영역 침범 GROUP/LINE 제거"""
    to_remove = []
    for sh in slide.shapes:
        l = Emu(sh.left).inches if sh.left else 0
        t = Emu(sh.top).inches if sh.top else 0
        w = Emu(sh.width).inches if sh.width else 0
        # GROUP 도표 placeholder
        if sh.shape_type == 6 and l < 1.0 and w > 5.0:
            to_remove.append(sh)
        # LINE — 도표 영역(T=3.50~11.10) 침범
        elif sh.shape_type == 9 and (3.50 < t < 11.10 or 0.7 < t < 0.95):
            to_remove.append(sh)
    for sh in to_remove:
        sh._element.getparent().remove(sh._element)


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


# ============== Cover (양식 idx 0 그대로) ==============
def fill_cover(slide):
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
            sections = [
                ('Summary', [
                    '- 핵심 베팅: 24.10~25.08 +190% 패턴이 26.08~27.07 빅뱅 20주년 + 9월 신인·NEXT MONSTER로 재현',
                    '- 1Q26 매출 +46.9%·OP +103.9%인데 주가는 3개월 -26.8%. 시장은 컨센 -5% 미달과 블핑 공백만 봤다',
                    '- 양현석 시스템 개편(작곡가 확충·안무 발주 2~3→10팀)으로 28년 한계 해소 중, 베몬이 첫 증거',
                    '- 12MF PER 15.9배 = 빅뱅 군 입대·버닝썬 당시 역사적 하단 구간',
                    '- 순현금 2,737억(시총 30%)·무차입. 어떤 IP 공백도 버티는 하방 안전판',
                ]),
                ('Investment Highlights', [
                    '1) 빅뱅 20주년 + 신인 2팀 = 24.10~25.08 +190% 패턴 재현. 빅뱅 BIGSHOW: REBORN 14개 도시 풀이어(2026.08~2027.01) + 9월 신인 5인조 + NEXT MONSTER 2027 상반기. 컨센 2027E OP 764억은 빅뱅 풀이어 미반영, 8월 일정 확정 시 4~6주 재상향 트리거',
                    '2) 단일 IP 리스크 시스템으로 해소. 6년 만의 보이그룹 9월 + NEXT MONSTER 2027 상반기. 베몬 미니 3집 CHOOM 초동 38.8만 자체 최고, 양현석 안무 2~3→10팀 확대 결과물',
                    '3) 순현금 2,737억 무너질 일 없는 회사. 시총 8,981억의 30%가 현금, OCF 909억·FCF 849억 흑자. 2024년 영업적자 해에도 NI 200억 유지',
                ]),
                ('Valuation', [
                    '24M Forward(2028E) 적정주가 89,000원 (2028E EPS 3,700원 × Target PER 24배). 현재가 48,050원 대비 상승여력 +85.2%, 도달 시점 2028년 말(2.5년 호라이즌)',
                    'Target PER 24배 = 4사 2028E Implied PER Median 13.5배 + IP 6종 분산 +5.0배 + 메가IP 양성 입증 +5.5배 덧셈 워터폴. 5가지 보수 가정 적용된 정직한 보수값',
                    '19개사 컨센 평균 78,789원 대비 +13% 높지만 EPS 시점 +19% × PER 보수 -5%의 정직한 분해. 1년+ 장기 보유 관점. 투자의견 BUY',
                ]),
            ]
            first = True
            for hdr, lines in sections:
                if first: p = tf.paragraphs[0]; first = False
                else: p = tf.add_paragraph()
                r = p.add_run(); r.text = hdr
                r.font.size = Pt(12); r.font.bold = True; r.font.color.rgb = NAVY
                for line in lines:
                    p = tf.add_paragraph()
                    r = p.add_run(); r.text = line
                    r.font.size = Pt(8.5)

    # 테이블 채우기 (v3 그대로)
    for sh in slide.shapes:
        if sh.shape_type != 19: continue
        t_pos = Emu(sh.top).inches if sh.top else 0
        tbl = sh.table
        rows, cols = len(tbl.rows), len(tbl.columns)

        if 5.5 < t_pos < 6.0 and rows == 8 and cols == 3:
            data = [
                ('Stock Data', '26.05.27.', ''),
                ('KOSDAQ지수(pt)', '', '789'),
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


# ============== v9 본문 (28 entries — 1 슬라이드 = 본문 1) ==============
# 각 entry: (헤더, 카피, 헤드, 본문)
# v3 CONTENT을 본문 1·2로 분할

CONTENT_V9 = []

# Slide 3-4: 산업분석 1 (워드 S3·S4)
CONTENT_V9.append(('산업분석 Industry Overview', '실적은 선방인데\n주가는 부진',
    '엔터 4사 -39%, 컨센은 +6%',
    'K-POP 산업이 1년 사이 가장 곤란한 자리에 와 있다. 글로벌 음악산업은 IFPI 기준 2014년 150억$ → 2025년 317억$로 11년간 두 배 넘게 자랐고, 스트리밍 부문이 220억$로 전체 69.6%를 차지하며 매년 6~10% 성장 중이다. 한국은 글로벌 음악산업 매출 7위로 올라섰고 미국 CD 판매 톱10 중 7개가 K-POP 앨범인 만큼 한국 기획사의 산업 내 위상은 분명히 높아진 상태다.\n\n문제는 산업이 자라는 동안 한국 엔터 4사 주가가 정반대로 움직였다는 점. 4사 합산 영업이익 컨센서스는 6개월 전 대비 +6% 상향됐는데도, 같은 기간 주가는 4사 평균 -39% 빠졌다. 12개월 선행 PER은 19배까지 내려와 2025년 25~30배 대비 한 단계 내려앉았다.'))
CONTENT_V9.append(('산업분석 Industry Overview', '한한령·모멘텀·반도체',
    '멀티플이 깎인 세 가지 이유',
    '산업 전문가들은 멀티플 하락의 원인을 세 축으로 분해한다. ① 한한령 해제 기대가 식었다. 2025년 EPEX 베이징·드림콘서트 베이징으로 중국 시장 개방 기대가 최고조에 달했으나, 2026년 1월 정부의 "해제까지 상당한 시간 소요" 정리로 중국 옵션 프리미엄이 통째로 빠졌다.\n\n② 다음 성장 트랙 부재. BTS 컴백 보유 하이브 제외 엔터 3사 평균 매출 성장률 전망은 +7.7%로 2022~2025년 +35~40% 대비 확연한 둔화.\n\n③ 외부 압도적 대체재. 삼성전자·SK하이닉스 합산 영업이익이 2025년 91조 → 2026년 579조 +500%, 반도체주 연초 대비 +112.8%. 이익 성장률 500%+ 반도체 대형주가 PER 10배 미만에서 거래되는 장세에서 연 10% 성장 엔터에 PER 20배 프리미엄을 지불할 자금은 자연히 줄어든다.'))

# Slide 5-6: 산업분석 2 (워드 S5·S6)
CONTENT_V9.append(('산업분석 Industry Overview', '하반기에 첫 단추가\n풀린다',
    '디레이팅이 영구가 아닌 이유 — 회복 트리거 4가지',
    '디레이팅이 영구적이라고 보기 어려운 이유는 회복 단서가 시장 안에 이미 나와 있기 때문. 키움증권 회복 트리거 4가지 — 산업 구조 카드 2 + 단기 카드 2.\n\n[카드 1] 콘텐츠 수익화: K-POP 강점인 고퀄리티 콘텐츠 제작 역량은 동시에 비용 부담 늘려 OPM 깎는 병목. 자체 예능을 무료 → 구독 모델로 돌리면 산업 전체 연 매출 잠재력 2.4조·영업이익 8,400억 새 시장.\n\n[카드 2] 글로벌 레이블 진출: 66조 글로벌 레이블 시장에서 한국 4사 360도 통합 모델이 글로벌 빅3 대비 협상력 확보. BTS 월투가 테일러 스위프트 대비 부가매출 효율 +49% 우위.\n\n[카드 3] 현지화 IP: 캣츠아이(북미)·앤팀(일본) 같은 K-POP 시스템 수출 레퍼런스.\n\n[카드 4] 메가 IP 컴백: 4가지 중 2026 하반기 가장 빨리 가시화 = 와이지 즉시 수혜.'))
CONTENT_V9.append(('산업분석 Industry Overview', '같은 산업\n4가지 비즈니스 모델',
    '하이브·SM·JYP·YG — 같은 산업 다른 사업',
    'K-POP은 한국 4사가 사실상 다 차지하고 있지만, 4사가 같은 사업을 하는 것은 아니다.\n\n하이브(시총 10.1조·PER 25배): BTS 단일 IP 의존도 75%까지 갔던 회사. BTS 군 복무 공백을 NewJeans·LE SSERAFIM·ENHYPEN 다종 IP로 메움, 캣츠아이(북미) 현지화 베팅. 어도어 분쟁으로 자체 양성 검증 의문.\n\nSM(시총 2.0조·PER 15배): 에스파·NCT·RIIZE 다종 IP, 일본·동남아 현지화 강점. RIIZE 정체로 차세대 메가 IP 의문.\n\nJYP(시총 2.17조·PER 16배): 트와이스·스트레이키즈 외 신규 부재. OPM 25.1% 업계 최고에도 PER 16배 정체.\n\nYG(시총 8,981억·PER 15.9배): 베이비몬스터로 차세대 후보 입증 + 9월 신인·NEXT MONSTER 6종 IP 분산. 4사 중 유일 "메가 IP 양성 + 컴백 효율화" 두 구조적 변화 동시 보유.'))

# Slide 7-8: 기업분석 1 (워드 S7·S8)
CONTENT_V9.append(('기업분석 Company Overview', 'K-POP을 만들어 파는\n28년',
    '이 회사를 한 문단으로',
    '와이지엔터테인먼트는 K-POP 아티스트라는 지식재산(IP)을 직접 발굴·트레이닝·제작해 음반·음원·콘서트·MD·글로벌 라이선싱으로 전 세계 팬덤에 파는 글로벌 엔터테인먼트 기업. 1996년 양현석 프로듀서가 설립(법인 1998년)했고 2011년 11월 코스닥 상장(122870).\n\n28년 라인업: 지누션(1997)·1TYM(2000)·세븐(2003)·빅뱅(2006)·2NE1(2009)·위너(2014)·아이콘(2015)·블랙핑크(2016)·트레저(2020)·베이비몬스터(2023). 특히 빅뱅과 블랙핑크는 동사의 정체성을 만든 두 메가 IP이며 한국 K-POP 글로벌화의 1세대 성공 사례.\n\n경영체제: 2019년 양현석 일선 후퇴 후 전문경영인 체제, 현재 양민석 단독 대표이사. 최대주주 양현석 외 5인 22.95%, 2대 주주 네이버 8.89%(VIBE 협업), 국민연금 5.05%.'))
CONTENT_V9.append(('기업분석 Company Overview', '음반·공연·음원·기타\n네 개의 수익원',
    '공연 매출이 1년 만에 7배 뛴 이유',
    '사업은 음반·상품 37%(2,018억), 공연 23%(1,264억), 음원 16%(872억), 기타(로열티·광고·출연) 24%(1,300억)로 구성.\n\n가장 주목할 부문은 공연 매출 2024년 170억 → 2025년 1,264억으로 1년 만에 7배 폭증 — 블랙핑크 DEADLINE 글로벌 투어(16개 도시·33회) 효과. "와이지 실적은 대형 IP 활동 사이클에 절대 연동된다"는 명제의 가장 강력한 증거.\n\n2024년 매출 -36% 추락도 블핑 한 팀이 쉬었기 때문, 2025년 매출 +49% 반등도 블핑이 돌아왔기 때문이다. 수출 비중도 2024년 38.9% → 2025년 56.9%로 18%p 점프. 내수보다 수출이 더 큰 글로벌 콘텐츠 기업 구조 완성.'))

# Slide 9-10: 기업분석 2 (워드 S9·S10)
CONTENT_V9.append(('기업분석 Company Overview', '감당 가능한 만큼만\n만들던 회사',
    '오래된 구조적 한계',
    '와이지엔터테인먼트는 오랫동안 "소수의 아티스트, 긴 컴백 주기"라는 한계를 안고 있었다. 양현석 본인도 인터뷰에서 인정했듯 회사가 동시에 감당할 수 있는 아티스트 수가 제한적이었고, 한 팀의 컴백과 다음 컴백 사이 공백이 길었다.\n\n빅뱅·블랙핑크 같은 메가 IP를 만드는 능력은 분명했지만 그 IP를 "몇 개"밖에 굴리지 못한다는 것이 구조적 한계. 보유 IP가 적으면 한 팀이 쉴 때 실적이 곧장 절벽. 2024년 매출 -36% 추락, 2026년 1분기 시장 실망 모두 이 구조에서 비롯.\n\n단일 IP 리스크는 외부 비판이 아니라 28년간 안고 온 내부 구조 문제. 더 큰 문제는 긴 공백기가 팬덤 이탈로 이어진다는 점. 진짜 숙제는 "메가 IP 만드는 능력은 유지하면서 컴백 주기를 어떻게 단축할 것인가"였다.'))
CONTENT_V9.append(('기업분석 Company Overview', '작곡가를 늘리고\n조직을 바꿨다',
    '시스템 개편 + 베이비몬스터 정량 증명',
    '그 구조가 지금 바뀌고 있다. 양현석은 최근 인터뷰에서 작곡가·프로듀서 인력 대폭 확충, 안무 발주를 통상 2~3팀에서 10팀 규모로 확대했다고 직접 밝혔다. 단순한 인력 충원이 아니라 여러 팀의 곡·안무 작업이 동시 진행될 인프라가 깔렸다는 뜻.\n\n프로듀서 중심 시스템 + 일본·태국·중국·서구권 연습생을 선발하는 글로벌 트레이닝 센터 신설. 양현석은 "1년 안에 새 IP 두세 개 데뷔" 목표 제시.\n\n메가 IP 양성 능력 정량 증명 — 베이비몬스터 2026.05 유튜브 구독자 1,200만 K팝 걸그룹 역대 최단, 5세대 걸그룹 1위·K팝 걸그룹 전체 3위. 미니 3집 CHOOM 초동 387,871장 자체 최고, 6일차 누적 58.7만. 뮤직비디오 공개 직후 유튜브 월드와이드 트렌딩 1위, 반나절 1,500만 뷰. iM증권은 베몬을 "차세대 메가 IP 후보"로 분류.'))

# Slide 11-12: 기업분석 3 (워드 S11·S12)
CONTENT_V9.append(('기업분석 Company Overview', '28년 매출 절벽 사이클이\n해소되는 첫 신호',
    '28년 매출 절벽 사이클의 구조적 해소',
    '와이지엔터테인먼트의 컴백 주기 문제는 단순한 운영 비효율이 아니라 회사 매출의 생존 변수였다. 2024년 매출 -36% 절벽은 그해 활동 IP가 사실상 트레저 한 팀뿐이었던 결과이며, 블랙핑크 그룹 활동 공백마다 같은 패턴이 반복됐다.\n\n실제로 5년 주가 차트를 펼치면 IP 활동 공백 구간마다 매출과 주가가 동시에 추락하는 사이클이 매번 등장한다. 컴백 주기를 줄였다는 것은 곧 매출 절벽이 재발할 확률을 구조적으로 낮췄다는 의미.\n\n베이비몬스터는 2024년 4월 데뷔 후 2년 1개월 만에 5개 앨범 발매. 평균 컴백 간격 약 5개월. 블랙핑크가 2016년 8월 데뷔 후 정규 1집까지 4년 2개월 걸린 것 대비 컴백 속도 5~6배 빠르다. 와이지엔터테인먼트가 28년간 안고 온 가장 큰 구조적 약점이 해소되는 첫 신호다.'))
CONTENT_V9.append(('기업분석 Company Overview', '6종 IP 포트폴리오\n완성으로 가는 길',
    '신인 2팀 데뷔 + 수익화 속도',
    '컴백이 잦아진 만큼 수익화 속도도 가팔라지고 있다. 유진투자증권에 따르면 베이비몬스터는 2025년 한 번의 실물 앨범 + 첫 월투·아시아 팬콘투어만으로 연 약 400억 MD 매출. 본격 컴백 전임에도 1Q26 베몬·트레저 합산 MD 매출 130억.\n\n2026년 6월부터 시작되는 베몬 2차 월드투어는 일본 6·아시아 8·오세아니아 3 총 18개 도시 27회차 규모, 도쿄돔 입성·빌보드 핫 100 차트인이 회사 공식 목표.\n\n9월 데뷔 5인조 신인 보이그룹은 양현석이 직접 심사한 "2026 YG SPECIAL AUDITION: GO! DEBUT" 결과물. 신인 걸그룹 NEXT MONSTER는 4인조 확정 — 호주 출신 15세 이벨리(유튜브 1,900만 뷰), 태국 14세 찬야, 케이시. 두 팀 데뷔하면 보유 IP는 빅뱅·블핑·트레저·베몬·신인 보이·NEXT MONSTER 6종으로 분산되어 한 팀이 쉬어도 다른 팀이 매출을 메우는 포트폴리오 헤지 완성.'))

# Slide 13-14: 기업분석 4 (워드 S13·S14, 양식 idx 5 주가 히스토리)
CONTENT_V9.append(('기업분석 Company Overview', '5년 주가에\nIP 사이클이 찍혀 있다',
    '주가는 라인업이 비면 빠지고, 차면 오른다',
    '와이지엔터테인먼트의 5년 주가를 펼치면 곧 IP 사이클의 그래프가 된다. 매크로 변동성이 아니라 "지금 어떤 IP가 활동 중인가"와 "다음 신인은 누구인가"가 주가를 좌우한다.\n\n2021년 블랙핑크 정점 → 연말 55,700원. 2022년 활동 공백 + 텐센트뮤직 평가손 → 연말 43,850원 -21%. 2023.01·05·11 베이비몬스터 데뷔 발표 모멘텀 — 1월 +6.16%·5월 +17%·11월 +5.09% 3단계 마킹. 2023년 BORN PINK 월드투어 누적 모객 180만 → 동사 매출 사상 최대 5,692억.\n\n2024년 블랙핑크 활동 멈추고 트레저 1팀 의존 → 매출 -35.9%. 주가 47,000원대 → 2024.09.10 30,200원(5년 일봉 절대 최저, FDR 실측). 2024.10~2025.08 +190% 패턴 형성: 37,000원 → 107,400원(25.08.21 정점, 5년 일봉 절대 최고). 베타 0.43 — IP 사이클이 가격을 결정한다는 정량 증거.'))
CONTENT_V9.append(('기업분석 Company Overview', '5종 IP 동시 가동\n28년 역사상 가장 두꺼운',
    '하반기 라인업 이미 채워졌다',
    '현재 주가는 "라인업이 비어 보이는" 국면의 저점. 1분기 블랙핑크 공백이 부각되며 52주 최저(47,000원)에 근접. 그러나 이 종목 주가는 라인업이 채워지면 오른다.\n\n하반기 라인업은 이미 발표로 채워져 있다 — 빅뱅·베이비몬스터·트레저·신인 보이그룹·신인 걸그룹 5종. 4분기에는 다섯 팀이 동시에 활동하는 28년 역사상 가장 두꺼운 라인업 구간이 펼쳐진다.\n\n시장이 "비어 보이는 저점"으로 읽는 지금이, 라인업 관점에서는 가장 두꺼운 구간 진입 직전이라는 점이 본 리포트의 출발점. 다섯 팀 동시 가동 4분기 + 빅뱅 풀이어 2027년 1월까지 이어지면 라인업의 두께 자체가 변한 회사로 시장이 다시 분류할 가능성이 열려 있다. "구조적 전환"의 의미: IP 1~2개 절대 연동 ±35% 변동성 모델에서, 5~6개 IP 분산 ±15% 변동성 모델로의 분류 변경.'))

# Slide 15-16: 투자포인트 1 (워드 S15 박스1·박스2)
CONTENT_V9.append(('투자포인트 Investment Highlights', '빅뱅 20주년 풀이어\n핵심 미반영 모멘텀',
    '빅뱅 20주년 월드투어 — +190% 패턴의 핵심 트리거',
    '본 리포트가 빅뱅 20주년 월드투어를 투자포인트 1번으로 두는 이유는 단순한 단일 이벤트 모멘텀이 아니다. 직전 사이클(2024.10~2025.08) 와이지 주가가 37,000원 → 107,400원 +190% 상승했을 때, 그 핵심 트리거가 바로 "메가 IP 그룹의 재계약과 월드투어"(블랙핑크 DEADLINE)였다. 이번 사이클(2026.08~2027.07)에서 그 자리를 빅뱅 20주년 월드투어가 대체한다.\n\n빅뱅 데뷔 20주년 월드투어 "BIGSHOW: REBORN"은 단발 이벤트가 아니라 2026년 8월부터 2027년 1월까지 14개 도시(아시아·북미·유럽·오세아니아)를 도는 6개월 풀이어 실적. 2026년 4월 코첼라 무대에서 태양·지드래곤·대성 3인이 직접 발표, 4월 21일 투어명 공개.\n\n빅뱅은 K-POP 2세대 최정상 IP로 객단가(평균 25만원+)와 모객력이 동사 보유 IP 중 최상위. 2세대 K-POP 거물이 18년 차에 글로벌 14개 도시 투어를 도는 것은 K-POP 산업 전체에서 매우 드문 사례.'))
CONTENT_V9.append(('투자포인트 Investment Highlights', '컨센서스 2027년이\n비어 있다',
    '라인업은 정해졌는데 숫자가 없다',
    'Hana증권은 베이비몬스터·트레저·빅뱅 월드투어 하반기 합산 모객 약 70만 명 가정하며 2026년 영업이익 935억 추정. 컨센서스(806억) 대비 +16% 높은 수준. 빅뱅 객단가 우위(평균 25만+)와 MD 동반 매출 근거. 2016년 빅뱅 10주년 투어가 한국·일본·홍콩에서만 100만+ 모객 전례 감안하면 20주년은 4대륙 확장으로 더 큰 규모.\n\n핵심은 컨센서스가 빅뱅 투어의 2027년 몫을 비워 두고 있다는 점. 컨센 2027년 영업이익 764억으로 2026년 806억보다 오히려 낮다 — 빅뱅 투어가 2027년 1월까지 이어지는 풀이어 실적이라는 사실이 미반영.\n\n증권사 모델이 2027년 갱신 못하는 이유는 투어 도시별·월별 일정이 5월 현재 미공시. 8월 투어 개막·일정 확정 시 4~6주 안에 2027년 컨센 재상향 트리거 작동. 라인업은 정해졌는데 숫자가 비어 있는 "시간차"가 본 리포트가 사고자 하는 핵심 미반영 모멘텀.'))

# Slide 17-18: 투자포인트 2 (워드 S16·S17)
CONTENT_V9.append(('투자포인트 Investment Highlights', '6년 만의 보이그룹\n그리고 신인 걸그룹',
    'IP 포트폴리오 구조적 확장 — 직전 사이클 베몬 데뷔 자리',
    '본 리포트가 9월 신인 보이그룹과 NEXT MONSTER를 투자포인트 2번으로 두는 이유는 직전 사이클 +190% 상승의 또 다른 핵심 트리거가 "베이비몬스터 정식 데뷔(2024.04)와 첫 월드투어 SEE YOU THERE 발표"였기 때문. 이번 사이클에서 그 자리를 9월 신인 보이그룹 데뷔와 NEXT MONSTER 2027 상반기 데뷔 예고가 대체한다.\n\n베몬 데뷔 발표 단계별 주가 반응(2023.01 +6%·2023.05 +17%·2023.11 +5%) 감안하면 9월 신인 보이그룹에서도 동일한 단계적 상승 예상.\n\n와이지엔터테인먼트는 2026년 9월 5인조 신인 보이그룹을 데뷔시킨다. 트레저(2020년) 이후 6년 만의 보이그룹이며, 양현석이 5월 4일 공식 블로그 "2026 YG PLAN"에서 직접 발표. 신인 걸그룹 NEXT MONSTER도 2027년 상반기 데뷔 예고. 보이그룹은 일본·아시아 공연·MD 시장의 핵심 수익원으로 K-POP 보이그룹은 일본 객단가가 걸그룹의 1.5배 수준.'))
CONTENT_V9.append(('투자포인트 Investment Highlights', '구조적 전환의 초입\n분류 변경에 베팅',
    '2024년형 매출 절벽 재발 확률을 구조적으로 낮춘다',
    '이 확장이 중요한 이유는 단일 IP 리스크를 구조적으로 줄이기 때문. 2024년 매출 36% 추락은 블랙핑크 한 팀이 쉬었기 때문. 보유 IP가 두세 개뿐이면 한 팀 공백이 곧 회사 전체 공백.\n\n그러나 빅뱅·블랙핑크·베이비몬스터·트레저에 신인 보이그룹과 걸그룹까지 더해지면 한 팀이 쉬어도 다른 팀이 매출을 메우는 포트폴리오 헤지가 작동. 베이비몬스터 CHOOM 초동 38.8만 장은 이 헤지가 이미 실적으로 작동하기 시작했음을 보여준다.\n\n바뀐 육성 시스템이 IP 개수를 늘리는 한, 2024년형 매출 절벽이 같은 강도로 재발할 확률은 분명히 낮아진다. 와이지엔터테인먼트를 단순 저점 매수가 아니라 구조적 전환의 초입으로 본다. 동사 보유 IP는 빅뱅(2세대)·블핑(3세대)·트레저(4세대)·베몬(4세대)·신인 보이(5세대)·NEXT MONSTER(5세대)로 다세대 분산. K-POP 4사 중 가장 두꺼운 세대별 분산 포트폴리오.'))

# Slide 19-20: 투자포인트 3 (워드 S18·S19)
CONTENT_V9.append(('투자포인트 Investment Highlights', '시가총액 30%가 현금\n무너질 일 없는 회사',
    '순현금 2,737억 — 무차입이 만드는 하방 안전판',
    '와이지엔터테인먼트는 2025년 말 기준 순현금(현금성 자산 - 차입금) 2,737억 원 보유. 총차입금은 72억에 불과해 사실상 무차입이며 부채비율 28.9%. 시가총액 8,981억의 약 30%가 차감 대상 현금 — K-POP 4사 중 가장 보수적 재무구조 (하이브 순현금/시총 5%, JYP 28%, SM 17%).\n\n영업현금흐름(CFO) 2025년 909억, 잉여현금흐름(FCF) 849억 흑자 기조. 엔터테인먼트 종목은 IP 활동에 따라 실적 변동성이 크지만 와이지엔터테인먼트는 그 변동성을 견딜 재무 체력을 갖췄다. 실제로 영업적자를 낸 2024년에도 당기순이익 200억 원 안팎 유지 — 현금 베이스 덕분이다.\n\n신용평가 등급은 회사채 미발행으로 부여 대상 아니지만(분기보고서 명시), 유동비율 270%·이자보상배율 사실상 무한대로 엔터 업종 내 최상위 재무 건전성.'))
CONTENT_V9.append(('투자포인트 Investment Highlights', '4팩터 모델도 1등\n12MF PER 15.9배 역사적 하단',
    '재평가 과정 — 외부 정량 모델·역사 패턴 모두 매수 신호',
    '외부 정량 모델 검증: 본 리서치 작성자가 별도로 운영하는 정량 가치투자 대시보드(dacon-skills-dashboard)에서 와이지엔터테인먼트는 KOSPI·KOSDAQ 303종목 중 1등 STRONG_BUY 등극(2026.05 기준). PER·PBR 4팩터 Z-Score: s1_per 1.37·s1_pbr 1.11·s3_per 0.73·upside 1.47. Value Z 1.49 + Growth Z 1.94 = Total Z 1.67 최상위권.\n\n역사 패턴 매핑: 현재 12개월 선행 PER 15.9배는 빅뱅 군 입대(2017~19)·버닝썬 사건(2019) 당시 형성된 역사적 하단(PER 13~16배)과 유사한 구간. 과거 그 하단에서 블랙핑크(2016 데뷔)가 차세대 메가 IP로 부상하며 주가 +50~100% 멀티플 리레이팅 → 본 사이클에서 베이비몬스터 + 9월 신인 보이그룹이 동일 매핑.\n\n5월 CHOOM → 6월 베몬 월투·트레저 신보 → 8월 빅뱅 → 9월 신인 보이 → 10월 베몬 정규 2집 + 신인 걸 — 12개월 카탈리스트 빼곡하다.'))

# Slide 21-22: 리스크 (워드 S20·S21)
CONTENT_V9.append(('리스크 Risk', '블랙핑크 활동 시기\n회사가 통제 불가',
    '리스크 1 — 단일 IP 통제 불가',
    '가장 큰 리스크는 블랙핑크의 그룹 활동 시기를 회사가 통제하지 못한다는 점. 1분기 실망의 직접 원인도 블랙핑크의 상반기 추가 투어 무산이었다.\n\n블랙핑크는 2023년 12월 그룹 활동에 한해 재계약했고 개별 활동(지수·로제·제니·리사)은 별도 소속사가 관리하기 때문에 그룹 활동의 시기와 강도는 회사가 결정할 수 없는 변수. 2024년형 장기 공백이 재현되면 매출이 다시 흔들릴 수 있다.\n\n다만 본 리포트 핵심 논지대로 베이비몬스터·트레저·빅뱅·신인 라인업이 그 공백을 부분적으로 상쇄하며, 연간 매출이 2024년처럼 -36% 추락할 확률은 5종 IP 체제에서 분명히 낮아졌다. 2024년에는 보유 활동 IP가 사실상 트레저 1팀뿐이었지만, 2026 하반기에는 5팀이 동시 가동된다.'))
CONTENT_V9.append(('리스크 Risk', '영업외 평가손익\n신인 비용 + 보이그룹',
    '리스크 2·3·4 — 영업외 / 신인 비용 / 보이그룹 실패 시',
    '리스크 2 영업외 평가손익: 텐센트뮤직 지분과 20여 개 신기술투자조합의 공정가치 평가손익이 분기마다 순이익을 흔든다. 1Q26 텐센트뮤직 평가손실 약 70억 원이 순이익 압박. 일회성이 아니라 구조적 변동성.\n\n리스크 3 신인 비용 선행: 9월 신인 보이그룹과 베이비몬스터 글로벌 활동 비용이 상반기 먼저 들어오면서 마진 압박, 본격 수익 인식은 3분기 이후.\n\n리스크 4 9월 신인 보이그룹 데뷔 실패 시 시나리오 무효화: 데뷔 후 6개월 내 음반 판매량 20만 장 미만, 빌보드·오리콘·멜론 미진입, MV 1주 1억 뷰 미달 또는 멤버 이슈 발생 시 양성 시스템 반복 가능성 가설이 흔들린다. Target PER 24배 → 22배 회귀하고 적정주가 89,000원 → 78,000원 하향 조정 가능. 메인 시나리오 아니지만 정직하게 인지 — 2026.12 1차 점검·2027.03 재확인.'))

# Slide 23-24: 재무분석 1 (워드 S22·S23)
CONTENT_V9.append(('재무분석 Financial Overview', '1Q26 외형 두 배\n주가는 반토막',
    '1분기 실적의 진짜 구조 — 영업 정상 / 영업외 변동성',
    '와이지엔터테인먼트의 2026년 1분기 매출 1,471억(+46.9%), 영업이익 194억(+103.9%)으로 외형과 수익성 모두 두 배 가까이 성장. 핵심 견인 요인은 블랙핑크 DEADLINE 앨범의 폭발적 판매 — 초동 177.5만 장 자체 최고, 한터차트 총 194.3만 장, 일본·해외 판매와 구보 포함 전사 분기 판매량 약 210.6만 장. 1Q26 앨범 매출 252억 +323.7%, 콘서트 매출 309억 +313.0%.\n\n그러나 지배주주순이익은 영업이익을 크게 밑돌았다. 이유는 영업 바깥에 있다. 텐센트뮤직 지분 평가손실 약 70억이 영업외손익으로 잡히며 순이익을 깎았다.\n\n재무제표는 두 권으로 읽어야 한다 — 영업이 버는 돈의 장부는 정상화됐고, 흔드는 것은 영업 바깥의 평가손익. 시장은 영업이익보다 NI 흔들림에 더 민감하게 반응했고 1분기 -5% 미스에 주가 -27% 빠졌다.'))
CONTENT_V9.append(('재무분석 Financial Overview', '외국인은 나가고\n개인이 받는 저점',
    '수급 — 전형적인 바닥 분산 국면',
    '수급은 전형적인 바닥 분산 국면. 최근 20일간 외국인 5.95만주, 기관 38.5만주 순매도(현재가 환산 약 214억), 개인이 44.1만주(약 212억)를 거의 그대로 받아냈다.\n\n외국인 지분율은 1년 전 약 14%에서 10.86%로 하락 — 1분기 실망 국면에서 외국인이 구조적으로 이탈했음을 보여준다.\n\n외국인과 기관이 던진 물량을 개인이 흡수하는 구간은 통상 바닥 근처에서 나타난다. 본 리포트는 외국인 지분율이 12% 이상으로 회복되거나 외국인·기관이 20일 누적 순매수로 전환되는 시점을 투자 논지 재확인 신호로 본다.\n\n수급은 펀더멘털 회복보다 통상 후행한다 — 1Q26 영업이익이 +104% 회복됐는데 수급은 아직 매도 우위라는 점은, 펀더멘털과 수급 사이의 시간차가 곧 매수 기회임을 시사한다.'))

# Slide 25-26: 재무분석 2 (워드 S24·S25)
CONTENT_V9.append(('재무분석 Financial Overview', '버는 힘은 정상\n무너질 일은 없다',
    '5년 손익과 재무구조',
    '와이지엔터테인먼트의 5년 손익을 보면 IP 사이클의 진폭이 그대로 드러난다. 매출은 2023년 5,692억 → 2024년 3,649억으로 줄었다가 2025년 5,454억으로 회복했고, 영업이익률(K-IFRS 기준)은 2024년 -5.1%에서 2025년 9.6%로 흑자 전환. 컨센서스는 2026년 영업이익률 13.4%로 본다 — 진폭은 크지만 추세는 정상화 중.\n\n재무구조는 견고. 순현금 2,737억, 부채비율 28.9%, 유동비율 270%로 엔터 업종 내 최상위 수준.\n\n재무 위험의 본질은 부실이 아니라 IP 사이클과 영업외 평가손익의 변동성. 영업적자를 낸 2024년에도 당기순이익 200억 안팎 유지한 것이 이 현금 베이스의 직접 효과.'))
CONTENT_V9.append(('재무분석 Financial Overview', 'ROE 회복의 열쇠는\n영업 바깥에 있다',
    '듀폰 분해 — 영업외 변동성 안정화 시 두 자릿수 회복',
    '2025년 자기자본이익률(ROE) 7.4%로 2023년 14.0%의 절반 수준. 듀폰 분해(ROE를 순이익률·자산회전율·재무레버리지 셋으로 쪼개서 보는 방식)로 보면 하락 원인은 순이익률이며, 그 순이익률 하락은 영업이 아니라 영업외 평가손실에서 비롯됐다.\n\n바꿔 말하면 ROE 회복의 열쇠는 영업외 변동성의 안정화에 있다. 컨센서스는 2026년 ROE 10.8% 본다.\n\n빅뱅 투어와 신인 라인업으로 영업이익 정상화되고 영업외 손실 진정되면 ROE는 두 자릿수 회복 여지 충분. 차입금 과다, 매출채권 급증, 영업현금흐름 적자 같은 레드 플래그 점검에서도 모두 양호로 확인.'))

# Slide 27-28: 밸류에이션 1 (워드 S26 박스1·박스2)
CONTENT_V9.append(('밸류에이션 Valuation', '애널리스트 평균이 아닌\n자체 산출',
    '왜 자체 산출인가 — 증권사 단일 PER 산식의 한계',
    '와이지엔터테인먼트는 단일 지표로 평가하기 어려운 회사. 첫째, 순이익이 영업외 평가손익으로 분기마다 흔들려 후행 PER가 왜곡. 둘째, 베타 0.43으로 낮아 순수 DCF는 발산하기 쉽다. 셋째, 순현금 2,737억 자산 베이스가 따로 있어 PER만 보면 사업 가치를 제대로 못 잡는다.\n\n증권사 19개사는 모두 "Target Forward PER × 2026 EPS = 목표주가" 단일 산식 사용. 목표가 70,000~120,000원 분포·평균 78,789원(WiseReport 2026.05.18).\n\n본 리포트는 컨센 평균을 그대로 옮겨 쓰지 않는다 — 그건 애널리스트 리포트가 아니라 리스트. 대신 ① 2028E EPS 8단계 분해 산출, ② Target PER 24배 정량 워터폴, ③ EPS × PER 산식으로 적정주가 89,000원 도출. 시점도 다르다 — 증권사는 12M Forward(2026E EPS), 본 리포트는 24M Forward(2028E EPS) 채택.'))
CONTENT_V9.append(('밸류에이션 Valuation', '2028E EPS 3,700원\nTarget PER 24배',
    '적정주가 89,000원 — 8단계 분해 + Premium 덧셈 워터폴',
    '2028E EPS 8단계 분해: Step 1 매출 5,454억 → 7,000억(+28.3%). Step 2 OPM 2025 발표기준 13.1%(연결 9.6%) → 2028E 16%(+2.9%p, 활동기 정점 2023 15.3% 살짝 상회). Step 3 영업이익 1,120억. Step 4 영업외 -190 → +30억 정상화. Step 5 세전 1,150억. Step 6 법인세 25% → 세후 862.5억. Step 7 지배 80% → 690억. Step 8 EPS 3,691 ≒ 3,700원(채택). 컨센 2028E EPS 3,465원 대비 +6.8% 적극.\n\nTarget PER 24배 덧셈 워터폴: 4사 2028E Implied PER Median 13.5배 + IP 6종 분산 Premium +5.0배 + 메가IP 양성 입증 Premium +5.5배 = 24.0배(활동기 평균 27.5배 하단).\n\n산식: 3,700 × 24 = 88,800 ≒ 89,000원. 도달 시점 2028년 말(2.5년 호라이즌).'))

# Slide 29-30: 밸류에이션 2 (워드 S27·S28)
CONTENT_V9.append(('밸류에이션 Valuation', '89,000원이 정직한\n보수값인 이유',
    '5가지 보수 가정 + 순현금 Bridge',
    '본 리포트의 89,000원이 19개사 컨센 평균(78,789원) 대비 +13% 높다는 사실은 종종 "적극적이다"라고 평가되지만, 실상은 5가지 보수 가정이 적용된 정직한 보수값.\n\n① 9월 신인 보이그룹: 24M 50%만 반영(베몬 24M K-POP 걸그룹 3위 도달 패턴 차용). ② NEXT MONSTER: 2027 상반기 데뷔 가정 하 2028E 12M 25%만 반영. ③ 텐센트뮤직 평가손익 +30억 정상화만, 2021년 고점(+200억) 회복은 미반영. ④ 한한령 해제 옵션 0% 미반영(2016 빅뱅 중국 박스오피스 1위 930억 회복 가치 제외). ⑤ Target PER 24배는 활동기 평균 PER 27.5배 하단.\n\n위 5가지 보수 가정에도 도출된 89,000원. 가정 하나만 풀려도 자연스럽게 상향 — 9월 보이그룹 40→60% 시 94,000원, 한한령 부분 해제 시 100,000+.\n\n순현금 Bridge 4년 시계열: 2025A 2,737억 → 2026E 3,614 → 2027E 4,434 → 2028E 5,344억. 절대 누적 +2,607억 — 하방 안전판이 매년 강화되는 구조.'))
CONTENT_V9.append(('밸류에이션 Valuation', '저자의 핵심 베팅\nBUY (호라이즌 2.5년)',
    '5년 주가 패턴 재현 + 9월 보이그룹 검증 시험대',
    '저자는 와이지의 오랜 팬으로서 이 회사의 양성 능력을 굳건히 믿고 있다. 빅뱅·2NE1·블랙핑크·트레저·베이비몬스터로 이어지는 라인은 매 세대마다 글로벌 톱 메가 IP를 만들어 낸 28년 트랙 레코드. 여기에 2024.10~2025.08 +190% 상승 패턴이 이미 5년 주가 차트에 정량적으로 새겨져 있다.\n\n9월 신인 보이그룹 데뷔는 본 리포트 매수 관점의 결정적 시험대. 베이비몬스터 한 번의 성공만으로 "시스템"이라 단정할 수는 없고, 9월 5인조가 두 번째 증거가 되어야 한다. 음반 50만+ 또는 글로벌 차트 진입 시 시장은 "와이지 양성 시스템 = 반복 가능"으로 재평가하고 멀티플 22→24배 리레이팅.\n\n적정주가 89,000원은 도달 목표 시점 2028년 말(2.5년 호라이즌), 연 환산 +27%/년. 단기 변동성을 견디고 1년 이상 보유할 수 있는 투자자에게만 의미 있는 적정값. 투자의견 BUY 유지: 컨센 대비 +13%.'))


# ============== Layout map (31장) ==============
LAYOUT_MAP_V9 = [
    ('Cover', 0),
    ('Index', 1),
    # 산업 4장 (idx 3)
    ('산업', 3), ('산업', 3), ('산업', 3), ('산업', 3),
    # 기업 8장 (idx 4·5)
    ('기업', 4), ('기업', 4), ('기업', 4), ('기업', 4),
    ('기업', 4), ('기업', 4), ('기업-주가', 5), ('기업-주가', 5),
    # 투자 6장 (idx 6)
    ('투자', 6), ('투자', 6), ('투자', 6), ('투자', 6), ('투자', 6), ('투자', 6),
    # 리스크 2장 (idx 8)
    ('리스크', 8), ('리스크', 8),
    # 재무 4장 (idx 9)
    ('재무', 9), ('재무', 9), ('재무', 9), ('재무', 9),
    # 밸류 4장 (idx 10)
    ('밸류', 10), ('밸류', 10), ('밸류', 10), ('밸류', 10),
    # 재무제표 1장
    ('재무제표', 11),
]


def main():
    print('=== v9 빌드 시작 ===\n')
    src = Presentation(str(SRC))
    print(f'양식 로드: {len(src.slides)}장')

    # dst를 src 복사로 시작 (master/layout 공유)
    tmp = tempfile.NamedTemporaryFile(suffix='.pptx', delete=False)
    tmp.close()
    shutil.copy(SRC, tmp.name)
    dst = Presentation(tmp.name)

    # dst의 모든 슬라이드 제거
    sldIdLst = dst.slides._sldIdLst
    while len(list(sldIdLst)) > 0:
        sld = list(sldIdLst)[0]
        rId = sld.get(qn('r:id'))
        dst.part.drop_rel(rId)
        sldIdLst.remove(sld)
    print(f'dst 초기화: {len(dst.slides)}장 (빈 PPT, master/layout 공유)')

    # layout_map 순서대로 양식 슬라이드 복제 추가
    print(f'\n=== 31장 빌드 ({len(LAYOUT_MAP_V9)}장 매핑) ===')
    for i, (kind, src_idx) in enumerate(LAYOUT_MAP_V9):
        src_slide = src.slides[src_idx]
        new_slide = add_blank_slide_from_template(dst, src_slide)
        print(f'  Slide {i+1}: {kind} (양식 idx {src_idx})')

    print(f'\n빌드 완료: {len(dst.slides)}장')

    # Cover (idx 0)
    print('\n=== Cover 작성 ===')
    fill_cover(dst.slides[0])

    # Index — 양식 그대로

    # 본문 슬라이드 (idx 2 ~ 29)
    print('\n=== 28장 본문 채우기 ===')
    for i, content in enumerate(CONTENT_V9):
        slide_idx = i + 2  # Cover, Index 제외
        if slide_idx >= len(dst.slides) - 1: break  # 재무제표 제외
        slide = dst.slides[slide_idx]
        remove_unused_shapes(slide)
        fill_slide_v9(slide, *content)
        print(f'  Slide {slide_idx+1}: {content[0]} — {content[2][:30]}...')

    # 페이지 번호
    update_page_no(dst)

    dst.save(str(DST))
    print(f'\n저장: {DST.name}')
    print(f'크기: {DST.stat().st_size / 1024:.1f} KB')
    print(f'슬라이드: {len(dst.slides)}장')


if __name__ == '__main__':
    main()
