"""
v11 — 우수 리포트 양식 그대로 PDF 빌더
- 클래시스/로킷헬스케어/SK하이닉스 17기 리포트 디자인 분석 결과 반영:
  · A4 세로 (595 x 842pt = 8.26 x 11.69in)
  · 폰트: 맑은 고딕 (헤더 20pt bold / 부제 13pt bold / 본문 10pt)
  · 좌측 카피 영역 = 페이지 폭의 24% (142pt)
  · 본문 영역 = 페이지 폭의 70% (412pt)
  · 도표 영역 = 페이지 하단 30~35% (양식 위닝펀드 표준)
- 워드 박스 35개 1:1 → PDF 38페이지
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import Color
from PIL import Image

# 한글 폰트 등록
pdfmetrics.registerFont(TTFont('Malgun', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBold', 'C:/Windows/Fonts/malgunbd.ttf'))

# A4 pt 좌표계 (595 x 842, 1in=72pt)
PAGE_W, PAGE_H = A4  # 595.27 x 841.89

# 색상
NAVY = (0x26/255, 0x83/255, 0xC6/255)  # 양식 정확 색 #2683C6 (클래시스 p5 RGB 분석)
RED = (0xC8/255, 0x10/255, 0x2E/255)
GREY_DARK = (0.27, 0.27, 0.27)
GREY = (0.55, 0.55, 0.55)
GREY_LIGHT = (0.85, 0.85, 0.85)
BLACK = (0, 0, 0)

# 좌표 (우수 리포트 분석값)
HEADER_X = 36
HEADER_Y = PAGE_H - 35   # 상단 헤더 (카테고리)
HEADER_FS = 18

SUBTITLE_X = 142
SUBTITLE_Y_FROM_TOP = 70
SUBTITLE_FS = 13

COPY_X = 36
COPY_Y_FROM_TOP = 105
COPY_W = 100
COPY_FS = 9

BODY_X = 142
BODY_W = PAGE_W - 142 - 41   # 412pt
BODY_Y_FROM_TOP = 105
BODY_FS = 10
BODY_LH = 14    # line-height

CHART_X = 36
CHART_W = PAGE_W - 36 - 36
PAGE_NO_X = PAGE_W - 50
PAGE_NO_Y = 25

OUT = Path('output/와이지엔터/18-1_와이지엔터테인먼트_PDF_v13.pdf')
BOXES_JSON = Path('scripts/_yg_v10_boxes.json')
CHARTS = Path('output/와이지엔터/_charts')


def hr_line(c, x1, y, x2, color=GREY_LIGHT, w=0.5):
    c.setStrokeColorRGB(*color)
    c.setLineWidth(w)
    c.line(x1, y, x2, y)


def _color(rgb):
    return Color(rgb[0], rgb[1], rgb[2])


def make_body_style(fs=10, lh=14, color=BLACK, bold=False, align=0):
    return ParagraphStyle(
        f'body_{fs}_{lh}',
        fontName='MalgunBold' if bold else 'Malgun',
        fontSize=fs,
        leading=lh,
        textColor=_color(color),
        alignment=align,
        spaceAfter=2,
    )


def _clean_body_text(text):
    """본문 정리 — 외부 증권사 인용 문구 자연스럽게"""
    replacements = [
        ('유진투자증권에 따르면 ', ''),
        ('유진투자증권에 따르면, ', ''),
        ('유진투자증권에 따르면', ''),
        ('iM증권에 따르면 ', ''),
        ('iM증권에 따르면, ', ''),
        ('iM증권에 따르면', ''),
        ('Hana증권에 따르면 ', ''),
        ('하나증권에 따르면 ', ''),
        ('SK증권에 따르면 ', ''),
        ('교보증권에 따르면 ', ''),
        ('한화투자증권에 따르면 ', ''),
        ('키움증권에 따르면 ', ''),
        ('NH투자증권에 따르면 ', ''),
        # 정리 — 외부 분석 인용 줄임
        ('증권가는 ', ''),
        ('증권업계는 ', ''),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _split_long_para(p, max_len=180):
    """긴 단락을 마침표 또는 적절한 위치에서 분할"""
    import re
    if len(p) <= max_len:
        return [p]
    parts = []
    cur = ''
    sentences = re.split(r'(?<=[다요죠음됨임함\.])\s+', p)
    for s in sentences:
        if len(cur) + len(s) + 1 > max_len:
            if cur: parts.append(cur)
            cur = s
        else:
            cur = (cur + ' ' + s) if cur else s
    if cur: parts.append(cur)
    # 여전히 너무 길면 강제 분할
    final = []
    for p2 in parts:
        if len(p2) <= max_len * 1.5:
            final.append(p2)
        else:
            # 콤마 위치 분할
            for chunk in p2.split(', '):
                final.append(chunk)
    return final


def draw_paragraph_in_frame(c, text, x, y_top, y_bot, w, fs=10, lh=14, color=BLACK,
                            subheads=None):
    """Frame 안에 Paragraph로 본문 + subheads (소제목) 자동 줄바꿈"""
    style = make_body_style(fs=fs, lh=lh, color=color)
    sub_style = make_body_style(fs=fs+1, lh=lh+2, color=NAVY, bold=True)
    paras = []

    # subheads가 있으면 (subhead, body) 페어로 그림
    if subheads:
        for sub_obj in subheads:
            head = sub_obj.get('subhead', '')
            body = _clean_body_text(sub_obj.get('body', ''))
            if head:
                head_esc = head.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                paras.append(Paragraph(head_esc, sub_style))
            for p in body.split('\n'):
                p = p.strip()
                if not p: continue
                for sub_p in _split_long_para(p, max_len=180):
                    sub_p = sub_p.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    paras.append(Paragraph(sub_p, style))
    else:
        text = _clean_body_text(text)
        for p in text.split('\n'):
            p = p.strip()
            if not p: continue
            for sub_p in _split_long_para(p, max_len=180):
                sub_p = sub_p.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                paras.append(Paragraph(sub_p, style))
    if not paras: return y_top
    h = y_top - y_bot
    frame = Frame(x, y_bot, w, h, leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0, showBoundary=0)
    frame.addFromList(paras, c)
    return y_bot


def draw_paragraph_simple(c, text, x, y_top, w, h, fs=10, lh=14, color=BLACK, bold=False):
    """Frame + Paragraph 본문"""
    style = make_body_style(fs=fs, lh=lh, color=color, bold=bold)
    paras = []
    for p in text.split('\n'):
        p = p.strip()
        if p:
            p = p.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            paras.append(Paragraph(p, style))
    if not paras: return
    frame = Frame(x, y_top - h, w, h, leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0, showBoundary=0)
    frame.addFromList(paras, c)


def short_copy(box_title):
    """박스 제목 → 좌측 카피 (12~18자 2줄)"""
    t = box_title.split('—')[0].split(':')[0].strip()
    return t[:30]


def header_label(cat):
    return {
        '산업': 'Industry Overview',
        '기업': 'Company Overview',
        '기업-주가': 'Company Overview',
        '투자': 'Investment Highlights',
        '리스크': 'Risk',
        '재무': 'Financial Overview',
        '밸류': 'Valuation',
    }.get(cat, '')


def header_kor(cat):
    return {
        '산업': '산업분석',
        '기업': '기업분석',
        '기업-주가': '기업분석',
        '투자': '투자포인트',
        '리스크': '리스크',
        '재무': '재무분석',
        '밸류': '밸류에이션',
    }.get(cat, '')


def categorize(slide_num):
    n = int(slide_num) if str(slide_num).isdigit() else 0
    if 3 <= n <= 6: return '산업'
    if 7 <= n <= 12: return '기업'
    if n == 13: return '기업-주가'
    if n == 14: return '기업'
    if 15 <= n <= 19: return '투자'
    if 20 <= n <= 21: return '리스크'
    if 22 <= n <= 25: return '재무'
    if 26 <= n <= 28: return '밸류'
    return '기업'


# 도표 매핑 — 박스당 도표 리스트 (1개 또는 2개)
# 2개면 좌우 분할 (우수 리포트 양식)
CHART_MAP = {
    0:  [('industry_consensus_vs_price', '도표 01.', '엔터 4사 영업이익 컨센 +6% vs 주가 -39%', '키움증권, NH투자증권')],
    1:  [('industry_ifpi', '도표 02.', 'IFPI 글로벌 음악산업 매출 11년', 'IFPI 2025')],
    2:  [('industry_triggers', '도표 03.', '회복 트리거 4가지', '키움증권(2026.05.07)'),
         ('industry_4comp', '도표 04.', 'K-POP 4사 12MF PER + 시총', 'FnGuide, WiseReport')],
    3:  [('m_4comp_lineup_full', '도표 05.', 'K-POP 4사 IP 라인업 — 4사 모두 9팀, 메가 IP 분포', '각 사 공식 데뷔 발표·분기보고서, 위닝펀드')],
    4:  [('m_yg_5y_structure', '도표 06.', 'YG 매출 부문별 5년 + OPM 정상화', 'FnGuide, DART, 위닝펀드')],
    5:  [('company_revenue_5y', '도표 07.', 'YG 매출 부문별 5년 (공연 7배)', 'FnGuide, DART')],
    6:  [('m_first5_albums', '도표 08.', 'YG IP 첫 5개 앨범 소요', 'DART')],
    7:  [('baemon_youtube', '도표 09.', '베몬 YT 1,200만 (K팝 최단)', 'iM증권(2026.04.15)'),
         ('company_comeback_cycle', '도표 10.', 'YG IP 평균 컴백 간격', 'DART')],
    8:  [],  # 도표 11 제거 (4사 양성 시스템 비교 — 사용자 요청)
    9:  [('m45_4comp_gen_ip', '도표 11.', 'K-POP 4사 두 문제 동시 해결 비교', 'WiseReport')],
    10: [('m30_5y_events', '도표 12.', '5년 주가 9개 이벤트 마킹', 'FDR, 공시, 위닝펀드 3조 황성혁')],
    11: [('ip_timeline', '도표 13.', '5종 IP 동시 가동 타임라인', 'DART, 공시')],
    12: [],  # 도표 14 제거 (5년 패턴 재현 베팅 박스 — 본문 길어서 도표 없음, 사용자 요청)
    13: [('m38_bigbang_tour', '도표 14.', '빅뱅 BIGSHOW 14개 도시 투어', 'iM증권(2026.04.15), 위닝펀드'),
         ('m_bigbang_coachella', '도표 15.', '코첼라 2026 톱5 (빅뱅 1,750만뷰)', '코첼라 공식, iM증권, 위닝펀드')],
    14: [('consensus_2027', '도표 16.', '컨센 2027E OP — 빅뱅 미반영', 'FnGuide 19개사')],
    15: [('m46_boygroup_6y', '도표 17.', '6년 만의 보이그룹 — 9월 5인조', 'YG 2026 PLAN')],
    16: [('m_newbie_schedule', '도표 18.', '하반기 신인·메가 IP 데뷔 타임라인', 'YG 2026 PLAN, 공시, 위닝펀드')],
    17: [('cash_ratio', '도표 19.', 'K-POP 4사 순현금/시총', 'FnGuide, 분기보고서')],
    18: [('m_6ip_matrix', '도표 20.', 'YG 6종 IP 분기별 활동 매트릭스', 'DART, 공시 일정, 위닝펀드')],
    19: [('z_score_4factor', '도표 21.', '4팩터 Z-Score (303종목 1등)', 'dacon-skills-dashboard'),
         ('per_historical', '도표 22.', '12MF PER — 역사적 하단', 'FnGuide, FDR')],
    20: [('m35_cycle_compare', '도표 23.', '블핑 vs 베몬 부상기 비교', 'FDR, 본 리포트')],
    21: [('m_risk_matrix', '도표 24.', '리스크 매트릭스 (Risk 1·4 우선)', '본 리포트 자체 산정, 위닝펀드')],
    22: [],
    23: [('m62_sept_scenario', '도표 25.', '9월 신인 데뷔 실패 시 시나리오', '본 리포트')],
    24: [('q1_revenue', '도표 26.', '1Q26 부문별 매출 (+46.9%)', 'WiseReport 1Q26')],
    25: [('supply_20d', '도표 27.', '20일 수급 — 바닥 분산', 'KIS API')],
    26: [('income_5y', '도표 28.', 'YG 5년 매출·영업이익', 'FnGuide')],
    27: [('m69_roe_dupont', '도표 29.', 'ROE 듀폰 분해 5년', 'FnGuide')],
    28: [('per_waterfall', '도표 30.', 'Target PER 24배 워터폴', '본 리포트, FnGuide')],
    29: [('eps_waterfall', '도표 31.', '2028E EPS 8단계 분해', '본 리포트')],
    30: [('m79_5_assumptions', '도표 32.', '5가지 보수 가정 매트릭스', '본 리포트'),
         ('cash_bridge', '도표 33.', '순현금 Bridge 4년', 'FnGuide, 본 리포트')],
    31: [('cash_bridge', '도표 34.', '순현금 Bridge 4년 — 누적 +2,607억', 'FnGuide, 본 리포트')],
    32: [('m83_ip_quarterly', '도표 35.', 'IP 라이프사이클', '본 리포트')],
    33: [('scenario_3', '도표 36.', 'Bear/Base/Bull 3시나리오', '본 리포트'),
         ('m88_price_ladder', '도표 37.', '가격 사다리', '본 리포트')],
    34: [('m89_buy_conclusion', '도표 38.', 'BUY 결론 — 호라이즌 2.5년', '본 리포트')],
}


def _adjust_source(source):
    """자체 제작 도표 출처 '위닝펀드 3조 황성혁' 통일 + 중복 제거"""
    s = source
    s = s.replace('본 리포트 자체 추정', '위닝펀드 3조 황성혁')
    s = s.replace('본 리포트 자체 산정', '위닝펀드 3조 황성혁')
    s = s.replace('본 리포트', '위닝펀드 3조 황성혁')
    # 마커로 보호하면서 단독 '위닝펀드' → '위닝펀드 3조 황성혁'
    s = s.replace('위닝펀드 3조 황성혁', '__WFHSH__')
    s = s.replace('위닝펀드', '__WFHSH__')
    s = s.replace('__WFHSH__', '위닝펀드 3조 황성혁')
    # 중복 제거 (인접 중복)
    while '위닝펀드 3조 황성혁, 위닝펀드 3조 황성혁' in s:
        s = s.replace('위닝펀드 3조 황성혁, 위닝펀드 3조 황성혁', '위닝펀드 3조 황성혁')
    return s


def draw_single_chart(c, png_path, chart_no, title, source, x, top_y, w, bottom_y, paired=False, fixed_line_y=None):
    """양식 통일 — 박스 없음 + 굵은 검정 가로선. fixed_line_y면 가로선 y 강제 (좌우 도표 동일화)"""
    source = _adjust_source(source)

    fs_caption = 9.5
    full_caption = f'{chart_no}  {title}'
    cap_width = c.stringWidth(full_caption, 'MalgunBold', fs_caption)
    c.setFont('MalgunBold', fs_caption)
    c.setFillColorRGB(*BLACK)
    if cap_width > w - 4:
        c.drawString(x, top_y - 11, chart_no)
        title_lines = []
        line = ''
        for ch in title:
            if c.stringWidth(line + ch, 'MalgunBold', fs_caption) > w - 4:
                title_lines.append(line)
                line = ch
            else:
                line += ch
        if line: title_lines.append(line)
        cur_y = top_y - 22
        for ln in title_lines:
            c.drawString(x, cur_y, ln)
            cur_y -= 11
        line_y = fixed_line_y if fixed_line_y is not None else (cur_y - 2)
        c.setStrokeColorRGB(*BLACK); c.setLineWidth(1.5)
        c.line(x, line_y, x + w, line_y)
        chart_top_y = line_y - 6
    else:
        c.drawString(x, top_y - 12, full_caption)
        line_y = fixed_line_y if fixed_line_y is not None else (top_y - 18)
        c.setStrokeColorRGB(*BLACK); c.setLineWidth(1.5)
        c.line(x, line_y, x + w, line_y)
        chart_top_y = line_y - 6

    # === 도표 이미지 ===
    src_top_y = bottom_y + 22
    chart_h_avail = chart_top_y - src_top_y - 4

    if png_path and Path(png_path).exists():
        try:
            im = Image.open(png_path)
            iw, ih = im.size
            if w * (ih / iw) <= chart_h_avail:
                draw_w = w * 0.96; draw_h = draw_w * (ih / iw)
                draw_x = x + (w - draw_w) / 2
                draw_y = chart_top_y - draw_h - (chart_h_avail - draw_h) / 2
            else:
                draw_h = chart_h_avail; draw_w = draw_h * (iw / ih)
                if draw_w > w: draw_w = w; draw_h = w * (ih / iw)
                draw_x = x + (w - draw_w) / 2
                draw_y = src_top_y + (chart_h_avail - draw_h) / 2
            c.drawImage(str(png_path), draw_x, draw_y, draw_w, draw_h, preserveAspectRatio=True)
        except Exception as e:
            print(f'  ! 도표 실패: {png_path}: {e}')

    # === 출처 위 굵은 검정 실선 ===
    c.setStrokeColorRGB(*BLACK); c.setLineWidth(1.5)
    c.line(x, bottom_y + 20, x + w, bottom_y + 20)

    # 출처 — 폭 초과 시 wrap
    c.setFont('Malgun', 7.5)
    c.setFillColorRGB(*BLACK)
    src_text = f'자료 : {source}'
    src_w = c.stringWidth(src_text, 'Malgun', 7.5)
    if src_w > w - 4:
        # 두 줄 wrap (글자 단위)
        line = ''
        cur_y = bottom_y + 10
        for ch in src_text:
            if c.stringWidth(line + ch, 'Malgun', 7.5) > w - 4:
                c.drawString(x, cur_y, line)
                cur_y -= 9
                line = ch
            else:
                line += ch
        if line:
            c.drawString(x, cur_y, line)
    else:
        c.drawString(x, bottom_y + 6, src_text)


def draw_charts(c, charts, top_y, bottom_y):
    """도표 리스트 → 1개면 단일 양식 / 2개면 좌우 분할 양식"""
    if not charts: return
    if len(charts) == 1:
        ch = charts[0]
        png = CHARTS / f'{ch[0]}.png'
        draw_single_chart(c, png, ch[1], ch[2], ch[3], CHART_X, top_y, CHART_W, bottom_y,
                         paired=False)
    else:
        # 2개+ 좌우 분할 — 두 도표 캡션 wrap 미리 계산해 가로선 y 동일화
        gap = 14
        half_w = (CHART_W - gap) / 2

        # 좌우 캡션 라인 수 계산 → 더 많은 줄 기준으로 line_y 결정
        def _count_caption_lines(chart_no, title, fs=9.5, max_w=half_w - 4):
            full = f'{chart_no}  {title}'
            if c.stringWidth(full, 'MalgunBold', fs) <= max_w:
                return 1  # 단일 줄
            # 도표번호 1줄 + 제목 wrap 줄
            lines = 1
            line = ''
            for ch in title:
                if c.stringWidth(line + ch, 'MalgunBold', fs) > max_w:
                    lines += 1
                    line = ch
                else:
                    line += ch
            if line: lines += 1
            return lines

        lines_l = _count_caption_lines(charts[0][1], charts[0][2])
        lines_r = _count_caption_lines(charts[1][1], charts[1][2])
        max_lines = max(lines_l, lines_r)
        # line_y 통일 (좌우 동일)
        if max_lines == 1:
            shared_line_y = top_y - 18
        else:
            # 도표번호 줄 + 제목 줄 N개 = top_y-11, -22, -33... 마지막 줄 끝 -2
            shared_line_y = top_y - 22 - (max_lines - 1) * 11 - 2

        # 좌측
        ch_l = charts[0]
        png_l = CHARTS / f'{ch_l[0]}.png'
        draw_single_chart(c, png_l, ch_l[1], ch_l[2], ch_l[3],
                         CHART_X, top_y, half_w, bottom_y, paired=True,
                         fixed_line_y=shared_line_y)
        # 우측
        ch_r = charts[1]
        png_r = CHARTS / f'{ch_r[0]}.png'
        draw_single_chart(c, png_r, ch_r[1], ch_r[2], ch_r[3],
                         CHART_X + half_w + gap, top_y, half_w, bottom_y, paired=True,
                         fixed_line_y=shared_line_y)
        # 세로 분리선 — 가로선 너머로 1.5pt 연장 (양 끝 가로선과 정확 만남)
        sep_x = CHART_X + half_w + gap / 2
        c.setStrokeColorRGB(*BLACK); c.setLineWidth(1.5)
        # 위 가로선 y=top_y-18 → 세로선이 y=top_y-19 (1pt 위까지)
        # 아래 가로선 y=bottom_y+16 → 세로선이 y=bottom_y+17 (1pt 아래까지)
        # ReportLab: y_high → y_low 순서 (top_y-19가 위 = y_high)
        c.line(sep_x, top_y - 19, sep_x, bottom_y + 17)


def get_layout(body_chars):
    """본문 글자 수에 따라 본문 / 도표 영역 비율 동적 — 양식 H=3.26 가까이"""
    # 페이지 가용 영역: y=130 ~ y=60 (양식 하단 가로선 y=34 + 26pt 여유)
    page_top = PAGE_H - 130
    page_bot = 60  # 40 → 60 (양식 하단 라인/로고와 충분 거리)
    total_h = page_top - page_bot

    # 도표 크기 우선 — body 약간 줄이고 chart 더 크게
    if body_chars < 700:
        body_h = 240; chart_h = 400
    elif body_chars < 1100:
        body_h = 330; chart_h = 300
    elif body_chars < 1500:
        body_h = 420; chart_h = 220
    elif body_chars < 2000:
        body_h = 460; chart_h = 180
    elif body_chars < 2500:
        body_h = 480; chart_h = 160
    elif body_chars < 3500:
        body_h = 480; chart_h = 160  # 박스 10 (5년 주가, 2700자) — 도표 크게 + 본문 일부 잘림 허용
    else:
        body_h = total_h - 10
        chart_h = 0

    body_top_y = page_top
    body_bot_y = body_top_y - body_h
    chart_top_y = body_bot_y - 15
    # 도표 하단은 page_bot 이상 보장
    chart_bot_y = max(page_bot, chart_top_y - chart_h) if chart_h > 0 else 0
    return dict(body_top=body_top_y, body_bot=body_bot_y,
                chart_top=chart_top_y, chart_bot=chart_bot_y,
                has_chart=(chart_h > 50))


def draw_combined_page(c, cat, box1, box2, charts, page_num, total_pages):
    """본문 2개 + 도표 좌우 분할 — P10 양식 (사용자 요청 합본)"""
    body1 = '\n'.join(s['body'] for s in box1['subs'])
    body2 = '\n'.join(s['body'] for s in box2['subs'])

    # 1. 상단 카테고리 헤더
    c.setFont('MalgunBold', HEADER_FS)
    c.setFillColorRGB(*NAVY)
    cat_kor = header_kor(cat)
    cat_en = header_label(cat)
    c.drawString(HEADER_X, HEADER_Y, cat_kor)
    c.setFont('Malgun', 10)
    c.setFillColorRGB(*GREY)
    en_w = c.stringWidth(cat_kor, 'MalgunBold', HEADER_FS)
    c.drawString(HEADER_X + en_w + 8, HEADER_Y + 2, cat_en)
    # (상단 구분선은 draw_top_logo에서 단일로 그림 — 중복 제거)

    # 2. 두 박스 본문 영역 — 상단/하단 각 H=180~200
    # 상단 본문 영역
    y_top1 = PAGE_H - 80
    body1_h = 200
    y_bot1 = y_top1 - body1_h - 10  # 박스 제목 + 본문

    # 상단 박스 제목
    c.setFont('MalgunBold', SUBTITLE_FS)
    c.setFillColorRGB(*NAVY)
    sub1 = box1['box_title']
    sub_lines = _wrap_str(c, sub1, BODY_W, 'MalgunBold', SUBTITLE_FS)
    for i, ln in enumerate(sub_lines):
        c.drawString(SUBTITLE_X, y_top1 - i * (SUBTITLE_FS + 4), ln)
    # 좌측 카피 1 (TPL_BLUE)
    copy1 = short_copy(box1['box_title'])
    draw_paragraph_simple(c, copy1, COPY_X, y_top1, COPY_W, 50,
                         fs=9, lh=11, color=NAVY, bold=True)
    # 본문 1 — 부제와 간격 축소
    body1_start = y_top1 - len(sub_lines) * (SUBTITLE_FS + 4) - 2
    draw_paragraph_in_frame(c, body1, BODY_X, body1_start, y_bot1, BODY_W,
                           fs=9.5, lh=12.5, color=BLACK)

    # 하단 본문 영역
    y_top2 = y_bot1 - 5
    body2_h = 200
    y_bot2 = y_top2 - body2_h - 10
    sub2 = box2['box_title']
    sub_lines2 = _wrap_str(c, sub2, BODY_W, 'MalgunBold', SUBTITLE_FS)
    for i, ln in enumerate(sub_lines2):
        c.drawString(SUBTITLE_X, y_top2 - i * (SUBTITLE_FS + 4), ln)
    copy2 = short_copy(box2['box_title'])
    draw_paragraph_simple(c, copy2, COPY_X, y_top2, COPY_W, 50,
                         fs=9, lh=11, color=NAVY, bold=True)
    body2_start = y_top2 - len(sub_lines2) * (SUBTITLE_FS + 4) - 2
    draw_paragraph_in_frame(c, body2, BODY_X, body2_start, y_bot2, BODY_W,
                           fs=9.5, lh=12.5, color=BLACK)

    # 3. 도표 영역 (페이지 하단)
    chart_top = y_bot2 - 12
    chart_bot = 60
    if charts:
        draw_charts(c, charts, top_y=chart_top, bottom_y=chart_bot)

    # 우상단 V 로고 + 하단 푸터
    draw_top_logo(c)
    draw_bottom_footer(c, page_num)


TPL_LINE = (0/255, 112/255, 192/255)  # 양식 가로선 정확 색


def draw_top_logo(c):
    """양식 상단 그래픽은 post-process에서 양식 PDF import — 페이지번호만"""
    pass


def draw_bottom_footer(c, page_num):
    """양식 하단 그래픽은 post-process에서 양식 PDF import — 페이지번호만"""
    c.setFont('Malgun', 9)
    c.setFillColorRGB(*BLACK)
    c.drawString(PAGE_W - 45, PAGE_H - 824, f'|   {page_num}')


def _wrap_str(c, text, w, font='MalgunBold', fs=13):
    """텍스트 줄바꿈 (한글)"""
    lines = []
    line = ''
    for ch in text:
        if c.stringWidth(line + ch, font, fs) > w:
            lines.append(line)
            line = ch
        else:
            line += ch
    if line: lines.append(line)
    return lines


def _force_body_full_page(body_chars):
    """도표 없는 박스 — 본문 전체 페이지 사용 (공백 제거)"""
    return 9999  # 큰 값 → get_layout이 chart_h=0 case 반환


def draw_body_page(c, cat, box_title, copy_text, body, page_num, total_pages,
                   chart_info=None, subheads=None):
    """본문 페이지 1장 그리기 (우수 리포트 양식)"""
    body_chars = len(body)
    # 도표 없는 경우 본문 전체 페이지 차지 (공백 제거)
    if not chart_info:
        body_chars = 9999
    L = get_layout(body_chars)

    # 1. 상단 카테고리 헤더 ("1. 산업분석 Industry Overview")
    c.setFont('MalgunBold', HEADER_FS)
    c.setFillColorRGB(*NAVY)
    cat_kor = header_kor(cat)
    cat_en = header_label(cat)
    c.drawString(HEADER_X, HEADER_Y, cat_kor)
    c.setFont('Malgun', 10)
    c.setFillColorRGB(*GREY)
    en_w = c.stringWidth(cat_kor, 'MalgunBold', HEADER_FS)
    c.drawString(HEADER_X + en_w + 8, HEADER_Y + 2, cat_en)

    # (상단 구분선은 draw_top_logo에서 단일로 그림 — 중복 제거)

    # 2. 부제 (박스 제목, 13pt bold, 본문 영역 시작)
    sub_y = PAGE_H - SUBTITLE_Y_FROM_TOP
    c.setFont('MalgunBold', SUBTITLE_FS)
    c.setFillColorRGB(*NAVY)
    sub_lines = []
    line = ''
    for ch in box_title:
        if c.stringWidth(line + ch, 'MalgunBold', SUBTITLE_FS) > BODY_W:
            sub_lines.append(line)
            line = ch
        else:
            line += ch
    if line: sub_lines.append(line)
    for i, ln in enumerate(sub_lines):
        c.drawString(SUBTITLE_X, sub_y - i * (SUBTITLE_FS + 4), ln)

    # 3. 좌측 카피 (TPL_BLUE 하늘색, Bold)
    copy_y = PAGE_H - COPY_Y_FROM_TOP
    if copy_text:
        draw_paragraph_simple(c, copy_text, COPY_X, copy_y, COPY_W, 80,
                             fs=9, lh=11, color=NAVY, bold=True)

    # 4. 본문 (Paragraph + Frame) — 부제와 간격 축소
    body_start_y = sub_y - len(sub_lines) * (SUBTITLE_FS + 4) - 2
    # 본문 폰트 크기 동적
    if body_chars < 1500:
        fs = 10; lh = 14
    elif body_chars < 2500:
        fs = 9.5; lh = 13
    else:
        fs = 9; lh = 12
    # 본문 영역 하단 = body_bot (도표 영역 위)
    body_bot_y = L['body_bot']
    draw_paragraph_in_frame(c, body, BODY_X, body_start_y, body_bot_y, BODY_W,
                           fs=fs, lh=lh, color=BLACK, subheads=subheads)

    # 5. 도표 (1개=전체폭 / 2개=좌우 분할)
    if chart_info and L['has_chart']:
        draw_charts(c, chart_info, top_y=L['chart_top'], bottom_y=L['chart_bot'])

    # 6. 우상단 V 로고
    draw_top_logo(c)
    # 7. 하단 footer 라인 + 위닝펀드 로고/페이지번호
    draw_bottom_footer(c, page_num)


def draw_cover(c, cover_boxes):
    """Cover 페이지 v3 — 좌측 종목정보/BUY 박스 + 우측 Summary/Highlights/Valuation 자동 fit"""
    # 상단 회사명
    c.setFont('MalgunBold', 24)
    c.setFillColorRGB(*NAVY)
    c.drawString(HEADER_X, PAGE_H - 80, '와이지엔터테인먼트 (122870)')
    c.setFont('Malgun', 12)
    c.setFillColorRGB(*GREY_DARK)
    c.drawString(HEADER_X, PAGE_H - 100, '5년 +190% 패턴, 다시 그릴 차례')

    # 상단 라인
    hr_line(c, HEADER_X, PAGE_H - 110, PAGE_W - HEADER_X, color=NAVY, w=1.5)

    # === 좌측 박스 (Stock Data + BUY 89,000원) ===
    box_x = HEADER_X
    box_y = PAGE_H - 135
    box_w = 200
    c.setFont('MalgunBold', 11)
    c.setFillColorRGB(*NAVY)
    c.drawString(box_x, box_y, '종목정보')
    info = [
        ('업종', 'KOSDAQ / 엔터'),
        ('주가 (5/27)', '48,050원'),
        ('상장일', '2011.11.23'),
        ('52주 최고/최저', '79,000 / 47,000원'),
        ('시가총액', '8,981억'),
        ('발행주식수', '18,691천주'),
        ('외국인 지분율', '10.86%'),
    ]
    c.setFont('Malgun', 9)
    c.setFillColorRGB(*GREY_DARK)
    for i, (k, v) in enumerate(info):
        c.drawString(box_x, box_y - 18 - i * 13, k)
        c.drawString(box_x + 95, box_y - 18 - i * 13, v)

    # BUY 박스
    buy_y = box_y - 130
    c.setStrokeColorRGB(*NAVY)
    c.setLineWidth(1.5)
    c.rect(box_x, buy_y - 75, box_w, 75, stroke=1, fill=0)
    c.setFont('MalgunBold', 22)
    c.setFillColorRGB(*NAVY)
    c.drawString(box_x + 12, buy_y - 30, 'BUY')
    pairs = [
        ('목표 주가', '89,000원', NAVY),
        ('현재 주가', '48,050원', None),
        ('상승 여력', '+85.2%', RED),
    ]
    for i, (k, v, col) in enumerate(pairs):
        y_off = buy_y - 45 - i * 12
        c.setFont('Malgun', 8.5); c.setFillColorRGB(*GREY_DARK)
        c.drawString(box_x + 12, y_off, k)
        c.setFont('MalgunBold', 10)
        c.setFillColorRGB(*(col or GREY_DARK))
        c.drawString(box_x + 85, y_off, v)

    # === 우측 영역 - Summary/Highlights/Valuation 자동 fit ===
    right_x = box_x + box_w + 18
    right_w = PAGE_W - right_x - HEADER_X
    avail_top = PAGE_H - 135
    avail_bot = 65
    avail_h = avail_top - avail_bot

    # 박스 분량 계산
    box_lens = []
    for box in cover_boxes:
        body = '\n'.join(s['body'] for s in box['subs'])
        # 한 줄당 약 50자 가정 (8pt × right_w)
        lines = sum(max(1, (len(p) // 50) + 1) for p in body.split('\n') if p.strip())
        box_lens.append((box, body, lines))

    # 각 박스 높이 = (avail_h - 박스 헤더3개*15) * (lines / total_lines)
    total_lines = sum(L[2] for L in box_lens)
    header_h = 14
    spacing = 6
    body_total_h = avail_h - len(cover_boxes) * (header_h + spacing)
    # 박스별 H 배분
    cur_y = avail_top
    for box, body, lines in box_lens:
        title = box['box_title']
        c.setFont('MalgunBold', 11)
        c.setFillColorRGB(*NAVY)
        c.drawString(right_x, cur_y, title)
        cur_y -= header_h

        box_h = body_total_h * (lines / total_lines) if total_lines > 0 else 100
        # 폰트 사이즈 자동 — 줄 수와 박스 H에 따라
        lh = max(9, box_h / lines) if lines > 0 else 11
        fs = min(8.5, lh - 1.5)
        draw_paragraph_simple(c, body, right_x, cur_y, right_w, box_h,
                             fs=fs, lh=lh, color=BLACK)
        cur_y -= box_h + spacing

    # Cover footer (양식 그대로 — WinningFund 로고만)
    draw_top_logo(c)
    draw_bottom_footer(c, 1)


def draw_index(c, body_boxes):
    c.setFont('MalgunBold', 22)
    c.setFillColorRGB(*NAVY)
    c.drawString(HEADER_X, PAGE_H - 80, '목차  Index')
    hr_line(c, HEADER_X, PAGE_H - 95, PAGE_W - HEADER_X, color=NAVY, w=1.5)

    sections = [
        ('1. 산업분석', 'Industry Overview', '3 - 6'),
        ('2. 기업분석', 'Company Overview', '7 - 15'),
        ('3. 투자포인트', 'Investment Highlights', '16 - 23'),
        ('4. 리스크', 'Risk', '24 - 26'),
        ('5. 재무분석', 'Financial Overview', '27 - 30'),
        ('6. 밸류에이션', 'Valuation', '31 - 37'),
        ('재무제표', 'Financial Statements', '38'),
    ]
    y = PAGE_H - 140
    for kor, eng, page in sections:
        c.setFont('MalgunBold', 14)
        c.setFillColorRGB(*NAVY)
        c.drawString(HEADER_X + 20, y, kor)
        c.setFont('Malgun', 11)
        c.setFillColorRGB(*GREY)
        kor_w = c.stringWidth(kor, 'MalgunBold', 14)
        c.drawString(HEADER_X + 20 + kor_w + 8, y + 1, eng)
        c.setFont('MalgunBold', 14)
        c.setFillColorRGB(*GREY_DARK)
        c.drawRightString(PAGE_W - HEADER_X - 10, y, page)
        # 점선
        c.setStrokeColorRGB(*GREY_LIGHT)
        c.setLineWidth(0.5)
        c.setDash(1, 2)
        c.line(HEADER_X + 200, y + 4, PAGE_W - HEADER_X - 50, y + 4)
        c.setDash()
        y -= 50

    # Index footer + 로고
    draw_top_logo(c)
    draw_bottom_footer(c, 2)


def draw_financial_statements(c, page_num):
    c.setFont('MalgunBold', HEADER_FS)
    c.setFillColorRGB(*NAVY)
    c.drawString(HEADER_X, HEADER_Y, '재무제표')
    c.setFont('Malgun', 10)
    c.setFillColorRGB(*GREY)
    c.drawString(HEADER_X + 70, HEADER_Y + 2, 'Financial Statements')
    hr_line(c, HEADER_X, HEADER_Y - 8, PAGE_W - HEADER_X, color=NAVY, w=1.5)

    # FnGuide 재무제표 스크린샷을 도표로 삽입 (하단 Compliance Notice 공간 확보)
    fng = Path('output/와이지엔터/_charts/m_fnguide_financials.png')
    draw_single_chart(
        c, fng, '도표 39.', 'YG 재무제표 요약 (손익계산서·재무비율·추정)', 'FnGuide',
        x=CHART_X, top_y=PAGE_H - 68, w=CHART_W, bottom_y=300,
    )

    draw_top_logo(c)
    draw_bottom_footer(c, page_num)


def main():
    print('=== v11 PDF 빌드 시작 ===\n')
    OUT.parent.mkdir(exist_ok=True, parents=True)

    with open(BOXES_JSON, encoding='utf-8') as f:
        boxes = json.load(f)
    cover_boxes = [b for b in boxes if b['slide_num'] == '1']
    body_boxes = [b for b in boxes if b['slide_num'] not in ('1', '2', '29')]
    print(f'박스: Cover {len(cover_boxes)} / 본문 {len(body_boxes)}')

    total_pages = 2 + len(body_boxes) + 1  # Cover + Index + 본문 + 재무제표

    c = canvas.Canvas(str(OUT), pagesize=A4)
    c.setTitle('와이지엔터테인먼트 기업분석 리포트')
    c.setAuthor('Winning Fund 18-1')

    # Page 1: Cover
    print(f'  Page 1: Cover')
    draw_cover(c, cover_boxes)
    c.showPage()

    # Page 2: Index
    print(f'  Page 2: Index')
    draw_index(c, body_boxes)
    c.showPage()

    # 합칠 박스 쌍 (사용자 요청: P8-9, P17-18, P19-20, P24-25, P27-28, P29-30)
    # 페이지 번호 → 박스 idx: P3=0, P4=1, ..., Pn = n-3
    # 합칠 idx 쌍 (현재 박스 인덱스)
    # 합본 — 중복 메시지 압축 (월가 시니어 애널리스트 의사결정):
    # (8, 9): 시스템 개편 + 4사 두 문제 동시 해결 — 메가 IP 양성·컴백 단축 핵심 통합
    COMBINED = {(5, 6), (8, 9), (14, 15), (16, 17), (21, 22), (24, 25), (26, 27)}
    combined_skip = {b for pair in COMBINED for b in pair if b != min(pair)}

    page_num = 3
    i = 0
    while i < len(body_boxes):
        if i in combined_skip:
            i += 1; continue
        pair = next(((a, b) for a, b in COMBINED if a == i), None)
        if pair:
            a, b = pair
            box1 = body_boxes[a]
            box2 = body_boxes[b]
            cat = categorize(box1['slide_num'])
            # 두 박스의 도표 합치기 (각 1개씩 → 좌우 분할)
            ch1 = CHART_MAP.get(a, [])
            ch2 = CHART_MAP.get(b, [])
            charts = (ch1 + ch2)[:2]  # 최대 2개 (좌우)
            draw_combined_page(c, cat, box1, box2, charts, page_num, 0)
            c.showPage()
            print(f'  P{page_num:2}: [합본] {cat} | {box1["box_title"][:25]} + {box2["box_title"][:25]}')
            i = b + 1
            page_num += 1
        else:
            box = body_boxes[i]
            cat = categorize(box['slide_num'])
            copy = short_copy(box['box_title'])
            # 박스 10 (5년 주가) — 9개 이벤트 1단락 압축 (도표 12 시각화 + 핵심 정보 유지)
            subs_for_render = box['subs']
            if i == 10:
                summary_para = (
                    '5년 주가를 펼치면 IP 사이클이 9개 변곡점으로 새겨져 있다(도표 12 마킹). '
                    '2021년 블랙핑크 정점(연말 55,700원) → 2022년 활동 공백·텐센트뮤직 평가손 -21% → '
                    '2023년 베이비몬스터 데뷔 발표 3단계 모멘텀(1·5·11월 +6/+17/+5%) → '
                    'BORN PINK 월드투어 누적 모객 180만으로 매출 사상 최대 5,692억 → '
                    '2024년 매출 -36% 절벽과 5년 절대 최저 30,200원 → '
                    '24.10~25.08 +190% 패턴 형성(37,000 → 107,400원) → '
                    '2025년 12월 평가손 재발 → 2026년 1Q 블핑 상반기 투어 무산 → '
                    '5월 CHOOM 흥행과 회복 시그널. '
                    '각 변곡점은 IP 라인업의 두께와 메가 IP 활동 여부에 정확히 동조했다.'
                )
                subs_for_render = []
                summary_inserted = False
                for s in box['subs']:
                    if any(ch in s.get('subhead', '') for ch in '①②③④⑤⑥⑦⑧⑨'):
                        if not summary_inserted:
                            subs_for_render.append({'subhead': '5년 주가 9개 변곡점 — IP 라인업과 동조',
                                                    'body': summary_para})
                            summary_inserted = True
                        continue
                    subs_for_render.append(s)
            body = '\n'.join(s['body'] for s in subs_for_render)
            chart_info = CHART_MAP.get(i, [])
            draw_body_page(c, cat, box['box_title'], copy, body,
                          page_num, 0, chart_info, subheads=subs_for_render)
            c.showPage()
            print(f'  P{page_num:2}: {cat} | {box["box_title"][:35]} ({len(body)}자)')
            i += 1
            page_num += 1
    total_pages = page_num

    # 마지막: 재무제표
    final_page = page_num
    print(f'  Page {final_page}: 재무제표')
    draw_financial_statements(c, final_page)
    c.showPage()
    total_pages = final_page

    c.save()
    print(f'\n저장: {OUT}')
    print(f'크기: {OUT.stat().st_size / 1024:.1f} KB / {total_pages}p')


if __name__ == '__main__':
    main()
