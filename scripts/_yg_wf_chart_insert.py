"""
워드 도표 메모 → PNG 이미지 정확 1:1 매칭 (강제 매칭 제거)
- 1:1 매칭 검증된 도표만 이미지화
- 나머지는 도표 메모 텍스트 그대로 유지
"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from pathlib import Path

DOC_PATH = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\18-1_와이지엔터테인먼트_본문_편집용.docx')
CHARTS = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\_charts')

# 정확 1:1 매칭 (메모의 고유 키워드 → PNG)
# 키워드는 메모를 다른 메모와 구분할 수 있는 정확한 식별자
EXACT_MATCH = [
    ('IFPI 글로벌 음악산업 매출 11년 시계열', 'industry_ifpi'),
    ('엔터 4사 영업이익 컨센 +6% vs 주가 -39% 듀얼', 'industry_consensus_vs_price'),
    ('4개 회복 트리거 산업 구조 카드(중장기 2) vs 단기 카드(2) 분류', 'industry_triggers'),
    ('4사 비즈니스 모델 비교표', 'industry_4comp'),
    ('매출 부문별 5년 시계열 (음반·공연·음원·기타 stacked bar', 'company_revenue_5y'),
    ('베이비몬스터 유튜브 구독자 추이 (2024.04 데뷔 → 2026.05 1,200만', 'baemon_youtube'),
    ('와이지 IP별 평균 컴백 간격 비교 (베이비몬스터 5개월', 'company_comeback_cycle'),
    ('베이비몬스터 일본 팝업스토어 + MD 라인업 (iM증권 차용)', 'analyst_iM_p2'),
    ('2024.10~2025.08 +190% 상승 구간 확대 차트', 'pattern_190'),
    ('2026 하반기 5종 IP 동시 가동 일정표 (빅뱅 20주년 8월~2027.01', 'ip_timeline'),
    ('19개 증권사 컨센 2026E vs 2027E 영업이익 비교', 'consensus_2027'),
    ('YG 5년 매출 변동폭 비교 (2024 -36% 절벽', 'income_5y'),
    ('K-POP 4사 순현금/시총 비율 비교 (와이지 30%', 'cash_ratio'),
    ('4팩터 Z-Score 막대 그래프 (s1_per 1.37', 'z_score_4factor'),
    ('YG 5년 12MF PER 추이 + 역사적 하단 마킹', 'per_historical'),
    ('1Q26 부문별 매출 분해 (상제품 652.7·공연 309.4', 'q1_revenue'),
    ('외국인·기관·개인 20일 순매수 막대 그래프', 'supply_20d'),
    ('5년 매출·영업이익·OPM 시계열 막대 그래프', 'income_5y'),
    ('2028E EPS 8단계 분해 워터폴', 'eps_waterfall'),
    ('Target PER 24배 덧셈 워터폴', 'per_waterfall'),
    ('Bear/Base/Bull 3시나리오 적정주가 매트릭스', 'scenario_3'),
    ('순현금 Bridge 4년 시계열 (2025A 2,737', 'cash_bridge'),
]


def find_match(memo_text):
    for keyword, png_name in EXACT_MATCH:
        if keyword in memo_text:
            png_path = CHARTS / f'{png_name}.png'
            if png_path.exists():
                return png_path, keyword
    return None, None


def short_caption(memo_text):
    text = memo_text.replace('📊 [도표 제안]', '').strip()
    text = re.sub(r'^(★\s*)?(핵심\s*도표\s*권장|추가\s*권장)\s*:\s*', '', text)
    text = re.sub(r'\s*\[(스크린샷|신규).*?\].*$', '', text)
    text = re.sub(r'\s*—\s*이미 적용됨\s*$', '', text)
    return text.strip()


def main():
    doc = Document(str(DOC_PATH))
    print(f'문서 로드: {len(doc.paragraphs)}개 단락')

    chart_paras = [(i, p) for i, p in enumerate(doc.paragraphs) if '📊 [도표 제안]' in p.text]
    print(f'도표 제안 단락: {len(chart_paras)}개')

    inserted = 0
    text_only = 0
    text_only_list = []
    used_png = []
    for idx, p in chart_paras:
        memo_text = p.text
        png_path, kw = find_match(memo_text)
        caption = short_caption(memo_text)

        if png_path:
            # 텍스트 제거 + 이미지 삽입
            for r in list(p.runs):
                r._r.getparent().remove(r._r)
            run = p.add_run()
            run.text = f'[도표] {caption}\n'
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(0x1E, 0x3A, 0x6D)
            run.font.italic = True
            run.font.bold = True
            run2 = p.add_run()
            run2.add_picture(str(png_path), width=Inches(5.5))
            inserted += 1
            used_png.append(png_path.stem)
        else:
            # 텍스트 메모 그대로 유지 (단, 회색·이탤릭으로 다듬기)
            for r in list(p.runs):
                r._r.getparent().remove(r._r)
            run = p.add_run()
            run.text = f'[도표 미생성 — 작성 필요] {caption}'
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)
            run.font.italic = True
            text_only += 1
            text_only_list.append(caption[:60])

    print(f'\n=== 결과 ===')
    print(f'★ PNG 이미지 삽입: {inserted}개')
    print(f'★ 텍스트 메모 유지 (PNG 미생성): {text_only}개')
    print()
    print('사용된 PNG 분포 (중복 확인):')
    from collections import Counter
    for png, cnt in Counter(used_png).most_common():
        print(f'  {png}: {cnt}회')

    print()
    print(f'=== 도표 PNG 미생성 (작성 필요) {text_only}개 ===')
    for cap in text_only_list[:30]:
        print(f'  - {cap}')
    if len(text_only_list) > 30:
        print(f'  ... (총 {len(text_only_list)}개)')

    doc.save(str(DOC_PATH))
    print(f'\n저장 크기: {DOC_PATH.stat().st_size/1024:.1f} KB')


if __name__ == '__main__':
    main()
