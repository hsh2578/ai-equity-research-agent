"""
위닝펀드 18-1 YG Slide 9 도표 교체:
좌측 OP 컨센 막대(기존 메시지 유지) + 우측 ATP×모객 매트릭스(Hana 935 산식 근거)
1x2 grid in one PNG (5.69" x 3.06")
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib import font_manager
import numpy as np
from pathlib import Path

# 폰트
for f in ('Pretendard', 'Malgun Gothic', 'NanumGothic'):
    try:
        font_manager.findfont(f, fallback_to_default=False)
        mpl.rcParams['font.family'] = f
        break
    except Exception:
        continue
mpl.rcParams['axes.unicode_minus'] = False

NAVY = '#1F3A5F'
GOLD = '#C9A961'
RED  = '#C0392B'
LBLU = '#5B8AB5'
GREY = '#8B95A1'

fig = plt.figure(figsize=(5.69, 3.06), dpi=200)
fig.patch.set_facecolor('white')
gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.05], wspace=0.45)

# === 좌측: OP 컨센 막대 ===
ax1 = fig.add_subplot(gs[0, 0])
ax1.set_facecolor('white')
years = ['2024', '2025', '2026E', '2027E']
ops   = [-186, 522, 806, 764]
colors_op = [RED, LBLU, NAVY, NAVY]
bars = ax1.bar(years, ops, color=colors_op, width=0.58, edgecolor='none')
# Hana 추정 점선
ax1.axhline(935, color=GOLD, linestyle='--', linewidth=1.5, dashes=(5, 3))
ax1.text(3.45, 935, 'Hana 추정\n935', fontsize=7, color=GOLD,
         fontweight='bold', va='center', ha='left')

# 막대 끝 라벨
for bar, v in zip(bars, ops):
    color_label = RED if v < 0 else NAVY
    va = 'top' if v < 0 else 'bottom'
    off = -20 if v < 0 else 18
    ax1.text(bar.get_x() + bar.get_width()/2, v + off, f'{v}',
             ha='center', va=va, fontsize=8.5, fontweight='bold', color=color_label)

ax1.axhline(0, color='#888', linewidth=0.6)
ax1.set_ylim(-300, 1100)
ax1.set_yticks([])
ax1.tick_params(axis='x', labelsize=8, colors='#555')
for s in ('top', 'right', 'left'):
    ax1.spines[s].set_visible(False)
ax1.spines['bottom'].set_color('#CCC')
ax1.set_title('영업이익 컨센 (억원)\n2027E가 2026E보다 낮다',
              fontsize=8.5, fontweight='bold', color=NAVY, loc='left', pad=6)

# === 우측: ATP × 모객 3x3 매트릭스 ===
ax2 = fig.add_subplot(gs[0, 1])
ax2.set_facecolor('white')

# 데이터 (티켓 매출, 억원): ATP × 모객
atps   = [22, 25, 28]              # 만원
mokeks = [35, 40, 45]              # 만명
matrix = np.array([
    [770,  880,  990 ],   # ATP 22만
    [875,  1000, 1125],   # ATP 25만 (중앙 = Base)
    [980,  1120, 1260],   # ATP 28만 (우하 = Bull)
])

# Heatmap (값에 비례한 색)
im = ax2.imshow(matrix, cmap='YlOrBr', vmin=600, vmax=1400, aspect='auto')

# 셀 라벨
for i in range(3):
    for j in range(3):
        v = matrix[i, j]
        is_base = (i == 1 and j == 1)
        is_bull = (i == 2 and j == 2)
        weight = 'bold' if (is_base or is_bull) else 'normal'
        color  = NAVY if v < 1100 else 'white'
        label = f'{v:,}'
        if is_base:
            label += '\n(Base)'
        if is_bull:
            label += '\n(Bull)'
        ax2.text(j, i, label, ha='center', va='center',
                 fontsize=7.5, fontweight=weight, color=color)

# Base/Bull 셀 테두리 강조
from matplotlib.patches import Rectangle
ax2.add_patch(Rectangle((0.5, 0.5), 1, 1, fill=False, edgecolor=NAVY, linewidth=1.8))
ax2.add_patch(Rectangle((1.5, 1.5), 1, 1, fill=False, edgecolor=RED,  linewidth=1.8))

# 축 라벨
ax2.set_xticks(range(3))
ax2.set_xticklabels([f'{m}만' for m in mokeks], fontsize=7.5, color='#444')
ax2.set_yticks(range(3))
ax2.set_yticklabels([f'{a}만' for a in atps], fontsize=7.5, color='#444')
ax2.set_xlabel('모객 (명)', fontsize=7.5, color='#555', labelpad=2)
ax2.set_ylabel('ATP (원)', fontsize=7.5, color='#555', labelpad=2)
ax2.tick_params(length=0)
for s in ('top', 'right', 'bottom', 'left'):
    ax2.spines[s].set_visible(False)
ax2.set_title('빅뱅 투어 티켓 매출 (억원)\nATP × 모객 — Hana 935 산식 근거',
              fontsize=8.5, fontweight='bold', color=NAVY, loc='left', pad=6)

# Footnote
fig.text(0.99, 0.01, '출처: FnGuide 컨센·SK증권 Arirang 추정 방법론 차용 (MD 매출 별도)',
         fontsize=5.8, color='#999', ha='right')

plt.tight_layout(rect=(0, 0.03, 1, 0.97))

out = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\_chart_s09_op_atp_matrix.png')
plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
print(f'Saved: {out}')
