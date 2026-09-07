"""애널리스트 PDF에서 도표 영역만 크롭해 스크린샷 추출"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import fitz
from pathlib import Path

OUT = Path('output/와이지엔터/_charts')
OUT.mkdir(parents=True, exist_ok=True)

# (출력 파일명, PDF 경로, 페이지 0-based, 자르기 비율 x0/y0/x1/y1)
EXT = [
    ('m39_objectdanga', 'output/와이지엔터/20260415_company_330884000.pdf', 2, (0.05, 0.55, 0.95, 0.95)),
    ('m42_bigbang_10y', 'output/와이지엔터/20260415_company_330884000.pdf', 3, (0.05, 0.05, 0.95, 0.55)),
    ('m64_op_vs_ni', 'output/와이지엔터/20260511_company_405800000.pdf', 1, (0.05, 0.15, 0.95, 0.65)),
    ('m65_foreign_ratio', 'output/와이지엔터/20260511_company_902719000.pdf', 1, (0.05, 0.45, 0.95, 0.95)),
    ('m71_consensus_dist', 'output/와이지엔터/20260511_company_209835000 (1).pdf', 3, (0.05, 0.05, 0.95, 0.55)),
    ('m77_report_vs_consensus', 'output/와이지엔터/20260511_company_209835000 (1).pdf', 2, (0.05, 0.15, 0.95, 0.75)),
    ('m60_tencent_pl', 'output/와이지엔터/20260511_company_569325000.pdf', 2, (0.05, 0.15, 0.95, 0.75)),
    ('m70_roe_recovery', 'output/와이지엔터/20260413_company_408439000.pdf', 3, (0.05, 0.15, 0.95, 0.95)),
]


def extract(name, pdf_path, page_idx, crop):
    try:
        doc = fitz.open(pdf_path)
        if page_idx >= len(doc):
            print(f'  {name}: 페이지 초과 (PDF {len(doc)}p)')
            return
        page = doc[page_idx]
        rect = page.rect
        x0 = rect.x0 + (rect.x1-rect.x0) * crop[0]
        y0 = rect.y0 + (rect.y1-rect.y0) * crop[1]
        x1 = rect.x0 + (rect.x1-rect.x0) * crop[2]
        y1 = rect.y0 + (rect.y1-rect.y0) * crop[3]
        clip = fitz.Rect(x0, y0, x1, y1)
        mat = fitz.Matrix(2.5, 2.5)
        pix = page.get_pixmap(matrix=mat, clip=clip)
        out_path = OUT / f'{name}.png'
        pix.save(str(out_path))
        print(f'  saved: {name}.png ({pix.width}x{pix.height}px)')
    except Exception as e:
        print(f'  {name} failed: {e}')


def main():
    print('=== 애널리스트 PDF 도표 크롭 추출 ===\n')
    for name, pdf, p, crop in EXT:
        extract(name, pdf, p, crop)
    print('\n완료')


if __name__ == '__main__':
    main()
