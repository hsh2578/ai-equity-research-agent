# -*- coding: utf-8 -*-
"""ta_pdf_tables -- PDF 의 괘선 표를 행·열 그대로 Markdown 으로 뽑는다 (v5.26, 2026-09-21).

왜: fitz(get_text) 는 표를 한 셀 한 줄로 풀어 열이 섞인다(한화 신세계 2Q 리뷰 재무표 실측).
증권사 실적·밸류 표가 정독의 핵심인데 그걸 눈으로 다시 맞추느라 시간이 들고 오독이 났다.
docling(표 구조 모델, torch) 대신 pdfplumber(텍스트층 괘선 표) 를 쓴다 -- 한화 5p 1.4초, 교보 50p 10.7초,
분기표 12열 x 8행이 제자리(실측). 병합 셀이 많은 IR 덱·사이드바 요약표는 못 살린다(그건 .txt 로).

사용:
  python scripts/ta_pdf_tables.py {pdf}                 # 옆에 {pdf 이름}.tables.md 저장
  python scripts/ta_pdf_tables.py --dir data/{종목}/ta/reports/company   # 폴더의 모든 pdf
수집기(ta_collect_reports / ta_company_ir / ta_kind_ir) 는 저장 직후 write_tables_md() 를 부른다.
실패는 예외를 삼키지 않고 (0, 사유) 로 돌려준다 -- 조용한 실패 금지.
"""
from __future__ import annotations

import io
import os
import re
import sys

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

MIN_ROWS = 3
MIN_COLS = 2


def _cell(c) -> str:
    return re.sub(r'\s+', ' ', str(c)).strip().replace('|', '/') if c is not None else ''


def _is_useful(rows) -> bool:
    if len(rows) < MIN_ROWS:
        return False
    ncol = max(len(r) for r in rows)
    if ncol < MIN_COLS:
        return False
    filled = sum(1 for r in rows for c in r if _cell(c))
    return filled >= 0.3 * len(rows) * ncol  # 빈 칸 투성이(text 전략 오탐) 제외


def table_to_md(rows) -> str:
    ncol = max(len(r) for r in rows)
    norm = [[_cell(c) for c in r] + [''] * (ncol - len(r)) for r in rows]
    out = ['| ' + ' | '.join(norm[0]) + ' |', '|' + '---|' * ncol]
    out += ['| ' + ' | '.join(r) + ' |' for r in norm[1:]]
    return '\n'.join(out)


def extract_tables(pdf_path: str):
    """-> list[(page_no, rows)]. pdfplumber 기본(괘선) 전략만 -- text 전략은 사이드바를 표로 오인한다(실측)."""
    import pdfplumber
    found = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            for tb in page.extract_tables() or []:
                if tb and _is_useful(tb):
                    found.append((i, tb))
    return found


def tables_md(pdf_path: str) -> tuple[str, int]:
    found = extract_tables(pdf_path)
    parts = [f'# {os.path.basename(pdf_path)} -- 괘선 표 {len(found)}개 (pdfplumber, 셀 병합 표는 .txt 로)']
    for page, rows in found:
        parts.append(f'\n## p{page} ({len(rows)}행 x {max(len(r) for r in rows)}열)\n\n' + table_to_md(rows))
    return '\n'.join(parts) + '\n', len(found)


def write_tables_md(pdf_path: str, out_path: str | None = None) -> tuple[int, str | None]:
    """-> (표 개수, 실패 사유 또는 None). 표가 0개여도 파일은 쓴다(무엇을 봤는지 남긴다)."""
    out_path = out_path or (os.path.splitext(pdf_path)[0] + '.tables.md')
    try:
        md, n = tables_md(pdf_path)
    except Exception as e:  # noqa: BLE001 -- 사유를 돌려준다
        return 0, f'{type(e).__name__}: {e}'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(md)
    return n, None


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf', nargs='?')
    ap.add_argument('--dir', help='폴더의 모든 .pdf')
    a = ap.parse_args(argv)
    targets = []
    if a.dir:
        targets = [os.path.join(a.dir, f) for f in sorted(os.listdir(a.dir)) if f.lower().endswith('.pdf')]
    elif a.pdf:
        targets = [a.pdf]
    if not targets:
        ap.error('pdf 또는 --dir')
    bad = 0
    for p in targets:
        n, err = write_tables_md(p)
        if err:
            bad += 1
            print(f'  [FAIL] {os.path.basename(p)}: {err}')
        else:
            print(f'  [ok  ] {os.path.basename(p)}: 표 {n}개 -> {os.path.basename(os.path.splitext(p)[0])}.tables.md')
    print(f'[ta_pdf_tables] {len(targets)}편, 실패 {bad}')
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
