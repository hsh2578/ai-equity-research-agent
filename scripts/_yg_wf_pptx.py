# -*- coding: utf-8 -*-
"""
위닝펀드 18-1 양식 파일(18-1_기업분석 리포트 양식.pptx)을 PowerPoint COM으로
직접 열어 텍스트·표·도표를 채우고, 섹션이 더 필요하면 해당 슬라이드를 복제한다.
build_yg_wf_report.py 가 build(template, out, charts_dir) 를 호출한다.
"""
import os
import win32com.client
import _yg_wf_content as C

PT = 28.3465                       # 1cm = 28.3465pt
FONT = "맑은 고딕"

# PowerPoint 상수
AUTOSIZE_NONE = 0                  # ppAutoSizeNone
AUTOSIZE_FIT = 1                   # ppAutoSizeShapeToFitText
ALIGN_L, ALIGN_C, ALIGN_R = 1, 2, 3
ORI_H = 1                          # msoTextOrientationHorizontal
SHP_RECT = 1                       # msoShapeRectangle
SAVE_PPTX = 24                     # ppSaveAsOpenXMLPresentation
MSO_TRUE, MSO_FALSE = -1, 0


def rgb(r, g, b):
    """COM 의 OLE 색상값 (0xBBGGRR)."""
    return r + (g << 8) + (b << 16)


NAVY = rgb(0x1B, 0x35, 0x5E)
BLUE = rgb(0x2E, 0x5C, 0x8A)
SKY = rgb(0x5B, 0x8F, 0xC2)
GOLD = rgb(0xC2, 0x99, 0x2E)
GRAY = rgb(0x55, 0x55, 0x55)
DARK = rgb(0x22, 0x22, 0x22)
WHITE = rgb(0xFF, 0xFF, 0xFF)

# A4 세로 (pt)
PGW, PGH = 595.0, 842.0


# ---------------------------------------------------------------------------
# 도우미
# ---------------------------------------------------------------------------
def _font(rng, size=None, bold=None, color=None, name=FONT):
    f = rng.Font
    if name:
        f.Name = name
        f.NameFarEast = name
    if size is not None:
        f.Size = size
    if bold is not None:
        f.Bold = MSO_TRUE if bold else MSO_FALSE
    if color is not None:
        f.Color.RGB = color


def _para_text(shape, paras):
    """paras = [(텍스트, dict(size,bold,color,align,space)), ...] 를 한 박스에 채운다.
    WordWrap/AutoSize 는 호출자가 미리 설정한다."""
    tr = shape.TextFrame.TextRange
    tr.Text = "\r".join(p[0] for p in paras)
    for i, (_, st) in enumerate(paras, 1):
        try:
            p = tr.Paragraphs(i)
        except Exception:
            continue
        _font(p, st.get("size"), st.get("bold"), st.get("color"))
        if "align" in st:
            p.ParagraphFormat.Alignment = st["align"]
        sp = st.get("space")
        if sp:
            pf = p.ParagraphFormat
            pf.LineRuleWithin = MSO_TRUE
            pf.SpaceWithin = sp
        if "before" in st:
            p.ParagraphFormat.SpaceBefore = st["before"]


def _add_text(slide, x, y, w, h, paras, wrap=True):
    tb = slide.Shapes.AddTextbox(ORI_H, x, y, w, h)
    tf = tb.TextFrame
    try:
        tf.AutoSize = AUTOSIZE_NONE          # 자동크기 끔 (폭 붕괴 방지)
    except Exception:
        pass
    tf.WordWrap = MSO_TRUE if wrap else MSO_FALSE
    tf.MarginLeft = 2
    tf.MarginRight = 2
    tf.MarginTop = 1
    tf.MarginBottom = 1
    _para_text(tb, paras)
    tb.Left, tb.Top, tb.Width, tb.Height = x, y, w, h
    return tb


def _add_pic_fit(slide, path, x, y, w, h):
    """이미지를 (x,y,w,h) 박스 안에 비율 유지하며 중앙 배치."""
    if not os.path.exists(path):
        print("    [WARN] 도표 누락:", os.path.basename(path))
        return None
    try:
        from PIL import Image
        im = Image.open(path)
        ratio = im.height / im.width
    except Exception:
        ratio = 0.55
    pw = w
    ph = pw * ratio
    if ph > h:
        ph = h
        pw = ph / ratio
    px = x + (w - pw) / 2
    py = y + (h - ph) / 2
    return slide.Shapes.AddPicture(path, MSO_FALSE, MSO_TRUE, px, py, pw, ph)


def _accent(slide, x, y, w, h, color=GOLD):
    sh = slide.Shapes.AddShape(SHP_RECT, x, y, w, h)
    sh.Fill.Solid()
    sh.Fill.ForeColor.RGB = color
    sh.Line.Visible = MSO_FALSE
    sh.Shadow.Visible = MSO_FALSE
    return sh


# ---------------------------------------------------------------------------
# 커버
# ---------------------------------------------------------------------------
def fill_cover(slide, charts_dir):
    m, cv = C.META, C.COVER
    tables = []
    for sh in list(slide.Shapes):
        try:
            t = int(sh.Type)
        except Exception:
            continue
        if t == 3 and "Chart" in sh.Name:          # 양식의 빈 차트 개체 제거
            sh.Delete()
            continue
        if t == 19:
            tables.append(sh)
            continue
        if t == 17 and sh.HasTextFrame:
            txt = sh.TextFrame.TextRange.Text
            if txt.startswith("회사명"):
                sh.TextFrame.WordWrap = MSO_FALSE
                tr = sh.TextFrame.TextRange
                tr.Text = f"{m['company']} ({m['code']})  |  {m['market']}"
                _font(tr, 15, True, NAVY)
            elif txt.strip() == "리포트 제목":
                sh.TextFrame.WordWrap = MSO_FALSE
                sh.Top = 86
                tr = sh.TextFrame.TextRange
                tr.Text = cv["title"]
                _font(tr, 24, True, NAVY)
            elif txt.startswith("최종 제출"):
                _fill_cover_body(sh)
            elif "Winning Fund" in txt and "Research Report" in txt:
                sh.TextFrame.TextRange.Text = "Winning Fund 18-1 Research Report"
            elif txt.strip() == "2026.05.00.":
                sh.TextFrame.TextRange.Text = m["date"]

    for sh in tables:
        tbl = sh.Table
        head = tbl.Cell(1, 1).Shape.TextFrame.TextRange.Text.strip()
        if head == "Stock Data":
            _fill_stockdata(tbl)
        elif head.startswith("주가 상승률"):
            _fill_returns(tbl)
        elif head.startswith("Consensus"):
            _fill_consensus(tbl)
        elif head == "BUY":
            _fill_buy(tbl, m)
        elif head.startswith("Stock price"):
            tbl.Cell(2, 1).Shape.TextFrame.TextRange.Text = ""
            _add_pic_fit(slide, os.path.join(charts_dir, "cover_price.png"),
                         sh.Left + 4, sh.Top + 26, sh.Width - 8, sh.Height - 32)
        elif "위닝펀드" in tbl.Cell(2, 1).Shape.TextFrame.TextRange.Text:
            tbl.Cell(2, 1).Shape.TextFrame.TextRange.Text = (
                f"{m['team']}\r{m['author']}\rE-Mail : {m['email']}")

    # 부제 (제목 박스 아래)
    _add_text(slide, 207, 137, 384, 15,
              [(cv["subtitle"], dict(size=10, bold=True, color=GOLD))],
              wrap=False)


def _fill_cover_body(shape):
    cv = C.COVER
    paras = [("Summary", dict(size=12.5, bold=True, color=NAVY, space=1.0))]
    for s in cv["summary"]:
        paras.append(("✓  " + s, dict(size=9.0, color=DARK, space=1.08)))
    paras.append((" ", dict(size=4)))
    paras.append(("Investment Highlight",
                  dict(size=12.5, bold=True, color=NAVY, before=4)))
    for i, (t, b) in enumerate(cv["highlights"], 1):
        paras.append((f"{i})  {t}", dict(size=10, bold=True, color=BLUE,
                                         before=5)))
        paras.append((b, dict(size=8.7, color=GRAY, space=1.08)))
    paras.append((" ", dict(size=4)))
    paras.append(("Valuation", dict(size=12.5, bold=True, color=NAVY,
                                    before=4)))
    paras.append((cv["valuation"], dict(size=8.9, color=DARK, space=1.1,
                                        before=2)))
    shape.Top = 157
    shape.Left = 205
    shape.Width = 378
    shape.TextFrame.WordWrap = MSO_TRUE
    _para_text(shape, paras)


def _cell(tbl, r, c, text, size=8.5, bold=False, color=GRAY, align=None):
    cell = tbl.Cell(r, c)
    tr = cell.Shape.TextFrame.TextRange
    tr.Text = str(text)
    _font(tr, size, bold, color)
    if align:
        tr.ParagraphFormat.Alignment = align


def _fill_stockdata(tbl):
    vals = {
        "KOSPI": ("KOSDAQ 지수(pt)", "744"),
        "52주": ("52주 최고/최저(원)", "79,000 / 47,000"),
        "거래량": ("거래량/거래대금", "114,585주 / 56억"),
        "시가총액": ("시가총액(억원)", "8,981"),
        "발행주식": ("발행주식수(천 주)", "18,691"),
        "주요주주": ("주요주주 지분율(%)", "22.95"),
        "외국인": ("외국인 지분율(%)", "10.86"),
    }
    _cell(tbl, 1, 2, "2026.05.22", 8, bold=True, color=WHITE, align=ALIGN_R)
    _cell(tbl, 1, 3, "", 8)
    for r in range(2, tbl.Rows.Count + 1):
        label = tbl.Cell(r, 1).Shape.TextFrame.TextRange.Text.strip()
        for key, (newlab, val) in vals.items():
            if key in label:
                _cell(tbl, r, 1, newlab, 8, color=DARK)
                if tbl.Columns.Count >= 2:
                    _cell(tbl, r, 2, newlab, 8, color=DARK)
                _cell(tbl, r, tbl.Columns.Count, val, 8.5, bold=True,
                      color=NAVY, align=ALIGN_R)
                break


def _fill_returns(tbl):
    rt = C.COVER["returns"]["rows"]
    for r, row in zip((3, 4), rt):
        _cell(tbl, r, 1, row[0], 8, color=DARK)
        for c in range(2, 5):
            _cell(tbl, r, c, row[c - 1], 8.5, bold=True, color=NAVY,
                  align=ALIGN_C)


def _fill_consensus(tbl):
    cd = C.COVER["consensus"]
    _cell(tbl, 2, 2, "2025", 8, bold=True, color=DARK, align=ALIGN_C)
    _cell(tbl, 2, 3, "2026E", 8, bold=True, color=DARK, align=ALIGN_C)
    for r, row in zip(range(3, 8), cd["rows"]):
        _cell(tbl, r, 1, row[0], 8, color=DARK)
        _cell(tbl, r, 2, row[2], 8.5, bold=True, color=NAVY, align=ALIGN_R)
        _cell(tbl, r, 3, row[3], 8.5, bold=True, color=NAVY, align=ALIGN_R)


def _fill_buy(tbl, m):
    _cell(tbl, 2, 2, f"{m['target_price']:,}", 11, bold=True, color=NAVY,
          align=ALIGN_R)
    _cell(tbl, 3, 2, f"{m['current_price']:,}", 11, bold=True, color=DARK,
          align=ALIGN_R)
    _cell(tbl, 4, 2, f"+{m['upside']}", 11, bold=True, color=GOLD,
          align=ALIGN_R)


# ---------------------------------------------------------------------------
# 목차
# ---------------------------------------------------------------------------
def fill_toc(slide):
    # 양식의 목차 섹션 박스가 좁아 영문 부제가 줄바꿈됨 -> 한글만 단일 행으로
    SEC = {"Introduction": "0. Introduction", "산업분석": "1. 산업분석",
           "기업분석": "2. 기업분석", "투자포인트": "3. 투자포인트",
           "리스크": "4. 리스크", "재무분석": "5. 재무분석",
           "밸류에이션": "6. 밸류에이션"}
    nums = []
    for sh in list(slide.Shapes):
        if int(sh.Type) == 17 and sh.HasTextFrame:
            txt = sh.TextFrame.TextRange.Text.strip()
            if txt == "00":
                nums.append(sh)
                continue
            if "소제목 소제목" in txt:
                sh.Delete()
                continue
            for k, v in SEC.items():
                if k in txt and txt != v:
                    sh.TextFrame.WordWrap = MSO_FALSE
                    sh.TextFrame.TextRange.Text = v
                    break
    nums.sort(key=lambda s: s.Top)
    pages = ["03", "04", "06", "09", "12", "13", "15"]
    for sh, pg in zip(nums, pages):
        tr = sh.TextFrame.TextRange
        tr.Text = pg
        _font(tr, 14, True, GOLD)


# ---------------------------------------------------------------------------
# 콘텐츠 슬라이드
# ---------------------------------------------------------------------------
BANDS = [(56.0, 408.0), (418.0, 800.0)]   # (블록 상단, 블록 하단) pt


def fill_content(slide, sd, charts_dir):
    title, content, labels, groups = None, [], [], []
    for sh in list(slide.Shapes):
        t = int(sh.Type)
        if t == 6:
            groups.append(sh)
        elif t == 17 and sh.HasTextFrame:
            txt = sh.TextFrame.TextRange.Text
            if sh.Top < 46 and sh.Left < 120:
                title = sh
            elif sh.Left > 110:
                content.append(sh)
            elif "요약" in txt:
                labels.append(sh)
    content.sort(key=lambda s: s.Top)
    for sh in labels:
        sh.Delete()
    for sh in groups:
        sh.Delete()
    if len(content) < 2:
        print("    [WARN] 콘텐츠 박스 부족:", sd["section"], len(content))
        return

    for i, bl in enumerate(sd["blocks"]):
        cb = content[i]
        b_top, b_bot = BANDS[i]
        cb.Left = 126.0
        cb.Width = 446.0
        cb.Top = b_top
        cb.TextFrame.WordWrap = MSO_TRUE
        try:
            cb.TextFrame.AutoSize = AUTOSIZE_FIT
        except Exception:
            pass
        _para_text(cb, [
            (bl["subtitle"], dict(size=13, bold=True, color=BLUE,
                                  space=1.05)),
            (bl["body"], dict(size=10, color=DARK, space=1.12, before=4)),
        ])
        # 좌측 요약 라벨
        _accent(slide, 20.0, b_top + 3, 3.4, 42.0, GOLD)
        _add_text(slide, 28.0, b_top, 92.0, 110.0,
                  [(bl["label"], dict(size=9.3, bold=True, color=NAVY,
                                      space=1.12))])
        # 도표
        if bl.get("chart"):
            try:
                text_bot = cb.Top + cb.Height
            except Exception:
                text_bot = b_top + 150
            cy = text_bot + 10
            ch = b_bot - cy
            if ch > 40:
                _add_pic_fit(slide, os.path.join(charts_dir,
                             bl["chart"] + ".png"), 62.0, cy, 471.0, ch)


# ---------------------------------------------------------------------------
# 재무제표 (Appendix)
# ---------------------------------------------------------------------------
def fill_appendix(slide):
    ft = C.FIN_TABLE
    for sh in list(slide.Shapes):
        t = int(sh.Type)
        if t == 6:
            sh.Delete()
        elif t == 17 and sh.HasTextFrame:
            txt = sh.TextFrame.TextRange.Text
            if txt.startswith("□") or "캡처" in txt:
                sh.Delete()
            elif txt.startswith("자료"):
                sh.TextFrame.TextRange.Text = "자료 : " + ft["source"]
                _font(sh.TextFrame.TextRange, 8, False, GRAY)

    rows = [ft["headers"]] + [
        [str(r[0])] + [f"{v:,}" if isinstance(v, int) else str(v)
                       for v in r[1:]] for r in ft["rows"]]
    n_r, n_c = len(rows), len(rows[0])
    gt = slide.Shapes.AddTable(n_r, n_c, 28.0, 110.0, 539.0, 26.0 * n_r)
    tbl = gt.Table
    widths = [95.0] + [(539.0 - 95.0) / (n_c - 1)] * (n_c - 1)
    for c in range(n_c):
        tbl.Columns(c + 1).Width = widths[c]
    for r in range(n_r):
        tbl.Rows(r + 1).Height = 26.0
        for c in range(n_c):
            cell = tbl.Cell(r + 1, c + 1)
            cell.Shape.TextFrame.MarginLeft = 4
            cell.Shape.TextFrame.MarginRight = 4
            tr = cell.Shape.TextFrame.TextRange
            tr.Text = rows[r][c]
            is_h = r == 0
            _font(tr, 9.0, is_h or c == 0, WHITE if is_h else
                  (NAVY if c == 0 else GRAY))
            tr.ParagraphFormat.Alignment = ALIGN_L if c == 0 else ALIGN_R
            cell.Shape.Fill.ForeColor.RGB = (
                NAVY if is_h else (rgb(0xEE, 0xF1, 0xF5) if r % 2 else WHITE))


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------
def build(template, out, charts_dir):
    template = os.path.abspath(template)
    out = os.path.abspath(out)
    if os.path.exists(out):
        try:
            os.remove(out)
        except Exception:
            pass
    app = win32com.client.Dispatch("PowerPoint.Application")
    pres = app.Presentations.Open(template, MSO_FALSE, MSO_FALSE, MSO_FALSE)
    try:
        # 1) 섹션 슬라이드 복제 (높은 인덱스부터: 재무10·투자8·기업6·산업4)
        for idx in (10, 8, 6, 4):
            pres.Slides(idx).Duplicate()
        # 17장: 1커버 2목차 3인트로 4산 5산 6기 7기 8기 9투 10투 11투
        #       12리 13재 14재 15밸 16재무제표 17체크
        pres.Slides(17).Delete()                 # 체크리스트 제거
        # 2) 커버 / 목차
        fill_cover(pres.Slides(1), charts_dir)
        fill_toc(pres.Slides(2))
        # 3) 콘텐츠 (슬라이드 3~15 = C.SLIDES 13장)
        for i, sd in enumerate(C.SLIDES):
            fill_content(pres.Slides(3 + i), sd, charts_dir)
        # 4) 재무제표 (슬라이드 16)
        fill_appendix(pres.Slides(16))
        pres.SaveAs(out, SAVE_PPTX)
        n = pres.Slides.Count
    finally:
        pres.Close()
        app.Quit()
    return n
