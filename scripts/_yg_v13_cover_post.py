"""v13 Cover 후처리 — 양식 PDF P1 통째 import + placeholder 텍스트만 overlay"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import fitz
from pathlib import Path

V13 = 'output/와이지엔터/18-1_와이지엔터테인먼트_PDF_v13.pdf'
TMPL = 'output/와이지엔터/_template_check.pdf'
BOXES_JSON = 'scripts/_yg_v10_boxes.json'

# 색상
TPL_BLUE = (38/255, 131/255, 198/255)
NAVY = (30/255, 58/255, 109/255)
RED = (200/255, 16/255, 46/255)
BLACK = (0, 0, 0)
GREY_DARK = (0.27, 0.27, 0.27)


NAVY_FILL = (30/255, 58/255, 109/255)
# 양식 정확 색 (drawings 측정)
TPL_HEADER_BLUE = (0/255, 112/255, 192/255)   # Stock Data·주가상승률 헤더 진한 파랑
TPL_LIGHT_BG = (209/255, 231/255, 246/255)    # 우측 본문 옅은 하늘색

# 모든 redact + insert_text 페어를 모아서 한 번에 처리 (배경 그래픽 보존)
_PENDING = []


def replace(p, rect, text, fs, font='kr', color=BLACK, bg=None):
    """텍스트만 redact (배경 보존) + 새 텍스트 — bg='navy' or 'white'면 박스 덮음"""
    if bg == 'navy':
        p.draw_rect(rect, color=NAVY_FILL, fill=NAVY_FILL, overlay=True)
    # bg=None이면 redact로 텍스트만 제거 (배경 그래픽 유지)
    p.add_redact_annot(rect, fill=None)
    _PENDING.append(('l', rect, text, fs, font, color))


def _text_w(text, fs):
    """텍스트 폭 추정 (한글 = fs, 영문/숫자 = fs * 0.55)"""
    w = 0
    for ch in text:
        w += fs * (1.0 if ord(ch) > 127 else 0.55)
    return w


def _draw_body_text(p, text, x, y, w, fs=10, lh=13, color=(0,0,0), bold=False, max_y=None):
    """본문 자동 줄바꿈 + max_y 안쪽으로 cap (하단 라인 침범 금지)"""
    font = 'krbd' if bold else 'kr'
    cur_y = y
    paragraphs = text.split('\n')
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph: continue
        line = ''
        for ch in paragraph:
            test = line + ch
            if _text_w(test, fs) > w - 4:
                if max_y and cur_y > max_y: return cur_y
                p.insert_text((x, cur_y), line, fontsize=fs, fontname=font, color=color)
                cur_y += lh
                line = ch
            else:
                line += ch
        if line:
            if max_y and cur_y > max_y: return cur_y
            p.insert_text((x, cur_y), line, fontsize=fs, fontname=font, color=color)
            cur_y += lh
    return cur_y


def replace_right(p, rect, text, fs, font='kr', color=BLACK, bg=None):
    """우측 정렬 — redact + 새 텍스트"""
    if bg == 'navy':
        p.draw_rect(rect, color=NAVY_FILL, fill=NAVY_FILL, overlay=True)
    p.add_redact_annot(rect, fill=None)
    _PENDING.append(('r', rect, text, fs, font, color))


def flush_redacts(p):
    """모든 redact 한 번에 적용 + 우측 본문 영역 흰색 + 외곽 라인 복원 + 폰트 재등록"""
    p.apply_redactions(images=0)
    # 우측 본문 영역만 흰색 (양식 라인/그래픽 제거)
    p.draw_rect(fitz.Rect(203, 138, 585, 808),
                color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
    # 양식 본문 박스 외곽 라인 복원 (NAVY 네이비)
    nv = (30/255, 58/255, 109/255)
    # 상단 라인
    p.draw_line((203, 138), (585, 138), color=nv, width=1.2)
    # 하단 라인 (본문글 아래) — 사용자 지적 라인
    p.draw_line((203, 808), (585, 808), color=nv, width=1.2)
    # 폰트 재등록
    p.insert_font(fontname='kr', fontfile='C:/Windows/Fonts/malgun.ttf')
    p.insert_font(fontname='krbd', fontfile='C:/Windows/Fonts/malgunbd.ttf')
    for align, rect, text, fs, font, color in _PENDING:
        by = rect.y0 + (rect.y1 - rect.y0) * 0.75
        if align == 'r':
            w = _text_w(text, fs)
            bx = rect.x1 - w - 2
        else:
            bx = rect.x0
        p.insert_text((bx, by), text, fontsize=fs, fontname=font, color=color)
    _PENDING.clear()


def main():
    print('=== Cover 후처리 시작 ===')

    with open(BOXES_JSON, encoding='utf-8') as f:
        boxes = json.load(f)
    cover_boxes = [b for b in boxes if b['slide_num'] == '1']

    # PDF 로드
    v13 = fitz.open(V13)
    tmpl = fitz.open(TMPL)

    # v13 P1 삭제 + 양식 P1 삽입
    v13.delete_page(0)
    v13.insert_pdf(tmpl, from_page=0, to_page=0, start_at=0)

    p = v13[0]
    # 한글 폰트 등록
    p.insert_font(fontname='kr', fontfile='C:/Windows/Fonts/malgun.ttf')
    p.insert_font(fontname='krbd', fontfile='C:/Windows/Fonts/malgunbd.ttf')

    # === 좌상단 "Winning Fund 17-1" → "18-1" 양식 그대로 + 텍스트만 교체 ===
    p.add_redact_annot(fitz.Rect(14, 14, 192, 32), fill=False)
    _PENDING.append(('l', fitz.Rect(14, 16, 192, 30),
                     'Winning Fund 18-1 Research Report', 10, 'kr', NAVY))
    # 우상단 — 양식 "18-1 Equity Research" 그대로 두고 날짜만 교체
    p.add_redact_annot(fitz.Rect(525, 26, 588, 42), fill=False)
    _PENDING.append(('l', fitz.Rect(528, 28, 585, 40),
                     '2026.05.28.', 10.6, 'krbd', NAVY))

    # === 회사명 + 부제 (양식 로킷 스타일) ===
    # 회사명: TPL_BLUE 하늘색
    replace(p, fitz.Rect(203, 50, 580, 96),
           '와이지엔터테인먼트 (122870)', 26, 'krbd', TPL_BLUE)
    # 부제: 검은색 굵게
    replace(p, fitz.Rect(203, 96, 580, 130),
           '하반기엔 갑자기, 야호!', 14, 'krbd', BLACK)

    # === 좌측 정보 — redact (배경 보존) + 새 텍스트 ===
    p.add_redact_annot(fitz.Rect(14, 228, 165, 242), fill=None)
    p.add_redact_annot(fitz.Rect(14, 243, 165, 257), fill=None)
    p.add_redact_annot(fitz.Rect(14, 258, 196, 272), fill=None)
    _PENDING.append(('l', fitz.Rect(14, 228, 165, 242), '위닝펀드 18-1기', 10, 'kr', BLACK))
    _PENDING.append(('l', fitz.Rect(14, 243, 165, 257), '3조 | 황성혁', 10, 'krbd', BLACK))
    _PENDING.append(('l', fitz.Rect(14, 258, 196, 272), 'E-Mail : hsh25781@naver.com', 9, 'kr', GREY_DARK))

    # === 좌측 BUY 박스 — 목표/현재/상승여력 (양식 동일 검은색) ===
    replace(p, fitz.Rect(100, 333, 195, 355), '89,000', 14, 'krbd', BLACK)
    replace(p, fitz.Rect(100, 360, 195, 382), '48,050', 14, 'krbd', BLACK)
    replace(p, fitz.Rect(100, 388, 195, 408), '+85.2', 14, 'krbd', BLACK)

    # === Stock Data 표 ===
    # 헤더 행 — 양식의 진한 파랑 배경을 다시 그려 보존 + 흰 텍스트
    p.draw_rect(fitz.Rect(155, 412, 195, 425),
                color=TPL_HEADER_BLUE, fill=TPL_HEADER_BLUE, overlay=True)
    p.add_redact_annot(fitz.Rect(155, 412, 195, 425), fill=False)
    _PENDING.append(('r', fitz.Rect(155, 412, 195, 425), '26.05.28.', 7, 'kr', (1,1,1)))
    # KOSPI지수 라벨 → KOSDAQ 변경 + 데이터
    replace(p, fitz.Rect(13, 424, 80, 437),
           'KOSDAQ지수(pt)', 7.6, 'kr', BLACK)
    replace_right(p, fitz.Rect(140, 424, 195, 437), '789', 7.6, 'kr', BLACK)
    # 52주 최고/최저
    replace_right(p, fitz.Rect(120, 437, 195, 450), '79,000/47,000', 7.6, 'kr', BLACK)
    # 거래량/거래대금
    replace_right(p, fitz.Rect(120, 449, 195, 462), '215천주/103억', 7.6, 'kr', BLACK)
    # 시가총액
    replace_right(p, fitz.Rect(140, 461, 195, 474), '8,981', 7.6, 'kr', BLACK)
    # 발행주식수
    replace_right(p, fitz.Rect(140, 474, 195, 487), '18,691', 7.6, 'kr', BLACK)
    # 주요주주 지분율
    replace_right(p, fitz.Rect(140, 487, 195, 500), '22.95%', 7.6, 'kr', BLACK)
    # 외국인 지분율
    replace_right(p, fitz.Rect(140, 499, 195, 512), '10.86%', 7.6, 'kr', BLACK)

    # === Consensus Data 표 ===
    # 매출액
    replace_right(p, fitz.Rect(95, 541, 132, 555), '5,454', 7.6, 'kr', BLACK)
    replace_right(p, fitz.Rect(155, 541, 192, 555), '6,010', 7.6, 'kr', BLACK)
    # 영업이익
    replace_right(p, fitz.Rect(95, 554, 132, 568), '522', 7.6, 'kr', BLACK)
    replace_right(p, fitz.Rect(155, 554, 192, 568), '806', 7.6, 'kr', BLACK)
    # 순이익
    replace_right(p, fitz.Rect(95, 566, 132, 580), '537', 7.6, 'kr', BLACK)
    replace_right(p, fitz.Rect(155, 566, 192, 580), '684', 7.6, 'kr', BLACK)
    # EPS
    replace_right(p, fitz.Rect(95, 579, 132, 593), '1,974', 7.6, 'kr', BLACK)
    replace_right(p, fitz.Rect(155, 579, 192, 593), '3,108', 7.6, 'kr', BLACK)
    # BPS
    replace_right(p, fitz.Rect(95, 591, 132, 606), '20,500', 7.6, 'kr', BLACK)
    replace_right(p, fitz.Rect(155, 591, 192, 606), '21,800', 7.6, 'kr', BLACK)

    # === 주가상승률 표 ===
    # 절대주가 (1M/6M/12M)
    replace_right(p, fitz.Rect(85, 631, 112, 646), '-3.8', 7.6, 'kr', BLACK)
    replace_right(p, fitz.Rect(125, 631, 154, 646), '-26.8', 7.6, 'kr', BLACK)
    replace_right(p, fitz.Rect(165, 631, 194, 646), '-24.2', 7.6, 'kr', BLACK)
    # 코스피대비 → 코스닥대비 (KOSDAQ 종목)
    replace(p, fitz.Rect(13, 644, 78, 657),
           '코스닥대비(%)', 7.6, 'kr', BLACK)
    replace_right(p, fitz.Rect(85, 644, 112, 659), '-5.2', 7.6, 'kr', BLACK)
    replace_right(p, fitz.Rect(125, 644, 154, 659), '-30.5', 7.6, 'kr', BLACK)
    replace_right(p, fitz.Rect(165, 644, 194, 659), '-29.0', 7.6, 'kr', BLACK)

    # === Stock price 영역 — "Stock price (주가추이)" 라벨 양식 그대로 보존 ===
    chart_png = Path('output/와이지엔터/_charts/cover_price.png')
    # "차트삽입" placeholder만 redact (라벨은 양식 그대로 유지)
    p.add_redact_annot(fitz.Rect(60, 720, 145, 752), fill=False)

    # === 우측 본문 영역 — 양식 옅은 하늘색 배경 보존 ===
    p.add_redact_annot(fitz.Rect(203, 140, 590, 800), fill=False)
    # 옅은 하늘색 배경 재그림 (양식의 (205, 145)~(580, 802) RGB(0.82, 0.91, 0.96))
    # apply 후 그릴 거라 _PENDING으로 늦게 처리하기 어려움 → 직접 draw_rect
    # 단 apply_redactions 후 그래픽도 영향 받으면 다시 그려야 → 별도 처리

    cur_y = 152
    right_x = 207
    right_w = 580 - right_x

    # Cover 요약본 — 중복 제거 + 핵심만 (워드 본문에서 압축)
    SECTIONS = [
        ('Summary', [],
         '24.10~25.08 +190% 패턴(37,000→107,400원, FDR 실측)이 26.08~27.07 빅뱅 20주년 + 9월 5인조 보이그룹 + NEXT MONSTER 2팀 데뷔로 재현된다.\n'
         '1Q26 매출 +46.9%·OP +103.9% 외형 정상화됐으나 컨센 -5% 미스로 주가 3개월 -26.8% — 시장은 영업외 평가손에만 반응.\n'
         '양현석 시스템 개편(작곡가·안무 발주 2~3→10팀)으로 28년 한계(소수 IP·긴 컴백) 구조적 해소 중. 베몬 유튜브 1,200만·CHOOM 초동 38.8만 자체 최고가 첫 정량 증거.\n'
         '12MF PER 15.9배 = 빅뱅 군 입대·버닝썬 당시 역사적 하단. 순현금 2,737억(시총 30%)·무차입으로 하방 안전판 견고.'),
        ('Investment Highlights', [],
         '(1) 빅뱅 20주년 + 신인 2팀 = +190% 패턴 핵심 트리거. 14개 도시 6개월 풀이어(2026.08~2027.01) + 9월 5인조 보이그룹 + NEXT MONSTER 2027 1H. 컨센 2027E OP 764억은 빅뱅 풀이어 미반영, 8월 일정 확정 시 4~6주 재상향 트리거.\n\n'
         '(2) 단일 IP 리스크 시스템으로 해소. 6년 만의 보이그룹 + NEXT MONSTER로 IP 6종 분산. 베몬 CHOOM 초동 38.8만 자체 최고로 양성 시스템 1차 검증 완료, 양현석 안무 발주 2~3→10팀 확대가 시스템적 뒷받침.\n\n'
         '(3) 순현금 2,737억 — 무너질 일 없는 회사. 시총 8,981억의 30%가 현금, 사실상 무차입. OCF 909억·FCF 849억 흑자. 2024년 영업적자 해에도 NI 200억 유지한 현금 베이스가 하방 안전판.'),
        ('Valuation', [],
         '24M Forward 2028E EPS 3,700원 × Target PER 24배 = 적정주가 89,000원. 현재가 48,050원 대비 상승여력 +85.2%.\n\n'
         'Target PER 24배 = 4사 Implied PER Median 13.5배 + IP 6종 분산 Premium +5.0배 + 메가IP 양성 입증 Premium +5.5배 덧셈 워터폴.\n\n'
         '5가지 보수 가정(9월 보이그룹 50%·NEXT MONSTER 25%·텐센트 정상화만·한한령 옵션 0%·PER 활동기 평균 하단)이 적용된 정직한 보수값.\n\n'
         '19개사 컨센 평균 78,789원 대비 +13%. 호라이즌 2.5년(2028E 말 도달), 연환산 +27%/년. 9월 신인 보이그룹 데뷔 성공이 시스템 검증 시험대.\n\n'
         '투자의견 BUY 유지. 5년 +190% 패턴이 재현되는 26.08~27.07 사이클이 본 리포트 핵심 베팅.'),
    ]

    # === 모든 redact 한 번에 적용 + 양식 배경 재그림 + 폰트 재등록 ===
    flush_redacts(p)

    # === 우측 본문 — 글자 크게 + 소제목별 간격 크게 ===
    cur_y = 148
    right_x = 207
    right_w = 580 - right_x
    bottom_limit = 798
    fs = 10
    lh = 14            # 줄간격 ↑↑ (12.5 → 14) — Valuation 후 공백 최소화
    for title, items, intro_text in SECTIONS:
        if cur_y > bottom_limit: break
        # 섹션 제목 14pt 굵게
        p.insert_text((right_x, cur_y), title, fontsize=14, fontname='krbd', color=TPL_BLUE)
        cur_y += 18  # 섹션 헤더 → 본문 간격 (14 → 18, 명확 분리)
        if intro_text:
            cur_y = _draw_body_text(p, intro_text, right_x, cur_y, right_w,
                                    fs=fs, lh=lh, color=BLACK, bold=True,
                                    max_y=bottom_limit)
            cur_y += 12  # 섹션 사이 간격 ↑ (2 → 12, 소제목별 명확 구분)

    # 차트 PNG 삽입 (redact 이후)
    if chart_png.exists():
        p.insert_image(fitz.Rect(35, 712, 200, 805), filename=str(chart_png))

    # === 모든 본문 페이지 (P2~P32)에 양식 우측 영역만 import + 가로선 도형 ===
    # 좌측 카테고리 헤더 영역(x<200)은 보존
    print('\n=== 본문 페이지에 양식 상단/하단 import (우측만) ===')
    TPL_LINE_RGB = (0/255, 112/255, 192/255)
    # 폰트 등록 (페이지번호 그릴 때 사용)
    pno_font_registered = False
    for pno in range(1, len(v13)):
        page = v13[pno]
        # 우측 V 로고 + 우상단 placeholder만 (가로선 영역 y<53 제외)
        clip_top = fitz.Rect(450, 0, 595, 52)
        page.show_pdf_page(clip_top, tmpl, 3, clip=clip_top)
        # 우측 WinningFund 로고 전체 import (y=814~842, x=400~535 — 페이지번호 영역 제외)
        clip_bot = fitz.Rect(400, 814, 535, 842)
        page.show_pdf_page(clip_bot, tmpl, 3, clip=clip_bot)
        # 가로선만 도형으로 (단일)
        page.draw_line(fitz.Point(28, 55.5), fitz.Point(562, 55.5),
                       color=TPL_LINE_RGB, width=1.5)
        page.draw_line(fitz.Point(28, 808), fitz.Point(562, 808),
                       color=TPL_LINE_RGB, width=1.5)
        # 페이지번호 — placeholder 영역(535~595, 810~828) 흰 박스 + 새 번호
        page.draw_rect(fitz.Rect(536, 810, 595, 828),
                       color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
        page.insert_font(fontname='kr', fontfile='C:/Windows/Fonts/malgun.ttf')
        page.insert_text((542, 823), f'|   {pno + 1}',
                         fontsize=10.5, fontname='kr', color=(0, 0, 0))
    print(f'  {len(v13)-1}장 양식 그래픽 적용 (좌측 카테고리 헤더 보존)')

    # === Compliance Notice — 재무제표 페이지(마지막) 하단에 통합 ===
    print('\n=== Compliance Notice (재무제표 페이지 하단 통합) ===')
    comp = v13[len(v13) - 1]  # 재무제표 페이지 (마지막)
    comp.insert_font(fontname='kr', fontfile='C:/Windows/Fonts/malgun.ttf')
    comp.insert_font(fontname='krbd', fontfile='C:/Windows/Fonts/malgunbd.ttf')
    # 재무제표 표 아래 (PDF y=560부터) Compliance 시작
    comp.insert_text((36, 575), '<Compliance Notice>', fontsize=13, fontname='krbd', color=TPL_HEADER_BLUE)
    comp.draw_line(fitz.Point(36, 582), fitz.Point(559, 582), color=TPL_HEADER_BLUE, width=1.2)
    notices = [
        '본 조사자료는 금융권 취업을 준비하고, 자본 시장을 공부하는 학생들에 대한 정보 공유 및 투자자들에게 도움이 될 만한 정보를 제공할 목적으로 작성되었으며, 담당자의 사전 동의 없이 무단 복제 및 배포할 수 없습니다.',
        '본 자료에 대한 저작권은 위닝펀드에 있습니다.',
        '본 자료에 첨부된 내용은 담당자가 신뢰할 만한 자료 및 정보를 선별한 것이므로 그 정확성이나 완전성을 보장할 수 없습니다. 따라서 본 자료를 통해 투자에 임할 경우 자신의 판단과 책임하에 최종 결정을 하시기 바랍니다.',
        '본 자료는 어떠한 경우에도 주식투자의 결과에 대한 법적 책임소재의 증빙자료로 사용될 수 없습니다.',
    ]
    y = 600
    for n in notices:
        comp.insert_text((40, y), '◆', fontsize=7.5, fontname='kr', color=TPL_HEADER_BLUE)
        line = ''
        for ch in n:
            if _text_w(line + ch, 8.5) > 500:
                comp.insert_text((54, y), line, fontsize=8.5, fontname='kr', color=BLACK)
                y += 12
                line = ch
            else:
                line += ch
        if line:
            comp.insert_text((54, y), line, fontsize=8.5, fontname='kr', color=BLACK)
            y += 12
        y += 6
    print('  Compliance Notice = 재무제표 페이지 하단 통합')

    v13.save(V13.replace('.pdf', '_temp.pdf'), deflate=True, garbage=4)
    v13.close()
    tmpl.close()

    # 임시 파일 → 원본 이름으로
    import shutil
    shutil.move(V13.replace('.pdf', '_temp.pdf'), V13)
    print(f'완료: {V13}')


if __name__ == '__main__':
    main()
