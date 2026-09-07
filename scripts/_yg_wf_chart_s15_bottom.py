"""
위닝펀드 18-1 YG Slide 15 도표 교체 (아래 슬롯, 5.80" x 3.29"):
좌측 Bear/Base/Bull 시나리오 막대 (기존 컨셉 유지)
+ 우측 4팩터 Z-Score 막대 (dacon-skills 가치투자 모델, 303종목 중 2등 STRONG_BUY)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib import font_manager
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
GREY = '#8B95A1'
GREEN = '#27AE60'
LBLU = '#5B8AB5'

fig = plt.figure(figsize=(5.80, 3.29), dpi=200)
fig.patch.set_facecolor('white')
gs = fig.add_gridspec(1, 2, width_ratios=[1, 1], wspace=0.42)

# === 좌측: 시나리오별 목표주가 (기존 컨셉 유지) ===
ax1 = fig.add_subplot(gs[0, 0])
ax1.set_facecolor('white')
scenarios = ['Bear', '현재가', 'Base', 'Bull']
prices    = [42000, 48050, 67000, 92000]
colors_sc = [RED, GREY, NAVY, GOLD]
deltas    = [-12.6, 0, 39.4, 91.4]

bars = ax1.bar(scenarios, prices, color=colors_sc, width=0.62, edgecolor='none')
for bar, p, d in zip(bars, prices, deltas):
    if d == 0:
        label = f'{p:,}\n현재'
    else:
        sign = '+' if d > 0 else ''
        label = f'{p:,}\n{sign}{d}%'
    ax1.text(bar.get_x() + bar.get_width()/2, p + 2500, label,
             ha='center', va='bottom', fontsize=8, fontweight='bold',
             color=NAVY if d >= 0 else RED)

ax1.set_ylim(0, 115000)
ax1.set_yticks([])
ax1.tick_params(axis='x', labelsize=8.5, colors='#333')
for s in ('top', 'right', 'left'):
    ax1.spines[s].set_visible(False)
ax1.spines['bottom'].set_color('#CCC')
ax1.set_title('시나리오별 목표주가\n하방은 현금, 상방은 빅뱅',
              fontsize=9, fontweight='bold', color=NAVY, loc='left', pad=6)

# === 우측: 4팩터 Z-Score (dacon-skills) ===
ax2 = fig.add_subplot(gs[0, 1])
ax2.set_facecolor('white')

# 데이터 (dacon-skills triple_cross.json 2026.05.21 기준)
factors  = ['5Y PER↓', '5Y PBR↓', 'Forward↑', '타겟 +%']
z_scores = [1.37, 1.107, 0.73, 1.472]
factor_colors = [NAVY, NAVY, LBLU, LBLU]  # Value(2) / Growth(2)

bars2 = ax2.bar(range(len(factors)), z_scores, color=factor_colors,
                width=0.62, edgecolor='none')
for i, (bar, z) in enumerate(zip(bars2, z_scores)):
    ax2.text(bar.get_x() + bar.get_width()/2, z + 0.05,
             f'{z:.2f}', ha='center', va='bottom',
             fontsize=8.5, fontweight='bold', color=NAVY)

# 0 line
ax2.axhline(0, color='#888', linewidth=0.6)

# 우상단 STRONG_BUY 박스 (Value/Growth 통합)
ax2.text(0.98, 0.97,
         '303종목 중 2등\nSTRONG_BUY\nValue 1.49 + Growth 1.94\n= Total Z 1.67',
         transform=ax2.transAxes, fontsize=7, fontweight='bold',
         color=GREEN, va='top', ha='right',
         bbox=dict(boxstyle='round,pad=0.32', facecolor='white',
                   edgecolor=GREEN, linewidth=1.0))

ax2.set_ylim(0, 2.2)
ax2.set_xticks(range(len(factors)))
ax2.set_xticklabels(factors, fontsize=7.5, color='#444')
ax2.set_yticks([0, 0.5, 1.0, 1.5, 2.0])
ax2.set_yticklabels(['0', '0.5', '1.0', '1.5', '2.0'], fontsize=7, color='#555')
ax2.tick_params(axis='x', length=0)
ax2.tick_params(axis='y', length=0)
for s in ('top', 'right'):
    ax2.spines[s].set_visible(False)
ax2.spines['left'].set_color('#CCC')
ax2.spines['bottom'].set_color('#CCC')
ax2.grid(True, axis='y', linestyle=':', linewidth=0.4, color='#EEE', zorder=0)
ax2.set_title('4팩터 Z-Score (가치투자 모델)\n외부 정량 모델도 매수 신호',
              fontsize=9, fontweight='bold', color=NAVY, loc='left', pad=6)

# Footnote
fig.text(0.99, 0.01,
         '출처: 본 리서치 시나리오 + dacon-skills 4팩터(303종목·2026.05.21)',
         fontsize=5.8, color='#999', ha='right')

plt.tight_layout(rect=(0.01, 0.04, 0.98, 0.96))

out = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\_chart_s15b_scenario_4factor.png')
plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
print(f'Saved: {out}')
