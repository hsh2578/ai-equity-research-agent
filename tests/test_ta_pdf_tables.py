# -*- coding: utf-8 -*-
"""ta_pdf_tables -- fitz 로 괘선 표 PDF 를 만들어 pdfplumber 추출이 행·열을 유지하는지 본다 (네트워크 없음).

실행: python tests/test_ta_pdf_tables.py
"""
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ta_pdf_tables as t  # noqa: E402

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_passed = 0
_failed = []


def eq(got, want, label):
    global _passed
    if got == want:
        _passed += 1
    else:
        _failed.append((label, want, got))


def make_pdf(path):
    """3행 x 4열 괘선 표 하나 + 표 밖 문장 한 줄."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((40, 40), 'Financial table test', fontsize=10)
    rows = [['', '2024', '2025', '2026E'], ['Revenue', '6,570', '6,929', '7,407'], ['EPS', '10,948', '1,445', '50,315']]
    x0, y0, cw, rh = 40, 70, 90, 20
    for r in range(len(rows) + 1):
        page.draw_line((x0, y0 + r * rh), (x0 + cw * 4, y0 + r * rh))
    for c in range(5):
        page.draw_line((x0 + c * cw, y0), (x0 + c * cw, y0 + rh * len(rows)))
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            page.insert_text((x0 + c * cw + 4, y0 + r * rh + 14), val, fontsize=9)
    doc.save(path)
    doc.close()


with tempfile.TemporaryDirectory() as d:
    pdf = os.path.join(d, 't.pdf')
    make_pdf(pdf)
    found = t.extract_tables(pdf)
    eq(len(found), 1, '괘선 표 1개 검출')
    page, rows = found[0]
    eq(page, 1, '페이지 번호')
    eq(len(rows), 3, '3행')
    eq(max(len(r) for r in rows), 4, '4열')
    eq(t._cell(rows[2][3]), '50,315', 'EPS 2026E 셀 제자리')
    eq(t._cell(rows[1][1]), '6,570', 'Revenue 2024 셀 제자리')
    n, err = t.write_tables_md(pdf)
    eq((n, err), (1, None), 'write_tables_md -> (1, None)')
    md = open(os.path.join(d, 't.tables.md'), encoding='utf-8').read()
    eq('| EPS | 10,948 | 1,445 | 50,315 |' in md, True, 'markdown 행')
    eq(t._is_useful([['a', 'b']]), False, '2행 이하는 표가 아니다')
    eq(t._is_useful([['', ''], ['', ''], ['x', '']]), False, '빈 칸 투성이는 표가 아니다')
    n2, err2 = t.write_tables_md(os.path.join(d, 'none.pdf'))
    eq(n2 == 0 and err2 is not None, True, '없는 파일은 (0, 사유)')

print('=' * 66)
for label, want, got in _failed:
    print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  ta_pdf_tables 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
