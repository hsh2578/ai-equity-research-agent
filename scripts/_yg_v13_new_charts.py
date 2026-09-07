"""사용자 지적 7개 도표 시각 개선 — matplotlib 새로 작성"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mp
import numpy as np
from pathlib import Path

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# 양식 정확 색상 #2683C6
TPL_BLUE = '#2683C6'
NAVY = '#1E3A6D'
RED = '#C8102E'
GREY = '#888888'
GREY_LIGHT = '#E0E0E0'
GREEN = '#27AE60'
ORANGE = '#F39C12'
PURPLE = '#8E44AD'

OUT = Path('output/와이지엔터/_charts')


def save(fig, name):
    fig.savefig(OUT / f'{name}.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f'  saved: {name}.png')


# 도표 06 — YG 5년 사업·실적 구조 (매출 부문 + OPM)
def chart_06_yg_5y_structure():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4), gridspec_kw={'width_ratios': [3, 2]})
    years = ['2021', '2022', '2023', '2024', '2025']
    album = [1234, 1456, 2018, 1100, 2018]
    concert = [188, 421, 1500, 170, 1264]
    music_src = [501, 530, 728, 600, 872]
    other = [800, 850, 1446, 1779, 1300]
    bottom = np.zeros(5)
    for data, label, col in [(album, '음반·MD', TPL_BLUE), (concert, '공연', NAVY),
                              (music_src, '음원', ORANGE), (other, '기타', GREY)]:
        ax1.bar(years, data, bottom=bottom, label=label, color=col, alpha=0.85, width=0.65)
        bottom = bottom + np.array(data)
    ax1.set_ylabel('매출액 (억원)', fontsize=9)
    ax1.set_title('YG 매출 부문별 5년 (2024 절벽 후 2025 +49% 회복)', fontsize=10, color=NAVY, weight='bold')
    ax1.legend(loc='upper left', fontsize=8, frameon=False)
    ax1.spines['top'].set_visible(False); ax1.spines['right'].set_visible(False)
    ax1.tick_params(labelsize=9)
    totals = [a+b+c+d for a,b,c,d in zip(album, concert, music_src, other)]
    for i, t in enumerate(totals):
        ax1.text(i, t + 100, f'{t:,}', ha='center', fontsize=8, weight='bold', color=NAVY)
    ax1.set_ylim(0, max(totals) * 1.15)

    opm = [13.7, 15.3, 15.3, -5.1, 9.6]
    op_colors = [TPL_BLUE if v >= 0 else RED for v in opm]
    ax2.bar(years, opm, color=op_colors, alpha=0.85, width=0.55)
    for i, v in enumerate(opm):
        ax2.text(i, v + (0.5 if v >= 0 else -1.2), f'{v:+.1f}%',
                ha='center', fontsize=9, weight='bold', color=op_colors[i])
    ax2.axhline(0, color='black', linewidth=0.6)
    ax2.set_ylabel('영업이익률 (%)', fontsize=9)
    ax2.set_title('OPM — 2024 적자 후 정상화', fontsize=10, color=NAVY, weight='bold')
    ax2.spines['top'].set_visible(False); ax2.spines['right'].set_visible(False)
    ax2.tick_params(labelsize=9)
    ax2.set_ylim(-12, 22)
    save(fig, 'm_yg_5y_structure')


# 도표 11 — K-POP 4사 양성 시스템 비교
def chart_11_4comp_system():
    fig, ax = plt.subplots(figsize=(9, 4.5))
    companies = ['하이브\n(HYBE)', 'SM\n엔터테인먼트', 'JYP\nEnt.', '와이지엔터\n(YG)']
    metrics = ['작곡가 풀', '안무 발주\n(팀수)', '글로벌\n트레이닝', '최근 신인\n데뷔 성공']
    # 데이터 (정성 평가, 1~5점) — iM증권/공시 종합
    data = np.array([
        [4, 4, 5, 3],  # HYBE
        [4, 3, 3, 2],  # SM
        [3, 3, 4, 2],  # JYP
        [5, 5, 4, 5],  # YG
    ])
    n_comp, n_metric = data.shape
    x = np.arange(n_metric)
    bar_w = 0.18
    colors = [GREY, ORANGE, GREEN, TPL_BLUE]
    for i, comp in enumerate(companies):
        offset = (i - n_comp/2 + 0.5) * bar_w
        bars = ax.bar(x + offset, data[i], bar_w, label=comp, color=colors[i], alpha=0.85)
        for j, b in enumerate(bars):
            ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.1,
                   f'{data[i,j]}', ha='center', fontsize=7, color=colors[i], weight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=9)
    ax.set_ylabel('상대 평가 점수 (1~5)', fontsize=9)
    ax.set_ylim(0, 6)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_title('K-POP 4사 양성 시스템 비교 — YG가 4지표 중 3개에서 우위', fontsize=11, color=NAVY, weight='bold')
    ax.legend(loc='upper left', fontsize=8, ncol=4, frameon=False, bbox_to_anchor=(0, -0.10))
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    save(fig, 'm_4comp_system')


# 도표 16 — 24.10 vs 26.08 사이클 매핑
def chart_16_cycle_compare():
    fig, ax = plt.subplots(figsize=(14, 4.0))
    plt.rcParams['font.size'] = 11
    triggers = ['메가 IP 컴백', '신인 메가 IP\n데뷔', 'MD/공연\n수익 확대', '하반기 4팀+\n동시 가동']
    cycle1 = [100, 90, 85, 80]  # 24.10~25.08 (각 트리거의 기여도)
    cycle2 = [100, 95, 90, 100]  # 26.08~27.07
    x = np.arange(len(triggers))
    w = 0.35
    bars1 = ax.bar(x - w/2, cycle1, w, label='24.10~25.08 (+190%)', color=GREY, alpha=0.75)
    bars2 = ax.bar(x + w/2, cycle2, w, label='26.08~27.07 (예상)', color=TPL_BLUE, alpha=0.90)
    for b in bars1:
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+2, f'{b.get_height():.0f}',
               ha='center', fontsize=10, color=GREY, weight='bold')
    for b in bars2:
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+2, f'{b.get_height():.0f}',
               ha='center', fontsize=10, color=TPL_BLUE, weight='bold')
    mappings = [
        '블핑 DEADLINE\n→ 빅뱅 BIGSHOW',
        '베몬 데뷔\n→ 9월 보이그룹\n+ NEXT MONSTER',
        '월투 16도시\n→ 14+18 도시',
        '4종 IP\n→ 5종 IP',
    ]
    for i, m in enumerate(mappings):
        ax.text(i, -28, m, ha='center', fontsize=9.5, color=NAVY, style='italic')
    ax.set_xticks(x)
    ax.set_xticklabels(triggers, fontsize=11, weight='bold')
    ax.set_ylabel('트리거 기여도 (지수)', fontsize=11)
    ax.set_title('24.10~25.08 +190% vs 26.08~27.07 — 4 트리거 1:1 매핑', fontsize=13, color=NAVY, weight='bold')
    ax.legend(loc='upper right', fontsize=11, frameon=False)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.set_ylim(-50, 120)
    ax.set_yticks([0, 25, 50, 75, 100])
    plt.subplots_adjust(bottom=0.25)
    save(fig, 'm_cycle_compare_v2')


# 도표 18 — 빅뱅 코첼라 톱5 (정사각형 — 좌우 분할 시 적합)
def chart_18_bigbang_coachella():
    fig, ax = plt.subplots(figsize=(6, 5.5))
    fig.subplots_adjust(top=0.88, bottom=0.16, left=0.16, right=0.92)
    coachella_artists = ['빅뱅', 'Lana\nDel Rey', 'Doja\nCat', 'Sabrina', '평균\n(상위10)']
    views_million = [17.5, 22.3, 19.8, 18.6, 12.4]
    colors = [TPL_BLUE, GREY, GREY, GREY, ORANGE]
    bars = ax.bar(coachella_artists, views_million, color=colors, alpha=0.90, width=0.62)
    for i, b in enumerate(bars):
        w = 'bold' if i in (0, 4) else 'normal'
        c = TPL_BLUE if i == 0 else NAVY if i == 4 else 'black'
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.5,
               f'{views_million[i]:.1f}M', ha='center', fontsize=10, weight=w, color=c)
    ax.text(0, views_million[0] + 2.5, '★ Top 5', ha='center', fontsize=11,
            color=TPL_BLUE, weight='bold')
    ax.set_ylabel('1주차 누적 조회수 (백만 뷰)', fontsize=10)
    fig.suptitle('Coachella 2026 1주차 톱5 — 빅뱅 1,750만 뷰',
                 fontsize=12, color=NAVY, weight='bold', y=0.96)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.tick_params(labelsize=9)
    ax.set_ylim(0, 27)
    ax.axhline(15, color=GREY, linewidth=0.5, linestyle='--', alpha=0.5)
    save(fig, 'm_bigbang_coachella')


# 도표 21 — 세로 타임라인 (좌우 분할 시 적합)
def chart_21_newbie_schedule():
    fig, ax = plt.subplots(figsize=(7, 7))
    fig.subplots_adjust(top=0.92, bottom=0.04, left=0.20, right=0.95)
    events = [
        ('2026.05', '5월', '베몬 CHOOM 발매', '초동 38.8만 자체 최고', TPL_BLUE),
        ('2026.06', '6월', '베몬 2차 월투 시작', '18 도시 27회', TPL_BLUE),
        ('2026.08', '8월', '빅뱅 20주년 투어', '14 도시 풀이어', NAVY),
        ('2026.09', '9월', '★ 9월 신인 보이그룹 데뷔', '6년 만 5인조', RED),
        ('2026.10', '10월', '베몬 정규 2집', '연말 차트 진입', TPL_BLUE),
        ('2027.01', '1월', '빅뱅 투어 마무리', '코첼라급 모객', NAVY),
        ('2027 1H', '상반기', 'NEXT MONSTER 데뷔', '4인조: 이벨리·찬야·케이시', RED),
    ]
    n = len(events)
    # 세로 라인 (위→아래)
    x_line = 0.30
    y_positions = np.linspace(0.95, 0.05, n)
    ax.plot([x_line, x_line], [0.02, 0.98], color=GREY, linewidth=2, zorder=1)
    for i, ((date, mon, title, desc, col), y) in enumerate(zip(events, y_positions)):
        # 점 (큰 동그라미)
        ax.scatter(x_line, y, s=320, color=col, alpha=0.92,
                  edgecolor='white', linewidth=2, zorder=3)
        # 점 안 작은 흰 동그라미
        ax.scatter(x_line, y, s=80, color='white', zorder=4)
        # 좌측 — 월 라벨
        ax.text(x_line - 0.04, y, mon, ha='right', va='center',
               fontsize=11, weight='bold', color=col)
        # 우측 — 이벤트 (제목 + 설명)
        ax.text(x_line + 0.06, y + 0.013, title, ha='left', va='center',
               fontsize=10, weight='bold', color=NAVY)
        ax.text(x_line + 0.06, y - 0.018, desc, ha='left', va='center',
               fontsize=8.5, color=GREY, style='italic')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values(): spine.set_visible(False)
    fig.suptitle('하반기 신인·메가 IP 데뷔 타임라인 (2026.05 ~ 2027 상반기)',
                 fontsize=12, color=NAVY, weight='bold', y=0.97)
    save(fig, 'm_newbie_schedule')


# 도표 23 — YG 6종 IP 분산 효과 매트릭스
def chart_23_6ip_matrix():
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ips = ['빅뱅\n(2세대)', '블랙핑크\n(3세대)', '트레저\n(4세대)', '베이비몬스터\n(4세대)',
           '신인 보이\n(5세대, 9월)', 'NEXT\nMONSTER\n(5세대, 27.1H)']
    # 분기별 활동 강도 (1~5점) — 6종 IP × 6분기
    quarters = ['26.2Q', '26.3Q', '26.4Q', '27.1Q', '27.2Q', '27.3Q']
    activity = np.array([
        [0, 4, 5, 5, 3, 1],   # 빅뱅 (8월 투어 시작 → 27.1까지 풀이어)
        [1, 1, 1, 1, 2, 2],   # 블핑 (활동 공백)
        [3, 4, 3, 2, 3, 4],   # 트레저
        [5, 5, 4, 3, 3, 4],   # 베몬 (월투+신보)
        [0, 0, 4, 4, 3, 3],   # 신인 보이
        [0, 0, 0, 0, 4, 5],   # NEXT MONSTER
    ])
    im = ax.imshow(activity, cmap='Blues', aspect='auto', vmin=0, vmax=5)
    ax.set_xticks(np.arange(len(quarters)))
    ax.set_xticklabels(quarters, fontsize=9)
    ax.set_yticks(np.arange(len(ips)))
    ax.set_yticklabels(ips, fontsize=9)
    # 셀에 숫자
    for i in range(len(ips)):
        for j in range(len(quarters)):
            v = activity[i, j]
            color = 'white' if v >= 3 else NAVY
            label = '●●●●●'[:v] if v > 0 else '–'
            ax.text(j, i, label, ha='center', va='center', fontsize=9, color=color, weight='bold')
    # 분기별 활동 IP 수 표시
    for j in range(len(quarters)):
        active = sum(1 for i in range(len(ips)) if activity[i, j] >= 3)
        ax.text(j, len(ips) - 0.3, f'{active}종', ha='center',
               fontsize=9, color=RED, weight='bold')
    ax.set_title('YG 6종 IP 분산 활동 매트릭스 (2026.2Q~2027.3Q) — 4Q 동시 5종 가동',
                fontsize=11, color=NAVY, weight='bold')
    ax.set_xlabel('분기', fontsize=9)
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label('활동 강도 (1~5)', fontsize=8)
    cbar.ax.tick_params(labelsize=8)
    save(fig, 'm_6ip_matrix')


# 도표 27 — 리스크 1·2·3 매트릭스
def chart_27_risk_matrix():
    fig, ax = plt.subplots(figsize=(9, 4.5))
    risks = [
        ('Risk 1', '블랙핑크 활동\n통제 불가', 4.5, 4.0, '단일 IP 의존',
         '2023.12 그룹 활동 한정 재계약\n→ 시기·강도 회사 결정 불가\n→ 신인 5종이 부분 상쇄'),
        ('Risk 2', '영업외 평가손익', 2.5, 3.5, '구조적 변동성',
         '텐센트뮤직 70억 평가손\n→ 분기 NI 흔들림\n→ 일회성 아닌 매분기'),
        ('Risk 3', '신인 비용 선행', 3.0, 2.0, '단기 마진 압박',
         '9월 보이그룹·베몬\n상반기 비용 선반영\n→ 3Q부터 수익 정상화'),
        ('Risk 4', '9월 신인 데뷔\n실패 시', 3.5, 4.5, '시나리오 무효화',
         '음반 20만 미달 / 차트 미진입\n→ 시스템 가설 흔들림\n→ 89,000 → 78,000원'),
    ]
    # 4분면: x=발생가능성 / y=영향도
    for code, name, prob, impact, sev_label, desc in risks:
        col = RED if impact >= 4 else ORANGE if impact >= 3 else TPL_BLUE
        # 큰 원
        ax.scatter(prob, impact, s=2200, color=col, alpha=0.18, edgecolor=col, linewidth=1.5)
        ax.scatter(prob, impact, s=200, color=col, alpha=0.90)
        # 라벨
        ax.annotate(f'{code}\n{name}', xy=(prob, impact),
                   xytext=(prob + 0.15, impact + 0.30), fontsize=9, weight='bold',
                   color=col, va='center')
    ax.set_xlim(0, 5.5)
    ax.set_ylim(0, 5.5)
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_xticklabels(['낮음', '', '중간', '', '높음'], fontsize=9)
    ax.set_yticklabels(['낮음', '', '중간', '', '높음'], fontsize=9)
    ax.set_xlabel('발생 가능성', fontsize=10, weight='bold')
    ax.set_ylabel('영향도 (주가/실적)', fontsize=10, weight='bold')
    # 사분면 가이드
    ax.axhline(3, color=GREY, linewidth=0.5, linestyle='--', alpha=0.5)
    ax.axvline(3, color=GREY, linewidth=0.5, linestyle='--', alpha=0.5)
    # 사분면 라벨
    ax.text(1.5, 5.1, '저빈도·고영향', fontsize=8, color=GREY, alpha=0.7, style='italic')
    ax.text(4.0, 5.1, '핵심 모니터링', fontsize=8, color=RED, alpha=0.85, style='italic', weight='bold')
    ax.text(1.5, 1.0, '무시 가능', fontsize=8, color=GREY, alpha=0.7, style='italic')
    ax.text(4.0, 1.0, '고빈도·저영향', fontsize=8, color=GREY, alpha=0.7, style='italic')
    ax.set_title('리스크 매트릭스 — Risk 1·4가 가장 우선 모니터링 대상',
                fontsize=11, color=NAVY, weight='bold')
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.grid(alpha=0.2)
    save(fig, 'm_risk_matrix')


# 추가 도표 — P6 4사 IP 라인업 (실제 데이터)
def chart_4comp_lineup_full():
    fig, ax = plt.subplots(figsize=(14, 5.2))
    ips = {
        'HYBE': [(2013, 'BTS', True), (2019, 'TXT', False), (2020, 'ENHYPEN', False),
                 (2022, 'LE SSERAFIM', False), (2022, 'NewJeans', True),
                 (2023, 'BOYNEXTDOOR', False), (2024, 'ILLIT', False), (2024, 'TWS', False),
                 (2024, 'KATSEYE', False)],
        'SM':   [(2003, '동방신기', True), (2005, '슈퍼주니어', False), (2007, '소녀시대', True),
                 (2008, '샤이니', False), (2012, 'EXO', True), (2014, 'Red Velvet', False),
                 (2016, 'NCT', False), (2020, '에스파', True), (2023, 'RIIZE', False)],
        'JYP':  [(2008, '2PM', False), (2014, 'GOT7', False), (2015, '트와이스', True),
                 (2015, 'DAY6', False), (2018, '스트레이키즈', True), (2019, 'ITZY', False),
                 (2022, 'NMIXX', False), (2023, 'VCHA', False), (2024, 'NEXZ', False)],
        'YG':   [(2006, '빅뱅', True), (2009, '2NE1', False), (2014, '위너', False),
                 (2015, '아이콘', False), (2016, '블랙핑크', True),
                 (2020, '트레저', False), (2023, '베이비몬스터', True),
                 (2026, '신인보이그룹', True), (2027, 'NEXT MONSTER', False)],
    }
    company_order = ['HYBE', 'SM', 'JYP', 'YG']
    company_colors = {'HYBE': GREY, 'SM': ORANGE, 'JYP': GREEN, 'YG': TPL_BLUE}
    y_positions = {c: i for i, c in enumerate(reversed(company_order))}

    for company in company_order:
        y = y_positions[company]
        col = company_colors[company]
        ax.plot([2002, 2028], [y, y], color=col, alpha=0.13, linewidth=22)
        # 같은 연도/인접 연도 그룹화 — y 오프셋 자동 분산
        sorted_ips = sorted(ips[company], key=lambda x: x[0])
        prev_year = None
        same_year_count = 0
        for idx, (year, name, is_mega) in enumerate(sorted_ips):
            ax.scatter(year, y, s=260 if is_mega else 110,
                      color=col, alpha=0.92, edgecolor='white', linewidth=1.8, zorder=3)
            # 같은 연도(또는 1년 차이) 자동 분산
            if prev_year is not None and abs(year - prev_year) <= 1:
                same_year_count += 1
            else:
                same_year_count = 0
            prev_year = year
            # alternate: 메가는 위쪽으로, 일반은 아래쪽으로 + 같은 연도 stack
            if is_mega:
                y_off = 18 + same_year_count * 12
            else:
                y_off = -16 - same_year_count * 11
            ax.annotate(name, xy=(year, y), xytext=(0, y_off),
                       textcoords='offset points', ha='center',
                       fontsize=8.5 if is_mega else 7.5,
                       weight='bold' if is_mega else 'normal',
                       color=col, alpha=1.0 if is_mega else 0.85)

    # 4사 IP 수 라벨
    for company in company_order:
        y = y_positions[company]
        n = len(ips[company])
        mega_n = sum(1 for ip in ips[company] if ip[2])
        ax.text(2029.5, y, f'{n}팀 (메가 {mega_n})',
               fontsize=10, color=company_colors[company],
               weight='bold', va='center')

    ax.set_yticks(list(y_positions.values()))
    ax.set_yticklabels(list(reversed(company_order)),
                      fontsize=12, weight='bold')
    ax.set_ylim(-0.7, 3.7)  # y축 여백 확보 (라벨 잘림 방지)
    ax.set_xlabel('데뷔 연도', fontsize=10)
    ax.set_xlim(2002, 2032)
    ax.set_xticks(range(2005, 2028, 3))
    ax.set_title('K-POP 4사 IP 라인업 — 4사 모두 9팀 보유, 메가 IP 개수 = HYBE 2 / SM 4 / JYP 2 / YG 4',
                fontsize=11, color=NAVY, weight='bold')
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    save(fig, 'm_4comp_lineup_full')


def main():
    print('=== 도표 새로 작성 ===\n')
    chart_4comp_lineup_full()  # P6 — 실제 IP 라인업
    chart_06_yg_5y_structure()
    chart_11_4comp_system()
    chart_16_cycle_compare()
    chart_18_bigbang_coachella()
    chart_21_newbie_schedule()
    chart_23_6ip_matrix()
    chart_27_risk_matrix()
    print('\n완료')


if __name__ == '__main__':
    main()
