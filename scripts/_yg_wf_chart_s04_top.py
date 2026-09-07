"""신규 도표 6개 — 산업분석 메모 3·4·5·6·7·10"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from matplotlib.patches import Patch

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

NAVY = '#1E3A6D'; RED = '#C8102E'; BLUE = '#5DADE2'; GREY = '#888888'; GOLD = '#C9A961'
OUT = Path('output/와이지엔터/_charts'); OUT.mkdir(parents=True, exist_ok=True)

def save(fig, name):
    fig.savefig(OUT / f'{name}.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f'  saved: {name}.png')

# 메모 3: 업종별 연초 대비 수익률
fig, ax = plt.subplots(figsize=(5, 3))
sectors = ['반도체(삼성·SK)', '코스피', '코스닥', 'K콘텐츠(엔터 4사)', 'YG']
returns = [112.8, 8.5, -5.2, -23.0, -24.2]
colors = [NAVY if v > 0 else RED for v in returns]
bars = ax.barh(sectors, returns, color=colors, alpha=0.85)
for i, b in enumerate(bars):
    ax.text(b.get_width() + (4 if returns[i]>0 else -4), b.get_y()+b.get_height()/2,
           f'{returns[i]:+.1f}%', ha='left' if returns[i]>0 else 'right', va='center', fontsize=9, weight='bold')
ax.axvline(0, color='black', linewidth=0.5)
ax.set_xlabel('연초 대비 수익률 (%)', fontsize=8)
ax.tick_params(labelsize=8)
ax.set_title('업종별 연초 대비 수익률 — 반도체 +112.8% vs K콘텐츠 -23%', fontsize=9, color=NAVY)
ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
save(fig, 'm03_sector_return')

# 메모 4: 엔터 4사 매출 성장률 추이
fig, ax = plt.subplots(figsize=(5, 3))
years = ['2022', '2023', '2024', '2025', '2026E']
growth = [40, 38, 35, 22, 7.7]
ax.plot(years, growth, color=NAVY, marker='o', linewidth=2.5, markersize=9)
ax.fill_between(years, growth, alpha=0.15, color=NAVY)
for i, v in enumerate(growth):
    ax.text(i, v+2, f'{v:.1f}%', ha='center', fontsize=10, weight='bold', color=NAVY)
ax.set_ylabel('매출 성장률 (% YoY)', fontsize=8)
ax.tick_params(labelsize=9)
ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
ax.set_title('엔터 4사 매출 성장률 추이 — 35% → 7.7% 둔화', fontsize=9, color=NAVY)
ax.axhline(0, color='black', linewidth=0.5)
save(fig, 'm04_revenue_growth')

# 메모 5: 글로벌 빅3 레이블
fig, ax = plt.subplots(figsize=(5, 3))
years = list(range(2014, 2025))
umg = [50, 53, 57, 65, 72, 79, 85, 99, 110, 119, 121]
sme = [25, 26, 28, 30, 32, 35, 38, 42, 45, 48, 51]
wmg = [15, 16, 17, 19, 22, 25, 28, 31, 34, 37, 39]
ax.plot(years, umg, color=NAVY, marker='o', label='UMG', linewidth=2)
ax.plot(years, sme, color=RED, marker='s', label='SME', linewidth=2)
ax.plot(years, wmg, color=BLUE, marker='^', label='WMG', linewidth=2)
ax.set_ylabel('매출 ($Bn)', fontsize=8)
ax.tick_params(labelsize=8)
ax.legend(fontsize=8, loc='upper left')
ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
ax.set_title('글로벌 빅3 레이블 10년 매출 — 음악 자산 운용사로 진화', fontsize=9, color=NAVY)
save(fig, 'm05_global_big3')

# 메모 6: BTS vs 테일러
fig, ax = plt.subplots(figsize=(5, 3))
cats = ['티켓 매출', 'MD·플랫폼', '부가매출 효율']
bts = [100, 65, 149]
taylor = [100, 35, 100]
x = np.arange(len(cats)); w = 0.35
ax.bar(x - w/2, bts, w, label='BTS (360도 통합)', color=NAVY)
ax.bar(x + w/2, taylor, w, label='테일러 스위프트', color=GREY)
ax.set_xticks(x); ax.set_xticklabels(cats, fontsize=8)
ax.set_ylabel('인덱스 (티켓=100)', fontsize=8)
ax.legend(fontsize=8, loc='upper left')
ax.tick_params(labelsize=8)
ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
ax.set_title('BTS vs 테일러 스위프트 월투 매출 구조 — +49% 효율 우위', fontsize=9, color=NAVY)
ax.annotate('+49%', xy=(2, 149), fontsize=12, weight='bold', color=RED, ha='center')
save(fig, 'm06_bts_taylor')

# 메모 7: 슈퍼팬 비율
fig, ax = plt.subplots(figsize=(5, 3))
cats = ['전체 음악시장', '팝 시장', 'K-POP 시장']
rates = [20, 26, 34]
colors2 = [GREY, BLUE, NAVY]
bars = ax.bar(cats, rates, color=colors2, alpha=0.9)
for i, b in enumerate(bars):
    ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.7,
           f'{rates[i]}%', ha='center', fontsize=12, weight='bold', color=colors2[i])
ax.set_ylabel('슈퍼팬 비율 (%)', fontsize=8)
ax.tick_params(labelsize=9)
ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
ax.set_title('슈퍼팬 비율 — K-POP 34% 최고 (Luminate 데이터)', fontsize=9, color=NAVY)
ax.set_ylim(0, 40)
save(fig, 'm07_superfan')

# 메모 10: 28년 데뷔 IP 타임라인
fig, ax = plt.subplots(figsize=(6.5, 3))
ips = [
    ('지누션', 1997, 'finished'), ('1TYM', 2000, 'finished'),
    ('세븐', 2003, 'finished'), ('빅뱅', 2006, 'mega'),
    ('2NE1', 2009, 'finished'), ('위너', 2014, 'finished'),
    ('아이콘', 2015, 'finished'), ('블랙핑크', 2016, 'mega'),
    ('트레저', 2020, 'active'), ('베이비몬스터', 2023, 'mega'),
    ('신인 보이', 2026, 'upcoming'), ('NEXT MONSTER', 2027, 'upcoming'),
]
colors_map = {'mega': RED, 'active': NAVY, 'finished': GREY, 'upcoming': GOLD}
for i, (name, year, status) in enumerate(ips):
    ax.scatter(year, 0, s=250 if status in ('mega','upcoming') else 100,
              color=colors_map[status], zorder=5,
              edgecolors='black' if status == 'mega' else None, linewidths=1.5 if status=='mega' else 0)
    ax.text(year, 0.35 if i % 2 == 0 else -0.35, name, ha='center', fontsize=8,
           weight='bold' if status == 'mega' else 'normal',
           color=RED if status == 'mega' else 'black')
ax.axhline(0, color='black', linewidth=0.5)
ax.set_xlim(1995, 2029)
ax.set_ylim(-0.8, 0.8)
ax.set_yticks([])
ax.set_xticks([1997, 2006, 2016, 2023, 2026])
ax.tick_params(labelsize=8)
for spine in ['top', 'right', 'left']:
    ax.spines[spine].set_visible(False)
ax.set_title('YG 28년 데뷔 IP 타임라인 — 메가 IP 빅뱅·블핑·베몬 3종', fontsize=9, color=NAVY)
legend = [Patch(color=RED, label='메가 IP'), Patch(color=NAVY, label='활동 중'),
          Patch(color=GOLD, label='데뷔 예정'), Patch(color=GREY, label='활동 종료')]
ax.legend(handles=legend, fontsize=7, loc='upper right', ncol=4, frameon=False)
save(fig, 'm10_28y_timeline')

print('\n=== 6개 신규 도표 완료 ===')
