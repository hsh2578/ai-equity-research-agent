"""워드 본문 편집용 docx의 도표 메모 → PNG 정밀 1:1 매칭 (v2)"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from pathlib import Path

DOC = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\18-1_와이지엔터테인먼트_본문_편집용.docx')
CHARTS = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\_charts')

# 정밀 1:1 매칭 — (도표 메모의 고유 키워드, PNG 파일명)
EXACT = [
    ('IFPI 글로벌 음악산업 매출 11년', 'industry_ifpi'),
    ('엔터 4사 영업이익 컨센 +6% vs 주가 -39% 듀얼', 'industry_consensus_vs_price'),
    ('업종별 연초 대비 수익률 비교', 'm03_sector_return'),
    ('엔터 4사 매출 성장률 추이', 'm04_revenue_growth'),
    ('글로벌 빅3 레이블 (UMG·SME·WMG) 10년', 'm05_global_big3'),
    ('BTS vs 테일러 스위프트 월드투어 매출 구조', 'm06_bts_taylor'),
    ('슈퍼팬 비율 비교', 'm07_superfan'),
    ('4개 회복 트리거 산업 구조 카드(중장기 2) vs 단기 카드(2)', 'industry_triggers'),
    ('4사 비즈니스 모델 비교표', 'industry_4comp'),
    ('28년 데뷔 IP 타임라인 (지누션 1997', 'm10_28y_timeline'),
    ('매출 부문별 5년 시계열 (음반·공연·음원·기타 stacked', 'company_revenue_5y'),
    ('베이비몬스터 유튜브 구독자 추이 (2024.04 데뷔', 'baemon_youtube'),
    ('와이지 IP별 평균 컴백 간격 비교', 'company_comeback_cycle'),
    ('베이비몬스터 일본 팝업스토어 + MD 라인업 (iM증권', 'analyst_iM_p2'),
    ('5년 일봉 주가 + 9개 이벤트 마킹', 'm30_5y_events'),
    ('2024.10~2025.08 +190% 상승 구간 확대', 'pattern_190'),
    ('2026 하반기 5종 IP 동시 가동 일정표', 'ip_timeline'),
    ('24.10~25.08 vs 26.08~27.07 사이클 비교 매트릭스', 'm35_cycle_compare'),
    ('빅뱅 BIGSHOW: REBORN 14개 도시 투어 일정표', 'm38_bigbang_tour'),
    ('K-POP 메가 IP 객단가 비교 (빅뱅 vs BTS vs', 'm39_objectdanga'),
    ('빅뱅 투어 ATP × 모객 매트릭스', 'm40_bigbang_atp'),
    ('빅뱅 코첼라 4월 12·19일 무대 1주차 영상 1,750만뷰', 'm41_coachella'),
    ('빅뱅 10주년 투어 모객 비교', 'm42_bigbang_10y'),
    ('19개 증권사 컨센 2026E vs 2027E 영업이익 비교', 'consensus_2027'),
    ('K-POP 4사 세대별 IP 보유 매트릭스', 'm45_4comp_gen_ip'),
    ('보이그룹 파이프라인 6년 공백 시각화', 'm46_boygroup_6y'),
    ('YG 5년 매출 변동폭 비교 (2024 -36% 절벽', 'income_5y'),
    ('K-POP 4사 순현금/시총 비율 비교', 'cash_ratio'),
    ('4팩터 Z-Score 막대 그래프 (s1_per 1.37', 'z_score_4factor'),
    ('YG 5년 12MF PER 추이 + 역사적 하단 마킹', 'per_historical'),
    ('블랙핑크 그룹 vs 개별 활동 시기 도식', 'm58_blackpink_solo'),
    ('텐센트뮤직 지분 평가손익 5년 시계열', 'm60_tencent_pl'),
    ('9월 보이그룹 데뷔 결과별 적정주가 시나리오', 'm62_sept_scenario'),
    ('1Q26 부문별 매출 분해 (상제품 652.7', 'q1_revenue'),
    ('영업이익 +103.9% vs 지배 NI 큰 폭', 'm64_op_vs_ni'),
    ('외국인 지분율 12개월 시계열', 'm65_foreign_ratio'),
    ('외국인·기관·개인 20일 순매수 막대', 'supply_20d'),
    ('5년 매출·영업이익·OPM 시계열 막대', 'income_5y'),
    ('ROE 듀폰 분해 5년 시계열', 'm69_roe_dupont'),
    ('2026E ROE 10.8% 회복 경로', 'm70_roe_recovery'),
    ('19개 증권사 Implied Target PER', 'm71_consensus_dist'),
    ('매출 부문별 5년 시계열 + 2028E 추정', 'm72_revenue_2028e'),
    ('YG 5년 발표기준 OPM 시계열 + 2028E 16%', 'm73_opm_2028e'),
    ('2028E EPS 8단계 분해 워터폴', 'eps_waterfall'),
    ('Target PER 24배 덧셈 워터폴', 'per_waterfall'),
    ('4사 Implied Target PER 비교 (하이브 22배', 'm76_4comp_implied_per'),
    ('본 리포트 vs 19개 증권사 컨센 격차 분해', 'm77_report_vs_consensus'),
    ('보수 가정 5가지 + 적정주가 민감도 매트릭스', 'm79_5_assumptions'),
    ('Bear/Base/Bull 3시나리오 적정주가 매트릭스', 'scenario_3'),
    ('순현금 Bridge 4년 시계열 (2025A 2,737', 'cash_bridge'),
    ('IP × 분기 매출 시간표 매트릭스', 'm83_ip_quarterly'),
    ("'양성 시스템 검증 매트릭스'", 'm86_system_validation'),
    ('가격 단계적 상승 사다리', 'm88_price_ladder'),
    ('BUY 결론 인포그래픽', 'm89_buy_conclusion'),
]


def find_match(memo):
    for kw, png in EXACT:
        if kw in memo:
            p = CHARTS / f'{png}.png'
            if p.exists():
                return p, kw
    return None, None


def short(memo):
    t = memo.replace('📊 [도표 제안]', '').strip()
    t = re.sub(r'^(★\s*)?(핵심\s*도표\s*권장|추가\s*권장)\s*:\s*', '', t)
    t = re.sub(r'\s*\[(스크린샷|신규).*?\].*$', '', t)
    t = re.sub(r'\s*—\s*이미 적용됨\s*$', '', t)
    return t.strip()


def main():
    doc = Document(str(DOC))
    print(f'문서 로드: {len(doc.paragraphs)}개 단락')

    memos = [(i, p) for i, p in enumerate(doc.paragraphs) if '📊 [도표 제안]' in p.text]
    print(f'도표 제안: {len(memos)}개')

    inserted = 0
    text_only = 0
    text_only_list = []
    from collections import Counter
    used_png = []

    for idx, p in memos:
        png, kw = find_match(p.text)
        cap = short(p.text)
        if png:
            for r in list(p.runs): r._r.getparent().remove(r._r)
            r1 = p.add_run(); r1.text = f'[도표] {cap}\n'
            r1.font.size = Pt(8); r1.font.bold = True
            r1.font.color.rgb = RGBColor(0x1E, 0x3A, 0x6D); r1.font.italic = True
            r2 = p.add_run()
            r2.add_picture(str(png), width=Inches(5.5))
            inserted += 1
            used_png.append(png.stem)
        else:
            for r in list(p.runs): r._r.getparent().remove(r._r)
            r = p.add_run(); r.text = f'[도표 권장] {cap}'
            r.font.size = Pt(8); r.font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA); r.font.italic = True
            text_only += 1
            text_only_list.append(cap[:70])

    print(f'\n=== 결과 ===')
    print(f'★ PNG 이미지 삽입: {inserted}개')
    print(f'★ 텍스트 메모만 유지: {text_only}개')
    print(f'\n사용된 PNG 분포:')
    for png, cnt in Counter(used_png).most_common():
        marker = ' [중복!]' if cnt > 1 else ''
        print(f'  {png}: {cnt}회{marker}')

    print(f'\n=== 텍스트 메모만 유지 ({text_only}개) ===')
    for t in text_only_list:
        print(f'  - {t}')

    doc.save(str(DOC))
    print(f'\n저장: {DOC.stat().st_size/1024:.1f} KB')


if __name__ == '__main__':
    main()
