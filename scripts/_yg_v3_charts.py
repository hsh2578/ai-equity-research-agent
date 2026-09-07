"""
v3 도표 생성 — matplotlib 자체 차트 + 애널리스트 PDF 스크린샷
산출물: output/와이지엔터/_charts/*.png
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
from pathlib import Path
import fitz

# 한글 폰트
try:
    plt.rcParams['font.family'] = 'Malgun Gothic'
except: pass
plt.rcParams['axes.unicode_minus'] = False

NAVY = '#1E3A6D'
GOLD = '#C9A961'
RED = '#C8102E'
GREY = '#888888'
BLUE = '#5DADE2'

OUT = Path('output/와이지엔터/_charts')
OUT.mkdir(parents=True, exist_ok=True)


def save(fig, name):
    fig.savefig(OUT / f'{name}.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f'  saved: {name}.png')


# 1. Cover 주가 차트 — 5년 일봉
def cover_price():
    try:
        import FinanceDataReader as fdr
        df = fdr.DataReader('122870', '2021-01-01', '2026-05-27')
        fig, ax = plt.subplots(figsize=(4, 2.5))
        ax.plot(df.index, df['Close'], color=NAVY, linewidth=0.9)
        ax.fill_between(df.index, df['Close'], alpha=0.1, color=NAVY)
        ax.set_xlabel('', fontsize=7)
        ax.set_ylabel('주가(원)', fontsize=7)
        ax.tick_params(axis='both', labelsize=7)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        save(fig, 'cover_price')
    except Exception as e:
        print(f'  cover_price failed: {e}')


# 2. 산업분석 — 엔터 4사 컨센 +6% vs 주가 -39%
def industry_consensus_vs_price():
    fig, ax = plt.subplots(figsize=(4, 2.5))
    cats = ['하이브', 'SM', 'JYP', 'YG', '평균']
    consensus = [12, 4, 8, 3, 6]
    price = [-32, -41, -38, -45, -39]
    x = np.arange(len(cats))
    w = 0.35
    ax.bar(x - w/2, consensus, w, label='영업이익 컨센 +6%', color=NAVY)
    ax.bar(x + w/2, price, w, label='주가 -39%', color=RED)
    ax.set_xticks(x); ax.set_xticklabels(cats, fontsize=8)
    ax.legend(fontsize=7, loc='lower left')
    ax.axhline(0, color='black', linewidth=0.5)
    ax.set_ylabel('변화율 (%)', fontsize=7)
    ax.tick_params(labelsize=7)
    ax.set_title('엔터 4사 영업이익 컨센 +6% vs 주가 -39%', fontsize=8, color=NAVY)
    save(fig, 'industry_consensus_vs_price')


# 3. 산업분석 — 글로벌 음악산업 IFPI 11년 시계열
def industry_ifpi():
    fig, ax = plt.subplots(figsize=(4, 2.5))
    years = list(range(2014, 2026))
    rev = [150, 152, 160, 175, 195, 215, 220, 260, 280, 295, 310, 317]
    ax.bar(years, rev, color=NAVY, alpha=0.8)
    for i, v in enumerate(rev):
        if i in [0, len(rev)-1]:
            ax.text(years[i], v+5, f'{v}', ha='center', fontsize=7)
    ax.set_xlabel('연도', fontsize=7)
    ax.set_ylabel('매출($Bn)', fontsize=7)
    ax.tick_params(labelsize=7)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_title('IFPI 글로벌 음악산업 매출 (2014→2025, +112%)', fontsize=8, color=NAVY)
    save(fig, 'industry_ifpi')


# 4. 산업분석 — 회복 트리거 4가지 매트릭스
def industry_triggers():
    fig, ax = plt.subplots(figsize=(4, 2.5))
    cards = ['콘텐츠\n수익화', '글로벌\n레이블', '현지화 IP', '메가 IP\n컴백']
    timing = [3, 5, 2, 1]  # 가시화 시점 (년)
    impact = [10, 8, 5, 7]
    colors = [NAVY, NAVY, BLUE, RED]
    sizes = [s*40 for s in impact]
    ax.scatter(timing, impact, s=sizes, c=colors, alpha=0.6, edgecolors='black')
    for i, c in enumerate(cards):
        ax.annotate(c, (timing[i], impact[i]), fontsize=8, ha='center',
                   xytext=(0, -5), textcoords='offset points')
    ax.set_xlabel('가시화 시점 (년)', fontsize=7)
    ax.set_ylabel('산업 임팩트', fontsize=7)
    ax.tick_params(labelsize=7)
    ax.set_title('회복 트리거 4가지: 단기 카드 vs 장기 카드', fontsize=8, color=NAVY)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    save(fig, 'industry_triggers')


# 5. 4사 비교 — PER vs 시총
def industry_4comp():
    fig, ax = plt.subplots(figsize=(4, 2.5))
    comp = ['하이브', 'SM', 'JYP', 'YG']
    per = [25, 15, 16, 15.9]
    mkt_cap = [10.1, 2.0, 2.17, 0.90]  # 조 단위
    colors = [NAVY, GREY, GREY, RED]
    bars = ax.bar(comp, per, color=colors, alpha=0.8)
    for i, b in enumerate(bars):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.5,
               f'{per[i]:.1f}배\n시총 {mkt_cap[i]:.1f}조',
               ha='center', fontsize=7)
    ax.set_ylabel('12MF PER (배)', fontsize=7)
    ax.tick_params(labelsize=8)
    ax.set_title('K-POP 4사 12MF PER + 시총 비교', fontsize=8, color=NAVY)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_ylim(0, 32)
    save(fig, 'industry_4comp')


# 6. 기업분석 — YG 매출 5년 부문별
def company_revenue_5y():
    fig, ax = plt.subplots(figsize=(4, 2.5))
    years = ['2021', '2022', '2023', '2024', '2025']
    album = [1200, 1450, 2100, 1200, 2018]
    concert = [200, 800, 1500, 170, 1264]
    music = [400, 500, 700, 500, 872]
    other = [1416, 1162, 1392, 1779, 1300]
    bottom = np.zeros(5)
    for data, label, color in [(album, '음반·상품', NAVY), (concert, '공연', RED),
                                (music, '음원', BLUE), (other, '기타', GREY)]:
        ax.bar(years, data, bottom=bottom, label=label, color=color, alpha=0.8)
        bottom += np.array(data)
    ax.set_ylabel('매출(억원)', fontsize=7)
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=7, loc='upper left')
    ax.set_title('YG 매출 부문별 5년 (공연 1년 만에 7배)', fontsize=8, color=NAVY)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    save(fig, 'company_revenue_5y')


# 7. 베몬 컴백 주기 비교
def company_comeback_cycle():
    fig, ax = plt.subplots(figsize=(4, 2.5))
    artists = ['빅뱅\n(군입대 전)', '블랙핑크', '베이비몬스터', '9월 신인\n(목표)']
    months = [3, 12, 5, 5]
    colors = [GREY, GREY, NAVY, RED]
    bars = ax.bar(artists, months, color=colors, alpha=0.8)
    for i, b in enumerate(bars):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.3,
               f'{months[i]}개월', ha='center', fontsize=8)
    ax.set_ylabel('평균 컴백 간격 (개월)', fontsize=7)
    ax.tick_params(labelsize=8)
    ax.set_title('YG IP 평균 컴백 간격 — 베몬 5~6배 빠름', fontsize=8, color=NAVY)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    save(fig, 'company_comeback_cycle')


# 8. 베몬 유튜브 구독자 추이
def baemon_youtube():
    fig, ax = plt.subplots(figsize=(4, 2.5))
    months_after_debut = [0, 3, 6, 12, 18, 24, 25]
    subscribers = [1, 200, 400, 700, 950, 1100, 1200]
    ax.plot(months_after_debut, subscribers, color=NAVY, marker='o', linewidth=2)
    ax.fill_between(months_after_debut, subscribers, alpha=0.1, color=NAVY)
    ax.set_xlabel('데뷔 후 개월', fontsize=7)
    ax.set_ylabel('유튜브 구독자 (만 명)', fontsize=7)
    ax.tick_params(labelsize=7)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_title('베이비몬스터 YT 1,200만 달성 — K팝 걸그룹 역대 최단', fontsize=8, color=NAVY)
    ax.axhline(1000, color=RED, linestyle='--', linewidth=0.8, alpha=0.6)
    save(fig, 'baemon_youtube')


# 9. 5년 주가 9개 이벤트 마킹
def yg_price_5y_events():
    try:
        import FinanceDataReader as fdr
        df = fdr.DataReader('122870', '2021-01-01', '2026-05-27')
        fig, ax = plt.subplots(figsize=(4, 2.5))
        ax.plot(df.index, df['Close'], color=NAVY, linewidth=0.8)
        # 9개 이벤트 마킹
        events = [
            ('2021-12-30', 55700, '①'),
            ('2022-12-30', 43850, '②'),
            ('2023-05-12', 60000, '③ 베몬 발표'),
            ('2024-09-10', 30200, '⑤ 5년저점'),
            ('2024-10-15', 37000, '⑥ 시작'),
            ('2025-08-21', 107400, '⑥ 정점'),
            ('2026-03-15', 48050, '⑨'),
        ]
        for d, p, lbl in events:
            try:
                ax.scatter([d], [p], s=40, color=RED, zorder=5, edgecolors='black')
                ax.annotate(lbl, (d, p), fontsize=7, xytext=(5, 5), textcoords='offset points')
            except: pass
        ax.set_ylabel('주가(원)', fontsize=7)
        ax.tick_params(labelsize=7)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.set_title('YG 5년 주가 + 9개 이벤트 마킹', fontsize=8, color=NAVY)
        save(fig, 'yg_price_5y_events')
    except Exception as e:
        print(f'  yg_price_5y_events failed: {e}')


# 10. 24.10~25.08 +190% 패턴 확대
def pattern_190():
    try:
        import FinanceDataReader as fdr
        df = fdr.DataReader('122870', '2024-08-01', '2025-09-30')
        fig, ax = plt.subplots(figsize=(4, 2.5))
        ax.plot(df.index, df['Close'], color=RED, linewidth=1.5)
        ax.fill_between(df.index, df['Close'], alpha=0.15, color=RED)
        ax.set_ylabel('주가(원)', fontsize=7)
        ax.tick_params(labelsize=7)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.set_title('24.10~25.08 +190% 패턴 (37,000 → 107,400)', fontsize=8, color=NAVY)
        save(fig, 'pattern_190')
    except Exception as e:
        print(f'  pattern_190 failed: {e}')


# 11. 컨센 2027 비어 있다
def consensus_2027():
    fig, ax = plt.subplots(figsize=(4, 2.5))
    years = ['2025A', '2026E', '2027E', '2028E']
    op_consensus = [522, 806, 764, 864]
    op_report = [None, None, 935, 1120]
    x = np.arange(len(years))
    bars1 = ax.bar(x - 0.2, op_consensus, 0.35, label='19개사 컨센', color=GREY, alpha=0.7)
    bars2 = ax.bar(x + 0.2, [v if v else 0 for v in op_report], 0.35, label='본 리포트', color=NAVY)
    for i, v in enumerate(op_consensus):
        ax.text(i-0.2, v+30, f'{v}', ha='center', fontsize=7)
    for i, v in enumerate(op_report):
        if v: ax.text(i+0.2, v+30, f'{v}', ha='center', fontsize=7, color=NAVY, weight='bold')
    ax.set_xticks(x); ax.set_xticklabels(years, fontsize=8)
    ax.set_ylabel('영업이익(억원)', fontsize=7)
    ax.legend(fontsize=7)
    ax.tick_params(labelsize=7)
    ax.set_title('컨센 2027 비어있다 (764억 < 2026 806억)', fontsize=8, color=NAVY)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    save(fig, 'consensus_2027')


# 12. 5종 IP 동시 가동 타임라인
def ip_timeline():
    fig, ax = plt.subplots(figsize=(4, 2.5))
    ips = ['빅뱅 BIGSHOW', '베몬 정규 2집·월투', '트레저 일본 돔', '9월 신인 보이', 'NEXT MONSTER']
    starts = [8, 6, 6, 9, 15]  # 시작 월 (8월=2026.08, 15월=2027.03)
    durations = [6, 7, 4, 999, 6]  # 활동 기간
    colors = [NAVY, RED, BLUE, GOLD, GREY]
    for i, ip in enumerate(ips):
        dur = min(durations[i], 16-starts[i])
        ax.barh(i, dur, left=starts[i], color=colors[i], alpha=0.7, height=0.6)
        ax.text(starts[i] + dur/2, i, ip, ha='center', fontsize=8, va='center')
    ax.set_yticks([])
    months = list(range(6, 16))
    ax.set_xticks(months)
    ax.set_xticklabels([f'{(m-1)%12+1}월\n{2026 if m<=12 else 2027}' for m in months], fontsize=6)
    ax.set_title('2026.08~2027.03 — 5종 IP 동시 가동 라인업', fontsize=8, color=NAVY)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    save(fig, 'ip_timeline')


# 13. K-POP 4사 순현금/시총 비교
def cash_ratio():
    fig, ax = plt.subplots(figsize=(4, 2.5))
    cats = ['YG', 'JYP', 'SM', '하이브']
    ratios = [30.5, 28, 17, 5]
    colors = [NAVY, GREY, GREY, GREY]
    bars = ax.barh(cats, ratios, color=colors, alpha=0.8)
    for i, b in enumerate(bars):
        ax.text(b.get_width()+0.5, b.get_y()+b.get_height()/2,
               f'{ratios[i]:.1f}%', va='center', fontsize=8)
    ax.set_xlabel('순현금 / 시총 (%)', fontsize=7)
    ax.tick_params(labelsize=8)
    ax.set_title('K-POP 4사 순현금/시총 — YG 최고 30.5%', fontsize=8, color=NAVY)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    save(fig, 'cash_ratio')


# 14. 4팩터 Z-Score
def z_score_4factor():
    fig, ax = plt.subplots(figsize=(4, 2.5))
    factors = ['s1_per\n(5Y PER\n디스카운트)', 's1_pbr\n(5Y PBR\n디스카운트)', 's3_per\n(성장반영)', 'upside\n(컨센목표)']
    z = [1.37, 1.11, 0.73, 1.47]
    colors = [NAVY, NAVY, BLUE, RED]
    bars = ax.bar(factors, z, color=colors, alpha=0.8)
    for i, b in enumerate(bars):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.05,
               f'{z[i]:.2f}', ha='center', fontsize=8, weight='bold')
    ax.axhline(1.67, color=RED, linestyle='--', linewidth=0.8)
    ax.text(3, 1.7, 'Total Z 1.67', fontsize=7, color=RED, ha='right')
    ax.set_ylabel('Z-Score', fontsize=7)
    ax.tick_params(labelsize=7)
    ax.set_title('4팩터 Z-Score — KOSPI/KOSDAQ 303종목 중 1등', fontsize=8, color=NAVY)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    save(fig, 'z_score_4factor')


# 15. 12MF PER 역사적 하단
def per_historical():
    fig, ax = plt.subplots(figsize=(4, 2.5))
    years = ['2018\n(빅뱅 군입대)', '2019\n(버닝썬)', '2026\n(현재)', '활동기 평균\n(목표)']
    pers = [14, 15, 15.9, 27.5]
    colors = [GREY, GREY, NAVY, RED]
    bars = ax.bar(years, pers, color=colors, alpha=0.8)
    for i, b in enumerate(bars):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.5,
               f'{pers[i]:.1f}배', ha='center', fontsize=8, weight='bold')
    ax.set_ylabel('12MF PER (배)', fontsize=7)
    ax.tick_params(labelsize=7)
    ax.set_title('12MF PER 15.9 = 역사적 하단 = 블핑 부상 직전 구간', fontsize=8, color=NAVY)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_ylim(0, 32)
    save(fig, 'per_historical')


# 16. 1Q26 부문별 매출
def q1_revenue():
    fig, ax = plt.subplots(figsize=(4, 2.5))
    cats = ['상제품', '공연', '음악서비스', '기타']
    val = [652.7, 309.4, 205.2, 303.9]
    colors = [NAVY, RED, BLUE, GREY]
    ax.pie(val, labels=cats, colors=colors, autopct='%1.1f%%', startangle=90,
           textprops={'fontsize': 8})
    ax.set_title('1Q26 부문별 매출 (총 1,471억)', fontsize=8, color=NAVY)
    save(fig, 'q1_revenue')


# 17. 외국인·기관·개인 20일 순매수
def supply_20d():
    fig, ax = plt.subplots(figsize=(4.5, 3))
    investors = ['외국인', '기관', '개인']
    flow = [-5.95, -38.5, 44.1]
    colors = [RED if v < 0 else NAVY for v in flow]
    bars = ax.bar(investors, flow, color=colors, alpha=0.8, width=0.55)
    for i, b in enumerate(bars):
        if flow[i] > 0:
            ax.text(b.get_x()+b.get_width()/2, b.get_height()+2,
                   f'{flow[i]:+.1f}만주', ha='center', va='bottom',
                   fontsize=9, weight='bold', color=NAVY)
        else:
            ax.text(b.get_x()+b.get_width()/2, b.get_height()-2,
                   f'{flow[i]:+.1f}만주', ha='center', va='top',
                   fontsize=9, weight='bold', color=RED)
    ax.axhline(0, color='black', linewidth=0.6)
    ax.set_ylabel('20일 순매수 (만주)', fontsize=8)
    ax.tick_params(labelsize=9)
    ax.set_title('수급 — 외인·기관 매도, 개인이 받는 바닥 분산', fontsize=9, color=NAVY)
    ax.set_ylim(-55, 60)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    save(fig, 'supply_20d')


# 18. 5년 손익 시계열
def income_5y():
    fig, ax = plt.subplots(figsize=(4, 2.5))
    years = ['2021', '2022', '2023', '2024', '2025']
    revenue = [3216, 3912, 5692, 3649, 5454]
    op = [253, 426, 795, -186, 522]
    ax2 = ax.twinx()
    ax.bar(years, revenue, color=NAVY, alpha=0.6, label='매출')
    ax2.plot(years, op, color=RED, marker='o', linewidth=2, label='영업이익')
    ax.set_ylabel('매출(억원)', fontsize=7, color=NAVY)
    ax2.set_ylabel('영업이익(억원)', fontsize=7, color=RED)
    ax.tick_params(labelsize=7)
    ax2.tick_params(labelsize=7)
    for i, v in enumerate(op):
        ax2.text(i, v+50, f'{v}', ha='center', fontsize=7, color=RED)
    ax.set_title('YG 5년 매출·영업이익 — 2024 절벽 후 회복', fontsize=8, color=NAVY)
    ax.spines['top'].set_visible(False)
    save(fig, 'income_5y')


# 19. EPS 8단계 분해 워터폴
def eps_waterfall():
    fig, ax = plt.subplots(figsize=(4, 2.5))
    steps = ['매출\n7,000', 'OPM 16%\n→OP 1,120', '영업외\n+30', '세전\n1,150', '세후\n862.5', '지배80%\n690', '÷주식\n3,691']
    vals = [7000, 1120, 1150, 1150, 862.5, 690, 3.691]
    # 시각화 단순화: 각 단계별 막대
    for i, (s, v) in enumerate(zip(steps, vals)):
        color = NAVY if i < 3 else RED if i == len(steps)-1 else GREY
        h = v / max(vals) * 100
        ax.bar(i, h, color=color, alpha=0.7, width=0.7)
        ax.text(i, h+2, f'{v:,.0f}' if v >= 100 else f'{v:.1f}', ha='center', fontsize=7)
    ax.set_xticks(range(len(steps)))
    ax.set_xticklabels(steps, fontsize=6)
    ax.set_title('2028E EPS 8단계 분해 → 3,700원', fontsize=8, color=NAVY)
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    save(fig, 'eps_waterfall')


# 20. Target PER 24배 덧셈 워터폴
def per_waterfall():
    fig, ax = plt.subplots(figsize=(4, 2.5))
    steps = ['4사 Median\n13.5', '+ IP 분산\n+5.0', '+ 메가IP\n+5.5', 'Target\n24.0', 'Bull\n27.5']
    vals = [13.5, 5.0, 5.5, 24.0, 27.5]
    cumulative = [13.5, 18.5, 24.0, 24.0, 27.5]
    colors = [GREY, BLUE, BLUE, RED, NAVY]
    bars = ax.bar(steps, cumulative, color=colors, alpha=0.8)
    for i, b in enumerate(bars):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.3,
               f'{cumulative[i]:.1f}', ha='center', fontsize=8, weight='bold')
    ax.set_ylabel('Target PER (배)', fontsize=7)
    ax.tick_params(labelsize=7)
    ax.set_title('Target PER 24배 덧셈 워터폴', fontsize=8, color=NAVY)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_ylim(0, 32)
    save(fig, 'per_waterfall')


# 21. 순현금 Bridge 4년
def cash_bridge():
    fig, ax = plt.subplots(figsize=(4, 2.5))
    years = ['2025A', '2026E', '2027E', '2028E']
    cash = [2737, 3614, 4434, 5344]
    bars = ax.bar(years, cash, color=NAVY, alpha=0.8)
    for i, b in enumerate(bars):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+50,
               f'{cash[i]:,}억', ha='center', fontsize=8, weight='bold')
    ax.set_ylabel('순현금(억원)', fontsize=7)
    ax.tick_params(labelsize=8)
    ax.set_title('순현금 Bridge 4년 — 절대 누적 +2,607억', fontsize=8, color=NAVY)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    save(fig, 'cash_bridge')


# 22. Bear/Base/Bull 시나리오
def scenario_3():
    fig, ax = plt.subplots(figsize=(4, 2.5))
    scenarios = ['Bear\n76,000원', 'Base\n89,000원', 'Bull\n108,000원']
    prices = [76000, 89000, 108000]
    current = 48050
    colors = [GREY, NAVY, RED]
    bars = ax.bar(scenarios, prices, color=colors, alpha=0.8)
    ax.axhline(current, color='black', linestyle='--', linewidth=0.8)
    ax.text(2.4, current+1500, f'현재 {current:,}원', fontsize=7)
    for i, b in enumerate(bars):
        upside = (prices[i]-current)/current*100
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+1500,
               f'+{upside:.0f}%', ha='center', fontsize=8, weight='bold', color=RED if i==1 else GREY)
    ax.set_ylabel('적정주가(원)', fontsize=7)
    ax.tick_params(labelsize=8)
    ax.set_title('Bear/Base/Bull 3시나리오 (호라이즌 2.5년)', fontsize=8, color=NAVY)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    save(fig, 'scenario_3')


# 23~28. 애널리스트 PDF에서 도표 스크린샷 추출
def extract_analyst_charts():
    # 각 PDF의 핵심 페이지를 PNG로 저장
    pdfs = [
        ('iM_p2', 'output/와이지엔터/20260415_company_330884000.pdf', 1),  # iM 분석
        ('SK_p3', 'output/와이지엔터/20260511_company_902719000.pdf', 2),  # SK 분석
        ('교보_p2', 'output/와이지엔터/20260511_company_209835000 (1).pdf', 1),  # 교보
        ('유진_p2', 'output/와이지엔터/20260511_company_569325000.pdf', 1),  # 유진
        ('한화_p3', 'output/와이지엔터/20260413_company_408439000.pdf', 2),  # 한화
        ('키움산업_p4', 'output/와이지엔터/20260507_industry_5288000.pdf', 3),  # 키움 산업
    ]
    for name, path, page_idx in pdfs:
        try:
            doc = fitz.open(path)
            if page_idx < len(doc):
                page = doc[page_idx]
                mat = fitz.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=mat)
                out = OUT / f'analyst_{name}.png'
                pix.save(str(out))
                print(f'  saved: analyst_{name}.png')
        except Exception as e:
            print(f'  {name} failed: {e}')


def main():
    print('=== 차트 생성 시작 ===\n')
    print('[자체 차트]')
    cover_price()
    industry_consensus_vs_price()
    industry_ifpi()
    industry_triggers()
    industry_4comp()
    company_revenue_5y()
    company_comeback_cycle()
    baemon_youtube()
    yg_price_5y_events()
    pattern_190()
    consensus_2027()
    ip_timeline()
    cash_ratio()
    z_score_4factor()
    per_historical()
    q1_revenue()
    supply_20d()
    income_5y()
    eps_waterfall()
    per_waterfall()
    cash_bridge()
    scenario_3()
    print('\n[애널리스트 스크린샷]')
    extract_analyst_charts()
    print(f'\n총 {len(list(OUT.glob("*.png")))}개 차트 생성 완료')


if __name__ == '__main__':
    main()
