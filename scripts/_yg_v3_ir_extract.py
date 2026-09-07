"""DART/SK증권 96p IR 리포트에서 와이지 아티스트 이미지·표지 추출"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import fitz
from pathlib import Path

OUT = Path('output/와이지엔터/_charts'); OUT.mkdir(parents=True, exist_ok=True)
PDF = 'output/와이지엔터/20260318072925850_0_ko.pdf'

# (출력명, 페이지(0-based), crop (x0,y0,x1,y1))
EXT = [
    # p34: 블랙핑크·빅뱅 바톤터치 (블핑 DEADLINE + 빅뱅 빅쇼 등 이미지 5개)
    ('m_ir_blackpink_bigbang', 33, (0.05, 0.10, 0.95, 0.65)),
    # p36: 블랙핑크 미니3집 DEADLINE 자켓·국립박물관 협업
    ('m_ir_deadline_album', 35, (0.05, 0.05, 0.95, 0.55)),
    # p64: 와이지엔터 30년 내공 표지 + 빅뱅·블핑 비주얼
    ('m_ir_yg_cover', 63, (0.05, 0.05, 0.95, 0.95)),
    # p66: Valuation 페이지
    ('m_ir_yg_valuation', 65, (0.05, 0.10, 0.95, 0.95)),
    # p68: 와이지 아티스트별 음반 판매량 + 콘서트 일정
    ('m_ir_yg_album_concert', 67, (0.05, 0.05, 0.95, 0.55)),
    # p69-70: 4대 기획사 데뷔 아티스트 비교 + 걸그룹 첫 월투 모객
    ('m_ir_4comp_debut', 69, (0.05, 0.05, 0.95, 0.55)),
    # p33: BTS Arirang 360도 개방형 무대 (참고용)
    ('m_ir_bts_arirang', 32, (0.05, 0.30, 0.95, 0.95)),
    # p35: 빅뱅 데이터 (BlackPink DEADLINE 투어 일정)
    ('m_ir_deadline_tour', 34, (0.05, 0.05, 0.95, 0.55)),
    # p37: 빅뱅 G-Dragon Übermensch + 빅뱅 사진
    ('m_ir_gdragon_uber', 36, (0.05, 0.05, 0.95, 0.55)),
]


def extract(name, page_idx, crop):
    try:
        doc = fitz.open(PDF)
        page = doc[page_idx]
        rect = page.rect
        x0 = rect.x0 + (rect.x1-rect.x0)*crop[0]
        y0 = rect.y0 + (rect.y1-rect.y0)*crop[1]
        x1 = rect.x0 + (rect.x1-rect.x0)*crop[2]
        y1 = rect.y0 + (rect.y1-rect.y0)*crop[3]
        clip = fitz.Rect(x0, y0, x1, y1)
        mat = fitz.Matrix(2.5, 2.5)
        pix = page.get_pixmap(matrix=mat, clip=clip)
        out_path = OUT / f'{name}.png'
        pix.save(str(out_path))
        print(f'  saved: {name}.png ({pix.width}x{pix.height}px)')
    except Exception as e:
        print(f'  {name} failed: {e}')


def main():
    print('=== IR 자료(SK증권 96p) 이미지 추출 ===\n')
    for n, p, c in EXT:
        extract(n, p, c)


if __name__ == '__main__':
    main()
