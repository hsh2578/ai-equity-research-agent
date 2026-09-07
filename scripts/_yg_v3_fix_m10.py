"""m10_28y_timeline 글자 겹침 수정"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from matplotlib.patches import Patch

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
NAVY = '#1E3A6D'; RED = '#C8102E'; GREY = '#888888'; GOLD = '#C9A961'
OUT = Path('output/와이지엔터/_charts')

# 각 IP에 위/아래·간격 명시 (가까운 IP끼리 다른 높이)
# (이름, 연도, status, label_pos: 'top1'/'top2'/'bot1'/'bot2')
ips = [
    ('지누션',       1997, 'finished', 'bot1'),
    ('1TYM',         2000, 'finished', 'top1'),
    ('세븐',         2003, 'finished', 'bot1'),
    ('빅뱅',         2006, 'mega',     'top1'),
    ('2NE1',         2009, 'finished', 'bot1'),
    ('위너',         2014, 'finished', 'top1'),
    ('아이콘',       2015, 'finished', 'bot2'),
    ('블랙핑크',     2016, 'mega',     'top2'),
    ('트레저',       2020, 'active',   'bot1'),
    ('베이비몬스터', 2023, 'mega',     'top1'),
    ('신인 보이',    2026, 'upcoming', 'bot2'),
    ('NEXT MONSTER',2027, 'upcoming', 'top2'),
]
y_pos_map = {'top1': 0.35, 'top2': 0.65, 'bot1': -0.35, 'bot2': -0.65}
colors_map = {'mega': RED, 'active': NAVY, 'finished': GREY, 'upcoming': GOLD}

fig, ax = plt.subplots(figsize=(7, 3.5))
for name, year, status, label_pos in ips:
    color = colors_map[status]
    size = 250 if status in ('mega', 'upcoming') else 100
    ax.scatter(year, 0, s=size, color=color, zorder=5,
              edgecolors='black' if status == 'mega' else None,
              linewidths=1.5 if status == 'mega' else 0)
    y = y_pos_map[label_pos]
    ax.text(year, y, name, ha='center', fontsize=8,
           weight='bold' if status == 'mega' else 'normal',
           color=RED if status == 'mega' else 'black')
    # 점선 연결
    ax.plot([year, year], [0, y * 0.7], color='lightgray', linewidth=0.5, linestyle=':', zorder=1)

ax.axhline(0, color='black', linewidth=0.8)
ax.set_xlim(1995, 2029)
ax.set_ylim(-1.0, 1.0)
ax.set_yticks([])
ax.set_xticks([1997, 2006, 2016, 2023, 2026])
ax.tick_params(labelsize=8)
for spine in ['top', 'right', 'left']:
    ax.spines[spine].set_visible(False)
ax.set_title('YG 28년 데뷔 IP 타임라인 — 메가 IP 빅뱅·블핑·베몬 3종', fontsize=10, color=NAVY, pad=15)
legend = [Patch(color=RED, label='메가 IP'), Patch(color=NAVY, label='활동 중'),
          Patch(color=GOLD, label='데뷔 예정'), Patch(color=GREY, label='활동 종료')]
ax.legend(handles=legend, fontsize=7, loc='upper center', bbox_to_anchor=(0.5, 1.15),
          ncol=4, frameon=False)

fig.savefig(OUT / 'm10_28y_timeline.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close(fig)
print('saved: m10_28y_timeline.png (글자 겹침 수정)')
