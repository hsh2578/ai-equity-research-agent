"""
범용 리포트 생성기 (v3 -- 단일 상세 PDF, Navy/Gold 디자인)

analysis.json → output/{종목}/report_{종목}_상세.pdf
  - HTML → PDF (Playwright Chromium)
  - Cover (1p) + Executive Summary (1p) + 21 섹션 자연 흐름 + Final Call (1p)
  - Navy (#0b2545) + Gold (#b8922e) 팔레트
  - 마크다운 풀 파싱 (### 헤딩, **bold**, *italic*, | 표 |, > 인용, - 리스트, ---)
  - 이모지 자동 strip (★☆ 별점만 보존)

이전 v2: 3개 파일 (상세PDF + 요약PDF + 대시보드HTML) — 폐기
  · 요약 PDF 생성 함수: _generate_summary_v2 (코드 보존만, 호출 안 됨)
  · 대시보드 HTML 생성 함수: generate_dashboard (코드 보존만, 호출 안 됨)
  · Word docx 기반 상세 함수: _generate_detailed_legacy_docx (코드 보존만, 호출 안 됨)

사용법:
  python scripts/generate_all.py scripts/analysis_{종목명}.json
"""

import json
import sys
import io as _io_utf8
sys.stdout = _io_utf8.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = _io_utf8.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import os
import re
import html as html_lib



_QUOTE_BOX_RE = re.compile(
    r'^>\s*\**\s*(?:사업보고서|반기보고서|분기보고서|SEC\s*10-[KQ]|컨퍼런스콜|증권사 리포트)', re.M)

def parse_market_cap(raw):
    """리포트 표기 시총 문자열 -> 숫자. 파싱 불가면 None.

    Peer 교차검증(#10)이 analysis.json `peers[].market_cap` 을 `_peer_snapshot.json`
    의 `market_cap_uk` 와 비교하는데, 기존 파서는 '조'/'억'/',' 만 지웠다.
    그래서 US 리포트의 "$5,062B" 를 만나면 float() 이 ValueError 를 냈고,
    **시총 비교가 통째로 건너뛰어졌다** (JYP v1 재발 방지 검증이 US 에선 꺼져 있었다).

    단위 규약 (스냅샷 생성기와 동일):
      KR "38,169억" / "3.82조"  -> 억 단위 숫자
      US "$5,062B" / "$1.2T"    -> B 단위 숫자

    실패 시 0 이 아니라 None 을 돌려준다. 0 은 '시총 0' 으로 읽혀 비교가
    조용히 통과하는 원인이 된다.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = s.replace(',', '').replace(' ', '')
    for junk in ('USD', 'usd', '$', '약', '원'):
        s = s.replace(junk, '')

    import re as _re

    # KR: '12조 3456억' 같은 혼합 표기를 먼저 처리
    jo = _re.search(r'(-?\d+(?:\.\d+)?)조', s)
    uk = _re.search(r'(-?\d+(?:\.\d+)?)억', s)
    if jo or uk:
        total = 0.0
        if jo:
            total += float(jo.group(1)) * 10000    # 조 -> 억
        if uk:
            total += float(uk.group(1))
        return total

    # US: T / B / M 접미사
    m = _re.search(r'(-?\d+(?:\.\d+)?)\s*([TBM])(?![A-Za-z])', s, _re.I)
    if m:
        val = float(m.group(1))
        mult = {'t': 1000.0, 'b': 1.0, 'm': 0.001}[m.group(2).lower()]
        return val * mult

    m = _re.search(r'-?\d+(?:\.\d+)?', s)
    return float(m.group(0)) if m else None


def consensus_columns(fin_headers):
    """커버 '컨센서스 요약' 이 쓸 두 열을 고른다.

    반환: (확정열_idx, 비교열_idx, 비교열이_추정인가) 또는 None(비교 불가).

    추정 열이 없을 때 예전 코드는 `fwd_idx = last_actual` 로 덮어써서 **같은 열을
    두 번** 썼다. 그 결과 커버에 "매출 2,946 -> 2,946 / EPS -556 -> -556" 이 찍히고
    라벨은 "TTM 실적 / TTM 추정" 이었다 -- 컨센서스를 수집하지 못한 종목마다
    **없는 예측이 첫 화면에** 올라간 셈이다(에프에스티 036810 실측).
    결측을 마지막 실적으로 메우지 않는다 (v5.6 규칙 5).
    """
    if not fin_headers or len(fin_headers) < 3:
        return None
    cols = list(range(1, len(fin_headers)))
    fwd = None
    for i in cols:
        h = str(fin_headers[i]).strip().upper()
        # 연도 뒤에 붙은 E/F 만 추정으로 본다. 'TTM' 같은 라벨을 오판하지 않는다.
        if re.search(r'\d\s*[EF]$', h):
            fwd = i
            break
    if fwd is not None:
        actual = fwd - 1
        if actual < 1:
            return None
        return (actual, fwd, True)
    # 추정 열이 없다 -> 직전 확정과 마지막 확정을 비교한다. '추정' 이라 부르지 않는다.
    return (cols[-2], cols[-1], False)


def md_table_to_html(txt, table_class=""):
    """섹션 본문 안의 마크다운 테이블을 HTML 테이블로 변환. 나머지는 <br>로 join."""
    lines = txt.split('\n')
    out = []
    i = 0
    cls = f' class="{table_class}"' if table_class else ''
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        if (stripped.startswith('|') and stripped.endswith('|')
                and i + 1 < len(lines)
                and re.match(r'^\s*\|[\s\-:|]+\|\s*$', lines[i+1])):
            header_cells = [c.strip() for c in stripped.strip('|').split('|')]
            i += 2
            body_rows = []
            while i < len(lines):
                row_line = lines[i].strip()
                if row_line.startswith('|') and row_line.endswith('|'):
                    cells = [c.strip() for c in row_line.strip('|').split('|')]
                    while len(cells) < len(header_cells):
                        cells.append('')
                    body_rows.append(cells[:len(header_cells)])
                    i += 1
                else:
                    break
            thead = ''.join(f'<th>{html_lib.escape(h)}</th>' for h in header_cells)
            tbody = ''.join(
                '<tr>' + ''.join(f'<td>{html_lib.escape(c)}</td>' for c in r) + '</tr>'
                for r in body_rows
            )
            out.append(f'<table{cls}><tr>{thead}</tr>{tbody}</table>')
            continue
        if stripped:
            out.append(html_lib.escape(stripped))
        i += 1
    return '<br>'.join(out)


# ============================================
# 1. 상세 리포트 (Word → PDF)
# ============================================
# Emoji ranges to drop (★ ☆ are preserved as they're used for star ratings)
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"  # misc symbols & pictographs
    "\U0001FA00-\U0001FAFF"  # extended pictographs
    "\U0001F000-\U0001F2FF"  # mahjong, playing cards, enclosed
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F680-\U0001F6FF"  # transport & map
    "\u2700-\u27BF"          # dingbats (✓ ✗ ✘ ✦ ❌ etc.)
    "\u2600-\u2604"          # weather (☀ ☁ ☂ ☃)
    "\u2611-\u2614"          # ballot box, umbrella
    "\u2620-\u2698"          # warning, peace, etc.
    "\u26A0-\u26FF"          # ⚠ ⚡ ⚪ ⚫ ⛔ etc.
    "\uFE0F"                 # variation selector-16
    "]+",
    flags=re.UNICODE,
)
# Decorative pictographs to explicitly drop (mostly outside or special)
_EXTRA_DROP_CHARS = "🔴🟠🟡🟢🔵🟣⚫⚪✅❌⚠️🎯🔥💎🏗📊🔍📚📌📈📉💰🎨🚀✨💡🛡⏱👁🛑🛠📑🏷"

def _strip_emoji(text):
    """Remove emoji and decorative pictographs from text. ★ ☆ are preserved (used in star ratings)."""
    if not text:
        return text
    # Drop known decorative chars first
    for ch in _EXTRA_DROP_CHARS:
        text = text.replace(ch, "")
    # Drop emoji ranges
    text = _EMOJI_RE.sub("", text)
    # Collapse extra whitespace introduced by removal
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text


def generate_detailed_report(data, output_dir):
    """v3: HTML 기반 단일 상세 PDF (Navy/Gold 디자인 + 21섹션 전체)."""
    return _generate_detailed_v3(data, output_dir)


def _generate_detailed_legacy_docx(data, output_dir):
    """Deprecated: legacy docx → PDF generator. Use _generate_detailed_v3 instead."""
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

    meta = data["meta"]
    price = data["price"]
    opinion = data["opinion"]
    sections = data["sections"]
    fin = data["financials"]

    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Malgun Gothic'
    style.font.size = Pt(10)

    def heading(text, level=1):
        # Strip markdown markers + emoji
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = _strip_emoji(text)
        h = doc.add_heading(text, level=level)
        for run in h.runs:
            run.font.name = 'Malgun Gothic'

    def para(text, bold=False, size=10):
        p = doc.add_paragraph()
        run = p.add_run(text)
        run.font.name = 'Malgun Gothic'
        run.font.size = Pt(size)
        run.bold = bold

    def add_inline_runs(p, text, base_size=10, base_bold=False, base_italic=False):
        """Parse inline markdown (**bold**, *italic*, `code`) and add as runs.
        Also strips emojis and decorative pictographs."""
        if not text:
            return
        text = _strip_emoji(text)
        if not text:
            return
        # Split by **bold**, *italic*, `code` while keeping the delimiters
        parts = re.split(r'(\*\*[^*\n]+?\*\*|`[^`\n]+?`)', text)
        # Note: avoid *italic* split because it conflicts with ** matching;
        # handle *...* in a second pass on plain segments
        for part in parts:
            if not part:
                continue
            if part.startswith('**') and part.endswith('**') and len(part) > 4:
                run = p.add_run(part[2:-2])
                run.bold = True
                run.font.name = 'Malgun Gothic'
                run.font.size = Pt(base_size)
                if base_italic:
                    run.italic = True
            elif part.startswith('`') and part.endswith('`') and len(part) > 2:
                run = p.add_run(part[1:-1])
                run.font.name = 'Consolas'
                run.font.size = Pt(base_size - 1)
            else:
                # Second pass: handle *italic* on plain text
                sub_parts = re.split(r'(\*[^*\n]+?\*)', part)
                for sp in sub_parts:
                    if not sp:
                        continue
                    if sp.startswith('*') and sp.endswith('*') and len(sp) > 2:
                        run = p.add_run(sp[1:-1])
                        run.italic = True
                        run.font.name = 'Malgun Gothic'
                        run.font.size = Pt(base_size)
                        if base_bold:
                            run.bold = True
                    else:
                        run = p.add_run(sp)
                        run.font.name = 'Malgun Gothic'
                        run.font.size = Pt(base_size)
                        if base_bold:
                            run.bold = True
                        if base_italic:
                            run.italic = True

    def add_md_paragraph(text, base_size=10, base_bold=False, base_italic=False, indent=None):
        """Add a paragraph that respects inline markdown."""
        p = doc.add_paragraph()
        if indent:
            p.paragraph_format.left_indent = Inches(indent)
        add_inline_runs(p, text, base_size=base_size, base_bold=base_bold, base_italic=base_italic)
        return p

    def add_md_heading(text, level=2):
        """Add a styled subheading from markdown ## or ###."""
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = _strip_emoji(text)
        if level <= 2:
            h = doc.add_heading(text, level=2)
            for run in h.runs:
                run.font.name = 'Malgun Gothic'
        elif level == 3:
            p = doc.add_paragraph()
            run = p.add_run(text)
            run.bold = True
            run.font.name = 'Malgun Gothic'
            run.font.size = Pt(12)
            run.font.color.rgb = RGBColor(13, 71, 161)
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(2)
        else:
            p = doc.add_paragraph()
            run = p.add_run(text)
            run.bold = True
            run.font.name = 'Malgun Gothic'
            run.font.size = Pt(11)
            p.paragraph_format.space_before = Pt(6)

    def table(headers, rows):
        t = doc.add_table(rows=1+len(rows), cols=len(headers))
        t.style = 'Light Grid Accent 1'
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, h in enumerate(headers):
            # Strip markdown + emoji from header cells
            clean = re.sub(r'\*\*(.+?)\*\*', r'\1', str(h))
            clean = re.sub(r'\*(.+?)\*', r'\1', clean)
            clean = _strip_emoji(clean)
            t.rows[0].cells[i].text = clean
        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                clean = re.sub(r'\*\*(.+?)\*\*', r'\1', str(val))
                clean = re.sub(r'\*(.+?)\*', r'\1', clean)
                clean = _strip_emoji(clean)
                t.rows[r_idx+1].cells[c_idx].text = clean

    def render_section_content(content):
        """Render section body. Parses markdown headings, lists, blockquotes, tables, inline emphasis."""
        if not content:
            return
        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            stripped = line.strip()

            # Empty line: skip (paragraph break handled by next non-empty)
            if not stripped:
                i += 1
                continue

            # 1. Markdown table
            if (stripped.startswith('|') and stripped.endswith('|')
                    and i + 1 < len(lines)
                    and re.match(r'^\s*\|[\s\-:|]+\|\s*$', lines[i+1])):
                header_cells = [c.strip() for c in stripped.strip('|').split('|')]
                i += 2
                body_rows = []
                while i < len(lines):
                    row_line = lines[i].strip()
                    if row_line.startswith('|') and row_line.endswith('|'):
                        cells = [c.strip() for c in row_line.strip('|').split('|')]
                        while len(cells) < len(header_cells):
                            cells.append('')
                        body_rows.append(cells[:len(header_cells)])
                        i += 1
                    else:
                        break
                if body_rows:
                    table(header_cells, body_rows)
                    para('')
                continue

            # 2. Horizontal rule (---) → spacer
            if re.match(r'^[-=*]{3,}$', stripped):
                para('')
                i += 1
                continue

            # 3. Markdown heading (#, ##, ###, ####)
            h_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            if h_match:
                level = len(h_match.group(1))
                text = h_match.group(2).rstrip('#').strip()
                add_md_heading(text, level=level)
                i += 1
                continue

            # 4. Blockquote (>) → italic indented paragraph
            if stripped.startswith('>'):
                # Collect consecutive quote lines
                quote_lines = []
                while i < len(lines) and lines[i].strip().startswith('>'):
                    quote_lines.append(lines[i].strip()[1:].strip())
                    i += 1
                quote_text = ' '.join(quote_lines)
                add_md_paragraph(quote_text, base_size=10, base_italic=True, indent=0.3)
                continue

            # 5. Bullet list (- or *)
            if re.match(r'^[-*+]\s+', stripped):
                text = re.sub(r'^[-*+]\s+', '', stripped)
                p = doc.add_paragraph(style='List Bullet')
                add_inline_runs(p, text, base_size=10)
                i += 1
                continue

            # 6. Numbered list
            if re.match(r'^\d+[\.\)]\s+', stripped):
                text = re.sub(r'^\d+[\.\)]\s+', '', stripped)
                p = doc.add_paragraph(style='List Number')
                add_inline_runs(p, text, base_size=10)
                i += 1
                continue

            # 7. Plain paragraph (with inline markdown)
            add_md_paragraph(stripped, base_size=10)
            i += 1

    # 표지
    doc.add_paragraph()
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f'{meta["stock_name"]} ({meta["stock_code"]})')
    run.font.size = Pt(28)
    run.bold = True
    run.font.color.rgb = RGBColor(13, 71, 161)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('Investment Research Report')
    run.font.size = Pt(16)
    run.font.color.rgb = RGBColor(21, 101, 192)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(meta["industry"])
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(100, 100, 100)

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cur = f'{meta["currency"]}{price["current"]:,}' if meta["country"] == "KR" else f'${price["current"]:,}'
    bear_p = f'{meta["currency"]}{opinion["target_bear"]:,}' if meta["country"] == "KR" else f'${opinion["target_bear"]:,}'
    base_p = f'{meta["currency"]}{opinion["target_base"]:,}' if meta["country"] == "KR" else f'${opinion["target_base"]:,}'
    bull_p = f'{meta["currency"]}{opinion["target_bull"]:,}' if meta["country"] == "KR" else f'${opinion["target_bull"]:,}'
    run = p.add_run(f'투자의견: {opinion["rating"]} | 목표주가: {base_p} | 현재가: {cur}')
    run.font.size = Pt(11)
    run.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f'투자 성격: {opinion["type"]} | 포트폴리오 역할: {opinion["portfolio_role"]}')
    run.font.size = Pt(10)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f'{meta["date"]} 기준')
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(150, 150, 150)

    doc.add_page_break()

    # 목차
    heading('목차', level=1)
    toc = [
        '1. 투자의견 & 목표주가', '2. 투자포인트', '3. 회사 개요',
        '4. 산업 & 시장', '5. 경쟁 구도', '6. 경제적 해자',
        '7. 경영진', '8. 재무 분석 + Forward 추정',
        '9. 밸류에이션', '10. 매크로 리스크', '11. 카탈리스트 타임라인',
        '12. Bear/Base/Bull 시나리오', '13. 투자 논문', '14. 숏 논거 + 반박',
        '15. 실적 Beat/Miss', '16. 애널리스트 컨센서스',
        '17. 수급 분석', '18. 주주환원', '19. Trust/Worry/Watch',
        '20. 실행 계획', '21. 분석 신뢰도'
    ]
    for item in toc:
        para(item, size=10)
    doc.add_page_break()

    # 핵심 추정 테이블
    heading('핵심 실적 추정 & 투자 지표', level=1)
    table(fin["headers"], fin["rows"])
    para(f'출처: {fin["source"]}', size=8)

    para('')
    para('사업부별 매출 비중', bold=True, size=11)
    seg_rows = [[s["name"], f'{s["pct"]}%', s["outlook"]] for s in data["segments"]]
    table(['사업부', '비중', '전망'], seg_rows)

    doc.add_page_break()

    # 21개 섹션
    section_titles = {
        "s01_opinion": "1. 투자의견 & 목표주가",
        "s02_investment_points": "2. 투자포인트 (Why This Stock Now?)",
        "s03_company_overview": "3. 회사 개요 / 비즈니스 모델",
        "s04_industry": "4. 산업 & 시장 분석",
        "s05_competition": "5. 경쟁 구도 + Peer Comparison",
        "s06_moat": "6. 경제적 해자 & 경쟁우위",
        "s07_management": "7. 경영진 분석",
        "s08_financial": "8. 재무 분석",
        "s09_valuation": "9. 밸류에이션",
        "s10_macro": "10. 매크로 리스크 & 민감도",
        "s11_catalysts": "11. 카탈리스트 타임라인",
        "s12_scenarios": "12. Bear / Base / Bull 시나리오",
        "s13_thesis": "13. 투자 논문 (Investment Thesis)",
        "s14_short_thesis": "14. 숏 논거 3가지 + 반박",
        "s15_beat_miss": "15. 실적 Beat/Miss 이력",
        "s16_consensus": "16. 애널리스트 컨센서스 비교",
        "s17_supply": "17. 수급 분석",
        "s18_shareholder_return": "18. 주주환원 정책",
        "s19_trust_worry_watch": "19. Trust / Worry / Watch",
        "s20_action_plan": "20. 실행 계획",
        "s21_reliability": "21. 분석 신뢰도 & 한계",
    }

    for key, title in section_titles.items():
        heading(title, level=1)
        content = sections.get(key, "")

        # 카탈리스트는 테이블로
        if key == "s11_catalysts" and "catalysts" in data:
            cat_rows = []
            for c in data["catalysts"]:
                cat_rows.append([
                    _strip_emoji(str(c.get("date", ""))),
                    _strip_emoji(str(c.get("event", ""))),
                    _strip_emoji(str(c.get("impact", ""))),
                ])
            if cat_rows:
                table(["시기", "이벤트", "영향"], cat_rows)
            # Also render any narrative content from s11 section
            if content:
                para('')
                render_section_content(content)
        elif content:
            render_section_content(content)

        # 8번 섹션에 Forward 추정 테이블 추가
        if key == "s08_financial":
            para('')
            para('Forward 실적 추정', bold=True, size=11)
            table(fin["headers"], fin["rows"])
            para(f'출처: {fin["source"]}', size=8)

        # 페이지 나누기 (일부 섹션 후)
        if key in ("s05_competition", "s08_financial", "s12_scenarios", "s15_beat_miss"):
            doc.add_page_break()

    # 저장
    name = meta["stock_name"].replace(" ", "")
    docx_path = os.path.join(output_dir, f'report_{name}_상세.docx')
    doc.save(docx_path)
    print(f'[OK] Word 생성: {docx_path}')

    # PDF 변환
    try:
        from docx2pdf import convert
        pdf_path = os.path.join(output_dir, f'report_{name}_상세.pdf')
        convert(docx_path, pdf_path)
        os.remove(docx_path)  # Word 파일 삭제 (PDF만 남김)
        print(f'[OK] 상세 PDF: {pdf_path} ({os.path.getsize(pdf_path)//1024} KB)')
    except Exception as e:
        print(f'[!!] PDF 변환 실패: {e}, Word 파일만 생성됨')


# ============================================
# 2. 요약 리포트 (HTML → PDF)
# ============================================
def generate_summary_report(data, output_dir):
    """Institutional-grade 8-page summary PDF (Navy + Gold palette, NYT/Bloomberg styling)."""
    return _generate_summary_v2(data, output_dir)


# ==========================================================================
# 2B. INSTITUTIONAL SUMMARY (v2 — Navy/Gold, 8-page fixed layout)
# ==========================================================================
_SUMMARY_V2_CSS = r"""
  @page { size: A4; margin: 0; }
  * { box-sizing: border-box; }
  html, body {
    margin: 0;
    padding: 0;
    font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
    color: #0a0e1a;
    font-size: 10pt;
    line-height: 1.65;
    -webkit-font-smoothing: antialiased;
  }
  .serif {
    font-family: Georgia, 'Times New Roman', 'Nanum Myeongjo', serif;
  }
  .page {
    width: 210mm;
    min-height: 297mm;
    padding: 20mm 22mm 22mm 22mm;
    position: relative;
    page-break-after: always;
    background: #ffffff;
  }
  .page:last-of-type { page-break-after: auto; }

  /* ---------- Running Header ---------- */
  .running-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 3mm;
    margin-bottom: 8mm;
    border-bottom: 1px solid #e4e7ec;
    font-size: 7.5pt;
    color: #7a8699;
    letter-spacing: 2px;
    text-transform: uppercase;
  }
  .running-header .brand { font-weight: 700; color: #0b2545; letter-spacing: 2.5px; }
  .running-header .page-num { font-variant-numeric: tabular-nums; }

  /* ---------- Section Caption + Heading ---------- */
  .section-caption {
    color: #b8922e;
    font-size: 8.5pt;
    letter-spacing: 3px;
    text-transform: uppercase;
    font-weight: 700;
    margin-top: 2mm;
  }
  .section-heading {
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 24pt;
    font-weight: 300;
    color: #0b2545;
    margin: 2mm 0 6mm 0;
    line-height: 1.15;
    letter-spacing: -0.3px;
  }
  .section-intro {
    font-size: 10pt;
    line-height: 1.65;
    color: #3a4658;
    margin-bottom: 6mm;
    max-width: 160mm;
  }

  /* ---------- Sub heading with gold bar ---------- */
  .sub-heading {
    font-size: 11pt;
    font-weight: 700;
    color: #0b2545;
    padding-left: 4mm;
    border-left: 3px solid #b8922e;
    margin: 6mm 0 3mm 0;
    line-height: 1.3;
  }
  p { margin: 2mm 0; }

  /* ========== PAGE 1: COVER ========== */
  .cover {
    background: linear-gradient(165deg, #0b2545 0%, #0e2b55 45%, #122f5d 100%);
    color: #f0f3f8;
    padding: 25mm 22mm 22mm 22mm;
    min-height: 297mm;
    position: relative;
  }
  .cover::before {
    content: "";
    position: absolute;
    top: 0; right: 0;
    width: 90mm; height: 90mm;
    background: radial-gradient(circle at top right, rgba(184,146,46,0.14), transparent 70%);
    pointer-events: none;
  }
  .cover .brand-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 5mm;
    border-bottom: 1px solid rgba(184,146,46,0.6);
    font-size: 8.5pt;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    color: #b8922e;
  }
  .cover .brand-bar .left { font-weight: 700; }
  .cover .cover-body { margin-top: 28mm; }
  .cover .cap-gold {
    color: #b8922e;
    font-size: 9pt;
    letter-spacing: 3px;
    text-transform: uppercase;
    font-weight: 600;
  }
  .cover h1.stock-title {
    font-family: Georgia, 'Times New Roman', 'Nanum Myeongjo', serif;
    font-size: 52pt;
    font-weight: 300;
    margin: 5mm 0 3mm 0;
    line-height: 0.95;
    color: #ffffff;
    letter-spacing: -1px;
  }
  .cover .stock-meta {
    font-size: 11pt;
    color: #b8c3d4;
    letter-spacing: 1px;
    font-weight: 300;
  }
  .cover .tagline {
    margin-top: 14mm;
    font-family: Georgia, serif;
    font-size: 18pt;
    font-weight: 300;
    line-height: 1.35;
    color: #e0e6f0;
    max-width: 140mm;
    font-style: italic;
  }
  .cover .pick-box {
    position: absolute;
    left: 22mm;
    right: 22mm;
    bottom: 29mm;
    border: 1px solid rgba(184,146,46,0.7);
    padding: 5mm 6mm;
    background: rgba(0,0,0,0.22);
    min-height: 32mm;
  }
  .cover .pick-label {
    color: #b8922e;
    font-size: 8pt;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    font-weight: 700;
  }
  .cover .pick-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 4mm;
  }
  .cover .pick-badge {
    display: inline-block;
    padding: 3mm 8mm;
    font-size: 16pt;
    font-weight: 700;
    color: #0b2545;
    background: #b8922e;
    letter-spacing: 2px;
  }
  .cover .pick-metrics {
    text-align: right;
    font-size: 10pt;
    color: #e0e6f0;
    font-variant-numeric: tabular-nums;
    line-height: 1.55;
  }
  .cover .pick-metrics .big {
    font-size: 14pt;
    font-weight: 600;
    color: #ffffff;
  }
  .cover .cover-footer {
    position: absolute;
    left: 22mm;
    right: 22mm;
    bottom: 18mm;
    font-size: 7.5pt;
    letter-spacing: 1.5px;
    color: #8593aa;
    text-transform: uppercase;
    display: flex;
    justify-content: space-between;
    padding-top: 4mm;
    border-top: 1px solid rgba(184,146,46,0.3);
  }

  /* ========== Cover Dashboard (3열 데이터 그리드, 융합 스타일) ========== */
  .cover .dashboard {
    position: absolute;
    left: 22mm;
    right: 22mm;
    bottom: 78mm;
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 6mm;
    background: rgba(0,0,0,0.22);
    border-top: 0.8px solid rgba(184,146,46,0.7);
    border-bottom: 0.8px solid rgba(184,146,46,0.7);
    padding: 4mm 5mm;
  }
  .cover .dash-block {
    padding: 0;
    font-size: 7.8pt;
    line-height: 1.55;
  }
  .cover .dash-title {
    color: #b8922e;
    font-size: 7pt;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    font-weight: 700;
    margin-bottom: 2.5mm;
    padding-bottom: 1mm;
    border-bottom: 0.5px solid rgba(184,146,46,0.5);
  }
  .cover .dash-row {
    display: flex;
    justify-content: space-between;
    color: #e0e6f0;
    font-variant-numeric: tabular-nums;
    padding: 0.3mm 0;
  }
  .cover .dash-row .lbl { color: #8593aa; font-size: 7.3pt; }
  .cover .dash-row .val { color: #ffffff; font-weight: 600; font-size: 7.8pt; }
  .cover .dash-row.pos .val { color: #86c7a5; }
  .cover .dash-row.neg .val { color: #e2a5a5; }

  /* pick-box 내 3-Target 세로 스펙트럼 */
  .cover .target-spectrum {
    display: grid;
    grid-template-columns: 1fr 1.2fr 1fr;
    gap: 0;
    margin-top: 2mm;
  }
  .cover .target-cell {
    padding: 1.5mm 3mm;
    border-right: 0.5px solid rgba(184,146,46,0.3);
    text-align: center;
  }
  .cover .target-cell:last-child { border-right: none; }
  .cover .target-cell .t-lbl {
    font-size: 7pt;
    letter-spacing: 2px;
    color: #8593aa;
    text-transform: uppercase;
    font-weight: 700;
  }
  .cover .target-cell .t-val {
    font-family: Georgia, serif;
    font-size: 14pt;
    font-weight: 400;
    color: #e0e6f0;
    margin-top: 0.5mm;
    font-variant-numeric: tabular-nums;
  }
  .cover .target-cell.base .t-val {
    font-size: 20pt;
    color: #ffffff;
    font-weight: 500;
  }
  .cover .target-cell.base .t-lbl { color: #b8922e; }
  .cover .target-cell.bear .t-val { color: #e2a5a5; }
  .cover .target-cell.bull .t-val { color: #86c7a5; }
  .cover .target-cell .t-delta {
    font-size: 7.5pt;
    color: #8593aa;
    margin-top: 0.3mm;
    font-variant-numeric: tabular-nums;
  }
  .cover .target-cell.base .t-delta { color: #d0d6e0; font-weight: 600; }

  /* ========== Verdict Card ========== */
  .verdict-card {
    border: 1px solid #e4e7ec;
    margin-top: 2mm;
  }
  .verdict-head {
    background: #0b2545;
    color: #ffffff;
    padding: 3.5mm 5mm;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 9pt;
    letter-spacing: 2px;
    text-transform: uppercase;
  }
  .verdict-head .title { font-weight: 700; }
  .verdict-rating-badge {
    background: #b8922e;
    color: #0b2545;
    padding: 1.8mm 5mm;
    font-weight: 700;
    font-size: 12pt;
    letter-spacing: 2px;
  }
  .verdict-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
  }
  .verdict-cell {
    padding: 4mm 5mm 4mm 5mm;
    border-right: 1px solid #e4e7ec;
    border-bottom: 1px solid #e4e7ec;
  }
  .verdict-cell.last-col { border-right: none; }
  .verdict-cell.last-row { border-bottom: none; }
  .verdict-cell .lbl {
    font-size: 7.5pt;
    color: #7a8699;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 600;
  }
  .verdict-cell .val {
    font-family: Georgia, serif;
    font-size: 17pt;
    font-weight: 400;
    color: #0b2545;
    margin-top: 1mm;
    font-variant-numeric: tabular-nums;
    line-height: 1.15;
  }
  .verdict-cell .delta {
    font-size: 8.5pt;
    color: #7a8699;
    margin-top: 0.5mm;
    font-variant-numeric: tabular-nums;
  }
  .verdict-cell .delta.pos { color: #2a6b4a; }
  .verdict-cell .delta.neg { color: #8b2e2e; }

  /* ========== Core Thesis italic block ========== */
  .core-thesis {
    margin-top: 6mm;
    padding: 5mm 6mm;
    background: #fafbfc;
    border-left: 3px solid #b8922e;
    font-family: Georgia, serif;
    font-size: 10.5pt;
    font-style: italic;
    line-height: 1.7;
    color: #2a3342;
  }
  .core-thesis::before {
    content: "Core Thesis";
    display: block;
    font-family: 'Malgun Gothic', sans-serif;
    font-size: 7.5pt;
    color: #b8922e;
    letter-spacing: 2px;
    text-transform: uppercase;
    font-weight: 700;
    margin-bottom: 2mm;
    font-style: normal;
  }

  /* ========== KPI Block ========== */
  .kpi-row {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 4mm;
    margin-top: 6mm;
  }
  .kpi-block {
    border-top: 3px solid #0b2545;
    padding: 3mm 4mm 4mm 4mm;
    background: #fafbfc;
  }
  .kpi-block .lbl {
    font-size: 7.5pt;
    color: #7a8699;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 700;
  }
  .kpi-block .val {
    font-family: Georgia, serif;
    font-size: 24pt;
    font-weight: 300;
    color: #0b2545;
    line-height: 1.1;
    margin-top: 1mm;
    font-variant-numeric: tabular-nums;
  }
  .kpi-block .note {
    font-size: 8pt;
    color: #7a8699;
    margin-top: 1mm;
  }

  /* ========== NYT/Bloomberg Table ========== */
  .nyt {
    width: 100%;
    border-collapse: collapse;
    font-size: 9pt;
    margin: 4mm 0;
  }
  .nyt thead tr {
    border-top: 2px solid #0b2545;
    border-bottom: 1px solid #0b2545;
  }
  .nyt thead th {
    padding: 2mm 3mm;
    text-align: left;
    font-size: 7.5pt;
    color: #7a8699;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    font-weight: 700;
  }
  .nyt thead th.num { text-align: right; }
  .nyt tbody tr { border-bottom: 1px solid #edf0f4; }
  .nyt tbody tr:last-child { border-bottom: 2px solid #0b2545; }
  .nyt tbody td {
    padding: 2.2mm 3mm;
    color: #0a0e1a;
    font-size: 9pt;
  }
  .nyt tbody td.num {
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-feature-settings: "tnum";
  }
  .nyt tbody td.name { font-weight: 600; color: #0b2545; }
  .nyt .bear-row td { color: #8b2e2e; }
  .nyt .bull-row td { color: #2a6b4a; }

  /* ========== Thesis Points ========== */
  .thesis-points { margin-top: 4mm; }
  .thesis-point {
    margin-bottom: 7mm;
    padding-left: 11mm;
    position: relative;
    padding-bottom: 4mm;
    border-bottom: 1px solid #edf0f4;
  }
  .thesis-point:last-child { border-bottom: none; }
  .thesis-point .num {
    position: absolute;
    left: 0;
    top: -1mm;
    font-family: Georgia, serif;
    color: #b8922e;
    font-size: 22pt;
    font-weight: 300;
    line-height: 1;
  }
  .thesis-point .title {
    font-size: 11.5pt;
    font-weight: 700;
    color: #0b2545;
    margin-bottom: 2mm;
    line-height: 1.35;
  }
  .thesis-point .body {
    font-size: 9.5pt;
    line-height: 1.65;
    color: #2a3342;
  }

  /* ========== Kill Switch ========== */
  .kill-switch {
    margin-top: 5mm;
    background: #f5eaea;
    border-left: 4px solid #8b2e2e;
    padding: 4mm 6mm 5mm 6mm;
  }
  .kill-switch .label {
    font-size: 8pt;
    color: #8b2e2e;
    text-transform: uppercase;
    letter-spacing: 2px;
    font-weight: 700;
  }
  .kill-switch .body {
    margin-top: 2mm;
    font-size: 9.5pt;
    line-height: 1.6;
    color: #3a2020;
  }

  /* ========== Final Call ========== */
  .final-call {
    margin-top: 12mm;
    border-top: 4px double #0b2545;
    border-bottom: 4px double #0b2545;
    padding: 7mm 9mm;
    position: relative;
  }
  .final-call .caption {
    color: #b8922e;
    font-size: 8pt;
    letter-spacing: 3px;
    text-transform: uppercase;
    font-weight: 700;
  }
  .final-call .conclusion {
    margin-top: 3mm;
    font-family: Georgia, serif;
    font-style: italic;
    font-size: 13pt;
    line-height: 1.55;
    color: #0b2545;
  }
  .final-call .signature {
    margin-top: 5mm;
    font-size: 8.5pt;
    color: #7a8699;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    display: flex;
    justify-content: space-between;
  }

  /* ========== Star Rating ========== */
  .rr-stars {
    display: table;
    width: 100%;
    margin-top: 4mm;
    border-top: 1px solid #e4e7ec;
    border-bottom: 1px solid #e4e7ec;
  }
  .rr-stars .row {
    display: table-row;
  }
  .rr-stars .cell {
    display: table-cell;
    padding: 3mm 4mm;
    vertical-align: middle;
    border-bottom: 1px solid #edf0f4;
  }
  .rr-stars .row:last-child .cell { border-bottom: none; }
  .rr-stars .label-cell {
    width: 30%;
    font-size: 9pt;
    font-weight: 700;
    color: #0b2545;
    letter-spacing: 1px;
    text-transform: uppercase;
  }
  .rr-stars .stars-cell {
    width: 30%;
    color: #b8922e;
    font-size: 15pt;
    letter-spacing: 1mm;
    line-height: 1;
  }
  .rr-stars .stars-cell .dim { color: #e4e7ec; }
  .rr-stars .value-cell {
    width: 40%;
    font-size: 9pt;
    color: #7a8699;
    font-variant-numeric: tabular-nums;
    text-align: right;
  }

  /* ========== Segment list ========== */
  .seg-list {
    margin-top: 3mm;
    border-top: 1px solid #e4e7ec;
  }
  .seg-item {
    display: flex;
    align-items: center;
    padding: 2.5mm 0;
    border-bottom: 1px solid #edf0f4;
    font-size: 9pt;
  }
  .seg-item .seg-name {
    width: 38%;
    font-weight: 600;
    color: #0b2545;
  }
  .seg-item .seg-pct {
    width: 18%;
    font-variant-numeric: tabular-nums;
    color: #0b2545;
    font-weight: 700;
  }
  .seg-item .seg-outlook {
    flex: 1;
    font-size: 8.5pt;
    color: #3a4658;
  }

  /* ========== Simple two column ========== */
  .two-col {
    display: grid;
    grid-template-columns: 1.1fr 1fr;
    gap: 7mm;
    margin-top: 4mm;
  }
  .two-col .col > .sub-heading:first-child { margin-top: 0; }

  /* ========== Page footer ========== */
  .page-footer {
    position: absolute;
    left: 22mm;
    right: 22mm;
    bottom: 12mm;
    padding-top: 3mm;
    border-top: 1px solid #e4e7ec;
    display: flex;
    justify-content: space-between;
    font-size: 7pt;
    color: #9ca6b5;
    letter-spacing: 1.5px;
    text-transform: uppercase;
  }
"""


def _sv2_extract_points(text, count=3):
    """Extract top N thesis points from s02. Supports both ### 포인트 N. and **포인트 N.** formats."""
    if not text:
        return []
    text = _strip_emoji(text)
    # Pattern A: ### 포인트 N. 제목 (markdown heading style)
    pattern_a = re.compile(
        r'###\s*\[?(?:Bear|Bull)?\]?\s*포인트\s*(\d+)[\.\)]?\s*([^\n]+)\n+'
        r'((?:(?!###|---|\Z)[\s\S])+?)(?=###|---|\Z)',
        re.MULTILINE
    )
    matches = pattern_a.findall(text)
    if not matches:
        # Pattern B: **포인트 N. 제목** (bold style)
        pattern_b = re.compile(
            r'\*\*포인트\s*(\d+)[\.\)]?\s*([^*\n]+?)\*\*\s*\n+'
            r'((?:(?!\*\*포인트|###)[\s\S])+?)(?=\*\*포인트|###|\Z)',
            re.MULTILINE
        )
        matches = pattern_b.findall(text)

    out = []
    for m in matches[:count]:
        num_s, title, body = m
        # Title: remove markdown emphasis
        title = re.sub(r'\*\*(.+?)\*\*', r'\1', title)
        title = re.sub(r'\*(.+?)\*', r'\1', title)
        title = title.strip()
        # Body: prefer the "주장" (claim) bullet for the lead, then "근거 숫자"
        # Strip emphasis
        body = re.sub(r'\*\*(.+?)\*\*', r'\1', body)
        body = re.sub(r'`(.+?)`', r'\1', body)
        # Try to extract claim ("주장:") line if present
        claim_match = re.search(r'주장\s*[::]\s*([^\n]+)', body)
        evidence_match = re.search(r'근거\s*숫자\s*[::]\s*([^\n]+)', body)
        market_missed_match = re.search(r'시장이?\s*놓친\s*것\s*[::]\s*([^\n]+)', body)

        parts = []
        if claim_match:
            parts.append(claim_match.group(1).strip())
        if evidence_match:
            ev = evidence_match.group(1).strip()
            if len(ev) > 180:
                ev = ev[:180].rsplit(' ', 1)[0] + '…'
            parts.append(ev)
        if market_missed_match and not parts:
            parts.append(market_missed_match.group(1).strip())

        if not parts:
            # Fallback: collapse body to first 260 chars
            tmp = re.sub(r'^-\s*', '', body, flags=re.MULTILINE)
            tmp = re.sub(r'\n+', ' ', tmp)
            tmp = re.sub(r'\s+', ' ', tmp).strip()
            parts.append(tmp[:260])

        body_clean = ' '.join(parts)
        if len(body_clean) > 280:
            body_clean = body_clean[:280].rsplit(' ', 1)[0] + '…'

        # Strip markdown table fragments and trailing pipes
        body_clean = re.sub(r'\|[^\n]*\|', '', body_clean)
        body_clean = re.sub(r'\s+', ' ', body_clean).strip()
        # Remove trailing dots+space artifacts
        body_clean = re.sub(r'\s*\.{2,}\s*$', '…', body_clean)
        if len(body_clean) > 280:
            body_clean = body_clean[:280].rsplit(' ', 1)[0] + '…'
        out.append({
            "num": num_s,
            "title": html_lib.escape(title),
            "body": html_lib.escape(body_clean),
        })
    return out


def _sv2_first_para(text, max_len=280, min_len=100):
    """Extract first meaningful narrative paragraph from a markdown section.

    Skips: headings, tables, code, footnotes (^\\*), labels-only lines, list markers.
    Joins multiple short paragraphs until reaching min_len for substance.
    """
    if not text:
        return ""
    text = _strip_emoji(text)

    # Pre-clean: split into paragraph blocks (separated by blank lines)
    blocks = re.split(r'\n\s*\n', text)

    candidates = []
    for blk in blocks:
        # Strip block of all skip-lines
        clean_lines = []
        for line in blk.split('\n'):
            s = line.strip()
            if not s:
                continue
            if s.startswith('#'):  # heading
                continue
            if s.startswith('|') or s.startswith('---') or s.startswith('==='):  # table/divider
                continue
            if s.startswith('```'):
                continue
            if s.startswith('>'):
                s = s[1:].strip()
            # Skip footnote lines (^*Foo: ...)
            if re.match(r'^\*[^*]', s):
                continue
            # Strip leading list markers but keep the content
            s = re.sub(r'^[-*]\s+', '', s)
            # Skip lines that are just **label**: with empty body
            if re.fullmatch(r'\*\*[^*]+\*\*\s*[::]?\s*', s):
                continue
            clean_lines.append(s)
        if not clean_lines:
            continue
        block_text = ' '.join(clean_lines)
        # Strip emphasis markers
        block_text = re.sub(r'\*\*(.+?)\*\*', r'\1', block_text)
        block_text = re.sub(r'\*(.+?)\*', r'\1', block_text)
        block_text = re.sub(r'`(.+?)`', r'\1', block_text)
        # Drop inline table fragments
        block_text = re.sub(r'\|[^\n]*\|', '', block_text)
        # Normalize whitespace
        block_text = re.sub(r'\s+', ' ', block_text).strip()
        # Skip very short blocks (likely orphan footnote or stub)
        if len(block_text) < 20:
            continue
        candidates.append(block_text)

    if not candidates:
        return ""

    # Join candidates until reaching min_len for substance
    joined = ""
    for c in candidates:
        if not joined:
            joined = c
        elif len(joined) < min_len:
            joined = joined + ' ' + c
        else:
            break

    if len(joined) > max_len:
        joined = joined[:max_len].rsplit(' ', 1)[0] + '…'

    return html_lib.escape(joined)


def _sv2_extract_kill_switch(text, max_len=300):
    """Look for 'reverse' or 'halve' scenario in risk section."""
    if not text:
        return ""
    text = _strip_emoji(text)
    # Look for the specific trigger pattern
    m = re.search(r'주가를\s*반토막[^\n]*\n+([^\n]+(?:\n[^\n#|]+){0,4})', text)
    if m:
        body = m.group(1)
    else:
        # Fallback: first paragraph of risk section
        return _sv2_first_para(text, max_len)
    body = re.sub(r'\*\*(.+?)\*\*', r'\1', body)
    body = re.sub(r'`(.+?)`', r'\1', body)
    body = re.sub(r'^-\s*', '', body, flags=re.MULTILINE)
    body = re.sub(r'\n+', ' ', body)
    body = re.sub(r'\s+', ' ', body).strip()
    if len(body) > max_len:
        body = body[:max_len].rsplit(' ', 1)[0] + '…'
    return html_lib.escape(body)


def _sv2_star_row(value_pct):
    """Return 5 stars HTML based on percent value."""
    if value_pct >= 40:
        filled = 5
    elif value_pct >= 20:
        filled = 4
    elif value_pct >= 0:
        filled = 3
    elif value_pct >= -20:
        filled = 2
    elif value_pct >= -40:
        filled = 1
    else:
        filled = 0
    stars = '★' * filled
    dim = '<span class="dim">' + ('★' * (5 - filled)) + '</span>' if filled < 5 else ''
    return stars + dim


def _generate_summary_v2(data, output_dir):
    """v2: 8-page institutional PDF with Navy/Gold palette."""
    meta = data["meta"]
    price = data["price"]
    opinion = data["opinion"]
    fin = data["financials"]
    segs = data["segments"]
    peers = data.get("peers", [])
    catalysts = data.get("catalysts", [])
    supply = data.get("supply", {})
    sections = data["sections"]

    name = meta["stock_name"].replace(" ", "")
    is_kr = meta["country"] == "KR"
    c = meta.get("currency", "원") if is_kr else "$"

    def fmt_money(v):
        if v is None:
            return "N/A"
        if is_kr:
            return f'{int(v):,}원'
        return f'${float(v):,.2f}'

    def safe(v, default="—"):
        return default if v is None else v

    # ---- Price ratios ----
    cur_price = price.get("current") or 1
    up_base = ((opinion["target_base"] - cur_price) / cur_price) * 100
    up_bull = ((opinion["target_bull"] - cur_price) / cur_price) * 100
    down_bear = ((opinion["target_bear"] - cur_price) / cur_price) * 100

    rating = opinion.get("rating", "HOLD")
    rating_type = opinion.get("type", "")
    rr = opinion.get("risk_reward", "—")

    # ---- Extract content ----
    thesis_points = _sv2_extract_points(sections.get("s02_investment_points", ""), 3)
    # Fallback: use generic bullets if extraction fails
    if len(thesis_points) < 3:
        thesis_points = [
            {"num": "1", "title": "투자포인트 #1", "body": _sv2_first_para(sections.get("s02_investment_points", ""), 240)},
            {"num": "2", "title": "투자포인트 #2", "body": _sv2_first_para(sections.get("s13_thesis", ""), 240)},
            {"num": "3", "title": "투자포인트 #3", "body": _sv2_first_para(sections.get("s14_short_thesis", ""), 240)},
        ]

    core_thesis = _sv2_first_para(sections.get("s13_thesis", "") or sections.get("s01_opinion", ""), 300)
    industry_overview = _sv2_first_para(sections.get("s04_industry", ""), 320)
    business_overview = _sv2_first_para(sections.get("s03_company_overview", ""), 300)
    financial_summary = _sv2_first_para(sections.get("s08_financial", ""), 300)
    valuation_summary = _sv2_first_para(sections.get("s09_valuation", ""), 280)
    macro_summary = _sv2_first_para(sections.get("s10_macro", ""), 260)
    kill_switch = _sv2_extract_kill_switch(sections.get("s10_macro", ""), 280)
    action_summary = _sv2_first_para(sections.get("s20_action_plan", ""), 280)
    final_conclusion = _sv2_first_para(sections.get("s13_thesis", "") or sections.get("s01_opinion", ""), 320)

    # ---- Tagline (cover subtitle, Georgia italic) ----
    # Priority: meta.tagline (LLM 생성 한국어 카피) > meta.subtitle (legacy) > derived
    tagline = meta.get("tagline") or meta.get("subtitle")
    if not tagline:
        industry = meta.get('industry', '')
        stock_name = meta.get('stock_name', '')
        # 한국어 개성 카피 (위닝펀드 스타일 참조)
        if rating == "BUY":
            tagline = f"{industry} -- 시장이 아직 보지 못한 비대칭"
        elif rating == "SELL":
            tagline = f"{industry} -- 내러티브가 가격을 앞서간 자리"
        else:
            tagline = f"{industry} -- 기대와 리스크 사이, 균형의 순간"
    tagline = _strip_emoji(tagline)

    # ---- Financials table subset (top 6 rows) ----
    fin_headers = fin.get("headers", [])
    fin_rows = fin.get("rows", [])[:6]

    def render_fin_table():
        if not fin_headers or not fin_rows:
            return "<p>재무 데이터 없음</p>"
        th = ''.join(
            f'<th class="{"num" if i > 0 else ""}">{html_lib.escape(str(h))}</th>'
            for i, h in enumerate(fin_headers)
        )
        rows_html = ''
        for row in fin_rows:
            cells = ''
            for i, v in enumerate(row):
                cls = "num" if i > 0 else "name"
                cells += f'<td class="{cls}">{html_lib.escape(str(v))}</td>'
            rows_html += f'<tr>{cells}</tr>'
        return f'<table class="nyt"><thead><tr>{th}</tr></thead><tbody>{rows_html}</tbody></table>'

    def render_peer_table():
        if not peers:
            return ""
        rows_html = ''
        for p in peers[:6]:
            highlight_cls = ' class="bull-row"' if p.get("highlight") else ''
            rows_html += (
                f'<tr{highlight_cls}>'
                f'<td class="name">{html_lib.escape(_strip_emoji(str(p.get("name",""))))}</td>'
                f'<td class="num">{html_lib.escape(_strip_emoji(str(p.get("market_cap",""))))}</td>'
                f'<td class="num">{html_lib.escape(_strip_emoji(str(p.get("per",""))))}</td>'
                f'<td class="num">{html_lib.escape(_strip_emoji(str(p.get("pbr",""))))}</td>'
                f'</tr>'
            )
        return (
            '<table class="nyt"><thead><tr>'
            '<th>Peer</th><th class="num">시가총액</th><th class="num">PER</th><th class="num">PBR</th>'
            '</tr></thead><tbody>' + rows_html + '</tbody></table>'
        )

    def render_segment_list():
        if not segs:
            return ""
        items = ''
        for s in segs[:6]:
            items += (
                f'<div class="seg-item">'
                f'<div class="seg-name">{html_lib.escape(_strip_emoji(str(s.get("name",""))))}</div>'
                f'<div class="seg-pct">{html_lib.escape(str(s.get("pct","")))}%</div>'
                f'<div class="seg-outlook">{html_lib.escape(_strip_emoji(str(s.get("outlook",""))))}</div>'
                f'</div>'
            )
        return f'<div class="seg-list">{items}</div>'

    def render_catalyst_table():
        if not catalysts:
            return ""
        rows_html = ''
        for ct in catalysts[:5]:
            rows_html += (
                f'<tr>'
                f'<td class="name">{html_lib.escape(_strip_emoji(str(ct.get("date",""))))}</td>'
                f'<td>{html_lib.escape(_strip_emoji(str(ct.get("event",""))))}</td>'
                f'<td class="num">{html_lib.escape(_strip_emoji(str(ct.get("impact",""))))}</td>'
                f'</tr>'
            )
        return (
            '<table class="nyt"><thead><tr>'
            '<th>시기</th><th>이벤트</th><th class="num">영향</th>'
            '</tr></thead><tbody>' + rows_html + '</tbody></table>'
        )

    # ==========================================================================
    # PAGE 1 — COVER
    # ==========================================================================
    cover_rating_color = {"BUY": "#0a56d6", "HOLD": "#6b7280", "SELL": "#d32f2f"}.get(rating, "#b8922e")

    # ----- Cover Dashboard 계산: 1M/6M/12M 수익률 (daily_prices 이용) -----
    def _calc_return(prices, trading_days):
        if not prices or len(prices) < 2:
            return None
        try:
            cur = float(prices[0].get('close', 0))
            idx = min(trading_days, len(prices) - 1)
            past = float(prices[idx].get('close', 0))
            if past == 0:
                return None
            return (cur - past) / past * 100
        except (TypeError, ValueError):
            return None

    daily = price.get('daily_prices', []) or []
    r_1m = _calc_return(daily, 21)   # ~1개월 거래일
    r_6m = _calc_return(daily, 126)  # ~6개월
    r_12m = _calc_return(daily, 252) # ~12개월

    def _ret_cell(v):
        if v is None:
            return '<span class="val">—</span>'
        cls = "pos" if v > 0 else "neg"
        return f'<span class="val" style="color:{"#86c7a5" if v>0 else "#e2a5a5"};">{v:+.1f}%</span>'

    # ----- Stock Data block -----
    def _price_fmt(v):
        if v is None or v == "":
            return "—"
        try:
            n = float(v)
            if is_kr:
                return f"{int(n):,}원"
            return f"${n:,.2f}"
        except (TypeError, ValueError):
            return str(v)

    # 52주 고/저 통합 포맷
    hi52 = price.get("high_52w")
    lo52 = price.get("low_52w")
    if hi52 and lo52:
        if is_kr:
            range_52w = f"{int(lo52):,} – {int(hi52):,}"
        else:
            range_52w = f"${lo52:,.2f} – ${hi52:,.2f}"
    else:
        range_52w = None

    stock_data_rows = [
        ("시가총액", price.get("market_cap")),
        ("52주 고/저", range_52w),  # 통합 1행
        # KIS 가 주는 PER 은 **직전 연간 EPS** 기준이지 TTM 이 아니다.
        # (실측 2026-09-08 LS일렉트릭: KIS 104.92배 = FY2025 EPS 1,911원 기준,
        #  TTM 지배순이익으로 계산하면 77.4배. 라벨이 TTM 이면 독자가 오해한다.)
        ("PER (후행)", f'{price.get("per")}x' if price.get("per") else None),
        ("PBR", f'{price.get("pbr")}x' if price.get("pbr") else None),
        ("EPS", _price_fmt(price.get("eps")) if price.get("eps") else None),
        ("BPS", _price_fmt(price.get("bps")) if price.get("bps") else None),
        ("배당수익률", price.get("dividend_yield")),
    ]

    # 빈 값 행 자동 스킵
    stock_data_html = ''
    for lbl, val in stock_data_rows:
        if val is None or val == "" or val == "—":
            continue
        stock_data_html += f'<div class="dash-row"><span class="lbl">{html_lib.escape(str(lbl))}</span><span class="val">{html_lib.escape(str(val))}</span></div>'

    # ----- 컨센서스 요약 block (재무 2년치 발췌 -- 실적/추정 명확화) -----
    cons_rows_html = ''
    cons_subtitle = ''
    _cons_is_forward = False
    if fin_headers and fin_rows and consensus_columns(fin_headers):
        # header에서 확정 마지막 idx + Forward 첫 idx 찾기
        last_actual, fwd_idx, is_forward = consensus_columns(fin_headers)
        _cons_is_forward = is_forward

        y_act = str(fin_headers[last_actual]) if last_actual < len(fin_headers) else ""
        y_fwd = str(fin_headers[fwd_idx]) if fwd_idx < len(fin_headers) else ""

        # 헤더 단위 정보 추출 (예: "매출(조)" → "조")
        rev_header = fin_headers[0] if fin_headers else ""
        unit_match = ""
        if "조" in str(rev_header): unit_match = "조원"
        elif "억" in str(rev_header): unit_match = "억원"
        elif "$" in str(rev_header) or "B" in str(rev_header).upper(): unit_match = "$B"

        # 서브타이틀: "2025 실적 / 2026E 추정"
        _unit = f' &nbsp;<span style="color:#b8922e;">({unit_match})</span>' if unit_match else ''
        _kind = '추정' if is_forward else '실적'
        cons_subtitle = (f'<div style="font-size:6.5pt; color:#8593aa; letter-spacing:1.5px; '
                         f'margin-bottom:1.5mm; text-align:center;">{html_lib.escape(y_act)} 실적 '
                         f'&nbsp;/&nbsp; {html_lib.escape(y_fwd)} {_kind}{_unit}</div>')

        # 핵심 5개 행 (주주(최대/외인) 는 데이터 없어 제외)
        keywords = [("매출", "매출"), ("영업이익", "영업이익"), ("순이익", "순이익"), ("EPS", "EPS"), ("OPM", "OPM")]
        for lbl, kw in keywords:
            for row in fin_rows:
                if row and kw in str(row[0]):
                    v_act = str(row[last_actual]) if last_actual < len(row) else None
                    v_fwd = str(row[fwd_idx]) if fwd_idx < len(row) else None
                    if not v_act or v_act == "—":
                        continue
                    cons_rows_html += f'<div class="dash-row"><span class="lbl">{html_lib.escape(lbl)}</span><span class="val" style="font-size:7pt;">{html_lib.escape(v_act)} → {html_lib.escape(v_fwd)}</span></div>'
                    break

    if not cons_rows_html:
        cons_rows_html = '<div class="dash-row"><span class="lbl">재무 데이터 없음</span><span class="val">—</span></div>'

    cons_block_title = '컨센서스 요약' if _cons_is_forward else '실적 추이'
    cons_rows_html = cons_subtitle + cons_rows_html

    # ----- 주가 수익률 & Forward 밸류에이션 block -----
    # 중복 방지: 52주 고/저는 Stock Data에만
    # 빈 행 자동 스킵
    ret_items = []
    if r_1m is not None: ret_items.append(("1개월", _ret_cell(r_1m)))
    if r_6m is not None: ret_items.append(("6개월", _ret_cell(r_6m)))
    if r_12m is not None: ret_items.append(("12개월", _ret_cell(r_12m)))
    if price.get("change_pct") is not None:
        cp = price.get("change_pct", 0)
        cls_c = "pos" if cp > 0 else ("neg" if cp < 0 else "")
        color_c = "#86c7a5" if cp > 0 else ("#e2a5a5" if cp < 0 else "#ffffff")
        ret_items.append(("일일 변동", f'<span class="val" style="color:{color_c};">{cp:+.2f}%</span>'))
    if price.get("per_forward_12m"):
        ret_items.append(("Forward PER", f'<span class="val">{price.get("per_forward_12m")}x</span>'))
    if price.get("sector_per"):
        ret_items.append(("섹터 PER", f'<span class="val">{price.get("sector_per")}x</span>'))

    returns_html = ''
    for lbl, cell in ret_items:
        returns_html += f'<div class="dash-row"><span class="lbl">{html_lib.escape(lbl)}</span>{cell}</div>'
    if not returns_html:
        returns_html = '<div class="dash-row"><span class="lbl">데이터 없음</span><span class="val">—</span></div>'

    page1 = f"""
<section class="page cover">
  <div class="brand-bar">
    <div class="left">AI Equity Research · {html_lib.escape(meta.get("country","KR"))} · {html_lib.escape(meta.get("market",""))}</div>
    <div class="right">{html_lib.escape(meta.get("date",""))}</div>
  </div>
  <div class="cover-body">
    <div class="cap-gold">— Equity Research Note —</div>
    <h1 class="stock-title">{html_lib.escape(meta.get("stock_name",""))}</h1>
    <div class="stock-meta">{html_lib.escape(meta.get("stock_code",""))} &nbsp;·&nbsp; {html_lib.escape(meta.get("industry",""))}</div>
    <div class="tagline">{html_lib.escape(tagline)}</div>
  </div>
  <div class="dashboard">
    <div class="dash-block">
      <div class="dash-title">핵심 지표</div>
      {stock_data_html}
    </div>
    <div class="dash-block">
      <div class="dash-title">{cons_block_title}</div>
      {cons_rows_html}
    </div>
    <div class="dash-block">
      <div class="dash-title">주가 수익률 · 밸류</div>
      {returns_html}
    </div>
  </div>
  <div class="pick-box">
    <div class="pick-label">투자의견 · 3-시나리오 목표주가 스펙트럼</div>
    <div class="pick-row" style="align-items:flex-start;">
      <div style="padding-top:2mm;">
        <span class="pick-badge" style="background:#b8922e;">{html_lib.escape(rating)}</span>
        <div style="margin-top:3mm; font-size:7.5pt; color:#b8c3d4; letter-spacing:1.5px;">
          Current &nbsp; <b style="color:#ffffff;">{fmt_money(cur_price)}</b><br>
          R/R &nbsp;&nbsp; <b style="color:#b8922e;">{html_lib.escape(str(rr))}</b>
        </div>
      </div>
      <div class="target-spectrum" style="flex:1; margin-left:6mm;">
        <div class="target-cell bear">
          <div class="t-lbl">Bear</div>
          <div class="t-val">{fmt_money(opinion.get("target_bear","—"))}</div>
          <div class="t-delta">{down_bear:+.1f}%</div>
        </div>
        <div class="target-cell base">
          <div class="t-lbl">Base</div>
          <div class="t-val">{fmt_money(opinion["target_base"])}</div>
          <div class="t-delta">{up_base:+.1f}%</div>
        </div>
        <div class="target-cell bull">
          <div class="t-lbl">Bull</div>
          <div class="t-val">{fmt_money(opinion.get("target_bull","—"))}</div>
          <div class="t-delta">{up_bull:+.1f}%</div>
        </div>
      </div>
    </div>
  </div>
  <div class="cover-footer">
    <span>Framework · 5-Layer Analysis · Q1–Q10 Quant Protocol</span>
    <span>v4 Single-Agent Research</span>
  </div>
</section>
"""

    # ==========================================================================
    # PAGE 2 — EXECUTIVE SUMMARY (Verdict Card + Core Thesis + KPI)
    # ==========================================================================
    # KPI 추출 — row label로 매칭 (인덱스 의존 제거)
    def find_row(keyword):
        for row in fin.get("rows", []):
            if row and keyword in str(row[0]):
                return row
        return None

    row_rev = find_row("매출")
    row_op = find_row("영업이익")
    row_opm = find_row("OPM")
    if not row_opm:
        row_opm = find_row("영업이익률")

    # headers e.g. ["항목","2021","2022","2023","2024","2025","2026E"]
    # 가장 최근 '확정' 값 = 마지막에서 Forward(E) 제외
    headers = fin.get("headers", [])
    # Forward 컬럼 인덱스 탐색 (E 포함)
    last_actual_idx = len(headers) - 1
    for i in range(len(headers) - 1, 0, -1):
        h = str(headers[i])
        if 'E' not in h.upper() and 'F' not in h.upper():
            last_actual_idx = i
            break

    def val_at(row, idx):
        if not row or idx >= len(row):
            return "—"
        return str(row[idx])

    kpi_revenue = val_at(row_rev, last_actual_idx)
    kpi_op = val_at(row_op, last_actual_idx)
    kpi_opm = val_at(row_opm, last_actual_idx)
    latest_year = headers[last_actual_idx] if last_actual_idx < len(headers) else ""

    down_cls = "neg" if down_bear < 0 else "pos"
    up_cls = "pos" if up_base > 0 else "neg"
    bull_cls = "pos" if up_bull > 0 else "neg"

    # 52주 고저 표시
    hi_52 = price.get("high_52w")
    lo_52 = price.get("low_52w")
    if hi_52 and lo_52 and is_kr:
        range_str = f"{int(lo_52):,} – {int(hi_52):,}"
    elif hi_52 and lo_52:
        range_str = f"${lo_52:,.2f} – ${hi_52:,.2f}"
    else:
        range_str = "—"

    # R/R 텍스트 짧게
    rr_short = str(rr)
    if len(rr_short) > 18:
        rr_short = rr_short.split('(')[0].strip() or rr_short[:18]

    page2 = f"""
<section class="page">
  <div class="running-header">
    <div class="brand">{html_lib.escape(meta.get("stock_name",""))} · Equity Research</div>
    <div class="page-num">01 / 07 &nbsp;·&nbsp; 02</div>
  </div>

  <div class="section-caption">01 · Executive Summary</div>
  <h2 class="section-heading">투자의견 요약</h2>
  <div class="section-intro">본 요약은 8페이지 구성의 기관용 리서치 노트이며, 상세 분석은 동일 폴더의 상세 PDF를 참조한다.</div>

  <div class="verdict-card">
    <div class="verdict-head">
      <div class="title">Investment Verdict</div>
      <div class="verdict-rating-badge" style="background:{cover_rating_color}; color:#ffffff;">{html_lib.escape(rating)}</div>
    </div>
    <div class="verdict-grid">
      <div class="verdict-cell">
        <div class="lbl">Current Price</div>
        <div class="val">{fmt_money(cur_price)}</div>
        <div class="delta">52W {html_lib.escape(range_str)}</div>
      </div>
      <div class="verdict-cell">
        <div class="lbl">Target · Base</div>
        <div class="val">{fmt_money(opinion["target_base"])}</div>
        <div class="delta {up_cls}">{up_base:+.1f}%</div>
      </div>
      <div class="verdict-cell last-col">
        <div class="lbl">Target · Bull</div>
        <div class="val">{fmt_money(opinion["target_bull"])}</div>
        <div class="delta {bull_cls}">{up_bull:+.1f}%</div>
      </div>
      <div class="verdict-cell last-row">
        <div class="lbl">Target · Bear</div>
        <div class="val">{fmt_money(opinion["target_bear"])}</div>
        <div class="delta {down_cls}">{down_bear:+.1f}%</div>
      </div>
      <div class="verdict-cell last-row">
        <div class="lbl">Market Cap</div>
        <div class="val">{html_lib.escape(str(price.get("market_cap","—")))}</div>
        <div class="delta">PER {safe(price.get("per"))} · PBR {safe(price.get("pbr"))}</div>
      </div>
      <div class="verdict-cell last-col last-row">
        <div class="lbl">Risk · Reward</div>
        <div class="val">{html_lib.escape(rr_short)}</div>
        <div class="delta">Div Yield {safe(price.get("dividend_yield"),"—")}%</div>
      </div>
    </div>
  </div>

  <div class="core-thesis">{core_thesis}</div>

  <div class="sub-heading">Key Financials &nbsp;·&nbsp; {html_lib.escape(latest_year)}</div>
  <div class="kpi-row">
    <div class="kpi-block">
      <div class="lbl">{html_lib.escape((row_rev[0] if row_rev else 'Revenue'))}</div>
      <div class="val">{html_lib.escape(str(kpi_revenue))}</div>
      <div class="note">Consolidated</div>
    </div>
    <div class="kpi-block">
      <div class="lbl">{html_lib.escape((row_op[0] if row_op else 'Operating Income'))}</div>
      <div class="val">{html_lib.escape(str(kpi_op))}</div>
      <div class="note">Operating basis</div>
    </div>
    <div class="kpi-block">
      <div class="lbl">{html_lib.escape((row_opm[0] if row_opm else 'OPM'))}</div>
      <div class="val">{html_lib.escape(str(kpi_opm))}</div>
      <div class="note">Operating Margin</div>
    </div>
  </div>

  <div class="page-footer">
    <span>{html_lib.escape(meta.get("stock_name",""))} · Executive Summary</span>
    <span>Page 02 / 08</span>
  </div>
</section>
"""

    # ==========================================================================
    # PAGE 3 — INVESTMENT THESIS (3 points)
    # ==========================================================================
    thesis_html = ''
    for pt in thesis_points[:3]:
        thesis_html += f"""
    <div class="thesis-point">
      <div class="num">{pt['num']}</div>
      <div class="title">{pt['title']}</div>
      <div class="body">{pt['body']}</div>
    </div>
"""

    page3 = f"""
<section class="page">
  <div class="running-header">
    <div class="brand">{html_lib.escape(meta.get("stock_name",""))} · Equity Research</div>
    <div class="page-num">02 / 07 &nbsp;·&nbsp; 03</div>
  </div>

  <div class="section-caption">02 · Investment Thesis</div>
  <h2 class="section-heading">Three Reasons</h2>
  <div class="section-intro">본 리포트의 핵심 주장을 구성하는 3개 포인트. 각 포인트는 정량 근거와 비대칭 R/R 논리를 포함한다.</div>

  <div class="thesis-points">
    {thesis_html}
  </div>

  <div class="page-footer">
    <span>{html_lib.escape(meta.get("stock_name",""))} · Investment Thesis</span>
    <span>Page 03 / 08</span>
  </div>
</section>
"""

    # ==========================================================================
    # PAGE 4 — BUSINESS & INDUSTRY
    # ==========================================================================
    page4 = f"""
<section class="page">
  <div class="running-header">
    <div class="brand">{html_lib.escape(meta.get("stock_name",""))} · Equity Research</div>
    <div class="page-num">03 / 07 &nbsp;·&nbsp; 04</div>
  </div>

  <div class="section-caption">03 · Business &amp; Industry</div>
  <h2 class="section-heading">사업 구조 &amp; 산업 포지셔닝</h2>

  <div class="sub-heading">Company Snapshot</div>
  <p>{business_overview}</p>

  <div class="sub-heading">Revenue Mix</div>
  {render_segment_list()}

  <div class="sub-heading">Industry Context</div>
  <p>{industry_overview}</p>

  <div class="page-footer">
    <span>{html_lib.escape(meta.get("stock_name",""))} · Business &amp; Industry</span>
    <span>Page 04 / 08</span>
  </div>
</section>
"""

    # ==========================================================================
    # PAGE 5 — FINANCIAL SNAPSHOT
    # ==========================================================================
    page5 = f"""
<section class="page">
  <div class="running-header">
    <div class="brand">{html_lib.escape(meta.get("stock_name",""))} · Equity Research</div>
    <div class="page-num">04 / 07 &nbsp;·&nbsp; 05</div>
  </div>

  <div class="section-caption">04 · Financial Snapshot</div>
  <h2 class="section-heading">5-Year Financials</h2>

  {render_fin_table()}
  <p style="font-size:7.5pt; color:#9ca6b5; margin-top:-2mm;">Source: {html_lib.escape(fin.get("source",""))}</p>

  <div class="sub-heading">Financial Highlights</div>
  <p>{financial_summary}</p>

  <div class="page-footer">
    <span>{html_lib.escape(meta.get("stock_name",""))} · Financial Snapshot</span>
    <span>Page 05 / 08</span>
  </div>
</section>
"""

    # ==========================================================================
    # PAGE 6 — VALUATION & SCENARIOS
    # ==========================================================================
    bear_star = _sv2_star_row(down_bear)
    base_star = _sv2_star_row(up_base)
    bull_star = _sv2_star_row(up_bull)

    scenario_table = f"""
<table class="nyt">
  <thead><tr>
    <th>Scenario</th>
    <th class="num">Target</th>
    <th class="num">vs Current</th>
    <th class="num">Probability</th>
  </tr></thead>
  <tbody>
    <tr class="bear-row">
      <td class="name">Bear</td>
      <td class="num">{fmt_money(opinion["target_bear"])}</td>
      <td class="num">{down_bear:+.1f}%</td>
      <td class="num">30%</td>
    </tr>
    <tr>
      <td class="name">Base</td>
      <td class="num">{fmt_money(opinion["target_base"])}</td>
      <td class="num">{up_base:+.1f}%</td>
      <td class="num">50%</td>
    </tr>
    <tr class="bull-row">
      <td class="name">Bull</td>
      <td class="num">{fmt_money(opinion["target_bull"])}</td>
      <td class="num">{up_bull:+.1f}%</td>
      <td class="num">20%</td>
    </tr>
  </tbody>
</table>
"""

    page6 = f"""
<section class="page">
  <div class="running-header">
    <div class="brand">{html_lib.escape(meta.get("stock_name",""))} · Equity Research</div>
    <div class="page-num">05 / 07 &nbsp;·&nbsp; 06</div>
  </div>

  <div class="section-caption">05 · Valuation</div>
  <h2 class="section-heading">가치 평가 &amp; 시나리오</h2>

  <div class="sub-heading">Scenario Analysis</div>
  {scenario_table}

  <div class="sub-heading">Risk · Reward</div>
  <div class="rr-stars">
    <div class="row">
      <div class="cell label-cell">Bear</div>
      <div class="cell stars-cell">{bear_star}</div>
      <div class="cell value-cell">{down_bear:+.1f}% / 30%</div>
    </div>
    <div class="row">
      <div class="cell label-cell">Base</div>
      <div class="cell stars-cell">{base_star}</div>
      <div class="cell value-cell">{up_base:+.1f}% / 50%</div>
    </div>
    <div class="row">
      <div class="cell label-cell">Bull</div>
      <div class="cell stars-cell">{bull_star}</div>
      <div class="cell value-cell">{up_bull:+.1f}% / 20%</div>
    </div>
  </div>

  <div class="sub-heading">Valuation Commentary</div>
  <p>{valuation_summary}</p>

  <div class="sub-heading">Peer Group</div>
  {render_peer_table()}

  <div class="page-footer">
    <span>{html_lib.escape(meta.get("stock_name",""))} · Valuation</span>
    <span>Page 06 / 08</span>
  </div>
</section>
"""

    # ==========================================================================
    # PAGE 7 — RISK
    # ==========================================================================
    page7 = f"""
<section class="page">
  <div class="running-header">
    <div class="brand">{html_lib.escape(meta.get("stock_name",""))} · Equity Research</div>
    <div class="page-num">06 / 07 &nbsp;·&nbsp; 07</div>
  </div>

  <div class="section-caption">06 · Risk Assessment</div>
  <h2 class="section-heading">리스크 &amp; Kill Switch</h2>

  <div class="sub-heading">Macro Risk Overview</div>
  <p>{macro_summary}</p>

  <div class="sub-heading">Upcoming Catalysts</div>
  {render_catalyst_table()}

  <div class="kill-switch">
    <div class="label">⚠ Kill Switch · Stop-Loss Triggers</div>
    <div class="body">{kill_switch}</div>
  </div>

  <div class="page-footer">
    <span>{html_lib.escape(meta.get("stock_name",""))} · Risk Assessment</span>
    <span>Page 07 / 08</span>
  </div>
</section>
"""

    # ==========================================================================
    # PAGE 8 — FINAL CALL + ACTION PLAN
    # ==========================================================================
    page8 = f"""
<section class="page">
  <div class="running-header">
    <div class="brand">{html_lib.escape(meta.get("stock_name",""))} · Equity Research</div>
    <div class="page-num">07 / 07 &nbsp;·&nbsp; 08</div>
  </div>

  <div class="section-caption">07 · Execution</div>
  <h2 class="section-heading">Action Plan &amp; Final Call</h2>

  <div class="sub-heading">Implementation Guide</div>
  <p>{action_summary}</p>

  <div class="final-call">
    <div class="caption">— Final Call —</div>
    <div class="conclusion">{final_conclusion}</div>
    <div class="signature">
      <span>Equity Research · Single-Agent v4</span>
      <span>{html_lib.escape(meta.get("date",""))}</span>
    </div>
  </div>

  <div class="page-footer">
    <span>{html_lib.escape(meta.get("stock_name",""))} · Final Call</span>
    <span>Page 08 / 08 · End of Report</span>
  </div>
</section>
"""

    # ==========================================================================
    # ASSEMBLE HTML
    # ==========================================================================
    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<title>{html_lib.escape(meta.get("stock_name",""))} — Equity Research</title>
<style>{_SUMMARY_V2_CSS}</style>
</head><body>
{page1}
{page2}
{page3}
{page4}
{page5}
{page6}
{page7}
{page8}
</body></html>
"""

    html_path = os.path.join(output_dir, f'report_{name}_요약.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

    # PDF variant
    try:
        from playwright.sync_api import sync_playwright
        pdf_path = os.path.join(output_dir, f'report_{name}_요약.pdf')
        file_url = "file:///" + os.path.abspath(html_path).replace("\\", "/")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(file_url)
            page.pdf(
                path=pdf_path,
                format="A4",
                margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
                print_background=True,
                prefer_css_page_size=True,
            )
            browser.close()
        os.remove(html_path)
        print(f'[OK] 요약 PDF (v2): {pdf_path} ({os.path.getsize(pdf_path)//1024} KB)')
    except Exception as e:
        print(f'[!!] PDF 변환 실패: {e}, HTML 파일은 생성됨 ({html_path})')


# ==========================================================================
# 2C. LEGACY SUMMARY (kept for reference)
# ==========================================================================
def _generate_summary_legacy(data, output_dir):
    """Deprecated: simple blue-themed summary. Kept for reference."""
    meta = data["meta"]
    price = data["price"]
    opinion = data["opinion"]
    fin = data["financials"]
    segs = data["segments"]
    peers = data.get("peers", [])
    catalysts = data.get("catalysts", [])
    supply = data.get("supply", {})
    quarterly = data.get("quarterly", {})
    sections = data["sections"]

    name = meta["stock_name"].replace(" ", "")
    is_kr = meta["country"] == "KR"
    c = meta["currency"] if is_kr else "$"

    def fmt(val):
        return f'{val:,}{c}' if is_kr else f'${val:,}'

    current = price["current"] or 1  # 0원 나누기 방지
    upside_base = ((opinion["target_base"] - current) / current) * 100
    upside_bull = ((opinion["target_bull"] - current) / current) * 100
    downside_bear = ((opinion["target_bear"] - current) / current) * 100

    # 시나리오 테이블 행
    scenario_rows = f'''
    <tr class="bear"><td><strong>Bear Case</strong></td><td>{fmt(opinion["target_bear"])}</td><td>{downside_bear:+.1f}%</td></tr>
    <tr><td><strong>Base Case</strong></td><td>{fmt(opinion["target_base"])}</td><td>{upside_base:+.1f}%</td></tr>
    <tr class="bull"><td><strong>Bull Case</strong></td><td>{fmt(opinion["target_bull"])}</td><td>{upside_bull:+.1f}%</td></tr>'''

    # 재무 테이블
    fin_header = ''.join(f'<th>{h}</th>' for h in fin["headers"])
    fin_rows = ''
    for row in fin["rows"]:
        cells = ''.join(f'<td>{v}</td>' for v in row)
        fin_rows += f'<tr>{cells}</tr>'

    # 사업부 테이블
    seg_rows = ''
    for s in segs:
        seg_rows += f'<tr><td><strong>{s["name"]}</strong></td><td>{s["pct"]}%</td><td>{s["outlook"]}</td></tr>'

    # Peer 테이블
    peer_rows = ''
    for p in peers:
        hl = ' style="background:#fff3e0;"' if p.get("highlight") else ''
        peer_rows += f'<tr{hl}><td><strong>{p["name"]}</strong></td><td>{p["market_cap"]}</td><td>{p["per"]}</td><td>{p["pbr"]}</td><td>{p["note"]}</td></tr>'

    # 카탈리스트
    cat_rows = ''
    for ct in catalysts:
        cat_rows += f'<tr><td>{ct["date"]}</td><td>{ct["event"]}</td><td>{ct["impact"]}</td></tr>'

    # 분기 실적
    q_html = ''
    if quarterly:
        q_header = ''.join(f'<th>{h}</th>' for h in quarterly["headers"])
        q_rows_html = ''
        for row in quarterly["rows"]:
            cells = ''.join(f'<td>{v}</td>' for v in row)
            q_rows_html += f'<tr>{cells}</tr>'
        q_html = f'''
        <h3>분기별 실적 ({quarterly["year"]})</h3>
        <table><tr>{q_header}</tr>{q_rows_html}</table>
        <p style="font-size:8pt; color:#999;">{quarterly.get("note","")}</p>'''

    # 수급
    supply_html = ''
    if supply:
        supply_html = f'''
        <h3>수급 분석 (최근 {supply.get("days",20)}일)</h3>
        <table>
        <tr><th>투자자</th><th>순매수</th></tr>
        <tr><td>외국인</td><td style="color:{"green" if supply["foreign"]>0 else "red"}">{supply["foreign"]:+,}주</td></tr>
        <tr><td>기관</td><td style="color:{"green" if supply["institution"]>0 else "red"}">{supply["institution"]:+,}주</td></tr>
        <tr><td>개인</td><td style="color:{"green" if supply["individual"]>0 else "red"}">{supply["individual"]:+,}주</td></tr>
        </table>
        <p style="font-size:9pt;">{supply.get("comment","")}</p>'''

    def summarize(key, max_len=400):
        txt = sections.get(key, "")
        # 마크다운 테이블 끊김 방지: 테이블이 있으면 자르지 않고 전체 렌더
        if re.search(r'\n\s*\|[\s\-:|]+\|', txt):
            return md_table_to_html(txt)
        if len(txt) > max_len:
            txt = txt[:max_len] + "..."
        return html_lib.escape(txt).replace('\n', '<br>')

    rating_class = {"BUY": "tag-buy", "HOLD": "tag-hold", "SELL": "tag-sell"}.get(opinion["rating"], "tag-hold")

    html = f'''<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<style>
  @page {{ size: A4; margin: 2cm 2.5cm; }}
  body {{ font-family: 'Malgun Gothic', sans-serif; font-size: 10pt; line-height: 1.6; color: #1a1a1a; }}
  h1 {{ font-size: 20pt; color: #0d47a1; border-bottom: 3px solid #0d47a1; padding-bottom: 6px; margin-top: 25px; }}
  h3 {{ font-size: 12pt; color: #1976d2; margin-top: 15px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 9pt; }}
  th {{ background: #1565c0; color: white; padding: 5px 7px; text-align: center; }}
  td {{ border: 1px solid #ddd; padding: 4px 7px; }}
  tr:nth-child(even) {{ background: #f5f5f5; }}
  .highlight {{ background: #fff3e0; padding: 10px; border-left: 4px solid #ff9800; margin: 8px 0; font-size: 9pt; }}
  .bear {{ background: #ffebee; }}
  .bull {{ background: #e8f5e9; }}
  .verdict {{ background: #e3f2fd; padding: 12px; border: 2px solid #1565c0; margin: 12px 0; text-align: center; }}
  .tag {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 9pt; font-weight: bold; }}
  .tag-buy {{ background: #4caf50; color: white; }}
  .tag-hold {{ background: #ff9800; color: white; }}
  .tag-sell {{ background: #f44336; color: white; }}
  .cover {{ text-align: center; padding: 60px 0; page-break-after: always; }}
  .cover h1 {{ font-size: 30pt; border: none; }}
  .pagebreak {{ page-break-before: always; }}
  .section-text {{ font-size: 9pt; line-height: 1.5; }}
</style></head><body>

<div class="cover">
  <h1>{meta["stock_name"]} ({meta["stock_code"]})</h1>
  <div style="font-size:14pt; color:#1565c0;">Investment Research Report -요약본</div>
  <div style="font-size:12pt; color:#666; margin-top:10px;">{meta["industry"]}</div>
  <div style="margin-top:40px;">
    <span class="tag {rating_class}">{opinion["rating"]}</span>
  </div>
  <div style="margin-top:15px; font-size:13pt;">
    목표주가: <strong>{fmt(opinion["target_base"])}</strong> | 현재가: <strong>{fmt(price["current"])}</strong>
  </div>
  <div style="font-size:10pt; color:#999; margin-top:30px;">{meta["date"]} 기준</div>
</div>

<h1>핵심 실적 추정</h1>
<table><tr>{fin_header}</tr>{fin_rows}</table>
<p style="font-size:8pt; color:#999;">출처: {fin["source"]}</p>

<h3>사업부별 매출 비중</h3>
<table><tr><th>사업부</th><th>비중</th><th>전망</th></tr>{seg_rows}</table>

<h1>1. 투자의견</h1>
<div class="verdict">
  <div style="font-size:14pt; font-weight:bold;">투자의견: {opinion["rating"]}</div>
  <div>현재가 {fmt(price["current"])} | 목표주가 {fmt(opinion["target_base"])} | 상승여력 {upside_base:+.1f}%</div>
</div>
<table>
  <tr><th>시나리오</th><th>적정주가</th><th>현재가 대비</th></tr>
  {scenario_rows}
</table>
<p>Risk-Reward: {opinion["risk_reward"]}</p>

<h1>2. 투자포인트</h1>
<div class="section-text">{summarize("s02_investment_points", 600)}</div>

<h1 class="pagebreak">3. 회사 개요</h1>
<table>
  <tr><td>회사명</td><td>{meta["stock_name"]}</td><td>종목코드</td><td>{meta["stock_code"]}</td></tr>
  <tr><td>시가총액</td><td>{price["market_cap"]}</td><td>현재가</td><td>{fmt(price["current"])}</td></tr>
  <tr><td>PER</td><td>{price["per"]}배</td><td>PBR</td><td>{price["pbr"]}배</td></tr>
  <tr><td>52주 최고/최저</td><td>{price["high_52w"]:,} / {price["low_52w"]:,}</td><td>배당수익률</td><td>{price.get("dividend_yield","N/A")}</td></tr>
</table>

<h1>5. 경쟁 구도</h1>
<table><tr><th>기업</th><th>시가총액</th><th>PER</th><th>PBR</th><th>비고</th></tr>{peer_rows}</table>

<h1>8. 재무 분석</h1>
<table><tr>{fin_header}</tr>{fin_rows}</table>
<p style="font-size:8pt; color:#999;">출처: {fin["source"]}</p>
{q_html}

<h1>4. 산업 & 시장</h1>
<div class="section-text">{summarize("s04_industry", 500)}</div>

<h1 class="pagebreak">6. 경제적 해자</h1>
<div class="section-text">{summarize("s06_moat", 400)}</div>

<h1>7. 경영진</h1>
<div class="section-text">{summarize("s07_management", 400)}</div>

<h1>9. 밸류에이션</h1>
<div class="section-text">{summarize("s09_valuation", 500)}</div>

<h1>10. 매크로 리스크</h1>
<div class="section-text">{summarize("s10_macro", 400)}</div>

<h1 class="pagebreak">11. 카탈리스트 타임라인</h1>
<table><tr><th>시기</th><th>이벤트</th><th>영향</th></tr>{cat_rows}</table>

<h1>12. 시나리오</h1>
<div class="section-text">{summarize("s12_scenarios", 600)}</div>

<h1>13. 투자 논문</h1>
<div class="highlight">{summarize("s13_thesis", 500)}</div>

<h1>14. 숏 논거 + 반박</h1>
<div class="section-text">{summarize("s14_short_thesis", 600)}</div>

<h1 class="pagebreak">15. 실적 Beat/Miss</h1>
<div class="section-text">{summarize("s15_beat_miss", 400)}</div>

<h1>16. 애널리스트 컨센서스</h1>
<div class="section-text">{summarize("s16_consensus", 300)}</div>

{supply_html}

<h1>18. 주주환원</h1>
<div class="section-text">{summarize("s18_shareholder_return", 300)}</div>

<h1 class="pagebreak">19. Trust / Worry / Watch</h1>
<div class="section-text">{summarize("s19_trust_worry_watch", 600)}</div>

<h1>20. 실행 계획</h1>
<div class="section-text">{summarize("s20_action_plan", 400)}</div>

<h1>21. 분석 신뢰도</h1>
<div class="section-text" style="font-size:8pt;">{summarize("s21_reliability", 500)}</div>

</body></html>'''

    html_path = os.path.join(output_dir, f'report_{name}_요약.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

    # PDF 변환
    try:
        from playwright.sync_api import sync_playwright
        pdf_path = os.path.join(output_dir, f'report_{name}_요약.pdf')
        file_url = "file:///" + os.path.abspath(html_path).replace("\\", "/")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(file_url)
            page.pdf(path=pdf_path, format="A4",
                     margin={"top":"20mm","bottom":"20mm","left":"25mm","right":"25mm"},
                     print_background=True)
            browser.close()
        os.remove(html_path)  # HTML 삭제 (PDF만 남김)
        print(f'[OK] 요약 PDF: {pdf_path} ({os.path.getsize(pdf_path)//1024} KB)')
    except Exception as e:
        print(f'[!!] PDF 변환 실패: {e}, HTML 파일만 생성됨')


# ==========================================================================
# 2D. INSTITUTIONAL DETAILED REPORT (v3 — single HTML→PDF, 21 sections, Navy/Gold)
# ==========================================================================

def _md_to_html_blocks(md_text):
    """Convert markdown section body to clean HTML blocks.

    Handles: ## ### #### headings, **bold**, *italic*, `code`,
             | tables |, --- hr, > blockquote, - bullet, 1. ordered list.
    Strips emojis and decorative pictographs.
    """
    if not md_text:
        return ""

    md_text = _strip_emoji(md_text)
    lines = md_text.split('\n')
    html_parts = []
    i = 0
    n = len(lines)

    # v5.0 풀 재설계: 섹션마다 ### h3 카운터 reset
    # nonlocal 사용 위해 closure 형태 -- 함수 내부 변수로 전환
    h3_counter = [0]  # mutable container for closure

    def render_inline(text):
        """Inline emphasis: **bold**, *italic*, `code`."""
        # Escape HTML first
        text = html_lib.escape(text)
        # Bold (must come before italic to avoid * conflict)
        text = re.sub(r'\*\*([^*\n]+?)\*\*', r'<strong>\1</strong>', text)
        # Italic
        text = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<em>\1</em>', text)
        # Inline code
        text = re.sub(r'`([^`\n]+?)`', r'<code>\1</code>', text)
        return text

    while i < n:
        line = lines[i].rstrip()
        stripped = line.strip()

        # Empty line: paragraph break (handled by accumulator)
        if not stripped:
            i += 1
            continue

        # 1. Markdown table
        if (stripped.startswith('|') and stripped.endswith('|')
                and i + 1 < n
                and re.match(r'^\s*\|[\s\-:|]+\|\s*$', lines[i+1])):
            header_cells = [c.strip() for c in stripped.strip('|').split('|')]
            i += 2
            body_rows = []
            while i < n:
                row_line = lines[i].strip()
                if row_line.startswith('|') and row_line.endswith('|'):
                    cells = [c.strip() for c in row_line.strip('|').split('|')]
                    while len(cells) < len(header_cells):
                        cells.append('')
                    body_rows.append(cells[:len(header_cells)])
                    i += 1
                else:
                    break
            # Render HTML table (NYT style)
            th = ''.join(
                f'<th class="num">{render_inline(h)}</th>' if idx > 0
                else f'<th>{render_inline(h)}</th>'
                for idx, h in enumerate(header_cells)
            )
            tr_html = ''
            for row in body_rows:
                cells_html = ''
                for idx, c in enumerate(row):
                    cls = 'num' if idx > 0 else 'name'
                    cells_html += f'<td class="{cls}">{render_inline(c)}</td>'
                tr_html += f'<tr>{cells_html}</tr>'
            html_parts.append(
                f'<table class="nyt"><thead><tr>{th}</tr></thead>'
                f'<tbody>{tr_html}</tbody></table>'
            )
            continue

        # 2. Horizontal rule → spacer
        if re.match(r'^[-=*]{3,}$', stripped):
            html_parts.append('<div class="hr-spacer"></div>')
            i += 1
            continue

        # 3. Markdown heading
        h_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if h_match:
            level = len(h_match.group(1))
            text = h_match.group(2).rstrip('#').strip()
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
            text = re.sub(r'\*(.+?)\*', r'\1', text)
            text = html_lib.escape(text)
            if level <= 2:
                html_parts.append(f'<h3 class="md-h2">{text}</h3>')
            elif level == 3:
                # v5.4 패치 (호텔신라 공백 사고 후): h3 카운터 강제 분할 비활성화
                # → 큰 섹션은 chromium 자동 분할에 맡김. h3는 break-inside: avoid만 적용.
                # 강제 page-break-before는 .section-block (섹션 단위)만 적용하고
                # 섹션 내부는 자연 흐름으로 페이지 채움 효율 극대화
                h3_counter[0] += 1
                html_parts.append(f'<h4 class="md-h3">{text}</h4>')
            else:
                html_parts.append(f'<h5 class="md-h4">{text}</h5>')
            i += 1
            continue

        # 4. Blockquote
        if stripped.startswith('>'):
            quote_lines = []
            while i < n and lines[i].strip().startswith('>'):
                quote_lines.append(lines[i].strip()[1:].strip())
                i += 1
            quote_text = ' '.join(quote_lines)
            html_parts.append(f'<blockquote class="md-quote">{render_inline(quote_text)}</blockquote>')
            continue

        # 5. Bullet list (collect contiguous)
        if re.match(r'^[-*+]\s+', stripped):
            items = []
            while i < n and re.match(r'^[-*+]\s+', lines[i].strip()):
                item_text = re.sub(r'^[-*+]\s+', '', lines[i].strip())
                items.append(f'<li>{render_inline(item_text)}</li>')
                i += 1
            html_parts.append('<ul class="md-bullet">' + ''.join(items) + '</ul>')
            continue

        # 6. Numbered list
        if re.match(r'^\d+[\.\)]\s+', stripped):
            items = []
            while i < n and re.match(r'^\d+[\.\)]\s+', lines[i].strip()):
                item_text = re.sub(r'^\d+[\.\)]\s+', '', lines[i].strip())
                items.append(f'<li>{render_inline(item_text)}</li>')
                i += 1
            html_parts.append('<ol class="md-ordered">' + ''.join(items) + '</ol>')
            continue

        # 7. Plain paragraph (collect contiguous non-empty, non-special lines)
        para_lines = []
        while i < n:
            ln = lines[i].rstrip()
            sl = ln.strip()
            if not sl:
                break
            # Stop at any special block
            if sl.startswith('#') or sl.startswith('|') or sl.startswith('>'):
                break
            if re.match(r'^[-*+]\s+|^\d+[\.\)]\s+', sl):
                break
            if re.match(r'^[-=*]{3,}$', sl):
                break
            para_lines.append(sl)
            i += 1
        if para_lines:
            joined = ' '.join(para_lines)
            html_parts.append(f'<p>{render_inline(joined)}</p>')

    return '\n'.join(html_parts)


_ANALYST_CSS = r"""
/* ===== v5.16 애널리스트 리포트 디자인 (증권사 PDF 50편 실측 기반) =====
   본문 9.2pt (삼성 7.8 / 하나 9.2 / 교보 9.5 실측 중앙값), 액센트 1색. */
:root{
  --ac:#0a56d6; --ac-dk:#083ea0; --ac-lt:#eef2fb;
  --ink:#14181d; --sub:#5b626b; --line:#dfe3ea; --rail:#eef2f8;
  --pos:#12694a; --neg:#c0392b;
}
html, body{ font-size:9.2pt !important; line-height:1.62 !important; color:var(--ink); }

/* ---- 커버: 좌측 데이터 레일 + 우측 본문 (삼성증권형) ---- */
.full-bleed.acover{
  background:var(--rail) !important; color:var(--ink) !important;
  padding:0 !important; display:flex !important;
  height:269mm; overflow:hidden; position:relative;   /* @page margin 14mm x2 를 뺀 값 */
}
.acover .rail{ width:52mm; padding:16mm 6mm 0 9mm; }
.acover .kind{ font-family:var(--font-body); font-size:19pt; font-weight:800;
  line-height:1.05; letter-spacing:-.5px; color:var(--ink); }
.acover .dt{ font-size:7.5pt; color:var(--sub); margin-top:3mm; }
.acover .team{ font-size:7pt; color:var(--ac); font-weight:700; margin-top:11mm; }
.acover .who{ font-size:8pt; font-weight:700; margin-top:1.2mm; }
.acover .mail{ font-size:6.4pt; color:var(--sub); }
.acover .rl-hr{ height:.4mm; background:var(--line); margin:3mm 0; }
.acover .blk{ margin-top:5mm; }
.acover .blkh{ font-size:7pt; font-weight:700; margin-bottom:1.4mm; }
.acover .blkh:before{ content:'▶'; color:var(--ac); font-size:5pt; margin-right:1.2mm; }
.acover .badge{ color:#fff; text-align:center; font-size:14pt; font-weight:800;
  letter-spacing:.5px; padding:1.4mm 0; border-radius:.5mm; }
.acover table{ width:100%; border-collapse:collapse; font-size:6.8pt; }
.acover td{ padding:.75mm 0; border-bottom:.25mm solid #e5e9ef; color:var(--sub);
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:19mm; }
.acover td.v{ text-align:right; color:var(--ink); font-weight:600;
  font-variant-numeric:tabular-nums; white-space:nowrap; max-width:none; }
.acover td.k{ color:var(--ac); font-weight:600; }
.acover .main{ flex:1; background:#fff; margin:9mm 9mm 9mm 0;
  border-radius:.8mm; padding:13mm 12mm; }
.acover .co{ font-size:26pt; font-weight:800; letter-spacing:-.8px; line-height:1.1; }
.acover .co span{ font-size:15pt; font-weight:400; color:var(--sub); }
.acover .atag{ font-size:11.5pt; color:var(--sub); margin-top:1.5mm; }
.acover .sum{ background:#f3f6fb; padding:4mm 5mm 4mm 9mm; margin:7mm 0 0;
  font-size:8pt; line-height:1.6; }
.acover .sum li{ margin-bottom:1.6mm; }
.acover .sh{ font-size:12pt; font-weight:800; color:var(--ac); margin:8mm 0 3mm; }
.acover .fin{ width:100%; border-collapse:collapse; font-size:6.9pt; margin-top:2mm; }
.acover .fin th{ background:var(--ac-lt); padding:1.2mm 1.6mm; text-align:right;
  font-weight:700; border-top:.35mm solid var(--ac); }
.acover .fin th:first-child{ text-align:left; }
.acover .fin td{ padding:1mm 1.6mm; text-align:right; border-bottom:.2mm solid #eef1f5;
  font-variant-numeric:tabular-nums; }
.acover .fin td:first-child{ text-align:left; color:var(--sub); }
.acover .fin tr:last-child td{ border-bottom:.35mm solid var(--ac); }
.acover .alogo{ position:absolute; left:9mm; bottom:8mm; font-size:11pt;
  font-weight:800; color:var(--ac); letter-spacing:-.3px; }

/* ---- 본문: 러닝헤더 + 큰 컬러 섹션 제목 (교보형) ---- */
.section-block{ padding-top:4mm; }
.section-block .running-head{ display:flex; justify-content:space-between;
  align-items:flex-end; border-bottom:.3mm solid var(--line);
  padding-bottom:1.5mm; margin-bottom:6mm; }
.section-block .rh-l{ font-size:8pt; font-weight:800; color:var(--ac); }
.section-block .rh-l small{ display:block; font-size:7pt; font-weight:400; color:#98a0aa; }
.section-block .rh-r{ font-size:7.4pt; color:#98a0aa; }
/* 실제 클래스명은 section-caption / section-heading 이다.
   교보형: section-caption를 러닝헤더처럼 얇게 올리고 제목을 크고 컬러로. */
.section-block .section-caption{
  font-size:7pt !important; font-weight:700 !important; color:#98a0aa !important;
  letter-spacing:2px !important; margin:0 0 1.5mm !important; }
.section-block .section-heading{
  font-family:var(--font-body) !important; font-size:17pt !important; font-weight:800 !important;
  color:var(--ac) !important; letter-spacing:-.6px !important; border:0 !important;
  padding:0 0 2mm !important; margin:0 0 5mm !important;
  border-bottom:.4mm solid var(--ac) !important; }
.section-block .section-intro{ font-size:8.2pt !important; color:var(--sub) !important; }
.section-block .section-body h3{ font-size:10.5pt; font-weight:800; color:var(--ink);
  border-left:1mm solid var(--ac); padding-left:2.5mm; margin:6mm 0 2.5mm; }
.section-block .section-body h4{ font-size:9.6pt; font-weight:700; color:var(--ac-dk);
  margin:5mm 0 2mm; }
.section-block .section-body p{ text-align:justify; margin:0 0 2.6mm; }
.section-block .section-body strong{ color:#000; font-weight:700; }
.margin-note{ background:var(--ac-lt) !important; border-left:.9mm solid var(--ac) !important;
  color:var(--ac-dk) !important; font-size:8.2pt !important; padding:2mm 3mm !important; }
table.nyt{ font-size:7.4pt !important; }
table.nyt th{ background:var(--ac-lt) !important; color:#243043 !important;
  border-top:.35mm solid var(--ac) !important; border-bottom:.2mm solid var(--line) !important;
  padding:1.3mm 1.8mm !important; }
table.nyt td{ padding:1.1mm 1.8mm !important; border-bottom:.18mm solid #eef1f5 !important; }
blockquote.md-quote{ border-left:.8mm solid var(--ac) !important; background:#fafbfd !important;
  font-size:8.2pt !important; color:#2a3038 !important; }
.report-chart figcaption{ font-size:7.2pt !important; color:var(--sub) !important; }
"""

_DETAILED_V3_CSS = r"""
  /* ============================================================
     WEB FONTS — Pretendard Variable (Korean primary)
     - 한글 본문: Pretendard (현대적, 가독성, tabular-nums 지원)
     - 영문 헤딩: Georgia 유지 (NYT 세리프 스타일)
     - 영문 본문: Pretendard 내장 Latin (SF/Roboto 느낌)
     ============================================================ */
  @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css');

  :root {
    --font-body: 'Pretendard Variable', 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, 'Apple SD Gothic Neo', 'Malgun Gothic', 'Noto Sans KR', sans-serif;
    --font-heading: Georgia, 'Times New Roman', 'Pretendard Variable', 'Pretendard', serif;
    --font-mono: 'JetBrains Mono', Consolas, 'Courier New', monospace;
  }

  /* ============================================================
     PAGE MODEL
     - @page margin defines uniform page margins on every page
     - Cover/Exec/Final: fixed-height boxes inside the page margin
       (no full bleed; the navy box sits inside white margins)
     - 21 content sections: flow naturally with break-inside hints
     ============================================================ */
  @page {
    size: A4;
    margin: 14mm 18mm 14mm 18mm;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0;
    padding: 0;
    font-family: var(--font-body);
    font-feature-settings: 'tnum' 1, 'kern' 1;
    color: #0a0e1a;
    font-size: 10pt;
    line-height: 1.65;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
  }

  /* Fixed pages (cover, exec, final) sit within @page margin.
     Width 174mm = 210 - 18 - 18; Height 268mm = 297 - 14 - 14 - 1mm safety. */
  .full-bleed {
    width: 174mm;
    height: 268mm;
    padding: 14mm 14mm 14mm 14mm;
    position: relative;
    page-break-after: always;
    overflow: hidden;
  }
  .full-bleed:last-of-type { page-break-after: auto; }
  /* Final page must always start on a fresh page */
  .full-bleed.final-page {
    page-break-before: always;
    break-before: page;
  }

  /* Cover background applied directly to the box */
  .full-bleed.cover {
    background: linear-gradient(165deg, #0b2545 0%, #0e2b55 45%, #122f5d 100%);
    color: #f0f3f8;
  }

  /* Content sections — pure natural flow.
     No break-inside, no break-before/after. Let chromium pack tightly.
     Only protect tables from splitting (visual integrity).
  */
  .content-flow {}

  .margin-note {
    display: block;
    margin: 1.5mm 0 3mm 0;
    padding: 1.2mm 0 1.2mm 3mm;
    border-left: 3px solid #b8922e;
    background: #fbf8f0;
    font-family: var(--font-body);
    font-size: 8.5pt;
    font-weight: 700;
    color: #0b2545;
    line-height: 1.4;
}
.report-chart {
    margin: 4mm 0 5mm 0;
    break-inside: avoid;
    page-break-inside: avoid;
    text-align: center;
}
.report-chart img { width: 100%; max-width: 158mm; height: auto; display: block; margin: 0 auto; }
.report-chart figcaption {
    font-family: var(--font-body);
    font-size: 8pt; font-weight: 600; color: #0b2545;
    text-align: left; margin-top: 1.5mm; padding-left: 2mm;
    border-left: 2px solid #b8922e;
}
.report-chart .chart-source { font-size: 6.8pt; color: #7a8494; text-align: right; margin-top: 0.8mm; }
.section-block {
    /* v5.4 -- 12섹션 깊은 분량 (섹션당 3,000~5,500자) 대응:
       각 섹션 새 페이지 시작 + 표/박스 분할 보호 */
    page-break-before: always;
    break-before: page;
    page-break-inside: auto;
    margin-top: 0;
    /* 섹션 하단 여백/구분선을 두면, 섹션이 페이지를 거의 채웠을 때 그 여백만
       다음 페이지로 넘어가고 이어지는 섹션의 page-break-before 가 또 넘겨서
       **빈 페이지**가 생긴다 (LULU v2 21p 실측). 각 섹션이 어차피 새 페이지에서
       시작하므로 하단 구분선은 시각적으로도 불필요하다. */
    margin-bottom: 0;
    padding-bottom: 0;
    border-bottom: none;
  }
  .section-block:first-of-type {
    /* 첫 섹션은 Executive Summary 다음 자연 흐름 */
    page-break-before: auto;
    break-before: auto;
  }
  .section-block:last-child {
    border-bottom: none;
    margin-bottom: 0;
  }
  /* 표/인용 박스/code block 분할 방지 (가독성 보호) */
  .section-block table,
  .section-block blockquote,
  .section-block pre {
    page-break-inside: avoid;
    break-inside: avoid;
  }
  .section-block .section-caption {
    margin-top: 0;
    margin-bottom: 0.5mm;
  }
  .section-block .section-heading {
    margin-top: 0.5mm;
    margin-bottom: 2.5mm;
    font-size: 16pt;
    line-height: 1.15;
  }
  .section-block .section-body > *:first-child {
    margin-top: 0;
  }
  .section-block .section-body > *:last-child {
    margin-bottom: 0;
  }
  /* v5.0 12섹션 깊은 분량 (s02 5,500자+) 자동 분할 -- h3 sub-header에서 break 가능 */
  .section-block .section-body h3 {
    page-break-after: avoid;
    break-after: avoid;
    page-break-inside: avoid;
    break-inside: avoid;
    margin-top: 5mm;
    margin-bottom: 2mm;
    font-size: 12pt;
    line-height: 1.3;
    color: #0b2545;
  }
  /* v5.0 풀 재설계: 한 섹션 내 3번째 h3부터 자동 새 페이지 (큰 섹션 압축 차단) */
  .section-block .section-body h3:nth-of-type(n+3) {
    page-break-before: always;
    break-before: page;
    margin-top: 0;
  }
  /* h3 + 다음 콘텐츠 (table/p/ul) 묶음 */
  .section-block .section-body h3 + table,
  .section-block .section-body h3 + p,
  .section-block .section-body h3 + ul,
  .section-block .section-body h3 + ol,
  .section-block .section-body h3 + blockquote {
    page-break-before: avoid;
    break-before: avoid;
  }
  .section-block .section-body h4 {
    page-break-after: avoid;
    break-after: avoid;
    margin-top: 3mm;
    margin-bottom: 1.5mm;
    font-size: 10.5pt;
    color: #1a3553;
  }
  /* 본문 텍스트 v5.0 깊이 대응 -- 가독성 우선 */
  .section-block .section-body {
    font-size: 9.5pt;
    line-height: 1.55;
  }
  .section-block .section-body p {
    margin: 1.5mm 0;
  }
  .section-block .section-body ul,
  .section-block .section-body ol {
    margin: 1.5mm 0;
    padding-left: 5mm;
  }
  .section-block .section-body li {
    margin: 0.5mm 0;
  }

  /* Avoid orphans/widows + table integrity */
  p { orphans: 2; widows: 2; margin: 1mm 0; }
  table.nyt { page-break-inside: avoid; break-inside: avoid; max-width: 100%; }
  blockquote.md-quote { page-break-inside: avoid; break-inside: avoid; }

  /* ---------- Cover absolute children — coordinates inside the 174x269 box ---------- */
  .full-bleed.cover .accent-corner {
    position: absolute;
    top: 0;
    right: 0;
    width: 80mm;
    height: 80mm;
    background: radial-gradient(circle at top right, rgba(184,146,46,0.18), transparent 70%);
    pointer-events: none;
    z-index: 0;
  }
  .full-bleed.cover .pick-box {
    left: 14mm;
    right: 14mm;
    bottom: 10mm;
    padding: 1.5mm 5mm !important;
    min-height: 22mm;
    max-height: 32mm;
    overflow: hidden;
  }
  .full-bleed.cover .cover-footer {
    left: 14mm;
    right: 14mm;
    bottom: 2mm;
    padding-top: 1mm;
    font-size: 5.5pt;
  }
  .full-bleed.cover .cover-body {
    margin-top: 10mm;
    position: relative;
    z-index: 1;
  }
  .full-bleed.cover h1.stock-title {
    font-size: 36pt;
    margin: 2mm 0 1.5mm 0;
    line-height: 1.05;
  }
  .full-bleed.cover .tagline {
    margin-top: 3mm;
    font-size: 12pt;
    line-height: 1.25;
    max-width: 130mm;
  }
  .full-bleed.cover .dashboard {
    position: absolute;
    left: 14mm;
    right: 14mm;
    bottom: 48mm;
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 4mm;
    background: rgba(0,0,0,0.22);
    border-top: 0.8px solid rgba(184,146,46,0.7);
    border-bottom: 0.8px solid rgba(184,146,46,0.7);
    padding: 2mm 4mm;
    max-height: 30mm;
    overflow: hidden;
  }
  .full-bleed.cover .dash-block {
    padding: 0;
    font-size: 6.2pt;
    line-height: 1.25;
  }
  .full-bleed.cover .dash-title {
    color: #b8922e;
    font-size: 6.5pt;
    letter-spacing: 2px;
    text-transform: uppercase;
    font-weight: 700;
    margin-bottom: 1.5mm;
    padding-bottom: 0.8mm;
    border-bottom: 0.5px solid rgba(184,146,46,0.5);
  }
  .full-bleed.cover .dash-row {
    display: flex;
    justify-content: space-between;
    color: #e0e6f0;
    font-variant-numeric: tabular-nums;
    padding: 0.15mm 0;
  }
  .full-bleed.cover .dash-row .lbl { color: #8593aa; font-size: 6.5pt; }
  .full-bleed.cover .dash-row .val { color: #ffffff; font-weight: 600; font-size: 6.8pt; }
  .full-bleed.cover .target-spectrum {
    display: grid;
    grid-template-columns: 1fr 1.2fr 1fr;
    gap: 0;
    margin-top: 1mm;
    flex: 1;
    margin-left: 5mm;
  }
  .full-bleed.cover .target-cell {
    padding: 0.8mm 2mm;
    border-right: 0.5px solid rgba(184,146,46,0.3);
    text-align: center;
  }
  .full-bleed.cover .target-cell:last-child { border-right: none; }
  .full-bleed.cover .target-cell .t-lbl {
    font-size: 6.5pt;
    letter-spacing: 1.5px;
    color: #8593aa;
    text-transform: uppercase;
    font-weight: 700;
  }
  .full-bleed.cover .target-cell .t-val {
    font-family: var(--font-heading);
    font-size: 9.5pt;
    font-weight: 400;
    color: #e0e6f0;
    margin-top: 0.3mm;
    font-variant-numeric: tabular-nums;
    line-height: 1.1;
    white-space: nowrap;
  }
  .full-bleed.cover .target-cell.base .t-val {
    font-size: 12pt;
    color: #ffffff;
    font-weight: 500;
    white-space: nowrap;
  }
  .full-bleed.cover .pick-badge {
    font-size: 11pt !important;
    line-height: 1.15 !important;
    padding: 1.5mm 4mm !important;
    white-space: normal !important;
    letter-spacing: 0.5px !important;
  }
  .full-bleed.cover .dash-row { white-space: nowrap; }
  .full-bleed.cover .target-cell.base .t-lbl { color: #b8922e; }
  .full-bleed.cover .target-cell.bear .t-val { color: #e2a5a5; }
  .full-bleed.cover .target-cell.bull .t-val { color: #86c7a5; }
  .full-bleed.cover .target-cell .t-delta {
    font-size: 7.5pt;
    color: #8593aa;
    margin-top: 0.3mm;
    font-variant-numeric: tabular-nums;
  }
  .full-bleed.cover .target-cell.base .t-delta { color: #d0d6e0; font-weight: 600; }
  .cover .brand-bar {
    display: flex;
    justify-content: space-between;
    padding-bottom: 5mm;
    border-bottom: 1px solid rgba(184,146,46,0.6);
    font-size: 8.5pt;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    color: #b8922e;
    font-weight: 700;
  }
  .cover .cover-body { margin-top: 48mm; }
  .cover .cap-gold {
    color: #b8922e;
    font-size: 9pt;
    letter-spacing: 3px;
    text-transform: uppercase;
    font-weight: 600;
  }
  .cover h1.stock-title {
    font-family: var(--font-heading);
    font-size: 52pt;
    font-weight: 300;
    margin: 5mm 0 3mm 0;
    line-height: 0.95;
    color: #ffffff;
    letter-spacing: -1px;
  }
  .cover .stock-meta {
    font-size: 11pt;
    color: #b8c3d4;
    letter-spacing: 1px;
    font-weight: 300;
  }
  .cover .tagline {
    margin-top: 14mm;
    font-family: var(--font-heading);
    font-size: 17pt;
    font-weight: 300;
    line-height: 1.4;
    color: #e0e6f0;
    max-width: 145mm;
    font-style: italic;
  }
  .cover .pick-box {
    position: absolute;
    left: 22mm;
    right: 22mm;
    bottom: 42mm;
    border: 1px solid rgba(184,146,46,0.7);
    padding: 6mm 7mm;
    background: rgba(0,0,0,0.18);
  }
  .cover .pick-label {
    color: #b8922e;
    font-size: 8pt;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    font-weight: 700;
  }
  .cover .pick-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 4mm;
  }
  .cover .pick-badge {
    display: inline-block;
    padding: 3mm 8mm;
    font-size: 16pt;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: 2px;
  }
  .cover .pick-metrics {
    text-align: right;
    font-size: 10pt;
    color: #e0e6f0;
    font-variant-numeric: tabular-nums;
    line-height: 1.55;
  }
  .cover .pick-metrics .big {
    font-size: 14pt;
    font-weight: 600;
    color: #ffffff;
  }
  .cover .cover-footer {
    position: absolute;
    left: 22mm;
    right: 22mm;
    bottom: 18mm;
    font-size: 7.5pt;
    letter-spacing: 1.5px;
    color: #8593aa;
    text-transform: uppercase;
    display: flex;
    justify-content: space-between;
    padding-top: 4mm;
    border-top: 1px solid rgba(184,146,46,0.3);
  }

  /* ---------- Running header ---------- */
  .running-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 3mm;
    margin-bottom: 7mm;
    border-bottom: 1px solid #e4e7ec;
    font-size: 7.5pt;
    color: #7a8699;
    letter-spacing: 2px;
    text-transform: uppercase;
  }
  .running-header .brand { font-weight: 700; color: #0b2545; letter-spacing: 2.5px; }

  /* ---------- Section caption + heading ---------- */
  .section-caption {
    color: #b8922e;
    font-size: 8.5pt;
    letter-spacing: 3px;
    text-transform: uppercase;
    font-weight: 700;
    margin-top: 0;
  }
  .section-heading {
    font-family: var(--font-heading);
    font-size: 24pt;
    font-weight: 300;
    color: #0b2545;
    margin: 2mm 0 6mm 0;
    line-height: 1.15;
    letter-spacing: -0.3px;
  }

  /* ---------- Markdown headings (rendered from ## ### in body) ---------- */
  .md-h2 {
    font-family: var(--font-heading);
    font-size: 12pt;
    font-weight: 600;
    color: #0b2545;
    margin: 4mm 0 1.5mm 0;
    padding-left: 3mm;
    border-left: 3px solid #b8922e;
    line-height: 1.3;
    page-break-after: avoid;
    break-after: avoid;
  }
  .md-h3 {
    font-size: 10pt;
    font-weight: 700;
    color: #0b2545;
    margin: 3mm 0 1mm 0;
    line-height: 1.3;
    page-break-after: avoid;
    break-after: avoid;
  }
  .md-h4 {
    font-size: 9.5pt;
    font-weight: 700;
    color: #3a4658;
    margin: 2.5mm 0 1mm 0;
    page-break-after: avoid;
  }

  /* ---------- Body paragraph ---------- */
  p {
    margin: 1.5mm 0;
    color: #2a3342;
    font-size: 9.5pt;
    line-height: 1.65;
    text-align: left;
  }
  strong { color: #0b2545; font-weight: 700; }
  em { font-style: italic; color: #2a3342; }
  code {
    font-family: var(--font-mono);
    font-size: 8.5pt;
    background: #f4f6f9;
    padding: 0.5mm 1.5mm;
    border-radius: 1mm;
  }

  /* ---------- Bullet / Numbered list ---------- */
  ul.md-bullet, ol.md-ordered {
    margin: 2mm 0 3mm 0;
    padding-left: 6mm;
  }
  ul.md-bullet li, ol.md-ordered li {
    margin: 1mm 0;
    color: #2a3342;
    font-size: 9.5pt;
    line-height: 1.6;
  }

  /* ---------- Blockquote ---------- */
  blockquote.md-quote {
    margin: 4mm 0;
    padding: 3mm 5mm;
    background: #fafbfc;
    border-left: 3px solid #b8922e;
    font-family: var(--font-heading);
    font-style: italic;
    font-size: 10pt;
    line-height: 1.65;
    color: #2a3342;
  }

  /* ---------- HR spacer ---------- */
  .hr-spacer {
    height: 0;
    margin: 4mm 0;
    border-top: 1px dashed #e4e7ec;
  }

  /* ---------- NYT/Bloomberg Table ---------- */
  table.nyt {
    width: 100%;
    border-collapse: collapse;
    font-size: 8.5pt;
    margin: 3mm 0 4mm 0;
    page-break-inside: avoid;
  }
  table.nyt thead tr {
    border-top: 2px solid #0b2545;
    border-bottom: 1px solid #0b2545;
  }
  table.nyt thead th {
    padding: 1.8mm 2.5mm;
    text-align: left;
    font-size: 7pt;
    color: #7a8699;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 700;
  }
  table.nyt thead th.num { text-align: right; }
  table.nyt tbody tr { border-bottom: 1px solid #edf0f4; }
  table.nyt tbody tr:last-child { border-bottom: 2px solid #0b2545; }
  table.nyt tbody td {
    padding: 1.8mm 2.5mm;
    color: #0a0e1a;
    font-size: 8.5pt;
    line-height: 1.45;
  }
  table.nyt tbody td.num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  table.nyt tbody td.name { font-weight: 600; color: #0b2545; }

  /* ---------- Verdict Card (Page 2) ---------- */
  .verdict-card {
    border: 1px solid #e4e7ec;
    margin-top: 2mm;
    page-break-inside: avoid;
  }
  .verdict-head {
    background: #0b2545;
    color: #ffffff;
    padding: 3.5mm 5mm;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 9pt;
    letter-spacing: 2px;
    text-transform: uppercase;
  }
  .verdict-head .title { font-weight: 700; }
  .verdict-rating-badge {
    color: #ffffff;
    padding: 1.8mm 5mm;
    font-weight: 700;
    font-size: 12pt;
    letter-spacing: 2px;
  }
  .verdict-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
  }
  .verdict-cell {
    padding: 4mm 5mm 4mm 5mm;
    border-right: 1px solid #e4e7ec;
    border-bottom: 1px solid #e4e7ec;
  }
  .verdict-cell.last-col { border-right: none; }
  .verdict-cell.last-row { border-bottom: none; }
  .verdict-cell .lbl {
    font-size: 7pt;
    color: #7a8699;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 700;
  }
  .verdict-cell .val {
    font-family: var(--font-heading);
    font-size: 16pt;
    font-weight: 400;
    color: #0b2545;
    margin-top: 1mm;
    font-variant-numeric: tabular-nums;
    line-height: 1.15;
  }
  .verdict-cell .delta {
    font-size: 8pt;
    color: #7a8699;
    margin-top: 0.5mm;
    font-variant-numeric: tabular-nums;
  }
  .verdict-cell .delta.pos { color: #2a6b4a; }
  .verdict-cell .delta.neg { color: #8b2e2e; }

  /* ---------- Core thesis / Final call ---------- */
  .core-thesis {
    margin-top: 6mm;
    padding: 5mm 6mm;
    background: #fafbfc;
    border-left: 3px solid #b8922e;
    font-family: var(--font-heading);
    font-size: 10.5pt;
    font-style: italic;
    line-height: 1.7;
    color: #2a3342;
  }
  .core-thesis::before {
    content: "Core Thesis";
    display: block;
    font-family: var(--font-body);
    font-size: 7.5pt;
    color: #b8922e;
    letter-spacing: 2px;
    text-transform: uppercase;
    font-weight: 700;
    margin-bottom: 2mm;
    font-style: normal;
  }
  .final-call {
    margin-top: 12mm;
    border-top: 4px double #0b2545;
    border-bottom: 4px double #0b2545;
    padding: 7mm 9mm;
    page-break-inside: avoid;
  }
  .final-call .caption {
    color: #b8922e;
    font-size: 8pt;
    letter-spacing: 3px;
    text-transform: uppercase;
    font-weight: 700;
  }
  .final-call .conclusion {
    margin-top: 3mm;
    font-family: var(--font-heading);
    font-style: italic;
    font-size: 13pt;
    line-height: 1.55;
    color: #0b2545;
  }
  .final-call .signature {
    margin-top: 5mm;
    font-size: 8.5pt;
    color: #7a8699;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    display: flex;
    justify-content: space-between;
  }

  /* ---------- TOC ---------- */
  .toc {
    margin-top: 4mm;
    columns: 2;
    column-gap: 10mm;
  }
  .toc-item {
    display: flex;
    justify-content: space-between;
    padding: 2mm 0;
    border-bottom: 1px dotted #e4e7ec;
    font-size: 9pt;
    color: #2a3342;
    break-inside: avoid;
  }
  .toc-item .num {
    color: #b8922e;
    font-weight: 700;
    width: 8mm;
  }
  .toc-item .title { flex: 1; }
  .toc-item .pg { color: #7a8699; font-variant-numeric: tabular-nums; }
  /* 독립 TOC 페이지 (full-bleed) 용 확장 레이아웃 */
  .toc.toc-full {
    margin-top: 8mm;
    columns: 2;
    column-gap: 14mm;
    column-rule: 1px solid #e4e7ec;
  }
  .toc.toc-full .toc-item {
    padding: 3mm 0;
    font-size: 10pt;
  }
  .toc.toc-full .toc-item .num {
    font-size: 11pt;
    font-family: Georgia, serif;
  }
  .toc.toc-full .toc-item:hover { background: #fafbfc; }
  .toc-page .section-intro {
    max-width: 140mm;
    margin-bottom: 8mm;
  }

  /* ---------- Page footer ---------- */
  .page-footer {
    position: absolute;
    left: 20mm;
    right: 20mm;
    bottom: 12mm;
    padding-top: 3mm;
    border-top: 1px solid #e4e7ec;
    display: flex;
    justify-content: space-between;
    font-size: 7pt;
    color: #9ca6b5;
    letter-spacing: 1.5px;
    text-transform: uppercase;
  }

  /* ---------- Section page wrapper ---------- */
  .section-block {
    margin-bottom: 8mm;
  }
  .section-block:first-child { margin-top: 0; }
"""


_SECTION_TITLES_DETAILED_V4 = [
    ("s01_opinion",            "01", "Investment Opinion",       "투자의견 & 목표주가"),
    ("s02_investment_points",  "02", "Investment Thesis",        "투자 포인트"),
    ("s03_company_overview",   "03", "Company Overview",         "회사 개요 & 비즈니스 모델"),
    ("s04_industry",           "04", "Industry & Market",        "산업 & 시장"),
    ("s05_competition",        "05", "Competitive Landscape",    "경쟁 구도 & Peer"),
    ("s06_moat",               "06", "Economic Moat",            "경제적 해자"),
    ("s07_management",         "07", "Management",               "경영진 & 지배구조"),
    ("s08_financial",          "08", "Financial Analysis",       "재무 분석"),
    ("s09_valuation",          "09", "Valuation",                "밸류에이션"),
    ("s10_macro",              "10", "Macro Risks",              "매크로 리스크"),
    ("s11_catalysts",          "11", "Catalyst Timeline",        "카탈리스트 타임라인"),
    ("s12_scenarios",          "12", "Scenarios",                "Bear / Base / Bull"),
    ("s13_thesis",             "13", "Investment Thesis",        "투자 논문"),
    ("s14_short_thesis",       "14", "Short Thesis",             "숏 논거 + 반박"),
    ("s15_beat_miss",          "15", "Earnings Beat / Miss",     "실적 Beat/Miss"),
    ("s16_consensus",          "16", "Analyst Consensus",        "애널리스트 컨센서스"),
    ("s17_supply",             "17", "Supply & Demand",          "수급 분석"),
    ("s18_shareholder_return", "18", "Shareholder Return",       "주주환원 정책"),
    ("s19_trust_worry_watch",  "19", "Trust / Worry / Watch",    "신뢰 / 우려 / 관찰"),
    ("s20_action_plan",        "20", "Action Plan",              "실행 계획"),
    ("s21_reliability",        "21", "Reliability",              "분석 신뢰도 & 한계"),
]

# v5.0 12섹션 (CFA 표준 통합 + ESG 신설)
_SECTION_TITLES_DETAILED_V5 = [
    ("s01_opinion_thesis",        "01", "Opinion & Thesis",         "투자의견 & 한 줄 투자 논문"),
    ("s02_thesis_catalysts",      "02", "Thesis & Catalysts",       "투자포인트 & 카탈리스트"),
    ("s03_company_overview",      "03", "Company Analysis",         "기업 분석"),
    ("s04_industry_competition",  "04", "Industry & Competition",   "산업 분석 & 경쟁 구도"),
    ("s05_management_fieldcheck", "05", "Management & Field Check", "경영진 & 현장 검증"),
    ("s06_financial",             "06", "Financial Analysis",       "재무 분석"),
    ("s07_valuation",             "07", "Valuation",                "밸류에이션"),
    ("s08_esg",                   "08", "ESG",                      "ESG 분석"),
    ("s09_scenarios_risks",       "09", "Scenarios & Risks",        "시나리오 & 리스크"),
    ("s10_earnings_consensus",    "10", "Earnings & Consensus",     "실적 · 컨센"),
    ("s11_supply_shareholder",    "11", "Supply & Shareholder",     "수급 & 주주환원"),
    ("s12_action_plan",           "12", "Action Plan",              "실행 계획 & Exit"),
]


def _detect_version(sections: dict) -> str:
    """v5.0 12섹션 또는 v4 21섹션 자동 감지."""
    v5_keys = {"s01_opinion_thesis", "s02_thesis_catalysts", "s06_financial", "s12_action_plan"}
    if any(k in sections for k in v5_keys):
        return "v5"
    return "v4"


def _apply_section_order(order, sections):
    """meta.section_order 로 v5 12섹션을 재정렬/축약한다 (위닝펀드 6섹션 구조용).

    2026-09 위닝펀드 수상작 12편 실측: 본문 섹션이 6개뿐이고
    산업 26% / 기업 19% / 투자포인트 17% / 리스크 10% / 재무 12% / 밸류 16% 다.
    ESG·실행계획·수급·경영진·컨센은 독립 섹션 없이 호스트 섹션에 녹아 있다.

    섹션을 **지우지 않고** 호스트로 병합한 뒤 렌더 순서만 여기서 지정한다.
    (지우면 verify_numbers/verify_facts 가 읽던 근거가 사라진다.)

    순서에서 빠진 정규 키에 본문이 남아 있으면 **ValueError 로 죽인다** --
    그 내용은 에러도 로그도 없이 PDF 에서 사라지기 때문이다.
    """
    table = {k: (k, n, en, ko) for k, n, en, ko in _SECTION_TITLES_DETAILED_V5}

    seen = set()
    for k in order:
        if k in seen:
            raise ValueError(f"meta.section_order 에 중복 키: {k}")
        if k not in table:
            raise ValueError(
                f"meta.section_order 의 '{k}' 는 정규 12키가 아니다. "
                f"alias 키(s08_financial 등)를 넣으면 본문이 두 번 렌더된다. "
                f"가능한 키: {', '.join(table)}")
        seen.add(k)

    dropped = [k for k in table if k not in seen and (sections.get(k) or '').strip()]
    if dropped:
        raise ValueError(
            f"meta.section_order 에서 빠졌는데 본문이 남아 있는 섹션: {', '.join(dropped)}. "
            f"병합했다면 원본을 빈 문자열로 비우고, 아니라면 순서에 넣어라. "
            f"이대로 두면 해당 내용이 PDF 에 나오지 않는다.")

    return [(k, f"{i:02d}", table[k][2], table[k][3]) for i, k in enumerate(order, start=1)]


def _get_section_titles(data) -> list:
    """v5.0이면 12섹션(meta.section_order 로 재편 가능), v4면 21섹션 목차 반환."""
    sections = data.get("sections", {}) if isinstance(data, dict) else {}
    if _detect_version(sections) != "v5":
        return _SECTION_TITLES_DETAILED_V4
    order = (data.get("meta") or {}).get("section_order") if isinstance(data, dict) else None
    if not order:
        return _SECTION_TITLES_DETAILED_V5
    return _apply_section_order(list(order), sections)


# 하위 호환: 기존 코드가 _SECTION_TITLES_DETAILED 참조 시 v4 사용
_SECTION_TITLES_DETAILED = _SECTION_TITLES_DETAILED_V4


def _generate_detailed_v3(data, output_dir):
    """Single institutional-grade PDF: cover + TOC + 21 sections + final call.

    Design: Navy/Gold palette, NYT/Bloomberg-style tables, full markdown rendering,
    emoji stripped throughout.
    """
    meta = data["meta"]
    price = data["price"]
    opinion = data["opinion"]
    sections = data["sections"]
    fin = data["financials"]
    peers = data.get("peers", [])
    catalysts = data.get("catalysts", [])
    segs = data.get("segments", [])

    name = meta["stock_name"].replace(" ", "")
    is_kr = meta["country"] == "KR"

    def fmt_money(v):
        if v is None:
            return "N/A"
        if is_kr:
            return f'{int(v):,}원'
        return f'${float(v):,.2f}'

    def safe(v, default="—"):
        return default if v is None else v

    cur_price = price.get("current") or 1
    up_base = ((opinion["target_base"] - cur_price) / cur_price) * 100
    up_bull = ((opinion["target_bull"] - cur_price) / cur_price) * 100
    down_bear = ((opinion["target_bear"] - cur_price) / cur_price) * 100
    rating = opinion.get("rating", "HOLD")
    rr = opinion.get("risk_reward", "—")
    rating_color = {"BUY": "#0a56d6", "HOLD": "#6b7280", "SELL": "#d32f2f"}.get(rating, "#6b7280")

    # ---- 52-week range
    hi_52 = price.get("high_52w")
    lo_52 = price.get("low_52w")
    if hi_52 and lo_52 and is_kr:
        range_str = f"{int(lo_52):,} – {int(hi_52):,}"
    elif hi_52 and lo_52:
        range_str = f"${lo_52:,.2f} – ${hi_52:,.2f}"
    else:
        range_str = "—"

    # ---- Tagline (cover) -- meta.tagline 우선, 없으면 한국어 fallback
    tagline = meta.get("tagline") or meta.get("subtitle")
    if not tagline:
        industry = meta.get('industry', '')
        if rating == "BUY":
            tagline = f"{industry} -- 시장이 아직 보지 못한 비대칭"
        elif rating == "SELL":
            tagline = f"{industry} -- 내러티브가 가격을 앞서간 자리"
        else:
            tagline = f"{industry} -- 기대와 리스크 사이, 균형의 순간"
    tagline = _strip_emoji(tagline)

    # ---- R/R short text
    rr_short = str(rr)
    if len(rr_short) > 18:
        rr_short = rr_short.split('(')[0].strip() or rr_short[:18]

    # ---- Core thesis & final conclusion
    core_thesis = _sv2_first_para(sections.get("s13_thesis", "") or sections.get("s01_opinion", ""), 320)
    final_conclusion = _sv2_first_para(sections.get("s13_thesis", "") or sections.get("s01_opinion", ""), 360)

    # =====================================================================
    # Cover Dashboard 데이터 준비 (1M/6M/12M 수익률, Stock Data, Consensus)
    # =====================================================================
    def _calc_return(prices, trading_days):
        if not prices or len(prices) < 2:
            return None
        try:
            cur = float(prices[0].get('close', 0))
            idx = min(trading_days, len(prices) - 1)
            past = float(prices[idx].get('close', 0))
            if past == 0:
                return None
            return (cur - past) / past * 100
        except (TypeError, ValueError):
            return None

    daily = price.get('daily_prices', []) or []
    r_1m = _calc_return(daily, 21)
    r_6m = _calc_return(daily, 126)
    r_12m = _calc_return(daily, 252)

    def _ret_cell(v):
        if v is None:
            return '<span class="val">—</span>'
        color = "#86c7a5" if v > 0 else "#e2a5a5"
        return f'<span class="val" style="color:{color};">{v:+.1f}%</span>'

    def _price_fmt(v):
        if v is None or v == "":
            return None
        try:
            n = float(v)
            if is_kr:
                return f"{int(n):,}원"
            return f"${n:,.2f}"
        except (TypeError, ValueError):
            return str(v)

    # 52주 고/저 통합 1행
    if hi_52 and lo_52:
        if is_kr:
            range_52w_fmt = f"{int(lo_52):,} – {int(hi_52):,}"
        else:
            range_52w_fmt = f"${lo_52:,.2f} – ${hi_52:,.2f}"
    else:
        range_52w_fmt = None

    # Stock Data (빈 값 자동 스킵)
    stock_data_rows = [
        ("시가총액", price.get("market_cap")),
        ("52주 고/저", range_52w_fmt),
        # KIS 가 주는 PER 은 **직전 연간 EPS** 기준이지 TTM 이 아니다.
        # (실측 2026-09-08 LS일렉트릭: KIS 104.92배 = FY2025 EPS 1,911원 기준,
        #  TTM 지배순이익으로 계산하면 77.4배. 라벨이 TTM 이면 독자가 오해한다.)
        ("PER (후행)", f'{price.get("per")}x' if price.get("per") else None),
        ("PBR", f'{price.get("pbr")}x' if price.get("pbr") else None),
        ("EPS", _price_fmt(price.get("eps"))),
        ("BPS", _price_fmt(price.get("bps"))),
        ("배당수익률", price.get("dividend_yield")),
    ]
    stock_data_html = ''
    for lbl, val in stock_data_rows:
        if val is None or val == "" or val == "—":
            continue
        stock_data_html += f'<div class="dash-row"><span class="lbl">{html_lib.escape(str(lbl))}</span><span class="val">{html_lib.escape(str(val))}</span></div>'

    # Consensus Data (재무 테이블에서 실적/추정 년도 2개 발췌)
    fin_headers_c = fin.get("headers", [])
    fin_rows_raw = fin.get("rows", [])
    # v5: dict ({"매출(조)": [...], ...}) / v4: list of list ([["매출", ...], ...]) 양쪽 모두 지원
    if isinstance(fin_rows_raw, dict):
        fin_rows_c = [[k] + list(v) for k, v in fin_rows_raw.items()]
        # dict에서는 헤더에 "항목" 빠질 수 있으므로 보정
        if fin_headers_c and len(fin_headers_c) == len(list(fin_rows_raw.values())[0]):
            fin_headers_c = ["항목"] + list(fin_headers_c)
    else:
        fin_rows_c = fin_rows_raw
    cons_rows_html = ''
    _cons_is_forward = False
    if fin_headers_c and fin_rows_c and consensus_columns(fin_headers_c):
        last_actual, fwd_idx, _cons_is_forward = consensus_columns(fin_headers_c)

        y_act = str(fin_headers_c[last_actual]) if last_actual < len(fin_headers_c) else ""
        y_fwd = str(fin_headers_c[fwd_idx]) if fwd_idx < len(fin_headers_c) else ""

        # 단위 추출: row label 첫 번째 (예: "매출(조)") 또는 헤더
        unit_match = ""
        for r in fin_rows_c:
            if r and "매출" in str(r[0]):
                lbl0 = str(r[0])
                if "(조)" in lbl0 or "조" in lbl0:
                    unit_match = "조원"; break
                if "(억)" in lbl0 or "억" in lbl0:
                    unit_match = "억원"; break

        _kind_c = '추정' if _cons_is_forward else '실적'
        subtitle = (f'<div style="font-size:6.5pt; color:#8593aa; letter-spacing:1.5px; '
                    f'margin-bottom:1.5mm; text-align:center;">{html_lib.escape(y_act)} 실적 '
                    f'&nbsp;→&nbsp; {html_lib.escape(y_fwd)} {_kind_c} '
                    f'<span style="color:#b8922e;">({unit_match})</span></div>') if unit_match else ''

        for lbl, kw in [("매출", "매출"), ("영업이익", "영업이익"), ("순이익", "순이익"), ("EPS", "EPS"), ("OPM", "OPM")]:
            for row in fin_rows_c:
                if row and kw in str(row[0]):
                    v_act = str(row[last_actual]) if last_actual < len(row) else None
                    v_fwd = str(row[fwd_idx]) if fwd_idx < len(row) else None
                    if not v_act or v_act == "—":
                        continue
                    cons_rows_html += f'<div class="dash-row"><span class="lbl">{html_lib.escape(lbl)}</span><span class="val" style="font-size:7pt;">{html_lib.escape(v_act)} → {html_lib.escape(v_fwd)}</span></div>'
                    break
        cons_rows_html = subtitle + cons_rows_html
    cons_block_title_c = '컨센서스 요약' if _cons_is_forward else '실적 추이'
    if not cons_rows_html:
        cons_rows_html = '<div class="dash-row"><span class="lbl">재무 데이터 없음</span><span class="val">—</span></div>'

    # 주가 수익률 (빈 값 자동 스킵, 52주 중복 제거)
    ret_items = []
    if r_1m is not None: ret_items.append(("1개월", _ret_cell(r_1m)))
    if r_6m is not None: ret_items.append(("6개월", _ret_cell(r_6m)))
    if r_12m is not None: ret_items.append(("12개월", _ret_cell(r_12m)))
    if price.get("change_pct") is not None:
        cp = price.get("change_pct", 0)
        color_c = "#86c7a5" if cp > 0 else ("#e2a5a5" if cp < 0 else "#ffffff")
        ret_items.append(("일일 변동", f'<span class="val" style="color:{color_c};">{cp:+.2f}%</span>'))
    if price.get("per_forward_12m"):
        ret_items.append(("Forward PER", f'<span class="val">{price.get("per_forward_12m")}x</span>'))
    if price.get("sector_per"):
        ret_items.append(("섹터 PER", f'<span class="val">{price.get("sector_per")}x</span>'))

    returns_html = ''
    for lbl, cell in ret_items:
        returns_html += f'<div class="dash-row"><span class="lbl">{html_lib.escape(lbl)}</span>{cell}</div>'
    if not returns_html:
        returns_html = '<div class="dash-row"><span class="lbl">데이터 없음</span><span class="val">—</span></div>'

    # =====================================================================
    # PAGE 1 — COVER (융합: 네이비/골드 기관급 + 위닝펀드 Dashboard + 3-Target 스펙트럼)
    # =====================================================================
    # 레일 3블록: 종목정보 / 밸류에이션 / 컨센서스 (실측값만, 없으면 행 생략)
    def _row(k, v, key=False):
        if v in (None, "", "—"):
            return ""
        cls = ' class="k"' if key else ""
        return f'<tr><td{cls}>{html_lib.escape(str(k))}</td><td class="v">{v}</td></tr>'

    _p = price
    _fp = lambda x: fmt_money(x) if x else None
    rail_stock = "".join([
        _row("목표주가", f'{fmt_money(opinion.get("target_base"))} {up_base:+.1f}%', True),
        _row("현재주가", fmt_money(cur_price)),
        _row("시가총액", _p.get("market_cap")),
        _row("발행주식수", f'{_p["shares_outstanding"]/1e8:.2f}억주' if _p.get("shares_outstanding") else None),
        _row("52주 최저/최고", f'{_fp(_p.get("low_52w"))} / {_fp(_p.get("high_52w"))}'
             if _p.get("low_52w") and _p.get("high_52w") else None),
    ])
    rail_val = "".join([
        _row("PER (후행)", f'{_p["per"]:.1f}배' if _p.get("per") else None),
        _row("PER (TTM)", f'{_p["ttm_per"]:.1f}배' if _p.get("ttm_per") else None),
        _row("PER (12M Fwd)", f'{_p["forward_per"]:.1f}배' if _p.get("forward_per") else None),
        _row("PBR", f'{_p["pbr"]:.2f}배' if _p.get("pbr") else None),
        _row("배당수익률", f'{_p["dividend_yield"]:.2f}%' if _p.get("dividend_yield") else None),
    ])
    rail_sc = "".join([
        _row("Bear", f'{fmt_money(opinion.get("target_bear"))} {down_bear:+.1f}%'),
        _row("Base", f'{fmt_money(opinion.get("target_base"))} {up_base:+.1f}%', True),
        _row("Bull", f'{fmt_money(opinion.get("target_bull"))} {up_bull:+.1f}%'),
        _row("Risk / Reward", html_lib.escape(rr_short)),
    ])

    # 요약 불릿 -- 마진 노트 / '한 줄 평가:' / 굵은 핵심문장 순으로 3단 fallback.
    # (리포트마다 강조 표기가 달라 한 패턴만 보면 불릿이 1개만 나온다 -- 실측)
    _s01 = sections.get("s01_opinion_thesis") or sections.get("s01_opinion") or ""
    _P_MARGIN = r"^>\s*\*\*한 줄:\*\*\s*(.+)$"
    _P_EVAL = r"^#{2,4}\s*[^\n]*한 줄 평가\s*:\s*(.+)$"
    _P_QUOTE = r"^>\s+(?!\*\*한 줄)(.{10,120})$"
    _bul = re.findall(_P_MARGIN, _s01, re.M)
    if len(_bul) < 3:
        _bul += [m.strip() for m in re.findall(_P_EVAL, _s01, re.M)]
    if len(_bul) < 3:
        _bul += [m.strip() for m in re.findall(_P_QUOTE, _s01, re.M)]
    if len(_bul) < 3:
        for m in re.findall(r"\*\*(.{14,110}?)\*\*", _s01):
            if "|" in m or m.startswith("한 줄"):
                continue
            _bul.append(m.strip())
            if len(_bul) >= 3:
                break
    _seen, _bul3 = set(), []
    for _b in _bul:
        _b = _b.strip().rstrip(".")
        if _b and _b not in _seen:
            _seen.add(_b)
            _bul3.append(_b)
        if len(_bul3) == 3:
            break

    def _bold(t):
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\g<1></strong>", t)

    sum_html = "".join('<li>%s</li>' % _bold(html_lib.escape(b)) for b in _bul3)

    def _story_paras(md, limit=4, maxlen=1500):
        """커버 본문 문단. 표/인용/소제목은 빼고 산문만 순서대로 담는다."""
        out, total = [], 0
        for ln in (md or "").split("\n\n"):
            t = ln.strip()
            if not t or t[0] in "#>|-*" or len(t) < 60:
                continue
            t = re.sub(r"\s+", " ", t)
            out.append(_bold(html_lib.escape(t)))
            total += len(t)
            if len(out) >= limit or total > maxlen:
                break
        return "".join("<p>%s</p>" % p for p in out)

    story_html = _story_paras(_s01)

    _fin = data.get("financials") or {}
    _hd = _fin.get("headers") or []
    _rw = _fin.get("rows") or []
    fin_html = ""
    if _hd and _rw:
        _keep = list(range(1, len(_hd)))[-4:]
        fin_html += "<tr>" + '<th>%s</th>' % html_lib.escape(str(_hd[0])) + "".join(
            '<th>%s</th>' % html_lib.escape(str(_hd[i])) for i in _keep) + "</tr>"
        for r in _rw[:6]:
            if not isinstance(r, list) or not r:
                continue
            fin_html += "<tr>" + '<td>%s</td>' % html_lib.escape(str(r[0])) + "".join(
                '<td>%s</td>' % (html_lib.escape(str(r[i])) if i < len(r) else "—")
                for i in _keep) + "</tr>"

    cover_html = f"""
<section class="full-bleed acover">
  <div class="rail">
    <div class="kind">COMPANY<br>REPORT</div>
    <div class="dt">{html_lib.escape(meta.get("date",""))}</div>
    <div class="team">{html_lib.escape(meta.get("industry",""))}</div>
    <div class="who">AI Equity Research</div>
    <div class="mail">{html_lib.escape(meta.get("market",""))} · {html_lib.escape(meta.get("stock_code",""))}</div>
    <div class="rl-hr"></div>
    <div class="blk">
      <div class="blkh">종목 정보</div>
      <div class="badge" style="background:{rating_color};">{html_lib.escape(rating)}</div>
      <table>{rail_stock}</table>
    </div>
    <div class="blk"><div class="blkh">밸류에이션</div><table>{rail_val}</table></div>
    <div class="blk"><div class="blkh">3-시나리오</div><table>{rail_sc}</table></div>
  </div>
  <div class="main">
    <div class="co">{html_lib.escape(meta.get("stock_name",""))} <span>({html_lib.escape(meta.get("stock_code",""))})</span></div>
    <div class="atag">{html_lib.escape(tagline)}</div>
    <ul class="sum">{sum_html}</ul>
    <div class="sh">WHAT'S THE STORY?</div>
    <div class="acover-body">{story_html}</div>
    <div class="sh" style="font-size:9.5pt; margin-top:7mm;">SUMMARY FINANCIAL DATA</div>
    <table class="fin">{fin_html}</table>
  </div>
  <div class="alogo">AI EQUITY RESEARCH</div>
</section>
"""

    # =====================================================================
    # PAGE 2 — Executive Summary (Verdict + Core Thesis + TOC)
    # =====================================================================
    down_cls = "neg" if down_bear < 0 else "pos"
    up_cls = "pos" if up_base > 0 else "neg"
    bull_cls = "pos" if up_bull > 0 else "neg"

    toc_items_html = ''
    _section_titles = _get_section_titles(data)
    for idx, (key, num, en, ko) in enumerate(_section_titles, start=1):
        toc_items_html += (
            f'<div class="toc-item">'
            f'<span class="num">{num}</span>'
            f'<span class="title">{html_lib.escape(ko)}</span>'
            f'<span class="pg">p.{idx + 2}</span>'
            f'</div>'
        )

    # ---- Executive Summary: Peer mini table (커버 중복 제거 후 추가)
    peer_mini_html = ''
    if peers:
        peer_mini_html = '<table class="nyt" style="margin-top:3mm;"><thead><tr><th>Peer</th><th class="num">시가총액</th><th class="num">PER</th><th class="num">PBR</th><th>비고</th></tr></thead><tbody>'
        for pe in peers[:5]:
            hi_cls = ' class="bull-row"' if pe.get("highlight") else ''
            peer_mini_html += (
                f'<tr{hi_cls}>'
                f'<td class="name">{html_lib.escape(_strip_emoji(str(pe.get("name",""))))}</td>'
                f'<td class="num">{html_lib.escape(_strip_emoji(str(pe.get("market_cap",""))))}</td>'
                f'<td class="num">{html_lib.escape(_strip_emoji(str(pe.get("per",""))))}</td>'
                f'<td class="num">{html_lib.escape(_strip_emoji(str(pe.get("pbr",""))))}</td>'
                f'<td style="font-size:8.5pt;">{html_lib.escape(_strip_emoji(str(pe.get("note","")))[:50])}</td>'
                f'</tr>'
            )
        peer_mini_html += '</tbody></table>'

    # ---- Executive Summary: Catalyst mini (상위 3건)
    cat_mini_html = ''
    if catalysts:
        cat_mini_html = '<table class="nyt" style="margin-top:3mm;"><thead><tr><th>시기</th><th>이벤트</th><th class="num">영향</th></tr></thead><tbody>'
        for ct in catalysts[:4]:
            cat_mini_html += (
                f'<tr>'
                f'<td class="name">{html_lib.escape(_strip_emoji(str(ct.get("date",""))))}</td>'
                f'<td>{html_lib.escape(_strip_emoji(str(ct.get("event","")))[:70])}</td>'
                f'<td class="num">{html_lib.escape(_strip_emoji(str(ct.get("impact",""))))}</td>'
                f'</tr>'
            )
        cat_mini_html += '</tbody></table>'

    exec_html = f"""
<section class="full-bleed exec-page">
  <div class="running-header">
    <div class="brand">{html_lib.escape(meta.get("stock_name",""))} · Equity Research</div>
    <div>EXECUTIVE SUMMARY</div>
  </div>

  <div class="section-caption">00 · EXECUTIVE SUMMARY</div>
  <h2 class="section-heading">한 문장 투자 논문 & 근거</h2>

  <div class="core-thesis">{core_thesis}</div>

  <div style="display:grid; grid-template-columns: 1fr 1fr; gap:6mm; margin-top:5mm; font-size:8pt;">
    <div>
      <h4 style="font-family:var(--font-heading); font-size:10pt; color:#0b2545; border-left:3px solid #b8922e; padding-left:2mm; margin:0 0 1mm 0;">Peer Comparison</h4>
      <p style="font-size:7.5pt; color:#5a6372; margin:0 0 1.5mm 0; line-height:1.35;">동일 업종 5사 밸류에이션 스냅샷 -- 상대 포지션 판단용.</p>
      <style scoped>.exec-page table.nyt {{ font-size: 7.5pt; }} .exec-page table.nyt th, .exec-page table.nyt td {{ padding: 1.5mm 2mm; }}</style>
      {peer_mini_html if peer_mini_html else '<p style="color:#9ca6b5;">Peer 데이터 없음</p>'}
    </div>
    <div>
      <h4 style="font-family:var(--font-heading); font-size:10pt; color:#0b2545; border-left:3px solid #b8922e; padding-left:2mm; margin:0 0 1mm 0;">Key Catalysts (향후 4건)</h4>
      <p style="font-size:7.5pt; color:#5a6372; margin:0 0 1.5mm 0; line-height:1.35;">투자 논문 실현/파괴를 좌우하는 임박 이벤트. 상세 s11 참조.</p>
      {cat_mini_html if cat_mini_html else '<p style="color:#9ca6b5;">Catalyst 데이터 없음</p>'}
    </div>
  </div>

  <div class="page-footer">
    <span>{html_lib.escape(meta.get("stock_name",""))} · Executive Summary</span>
    <span>Page 02</span>
  </div>
</section>

<section class="full-bleed toc-page">
  <div class="running-header">
    <div class="brand">{html_lib.escape(meta.get("stock_name",""))} · Equity Research</div>
    <div>Table of Contents</div>
  </div>

  <div class="section-caption">— TABLE OF CONTENTS —</div>
  <h2 class="section-heading">목차</h2>
  <div class="section-intro">본 리서치 노트는 {len(_section_titles)}개 섹션으로 구성되며, 각 섹션은 독립적으로 읽을 수 있도록 설계되었다. 권장 독서 순서: {'01 → 02 → 07 → 08 → 10 → 12' if len(_section_titles) == 12 else '01 → 02 → 09 → 12 → 13'}.</div>

  <div class="toc toc-full">{toc_items_html}</div>

  <div class="page-footer">
    <span>{html_lib.escape(meta.get("stock_name",""))} · Table of Contents</span>
    <span>Page 03</span>
  </div>
</section>
"""

    # =====================================================================
    # SECTION CONTENT — natural flow, no forced page breaks
    # Sections flow continuously after the executive page; chromium decides
    # page breaks automatically based on content height + break-inside hints.
    # =====================================================================
    # --- 도표 (v5.9): 위닝펀드 수상작은 페이지당 1.0~1.6개를 싣는다. 우리는 0개였다.
    # wf_charts(13종) / wf_chart_planner 는 이미 있었고 Word 경로에만 연결돼 있었다.
    _charts, _chart_problems = [], []
    try:
        from report_charts import build_charts, inject_tokens, replace_tokens
        _ap = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'analysis_%s.json' % meta.get('stock_name', ''))
        if os.path.exists(_ap):
            _charts, _chart_problems = build_charts(
                _ap, os.path.join(output_dir, 'charts'),
                section_order=[k for k, _n, _e, _k2 in _section_titles],
                sections=sections)
        else:
            _chart_problems.append('analysis.json 을 찾지 못했다: %s' % _ap)
    except Exception as _e:
        _chart_problems.append('도표 생성 실패: %s: %s' % (type(_e).__name__, _e))

    _by_sec = {}
    for _c in _charts:
        _by_sec.setdefault(_c['section_key'], []).append(_c)
    print('  도표 %d개 삽입' % len(_charts) if _charts else '  [WARN] 도표 0개')
    for _p in _chart_problems:
        print('  [WARN] %s' % _p)

    section_blocks_html = '<div class="content-flow">\n'
    for idx, (key, num, en, ko) in enumerate(_section_titles, start=1):
        body_md = sections.get(key, "")
        # v5.11: '> **한 줄:** X' 를 마진 노트로 (인용 박스와 구분한다)
        if body_md:
            body_md = re.sub(r'^\s*>\s*\*\*한 줄:\*\*\s*(.+)$',
                             r'[[MARGIN]]\1[[/MARGIN]]', body_md, flags=re.M)
        _sec_charts = _by_sec.get(key, [])
        if _sec_charts:
            body_md = inject_tokens(body_md, _sec_charts)
        body_html = _md_to_html_blocks(body_md)
        if _sec_charts:
            body_html = replace_tokens(body_html, _sec_charts)
        body_html = re.sub(r'\[\[MARGIN\]\](.*?)\[\[/MARGIN\]\]',
                           r'<aside class="margin-note">\1</aside>', body_html,
                           flags=re.S)
        body_html = re.sub(r'<p>\s*(<aside class="margin-note">.*?</aside>)\s*</p>',
                           r'\1', body_html, flags=re.S)
        if not body_html:
            body_html = '<p style="color:#9ca6b5;font-style:italic;">— 본 섹션의 콘텐츠가 비어있습니다 —</p>'

        section_blocks_html += f"""
<div class="section-block">
  <div class="section-caption">{num} · {html_lib.escape(en.upper())}</div>
  <h2 class="section-heading">{html_lib.escape(ko)}</h2>
  <div class="section-body">
    {body_html}
  </div>
</div>
"""
    section_blocks_html += '</div>\n'

    # =====================================================================
    # FINAL CALL PAGE
    # =====================================================================
    final_html = f"""
<section class="full-bleed final-page">
  <div class="running-header">
    <div class="brand">{html_lib.escape(meta.get("stock_name",""))} · Equity Research</div>
    <div>FINAL CALL</div>
  </div>

  <div class="section-caption">— FINAL CALL —</div>
  <h2 class="section-heading">최종 결론</h2>

  <div class="final-call">
    <div class="caption">— Final Call —</div>
    <div class="conclusion">{final_conclusion}</div>
    <div class="signature">
      <span>Equity Research · Single-Agent v4</span>
      <span>{html_lib.escape(meta.get("date",""))}</span>
    </div>
  </div>

  <div class="page-footer">
    <span>{html_lib.escape(meta.get("stock_name",""))} · End of Report</span>
    <span>End</span>
  </div>
</section>
"""

    # =====================================================================
    # ASSEMBLE
    # =====================================================================
    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<title>{html_lib.escape(meta.get("stock_name",""))} — Equity Research (Detailed)</title>
<style>{_DETAILED_V3_CSS}</style>
<style>{_ANALYST_CSS}</style>
</head><body>
{cover_html}
{exec_html}
{section_blocks_html}
{final_html}
</body></html>
"""

    html_path = os.path.join(output_dir, f'report_{name}_상세.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

    # PDF conversion via Playwright
    try:
        from playwright.sync_api import sync_playwright
        pdf_path = os.path.join(output_dir, f'report_{name}_상세.pdf')
        file_url = "file:///" + os.path.abspath(html_path).replace("\\", "/")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(file_url)
            page.pdf(
                path=pdf_path,
                format="A4",
                margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
                print_background=True,
                prefer_css_page_size=True,
            )
            browser.close()
        os.remove(html_path)
        print(f'[OK] 상세 PDF (v3): {pdf_path} ({os.path.getsize(pdf_path)//1024} KB)')
    except Exception as e:
        print(f'[!!] PDF 변환 실패: {e}, HTML 파일은 유지됨 ({html_path})')


# ============================================
# 3. 대시보드 (HTML, deprecated — kept for reference)
# ============================================
def generate_dashboard(data, output_dir):
    meta = data["meta"]
    price = data["price"]
    opinion = data["opinion"]
    fin = data["financials"]
    segs = data["segments"]
    peers = data.get("peers", [])
    catalysts = data.get("catalysts", [])
    supply = data.get("supply", {})
    sections = data["sections"]

    name = meta["stock_name"].replace(" ", "")
    is_kr = meta["country"] == "KR"
    c = meta["currency"] if is_kr else "$"

    def fmt(val):
        return f'{val:,}{c}' if is_kr else f'${val:,}'

    rating_class = {"BUY": "tag-buy", "HOLD": "tag-hold", "SELL": "tag-sell"}.get(opinion["rating"], "tag-hold")
    rating_bg = {"BUY": "#4caf50", "HOLD": "#ff9800", "SELL": "#f44336"}.get(opinion["rating"], "#ff9800")

    # 차트 데이터
    daily = price.get("daily_prices", [])
    if daily:
        chart_closes = [d.get("종가", d.get("close", 0)) for d in sorted(daily, key=lambda x: x.get("날짜", x.get("date", "")))]
    else:
        chart_closes = [price["current"]]
    chart_js = json.dumps(chart_closes)

    chart_min = min(min(chart_closes) * 0.85, opinion["target_bear"] * 0.9)
    chart_max = max(max(chart_closes) * 1.15, opinion["target_bull"] * 1.1)

    # 사업부 바
    seg_bars = ''
    colors = ['#1565c0,#42a5f5', '#7c4dff,#b388ff', '#00897b,#4db6ac', '#ff7043,#ffab91', '#ffc107,#ffeb3b']
    for i, s in enumerate(segs):
        color = colors[i % len(colors)]
        seg_bars += f'''
        <div style="display:flex; align-items:center; margin:8px 0;">
          <span style="width:120px; font-size:11px;">{s["name"]}</span>
          <div style="flex:1; height:24px; background:#1a237e; border-radius:4px; position:relative;">
            <div style="width:{s["pct"]}%; height:100%; background:linear-gradient(90deg, {color}); border-radius:4px; min-width:25px;"></div>
            <span style="position:absolute; right:5px; top:3px; font-size:11px;">{s["pct"]}%</span>
          </div>
        </div>'''

    # Forward 테이블
    fin_header = ''.join(f'<th>{h}</th>' for h in fin["headers"][1:])  # 항목 제외
    fin_rows_html = ''
    for row in fin["rows"][:4]:  # 매출, 영업이익, OPM, EPS만
        cells = ''.join(f'<td>{v}</td>' for v in row[1:])
        fin_rows_html += f'<tr><td>{row[0]}</td>{cells}</tr>'

    # Peer 바
    peer_bars = ''
    if peers:
        def parse_cap(s):
            s = s.replace("조","").replace("$","").replace("B","").replace("원","").strip()
            if "T" in s:
                return float(s.replace("T","")) * 1000
            try:
                return float(s)
            except:
                return 1
        max_cap = max(parse_cap(p["market_cap"]) for p in peers)
        for p in peers:
            cap_val = parse_cap(p["market_cap"])
            pct = (cap_val / max_cap) * 100
            hl_color = '#ffc107' if p.get("highlight") else '#42a5f5'
            hl_font = 'color:#ffc107; font-weight:bold;' if p.get("highlight") else ''
            peer_bars += f'''
            <div style="display:flex; align-items:center; margin:8px 0;">
              <span style="width:90px; font-size:12px; {hl_font}">{p["name"]}</span>
              <div style="flex:1; height:24px; background:#1a237e; border-radius:4px; position:relative;">
                <div style="width:{pct:.0f}%; height:100%; background:linear-gradient(90deg, {hl_color.replace('#ffc107','#ff9800,#ffc107').replace('#42a5f5','#1565c0,#42a5f5')}); border-radius:4px; min-width:20px;"></div>
                <span style="position:absolute; right:5px; top:3px; font-size:11px;">{p["market_cap"]}</span>
              </div>
            </div>'''

    # 카탈리스트 타임라인
    cat_items = ''
    for ct in catalysts:
        cat_items += f'''
        <div class="timeline-item">
          <div class="timeline-date">{ct["date"]}</div>
          <div class="timeline-event">{ct["event"]}</div>
        </div>'''

    # 수급
    supply_html = ''
    if supply:
        def supply_bar(val, max_val):
            pct = min(abs(val) / max(abs(supply["foreign"]), abs(supply["institution"]), abs(supply["individual"]), 1) * 100, 100)
            color = '#66bb6a' if val > 0 else '#ef5350'
            return f'<div style="height:8px; background:#1a237e; border-radius:4px;"><div style="width:{pct:.0f}%; height:100%; background:{color}; border-radius:4px;"></div></div>'

        supply_html = f'''
    <div class="card">
      <div class="card-title">수급 동향 (최근 {supply.get("days",20)}일)</div>
      <div style="margin-top:15px;">
        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
          <span style="font-size:12px;">외국인</span>
          <span class="{"positive" if supply["foreign"]>0 else "negative"}" style="font-size:12px;">{supply["foreign"]:+,}주</span>
        </div>
        {supply_bar(supply["foreign"], 1)}
        <div style="display:flex; justify-content:space-between; margin:12px 0 5px;">
          <span style="font-size:12px;">기관</span>
          <span class="{"positive" if supply["institution"]>0 else "negative"}" style="font-size:12px;">{supply["institution"]:+,}주</span>
        </div>
        {supply_bar(supply["institution"], 1)}
        <div style="display:flex; justify-content:space-between; margin:12px 0 5px;">
          <span style="font-size:12px;">개인</span>
          <span class="{"positive" if supply["individual"]>0 else "negative"}" style="font-size:12px;">{supply["individual"]:+,}주</span>
        </div>
        {supply_bar(supply["individual"], 1)}
      </div>
      <div style="font-size:11px; color:#90a4ae; text-align:center; margin-top:10px;">{supply.get("comment","")}</div>
    </div>'''

    # Trust/Worry/Watch 파싱
    tww = sections.get("s19_trust_worry_watch", "")
    trust_items = worry_items = watch_items = ''
    for line in tww.split('\n'):
        line = line.strip()
        if not line or line.startswith('Trust') or line.startswith('Worry') or line.startswith('Watch'):
            continue
        if line.startswith('1)') or line.startswith('2)') or line.startswith('3)'):
            # Determine which section based on position
            pass
    # 간단하게 3개씩 분배
    tww_lines = [l.strip() for l in tww.split('\n') if l.strip() and not l.strip().startswith(('Trust', 'Worry', 'Watch'))]
    trust_list = [l for l in tww_lines if any(l.startswith(f'{i})') for i in range(1,4))]
    sections_split = []
    current = []
    for l in tww_lines:
        if l.startswith('1)') and current:
            sections_split.append(current)
            current = []
        current.append(l)
    if current:
        sections_split.append(current)

    if len(sections_split) >= 3:
        trust_items = ''.join(f'<div class="trust-item trust-green">{l}</div>' for l in sections_split[0])
        worry_items = ''.join(f'<div class="trust-item trust-red">{l}</div>' for l in sections_split[1])
        watch_items = ''.join(f'<div class="trust-item trust-yellow">{l}</div>' for l in sections_split[2])
    else:
        trust_items = '<div class="trust-item trust-green">데이터 확인 필요</div>'
        worry_items = '<div class="trust-item trust-red">데이터 확인 필요</div>'
        watch_items = '<div class="trust-item trust-yellow">데이터 확인 필요</div>'

    html = f'''<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{meta["stock_name"]} ({meta["stock_code"]}) - Dashboard</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'Malgun Gothic','Segoe UI',sans-serif; background:#0a0e27; color:#e0e0e0; }}
  .dashboard {{ max-width:1400px; margin:0 auto; padding:20px; }}
  .header {{ text-align:center; padding:30px 0 20px; border-bottom:2px solid #1a237e; margin-bottom:20px; }}
  .header h1 {{ font-size:28px; color:#64b5f6; }}
  .header .subtitle {{ color:#90a4ae; font-size:14px; margin-top:5px; }}
  .verdict-bar {{ display:flex; justify-content:center; gap:20px; margin:15px 0; flex-wrap:wrap; }}
  .verdict-tag {{ padding:8px 24px; border-radius:20px; font-weight:bold; font-size:14px; }}
  .tag-buy {{ background:#4caf50; color:#fff; }}
  .tag-hold {{ background:#ff9800; color:#000; }}
  .tag-price {{ background:#1a237e; color:#64b5f6; border:1px solid #64b5f6; }}
  .tag-type {{ background:#311b92; color:#b388ff; }}
  .grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:15px; margin-bottom:20px; }}
  .card {{ background:#131736; border-radius:12px; padding:20px; border:1px solid #1a237e; }}
  .card-title {{ font-size:11px; color:#90a4ae; text-transform:uppercase; letter-spacing:1px; margin-bottom:8px; }}
  .card-value {{ font-size:28px; font-weight:bold; color:#64b5f6; }}
  .card-sub {{ font-size:12px; color:#78909c; margin-top:4px; }}
  .positive {{ color:#66bb6a; }} .negative {{ color:#ef5350; }}
  .grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:15px; margin-bottom:20px; }}
  .grid-3 {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:15px; margin-bottom:20px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th {{ background:#1a237e; color:#64b5f6; padding:10px; text-align:center; font-size:11px; }}
  td {{ padding:8px 10px; border-bottom:1px solid #1a237e; text-align:center; }}
  .scenario-box {{ padding:15px; border-radius:8px; margin:8px 0; }}
  .bear-bg {{ background:#1a0a0a; border:1px solid #b71c1c; }}
  .base-bg {{ background:#1a1a0a; border:1px solid #f9a825; }}
  .bull-bg {{ background:#0a1a0a; border:1px solid #2e7d32; }}
  .timeline {{ position:relative; padding-left:30px; }}
  .timeline-item {{ position:relative; padding:10px 0; border-left:2px solid #1a237e; padding-left:20px; }}
  .timeline-item::before {{ content:''; position:absolute; left:-7px; top:14px; width:12px; height:12px; border-radius:50%; background:#64b5f6; }}
  .timeline-date {{ font-size:11px; color:#64b5f6; font-weight:bold; }}
  .timeline-event {{ font-size:13px; color:#e0e0e0; margin-top:3px; }}
  .trust-item {{ padding:8px 12px; margin:5px 0; border-radius:6px; font-size:13px; }}
  .trust-green {{ background:#0a1a0a; border-left:3px solid #66bb6a; }}
  .trust-red {{ background:#1a0a0a; border-left:3px solid #ef5350; }}
  .trust-yellow {{ background:#1a1a0a; border-left:3px solid #ffc107; }}
</style></head><body>
<div class="dashboard">
  <div class="header">
    <h1>{meta["stock_name"]} ({meta["stock_code"]})</h1>
    <div class="subtitle">{meta["industry"]} | {meta["market"]} | {meta["date"]} 기준</div>
    <div class="verdict-bar">
      <span class="verdict-tag {rating_class}">{opinion["rating"]}</span>
      <span class="verdict-tag tag-price">목표가 {fmt(opinion["target_base"])}</span>
      <span class="verdict-tag tag-type">{opinion["type"]}</span>
    </div>
  </div>

  <div class="grid">
    <div class="card"><div class="card-title">현재가</div><div class="card-value">{fmt(price["current"])}</div><div class="card-sub">등락률 {price["change_pct"]:+.2f}%</div></div>
    <div class="card"><div class="card-title">시가총액</div><div class="card-value">{price["market_cap"]}</div><div class="card-sub">52주 {price["low_52w"]:,}~{price["high_52w"]:,}</div></div>
    <div class="card"><div class="card-title">PER</div><div class="card-value">{price["per"]}x</div><div class="card-sub">EPS {price["eps"]:,}</div></div>
    <div class="card"><div class="card-title">PBR</div><div class="card-value">{price["pbr"]}x</div><div class="card-sub">BPS {price["bps"]:,}</div></div>
  </div>

  <div class="card" style="margin-bottom:20px;">
    <div class="card-title">주가 추이 + 목표주가 밴드</div>
    <canvas id="priceChart" height="220"></canvas>
  </div>

  <div class="grid-3">
    <div class="card"><div class="card-title">사업부별 매출 비중</div>{seg_bars}<div style="font-size:10px; color:#546e7a; margin-top:8px;">출처: DART/SEC 사업보고서 기반 추정</div></div>
    <div class="card"><div class="card-title">Forward 실적 추정</div>
      <table style="font-size:11px;"><tr><th>항목</th>{fin_header}</tr>{fin_rows_html}</table>
      <div style="font-size:10px; color:#546e7a; margin-top:5px;">출처: 증권사 컨센서스</div></div>
    <div class="card"><div class="card-title">시나리오별 목표주가</div>
      <div class="scenario-box bear-bg"><strong style="color:#ef5350;">Bear: {fmt(opinion["target_bear"])}</strong></div>
      <div class="scenario-box base-bg"><strong style="color:#ffc107;">Base: {fmt(opinion["target_base"])}</strong></div>
      <div class="scenario-box bull-bg"><strong style="color:#66bb6a;">Bull: {fmt(opinion["target_bull"])}</strong></div>
      <div style="margin-top:10px; font-size:12px;">Risk-Reward: {opinion["risk_reward"]}</div></div>
  </div>

  <div class="grid-2">
    <div class="card"><div class="card-title">Peer Comparison</div>{peer_bars}</div>
    {supply_html if supply_html else '<div class="card"><div class="card-title">수급 데이터 없음</div></div>'}
  </div>

  <div class="grid-2">
    <div class="card"><div class="card-title">카탈리스트 타임라인</div><div class="timeline" style="margin-top:10px;">{cat_items}</div></div>
    <div class="card"><div class="card-title">실행 계획</div>
      <div style="font-size:12px; margin-top:10px;">{md_table_to_html(sections.get("s20_action_plan",""))}</div></div>
  </div>

  <div class="grid-3">
    <div class="card"><div class="card-title" style="color:#66bb6a;">TRUST</div>{trust_items}</div>
    <div class="card"><div class="card-title" style="color:#ef5350;">WORRY</div>{worry_items}</div>
    <div class="card"><div class="card-title" style="color:#ffc107;">WATCH</div>{watch_items}</div>
  </div>

  <div style="text-align:center; padding:20px; color:#546e7a; font-size:11px;">
    본 자료는 투자 참고용이며, 투자 결정의 책임은 투자자 본인에게 있습니다.<br>
    데이터 수집 시점: {meta["date"]} | DART/SEC + 한투API + 웹 검색 기반
  </div>
</div>

<script>
const canvas = document.getElementById('priceChart');
const ctx = canvas.getContext('2d');
canvas.width = canvas.parentElement.clientWidth - 40;
canvas.height = 220;
const closes = {chart_js};
const minP = {chart_min}, maxP = {chart_max};
const w = canvas.width, h = canvas.height;
const pad = {{top:15, bottom:25, left:10, right:10}};
const chartW = w - pad.left - pad.right;
const chartH = h - pad.top - pad.bottom;
function yPos(price) {{ return pad.top + chartH - ((price - minP) / (maxP - minP)) * chartH; }}
[{{price:{opinion["target_bull"]},color:'rgba(102,187,106,0.5)',label:'Bull {fmt(opinion["target_bull"])}'}},
 {{price:{opinion["target_base"]},color:'rgba(255,193,7,0.5)',label:'Base {fmt(opinion["target_base"])}'}},
 {{price:{opinion["target_bear"]},color:'rgba(239,83,80,0.5)',label:'Bear {fmt(opinion["target_bear"])}'}}].forEach(b => {{
  ctx.strokeStyle=b.color; ctx.setLineDash([5,5]);
  ctx.beginPath(); ctx.moveTo(pad.left,yPos(b.price)); ctx.lineTo(w-pad.right,yPos(b.price)); ctx.stroke();
  ctx.setLineDash([]); ctx.fillStyle=b.color; ctx.font='10px sans-serif';
  ctx.fillText(b.label, w-pad.right-90, yPos(b.price)-3);
}});
ctx.beginPath(); ctx.strokeStyle='#64b5f6'; ctx.lineWidth=2;
closes.forEach((p,i) => {{
  const x = pad.left + (i/(closes.length-1)) * chartW;
  if(i===0) ctx.moveTo(x,yPos(p)); else ctx.lineTo(x,yPos(p));
}}); ctx.stroke();
const lastX=pad.left+chartW, lastY=yPos(closes[closes.length-1]);
ctx.beginPath(); ctx.arc(lastX,lastY,5,0,Math.PI*2); ctx.fillStyle='#64b5f6'; ctx.fill();
ctx.fillStyle='#fff'; ctx.font='bold 11px sans-serif';
ctx.fillText('{fmt(price["current"])}', lastX-50, lastY-10);
</script>
</body></html>'''

    html_path = os.path.join(output_dir, f'dashboard_{name}.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'[OK] 대시보드: {html_path} ({os.path.getsize(html_path)//1024} KB)')


# ============================================
# 메인
# ============================================
def main():
    if len(sys.argv) < 2:
        print("사용법: python scripts/generate_all.py <analysis.json>")
        sys.exit(1)

    json_path = sys.argv[1]
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    name = data["meta"]["stock_name"].replace(" ", "")
    output_dir = os.path.join(project_root, "output", name)
    os.makedirs(output_dir, exist_ok=True)

    print(f'\n{"="*50}')
    print(f'  리포트 생성: {data["meta"]["stock_name"]} ({data["meta"]["stock_code"]})')
    print(f'{"="*50}\n')

    # 일봉 데이터 로드 (있으면)
    data_dir = os.path.join(project_root, "data", name)
    kis_path = os.path.join(data_dir, "data_kis.json")
    print(f"KIS 데이터 경로: {kis_path} (존재: {os.path.exists(kis_path)})")
    if os.path.exists(kis_path):
        with open(kis_path, 'r', encoding='utf-8') as f:
            kis = json.load(f)
        daily = kis.get("daily_prices", [])
        if daily:
            data["price"]["daily_prices"] = sorted(daily, key=lambda x: x.get("날짜", x.get("date", "")))

    # ============================================
    # 자동 품질 검증 (generate 전 필수 체크)
    # ============================================
    warnings = []
    errors = []
    sections = data.get("sections", {})

    # ============================================
    # v5.0 → v4.21 sections key fallback (v5.0 12섹션 → v4.21 21섹션 매핑)
    # v5.0 통합 섹션이 v4.21 21섹션 위치에 자동 표시되도록
    # ============================================
    _V5_TO_V4_FALLBACK = {
        # v5.0 새 키 → 매핑할 v4 키들 (한 v5 키가 여러 v4 위치에 표시될 수 있음)
        's01_opinion_thesis': ['s01_opinion', 's13_thesis'],
        's02_thesis_catalysts': ['s02_investment_points', 's11_catalysts'],
        's05_competitive_moat': ['s05_competition', 's06_moat'],
        's06_management_fieldcheck': ['s07_management'],
        's07_financial_analysis': ['s08_financial'],
        's08_valuation': ['s09_valuation'],
        's10_scenarios_risks': ['s10_macro', 's12_scenarios', 's14_short_thesis'],
        's11_earnings_consensus': ['s15_beat_miss', 's16_consensus', 's17_supply', 's18_shareholder_return'],
        's12_action_plan': ['s19_trust_worry_watch', 's20_action_plan', 's21_reliability'],
    }
    for v5k, v4_keys in _V5_TO_V4_FALLBACK.items():
        if v5k in sections and sections[v5k]:
            v5_content = sections[v5k]
            # v5.0 키 자체는 그대로 보존 (analysis_to_md 등 다른 도구 호환)
            # v4 위치 중 비어있는 곳에만 채우기 (v4 키가 이미 있으면 덮어쓰지 않음)
            for v4k in v4_keys:
                if not sections.get(v4k):
                    sections[v4k] = v5_content
    # ESG (s09_esg) 처리: v4에 대응 위치 없으므로 s10_macro 앞에 인라인 표시
    if sections.get('s09_esg') and 's10_macro' in sections:
        esg_content = sections['s09_esg']
        macro_content = sections['s10_macro']
        sections['s10_macro'] = esg_content + "\n\n---\n\n" + macro_content

    price = data.get("price", {})
    opinion = data.get("opinion", {})
    financials = data.get("financials", {})

    # 1. EPS 검증: price.eps와 재무테이블 EPS가 대략 일치하는지
    json_eps = price.get("eps", 0)
    if json_eps and price.get("per", 0) > 0:
        calc_eps = price.get("current", 0) / price.get("per", 1)
        if abs(json_eps - calc_eps) / max(abs(calc_eps), 1) > 0.3:
            warnings.append(f"EPS 불일치: JSON eps={json_eps}, 현재가/PER={calc_eps:.0f} (30%+ 차이)")

    # 2. 사업보고서 인용 체크: sections에 "사업보고서" 또는 "10-K" 키워드가 있는지
    all_sections_text = " ".join(str(v) for v in sections.values())
    quote_keywords = ["사업보고서에 따르면", "사업보고서에서", "10-K에 따르면", "10-K에서", "DART 사업보고서", "공시에 따르면"]
    # v4.18 이 **의무화한 인용 형식**은 서술형이 아니라 인용 박스다:
    #   > 사업보고서 II. 사업의 내용 (2026/08 공시): "..."
    # 위 서술형 키워드만 세면 규칙을 정확히 지킨 리포트가 "인용 0건" 경고를 받는다
    # (실측 2026-09-08 LS일렉트릭: 인용 박스 15개인데 구 카운터는 0건).
    quote_count = (sum(1 for kw in quote_keywords if kw in all_sections_text)
                   + len(_QUOTE_BOX_RE.findall(all_sections_text)))
    if quote_count < 2:
        warnings.append(f"사업보고서 인용 부족: {quote_count}건 (최소 3건 권장)")

    # 3. "왜?" 분석 체크: YoY 변동 설명이 있는지
    why_keywords = ["원인", "이유", "때문", "영향으로", "기인", "결과"]
    # 구 방식은 **몇 종류가 등장했는지**를 셌다(최대 6). 그러면 어휘 다양성을 재는
    # 것이지 분석 깊이를 재는 게 아니다. 실측(2026-09-08): LS일렉트릭이 총 65회로
    # 네 리포트 중 가장 많은데 종류가 4개라 경고, 42회짜리는 5종이라 통과했다.
    # **인과 분석이 가장 많은 리포트를 벌하는 검출기**였다. 총 등장 횟수로 바꾼다.
    why_count = sum(all_sections_text.count(kw) for kw in why_keywords)
    if why_count < 15:
        warnings.append(f'"왜?" 분석 부족: 원인/이유 언급 {why_count}회 (최소 15회 권장)')

    # 4. Risk-Reward 검증
    current = price.get("current", 0) or 1
    bear = opinion.get("target_bear", 0)
    bull = opinion.get("target_bull", 0)
    if current > 0 and bear > 0 and bull > 0:
        downside = (current - bear) / current
        upside = (bull - current) / current
        rr = upside / max(downside, 0.01)
        if opinion.get("rating") == "BUY" and rr < 2.0:
            warnings.append(f"BUY인데 R/R {rr:.1f}:1 (2.0 이상 권장). HOLD 재검토 필요?")

    # 5. 현재가 0원 체크
    if price.get("current", 0) == 0:
        errors.append("현재가가 0원 -KIS 데이터 확인 필요")

    # 6. 시가총액 교차검증 (KIS 데이터 vs JSON)
    kis_path = os.path.join(data_dir, "data_kis.json")
    if os.path.exists(kis_path):
        try:
            with open(kis_path, 'r', encoding='utf-8') as f:
                kis_data = json.load(f)
            kis_mktcap = kis_data.get("current_price", {}).get("시가총액", 0)
            json_mktcap = price.get("market_cap_num", 0)
            if kis_mktcap > 0 and json_mktcap > 0:
                ratio = json_mktcap / kis_mktcap
                if ratio < 0.5 or ratio > 2.0:
                    errors.append(
                        f"시총 불일치! JSON={json_mktcap:,}억 vs KIS={kis_mktcap:,}억 "
                        f"(비율 {ratio:.2f}x). 10배 오류 가능성. 반드시 수정 필요!"
                    )
                elif abs(ratio - 1.0) > 0.1:
                    warnings.append(
                        f"시총 차이: JSON={json_mktcap:,}억 vs KIS={kis_mktcap:,}억 "
                        f"(차이 {abs(ratio-1)*100:.0f}%)"
                    )
            # 현재가 교차검증
            kis_price = kis_data.get("current_price", {}).get("현재가", 0)
            json_price = price.get("current", 0)
            if kis_price > 0 and json_price > 0:
                price_diff = abs(kis_price - json_price) / kis_price
                if price_diff > 0.05:
                    warnings.append(
                        f"현재가 차이: JSON={json_price:,}원 vs KIS={kis_price:,}원 "
                        f"(차이 {price_diff*100:.1f}%)"
                    )
        except Exception as e:
            # 조용히 묵살 금지 — 시총 교차검증이 이 블록 안에서 일어나므로
            # 실패 시 최소한 경고는 남겨야 JYP/시총 10배 사고를 잡을 수 있다
            warnings.append(
                f"KIS 파일 읽기/파싱 실패 ({os.path.basename(kis_path)}): {type(e).__name__}: {e} "
                f"— 시총/현재가 교차검증이 수행되지 않음. data_kis.json 재수집 권장"
            )

    # 7. 재무 테이블 수치 정합성 (매출, 영업이익 등이 합리적 범위인지)
    fin_rows = financials.get("rows", [])
    fin_headers = financials.get("headers", [])
    for row in fin_rows:
        if len(row) < 2:
            continue
        label = row[0]
        for i, val in enumerate(row[1:], 1):
            try:
                # 숫자 파싱 (쉼표, 조, 억, x, % 제거)
                v_str = str(val).replace(",","").replace("x","").replace("%","").replace("배","")
                if "조" in str(val):
                    v_num = float(v_str.replace("조","")) * 10000
                elif "억" in str(val):
                    v_num = float(v_str.replace("억",""))
                else:
                    v_num = float(v_str) if v_str.replace(".","").replace("-","").isdigit() else None
                if v_num is None:
                    continue
                # 음수 영업이익률은 적자 → OK, 하지만 1000%+ 이익률은 오류
                if "이익률" in label or "마진" in label:
                    if abs(v_num) > 100:
                        warnings.append(f"재무 테이블 이상: {label} = {val} (이익률 100%+ 는 오류 가능)")
                # PER 10000+ 은 적자 기업 아니면 오류
                if "PER" in label and v_num > 5000:
                    warnings.append(f"재무 테이블: {label} = {val} (PER 5000+ 확인 필요)")
            except:
                continue

    # 8. Bear/Base/Bull 순서 검증
    bear = opinion.get("target_bear", 0)
    base = opinion.get("target_base", 0)
    bull = opinion.get("target_bull", 0)
    if bear > 0 and base > 0 and bull > 0:
        if not (bear < base < bull):
            errors.append(f"Bear/Base/Bull 순서 오류: Bear={bear}, Base={base}, Bull={bull}. Bear < Base < Bull 이어야 함")
        if bear > current:
            warnings.append(f"Bear({bear:,}) > 현재가({current:,}). Bear는 하방 시나리오인데 현재가보다 높음?")

    # 9. 배당수익률 검증
    div_yield = price.get("dividend_yield", "0%")
    try:
        dy = float(str(div_yield).replace("%",""))
        if dy > 20:
            warnings.append(f"배당수익률 {div_yield}는 비정상적으로 높음. 확인 필요")
    except:
        pass

    # 10. Peer 테이블 정확성 (JYP v1 사고 재발 방지)
    #     _peer_snapshot.json이 있으면 analysis.peers의 시총/PER/PBR을 그 값과 교차 대조
    peer_path = os.path.join(data_dir, "_peer_snapshot.json")
    if os.path.exists(peer_path):
        try:
            with open(peer_path, 'r', encoding='utf-8') as f:
                peer_snap = json.load(f)
            peers_json = data.get("peers", [])
            # "본 종목"(하이라이트) 제외하고 비교
            for p in peers_json:
                if p.get("highlight"):
                    continue
                pname = p.get("name", "")
                snap = None
                for snap_name, snap_data in peer_snap.items():
                    # 메타데이터 키(_collected_at 등)는 dict 가 아니다. 여기서 걸러내지 않으면
                    # 아래에서 snap.get(...) 이 AttributeError 를 내고, 그 예외가 바깥 except 에
                    # 잡혀 **Peer 검증 전체가 조용히 건너뛰어진다** (v5.5 방어 추가).
                    if not isinstance(snap_data, dict):
                        continue
                    if snap_name.lower().split()[0] in pname.lower() or pname.lower().split()[0] in snap_name.lower():
                        snap = snap_data
                        break
                if not snap:
                    warnings.append(f"Peer '{pname}'이 _peer_snapshot.json에 없음. 실시간 조회 필요")
                    continue
                # 시총 비교 (KR=억원 / US=$B, 각 시장 리포트가 쓰는 단위 그대로)
                json_mc = parse_market_cap(p.get("market_cap"))
                try:
                    if json_mc is None:
                        raise ValueError("market_cap 파싱 불가")
                    snap_mc = snap.get("market_cap_uk", 0)
                    if snap_mc > 0:
                        ratio = json_mc / snap_mc
                        if ratio < 0.7 or ratio > 1.3:
                            errors.append(
                                f"Peer '{pname}' 시총 불일치! JSON={json_mc:,.0f}억 vs KIS snapshot={snap_mc:,}억 "
                                f"(차이 {abs(ratio-1)*100:.0f}%). 추정치 사용 의심 — JYP v1 재발 경고"
                            )
                except (ValueError, TypeError):
                    pass
                # PER 비교
                json_per_str = str(p.get("per", "")).replace("x", "").replace("X", "").strip()
                if "적자" in json_per_str:
                    if snap.get("per", 0) >= 0:
                        warnings.append(f"Peer '{pname}' JSON은 '적자'인데 KIS PER={snap['per']} (양수). 확인 필요")
                else:
                    try:
                        json_per = float(json_per_str.split()[-1] if json_per_str else 0)
                        snap_per = snap.get("per", 0)
                        if snap_per != 0 and abs(json_per - snap_per) / abs(snap_per) > 0.1:
                            warnings.append(
                                f"Peer '{pname}' PER 불일치: JSON={json_per} vs KIS={snap_per} "
                                f"(차이 {abs(json_per - snap_per)/abs(snap_per)*100:.0f}%)"
                            )
                    except (ValueError, TypeError):
                        pass
        except Exception as e:
            warnings.append(f"_peer_snapshot.json 파싱 실패: {type(e).__name__}: {e} - Peer 정확성 검증 건너뜀")
    else:
        warnings.append("_peer_snapshot.json 없음. STEP 2.3(Peer KIS 실시간 조회)을 건너뛴 것으로 의심 - JYP v1 재발 위험")

    # 11. 역사 밴드 정확성 (연말 주가 추정 사고 재발 방지)
    band_path = os.path.join(data_dir, "_per_band.json")
    if os.path.exists(band_path):
        try:
            with open(band_path, 'r', encoding='utf-8') as f:
                band = json.load(f)
            # current_per는 KIS 원본과 일치해야 함
            band_cur_per = band.get("current_per", 0)
            json_per = price.get("per", 0)
            if band_cur_per > 0 and json_per > 0:
                if abs(band_cur_per - json_per) / json_per > 0.05:
                    warnings.append(
                        f"_per_band.json current_per={band_cur_per} vs JSON price.per={json_per} "
                        f"불일치. 둘 중 하나가 stale"
                    )
            # PER 시계열이 최소 3개는 있어야 밴드로서 의미 있음
            per_n = len(band.get("per_series", []))
            if per_n < 3:
                warnings.append(f"_per_band.json PER 시계열 {per_n}개 - 최소 3년은 필요. FDR 조회 실패 의심")
        except Exception as e:
            warnings.append(f"_per_band.json 파싱 실패: {type(e).__name__}: {e}")
    else:
        warnings.append("_per_band.json 없음. STEP 1.7(FDR 5년 연말 종가)을 건너뛴 것으로 의심 - 역사 밴드 추정 위험")

    # 결과 출력
    if errors:
        print("[ERROR] 심각한 오류 발견:")
        for e in errors:
            print(f"   [ERROR] {e}")
        print("   → 리포트 생성을 중단합니다. 데이터를 확인하세요.")
        sys.exit(1)

    if warnings:
        print(f"[WARN]  품질 경고 {len(warnings)}건:")
        for w in warnings:
            print(f"   [WARN]  {w}")
        print("   → 리포트는 생성하지만, 위 항목을 개선하면 품질이 올라갑니다.\n")
    else:
        print("[OK] 품질 검증 통과\n")

    # v3: 단일 상세 PDF (요약/대시보드 폐기)
    generate_detailed_report(data, output_dir)

    print(f'\n{"="*50}')
    print(f'  완료! output/{name}/report_{name}_상세.pdf')
    if warnings:
        print(f'  [WARN]  품질 경고 {len(warnings)}건 -위 경고 확인 권장')
    print(f'{"="*50}\n')


if __name__ == "__main__":
    main()
