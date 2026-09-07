"""신규 핵심 도표 17개 일괄 생성 (필요한 것만)"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from matplotlib.patches import Patch, Rectangle

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
NAVY = '#1E3A6D'; RED = '#C8102E'; BLUE = '#5DADE2'; GREY = '#888888'; GOLD = '#C9A961'
OUT = Path('output/와이지엔터/_charts'); OUT.mkdir(parents=True, exist_ok=True)


def save(fig, name):
    fig.savefig(OUT / f'{name}.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); print(f'  saved: {name}.png')


def m30():
    try:
        import FinanceDataReader as fdr
        import pandas as pd
        df = fdr.DataReader('122870', '2021-01-01', '2026-05-27')
        fig, ax = plt.subplots(figsize=(7, 3))
        ax.plot(df.index, df['Close'], color=NAVY, linewidth=0.7)
        events = [
            ('2021-12-30', 55700, '①21말 정점'),
            ('2022-12-30', 43850, '②TME 평가손'),
            ('2023-05-12', 60000, '③베몬 발표'),
            ('2023-12-29', 50900, '④BORN PINK'),
            ('2024-09-10', 30200, '⑤절대저점'),
            ('2024-10-15', 37000, '⑥24.10 시작'),
            ('2025-08-21', 107400, '⑥25.8 정점'),
            ('2025-12-30', 69400, '⑦25말'),
            ('2026-03-31', 48050, '⑧1Q 무산'),
        ]
        for d, p, lbl in events:
            ax.scatter([pd.Timestamp(d)], [p], s=40, color=RED, zorder=5, edgecolors='black', linewidths=0.5)
            ax.annotate(lbl, (pd.Timestamp(d), p), fontsize=6, xytext=(3, 3), textcoords='offset points')
        ax.set_ylabel('주가(원)', fontsize=8); ax.tick_params(labelsize=8)
        ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
        ax.set_title('YG 5년 일봉 + 9개 이벤트 마킹 (FDR 실측)', fontsize=10, color=NAVY)
        save(fig, 'm30_5y_events')
    except Exception as e:
        print(f'  m30 failed: {e}')


def m35():
    fig, ax = plt.subplots(figsize=(6, 3))
    cats = ['시작 시총(억)', '동시 가동 IP', '메가 IP 종류', '도달 시총(억)']
    prev = [6916, 2, 1, 20074]; this = [8981, 5, 2, 17500]
    x = np.arange(len(cats)); w = 0.35
    ax.bar(x - w/2, prev, w, label='24.10~25.08', color=GREY, alpha=0.8)
    ax.bar(x + w/2, this, w, label='26.08~27.07', color=NAVY)
    for i in range(len(cats)):
        ax.text(i-w/2, prev[i]+max(prev)*0.01, f'{prev[i]:,}' if prev[i]>50 else f'{prev[i]}', ha='center', fontsize=7)
        ax.text(i+w/2, this[i]+max(this)*0.01, f'{this[i]:,}' if this[i]>50 else f'{this[i]}', ha='center', fontsize=7, weight='bold', color=NAVY)
    ax.set_xticks(x); ax.set_xticklabels(cats, fontsize=8)
    ax.set_yscale('symlog'); ax.tick_params(labelsize=7)
    ax.legend(fontsize=7); ax.set_title('24.10~25.08 vs 26.08~27.07 사이클 비교', fontsize=9, color=NAVY)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    save(fig, 'm35_cycle_compare')


def m38():
    fig, ax = plt.subplots(figsize=(7, 3))
    cities = ['서울','도쿄','오사카','홍콩','방콕','KL','싱가포르','자카르타','시드니','멜번','LA','뉴욕','런던','파리']
    months = [8, 8, 9, 9, 10, 10, 11, 11, 11, 12, 12, 1, 1, 1]
    regions = ['아시아']*8 + ['오세아니아']*2 + ['북미']*2 + ['유럽']*2
    rc = {'아시아': NAVY, '오세아니아': BLUE, '북미': RED, '유럽': GOLD}
    colors = [rc[r] for r in regions]
    y = np.arange(len(cities))
    ax.barh(y, [1]*len(cities), left=months, color=colors, alpha=0.8, height=0.7)
    ax.set_yticks(y); ax.set_yticklabels(cities, fontsize=8)
    ax.set_xticks([8,9,10,11,12,13]); ax.set_xticklabels(['26.8','9','10','11','12','27.1'], fontsize=8)
    ax.invert_yaxis(); ax.set_xlim(7.5, 14)
    ax.set_title('빅뱅 BIGSHOW: REBORN 14개 도시 풀이어 (2026.08~2027.01)', fontsize=9, color=NAVY)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    legend = [Patch(color=rc[k], label=k) for k in rc]
    ax.legend(handles=legend, fontsize=7, ncol=4)
    save(fig, 'm38_bigbang_tour')


def m40():
    fig, ax = plt.subplots(figsize=(5.5, 3))
    sc = ['Bear\n60만·ATP 20만','Base\n70만·ATP 25만','Bull\n80만·ATP 28만']
    rev = [840, 1000, 1260]
    colors = [GREY, NAVY, RED]
    bars = ax.bar(sc, rev, color=colors, alpha=0.9)
    for i, b in enumerate(bars):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+30, f'{rev[i]:,}억', ha='center', fontsize=11, weight='bold', color=colors[i])
    ax.axhline(806, color='black', linestyle='--', linewidth=0.8, alpha=0.6)
    ax.text(2.4, 850, '컨센 806억', fontsize=7, ha='right')
    ax.set_ylabel('빅뱅 투어 매출 (억원)', fontsize=8); ax.tick_params(labelsize=8)
    ax.set_title('빅뱅 ATP × 모객 매트릭스 — Base 1,000억', fontsize=9, color=NAVY)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    save(fig, 'm40_bigbang_atp')


def m41():
    fig, ax = plt.subplots(figsize=(5.5, 3))
    p = ['Lady Gaga','Travis Scott','Charli XCX','Megan T.S.','빅뱅']
    v = [3200, 2800, 2400, 1900, 1750]
    colors = [GREY]*4 + [RED]
    bars = ax.barh(p, v, color=colors, alpha=0.9)
    for i, b in enumerate(bars):
        wt = 'bold' if i == 4 else 'normal'
        ax.text(b.get_width()+50, b.get_y()+b.get_height()/2, f'{v[i]:,}만뷰', va='center', fontsize=9, weight=wt)
    ax.set_xlabel('1주차 코첼라 영상 뷰 (만)', fontsize=8); ax.tick_params(labelsize=8)
    ax.invert_yaxis(); ax.set_xlim(0, 3500)
    ax.set_title('빅뱅 코첼라 1주차 1,750만뷰 — 글로벌 톱5', fontsize=9, color=NAVY)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    save(fig, 'm41_coachella')


def m45():
    fig, ax = plt.subplots(figsize=(6, 3))
    companies = ['YG','하이브','SM','JYP']
    gens = ['2세대','3세대','4세대','5세대']
    data = np.array([[1,1,2,2],[0,1,2,1],[0,0,3,1],[0,1,2,1]])
    im = ax.imshow(data, cmap='Blues', aspect='auto')
    ax.set_xticks(range(4)); ax.set_xticklabels(gens, fontsize=9)
    ax.set_yticks(range(4)); ax.set_yticklabels(companies, fontsize=10, weight='bold')
    for i in range(4):
        for j in range(4):
            if data[i,j] > 0:
                c = 'white' if data[i,j] >= 2 else 'black'
                ax.text(j, i, f'{data[i,j]}팀', ha='center', va='center', fontsize=10, color=c, weight='bold')
    ax.set_title('K-POP 4사 세대별 IP 보유 — YG 분산 최대', fontsize=9, color=NAVY)
    save(fig, 'm45_4comp_gen_ip')


def m46():
    fig, ax = plt.subplots(figsize=(7, 2.5))
    events = [(2006,'빅뱅'),(2014,'위너'),(2015,'아이콘'),(2020,'트레저'),(2026,'신인 5인조')]
    years = [e[0] for e in events]
    labels = [e[1] for e in events]
    ax.scatter(years, [0]*len(years), s=[200,150,150,200,300], color=[NAVY,GREY,GREY,NAVY,RED],
               zorder=5, edgecolors='black', linewidths=1)
    for i,(y,l) in enumerate(zip(years, labels)):
        ax.text(y, 0.4 if i%2==0 else -0.4, l, ha='center', fontsize=9, weight='bold' if i==4 else 'normal',
               color=RED if i==4 else 'black')
    ax.annotate('', xy=(2026,-0.15), xytext=(2020,-0.15), arrowprops=dict(arrowstyle='<->', color=RED, linewidth=2))
    ax.text(2023, -0.3, '6년 공백', fontsize=10, color=RED, weight='bold', ha='center')
    ax.axhline(0, color='black', linewidth=0.5)
    ax.set_xlim(2004, 2028); ax.set_ylim(-0.8, 0.8); ax.set_yticks([])
    ax.set_xticks([2006,2014,2015,2020,2026]); ax.tick_params(labelsize=8)
    for s in ['top','right','left']: ax.spines[s].set_visible(False)
    ax.set_title('YG 보이그룹 — 트레저 2020 → 6년 공백 → 2026.09 신인', fontsize=9, color=NAVY)
    save(fig, 'm46_boygroup_6y')


def m58():
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.barh(0, 8, left=2016, color=NAVY, height=0.6, alpha=0.8)
    ax.text((2016+2024)/2, 0, '그룹 활동 (YG 통제)', ha='center', va='center', fontsize=9, color='white', weight='bold')
    solo = [('지수\nBLISSOO',2025,1),('로제\nTBL',2024,2),('제니\nODD ATELIER',2024,2),('리사\nLLOUD',2024,2)]
    for i,(name,start,dur) in enumerate(solo):
        y = -(i+1)
        ax.barh(y, dur, left=start, color=RED, alpha=0.7, height=0.5)
        ax.text(start+dur/2, y, name, ha='center', va='center', fontsize=8, color='white', weight='bold')
    ax.set_xlim(2015, 2028); ax.set_yticks([]); ax.tick_params(labelsize=8)
    for s in ['top','right','left']: ax.spines[s].set_visible(False)
    ax.set_title('블랙핑크 그룹 vs 개별 활동 — YG 통제 가능: 그룹만', fontsize=9, color=NAVY)
    ax.set_xticks(list(range(2016, 2028, 2)))
    save(fig, 'm58_blackpink_solo')


def m62():
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    sc = [('성공','음반 50만+',89000,RED),('보통','음반 20~50만',84000,NAVY),
          ('실패','음반 20만 미만',78000,GOLD),('대실패','데뷔 무산',67000,GREY)]
    y = np.arange(len(sc))
    prices = [s[2] for s in sc]; labels = [f"{s[0]}\n({s[1]})" for s in sc]; colors = [s[3] for s in sc]
    bars = ax.barh(y, prices, color=colors, alpha=0.85)
    for i,b in enumerate(bars):
        ax.text(b.get_width()+800, b.get_y()+b.get_height()/2, f'{prices[i]:,}원', va='center', fontsize=10, weight='bold')
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel('적정주가 (원)', fontsize=8); ax.tick_params(labelsize=8)
    ax.set_xlim(0, 100000)
    ax.set_title('9월 보이그룹 결과별 적정주가 시나리오', fontsize=9, color=NAVY)
    ax.axvline(48050, color='black', linestyle='--', linewidth=0.8)
    ax.text(48050, 3.6, '현재 48,050원', fontsize=7)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    save(fig, 'm62_sept_scenario')


def m69():
    fig, ax = plt.subplots(figsize=(6, 3))
    years = ['2021','2022','2023','2024','2025','2026E']
    npm = [7.1, 12.0, 13.5, 5.5, 6.8, 11.4]
    turn = [0.55, 0.71, 0.82, 0.50, 0.74, 0.78]
    lev = [1.29, 1.36, 1.27, 1.16, 1.43, 1.45]
    roe = [npm[i]/100 * turn[i] * lev[i] * 100 for i in range(len(years))]
    ax.plot(years, roe, color=NAVY, marker='o', linewidth=2.5, markersize=8, label='ROE')
    ax.plot(years, npm, color=RED, marker='s', linewidth=1.5, linestyle='--', label='순이익률(%)')
    ax.plot(years, [t*10 for t in turn], color=BLUE, marker='^', linewidth=1.5, linestyle=':', label='자산회전율×10')
    for i,v in enumerate(roe):
        ax.text(i, v+0.5, f'{v:.1f}%', ha='center', fontsize=8, weight='bold', color=NAVY)
    ax.set_ylabel('비율 (%)', fontsize=8); ax.tick_params(labelsize=9)
    ax.legend(fontsize=7); ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.set_title('ROE 듀폰 분해 5년 — 2026E 10.8% 회복', fontsize=9, color=NAVY)
    save(fig, 'm69_roe_dupont')


def m72():
    fig, ax = plt.subplots(figsize=(6, 3))
    years = ['2021','2022','2023','2024','2025','2026E','2027E','2028E\n(본)']
    rev = [3216, 3912, 5692, 3649, 5454, 6010, 5660, 7000]
    colors = [GREY]*5 + [BLUE, BLUE, RED]
    bars = ax.bar(years, rev, color=colors, alpha=0.85)
    for i,b in enumerate(bars):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+100, f'{rev[i]:,}', ha='center', fontsize=8)
    ax.axhline(6132, color=NAVY, linestyle='--', linewidth=0.8)
    ax.text(7.4, 6300, '컨센 6,132억', fontsize=7, color=NAVY, ha='right')
    ax.set_ylabel('매출액 (억원)', fontsize=8); ax.tick_params(labelsize=8)
    ax.set_title('YG 매출 5년 + 2028E 7,000억 (컨센 +14%)', fontsize=9, color=NAVY)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    save(fig, 'm72_revenue_2028e')


def m73():
    fig, ax = plt.subplots(figsize=(6, 3))
    years = ['2021','2022','2023','2024','2025','2028E']
    opm = [7.9, 10.9, 15.3, -5.7, 13.1, 16.0]
    colors = [RED if v<0 else NAVY if i==len(opm)-1 else GREY for i,v in enumerate(opm)]
    bars = ax.bar(years, opm, color=colors, alpha=0.85)
    for i,b in enumerate(bars):
        ypos = b.get_height() + (0.5 if opm[i]>=0 else -1.5)
        ax.text(b.get_x()+b.get_width()/2, ypos, f'{opm[i]:.1f}%', ha='center', fontsize=9, weight='bold')
    ax.axhline(15.3, color=RED, linestyle='--', linewidth=0.8, alpha=0.6)
    ax.text(5.4, 15.7, '2023 정점 15.3%', fontsize=7, color=RED, ha='right')
    ax.axhline(0, color='black', linewidth=0.5)
    ax.set_ylabel('OPM (%, 발표기준)', fontsize=8); ax.tick_params(labelsize=8)
    ax.set_title('YG 5년 OPM + 2028E 16% — 활동기 정점 상회', fontsize=9, color=NAVY)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    save(fig, 'm73_opm_2028e')


def m76():
    fig, ax = plt.subplots(figsize=(5.5, 3))
    c = ['하이브','YG(본 리포트)','JYP','YG(컨센)','SM']
    pers = [22, 24, 13, 14.4, 12]
    colors = [GREY, RED, GREY, NAVY, GREY]
    bars = ax.barh(c, pers, color=colors, alpha=0.85)
    for i,b in enumerate(bars):
        ax.text(b.get_width()+0.3, b.get_y()+b.get_height()/2, f'{pers[i]:.1f}배', va='center', fontsize=10, weight='bold')
    ax.axvline(13.5, color='black', linestyle='--', linewidth=0.8)
    ax.text(13.5, 4.5, '4사 Median 13.5', fontsize=7, ha='center')
    ax.set_xlabel('Implied Target PER (배)', fontsize=8); ax.tick_params(labelsize=8)
    ax.set_title('4사 Implied Target PER — 본 24배', fontsize=9, color=NAVY)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    save(fig, 'm76_4comp_implied_per')


def m79():
    fig, ax = plt.subplots(figsize=(7, 3))
    a = ['Base','+보이그룹\n50→70%','+NEXT\n25→50%','+텐센트\n정상화','+한한령\n부분 해제','+PER\n24→26.5','모두\n풀림']
    p = [89000, 94000, 97000, 99000, 105000, 114000, 114000]
    d = [0, 5000, 3000, 2000, 6000, 9000, 0]
    colors = [NAVY] + [BLUE]*5 + [RED]
    bars = ax.bar(a, p, color=colors, alpha=0.85)
    for i,b in enumerate(bars):
        if i>0 and i<6:
            ax.text(b.get_x()+b.get_width()/2, b.get_height()+1500, f'+{d[i]:,}', ha='center', fontsize=8, color=RED, weight='bold')
        else:
            ax.text(b.get_x()+b.get_width()/2, b.get_height()+1500, f'{p[i]:,}', ha='center', fontsize=8, weight='bold')
    ax.set_ylabel('적정주가 (원)', fontsize=8); ax.tick_params(labelsize=7)
    ax.set_title('보수 가정 5가지 민감도 — 모두 풀릴 시 114,000원', fontsize=9, color=NAVY)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    save(fig, 'm79_5_assumptions')


def m83():
    fig, ax = plt.subplots(figsize=(7, 3))
    ips = ['빅뱅 BIGSHOW','베몬 정규 2집·월투','트레저 일본 돔','9월 신인 보이','NEXT MONSTER','블랙핑크']
    quarters = ['1Q26','2Q26','3Q26','4Q26','1Q27','2Q27','3Q27','4Q27','1Q28','2Q28','3Q28','4Q28']
    data = np.array([
        [0,0,0.3,0.6,1.0,0.4,0.3,0.2,0,0,0,0],
        [0.2,0.4,0.5,0.9,0.7,0.8,0.6,0.5,0.5,0.5,0.5,0.5],
        [0,0.3,0.5,0.3,0.2,0.4,0.6,0.4,0.3,0.3,0.3,0.3],
        [0,0,0,0.2,0.3,0.4,0.4,0.45,0.5,0.5,0.5,0.5],
        [0,0,0,0,0,0,0.2,0.25,0.25,0.3,0.3,0.3],
        [0.5,0.2,0.2,0.2,0.3,0.5,0.4,0.3,0.2,0.2,0.2,0.2],
    ])
    im = ax.imshow(data, cmap='Blues', aspect='auto', vmin=0, vmax=1)
    ax.set_yticks(range(len(ips))); ax.set_yticklabels(ips, fontsize=8)
    ax.set_xticks(range(len(quarters))); ax.set_xticklabels(quarters, fontsize=7, rotation=45)
    ax.set_title('IP × 분기 매출 시간표 (1Q26~4Q28, 진행률)', fontsize=9, color=NAVY)
    cbar = plt.colorbar(im, ax=ax, fraction=0.04, pad=0.02); cbar.ax.tick_params(labelsize=7)
    save(fig, 'm83_ip_quarterly')


def m86():
    fig, ax = plt.subplots(figsize=(6, 3))
    cats = ['음반 판매\n(데뷔 6M, 만장)','주요 차트\n진입(개)','MV 1주\n조회수(억뷰)','팬덤 YT\n구독(만)']
    baemon = [50, 4, 1.5, 1200]
    target = [40, 3, 1.0, 800]
    fail = [20, 0.5, 0.3, 300]
    x = np.arange(len(cats)); w = 0.27
    ax.bar(x-w, baemon, w, label='베몬 실제', color=NAVY, alpha=0.9)
    ax.bar(x, target, w, label='9월 목표', color=BLUE, alpha=0.9)
    ax.bar(x+w, fail, w, label='실패 임계', color=RED, alpha=0.7)
    ax.set_xticks(x); ax.set_xticklabels(cats, fontsize=7)
    ax.set_yscale('log'); ax.tick_params(labelsize=7)
    ax.legend(fontsize=7); ax.set_title('양성 시스템 검증 매트릭스 — 베몬 vs 9월 보이', fontsize=9, color=NAVY)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    save(fig, 'm86_system_validation')


def m88():
    fig, ax = plt.subplots(figsize=(6, 3))
    stages = ['현재 48,050','8월 빅뱅 일정\n→67,000','9월·10월\n→78,000','27.1 빅뱅종료\n→85,000','28년 말 안착\n→89,000']
    prices = [48050, 67000, 78000, 85000, 89000]
    colors = [GREY, BLUE, BLUE, NAVY, RED]
    y = np.arange(len(stages))
    ax.barh(y, prices, color=colors, alpha=0.85)
    for i,p in enumerate(prices):
        ax.text(p+1000, i, f'{p:,}원', va='center', fontsize=10, weight='bold')
    ax.set_yticks(y); ax.set_yticklabels(stages, fontsize=7)
    ax.set_xlabel('주가 (원)', fontsize=8); ax.tick_params(labelsize=8)
    ax.invert_yaxis(); ax.set_xlim(0, 100000)
    ax.set_title('89,000원 단계적 상승 사다리 (2.5년)', fontsize=9, color=NAVY)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    save(fig, 'm88_price_ladder')


def m89():
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    ax.axis('off')
    ax.add_patch(Rectangle((0.05, 0.7), 0.9, 0.25, facecolor=NAVY, alpha=0.9))
    ax.text(0.5, 0.83, 'BUY', fontsize=32, color='white', ha='center', va='center', weight='bold')
    ax.text(0.5, 0.74, '투자 호라이즌 2.5년', fontsize=10, color='white', ha='center', style='italic')
    metrics = [('적정주가','89,000원',NAVY),('현재가','48,050원','black'),
               ('Upside','+85.2%',RED),('연 환산','+27%/년',RED)]
    for i,(lbl,val,color) in enumerate(metrics):
        y = 0.55 - i*0.13
        ax.text(0.15, y, lbl, fontsize=10, va='center')
        ax.text(0.85, y, val, fontsize=13, va='center', ha='right', color=color, weight='bold')
    ax.set_xlim(0,1); ax.set_ylim(0,1)
    ax.set_title('투자의견 BUY — 컨센 대비 +13%', fontsize=10, color=NAVY)
    save(fig, 'm89_buy_conclusion')


def main():
    print('=== 신규 핵심 도표 17개 생성 ===\n')
    for f in [m30, m35, m38, m40, m41, m45, m46, m58, m62, m69, m72, m73, m76, m79, m83, m86, m88, m89]:
        f()
    print('\n완료')


if __name__ == '__main__':
    main()
