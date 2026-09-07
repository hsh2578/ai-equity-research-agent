"""애널리스트 PDF에서 추가 핵심 도표 페이지 크롭 추출"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import fitz
from pathlib import Path

OUT = Path('output/와이지엔터/_charts'); OUT.mkdir(parents=True, exist_ok=True)

# (출력명, PDF, 페이지(0-based), crop 비율 (x0,y0,x1,y1))
EXT = [
    # 미래에셋 (20260319) — 분기별 매출·영업이익률 + PER Band
    ('m_mirae_quarterly', 'output/와이지엔터/20260319_company_466854000.pdf', 1, (0.05, 0.15, 0.95, 0.65)),
    ('m_mirae_album_schedule', 'output/와이지엔터/20260319_company_466854000.pdf', 2, (0.05, 0.15, 0.95, 0.75)),
    ('m_mirae_per_pbr_band', 'output/와이지엔터/20260319_company_466854000.pdf', 4, (0.05, 0.05, 0.95, 0.55)),
    # iM증권 (20260415) — 지역별 매출 + 빅뱅 코첼라
    ('m_im_region_revenue', 'output/와이지엔터/20260415_company_330884000.pdf', 2, (0.05, 0.05, 0.95, 0.55)),
    ('m_im_bigbang_coachella', 'output/와이지엔터/20260415_company_330884000.pdf', 3, (0.05, 0.05, 0.95, 0.65)),
    # SK증권 (20260511) — 아티스트 컴백 일정
    ('m_sk_artist_schedule', 'output/와이지엔터/20260511_company_902719000.pdf', 3, (0.05, 0.05, 0.95, 0.55)),
    ('m_sk_per_band', 'output/와이지엔터/20260511_company_902719000.pdf', 4, (0.05, 0.05, 0.95, 0.55)),
    # 유진투자증권 (20260511) — 1Q26 Review 도표 풍부
    ('m_eugene_q1', 'output/와이지엔터/20260511_company_569325000.pdf', 1, (0.05, 0.05, 0.95, 0.65)),
    # 하나증권 (20260511) — 도표
    ('m_hana_table', 'output/와이지엔터/20260511_company_521572000.pdf', 2, (0.05, 0.15, 0.95, 0.85)),
    # 임수진 신한? (20260511_405800000) — 표지 + 표
    ('m_shinhan_summary', 'output/와이지엔터/20260511_company_405800000.pdf', 0, (0.05, 0.40, 0.95, 0.95)),
]


def extract(name, pdf_path, page_idx, crop):
    try:
        doc = fitz.open(pdf_path)
        if page_idx >= len(doc):
            print(f'  {name}: 페이지 초과')
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
    print('=== 애널리스트 PDF 추가 도표 추출 ===\n')
    for n, p, pg, c in EXT:
        extract(n, p, pg, c)
    print('\n완료')


if __name__ == '__main__':
    main()
