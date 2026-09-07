"""m03 라벨 겹침 수정"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
NAVY = '#1E3A6D'; RED = '#C8102E'
OUT = Path('output/와이지엔터/_charts')

fig, ax = plt.subplots(figsize=(6, 3.2))
sectors = ['반도체(삼성·SK)', '코스피', '코스닥', 'K콘텐츠(엔터 4사)', 'YG']
returns = [112.8, 8.5, -5.2, -23.0, -24.2]
colors = [NAVY if v > 0 else RED for v in returns]
bars = ax.barh(sectors, returns, color=colors, alpha=0.85)
for i, b in enumerate(bars):
    # 음수면 막대 왼쪽에 라벨(barh 끝 부분)
    if returns[i] < 0:
        ax.text(returns[i] - 3, b.get_y()+b.get_height()/2, f'{returns[i]:+.1f}%',
               ha='right', va='center', fontsize=9, weight='bold', color=RED)
    else:
        ax.text(returns[i] + 3, b.get_y()+b.get_height()/2, f'{returns[i]:+.1f}%',
               ha='left', va='center', fontsize=9, weight='bold', color=NAVY)
ax.axvline(0, color='black', linewidth=0.5)
ax.set_xlabel('연초 대비 수익률 (%)', fontsize=8)
ax.tick_params(labelsize=9)
ax.set_xlim(-45, 125)  # 라벨 공간 확보
ax.set_title('업종별 연초 대비 수익률 — 반도체 +112.8% vs K콘텐츠 -23%', fontsize=10, color=NAVY)
ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
fig.tight_layout()
fig.savefig(OUT / 'm03_sector_return.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close(fig)
print('saved: m03_sector_return.png (라벨 겹침 수정)')
