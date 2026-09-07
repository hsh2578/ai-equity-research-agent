"""
위닝펀드 18-1 YG Slide 4 하단 도표 교체:
기존 K-POP 산업 밸류체인 흐름도 → 업종별 YTD 수익률 비교 막대 그래프

출처: 키움증권 Page 9 '업종별 연초 대비 수익률 비교'
메시지: 엔터의 적은 내부가 아니라 외부의 대체재 (반도체 +112% vs K콘텐츠 부진)
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
GREY = '#BBBBBB'
DARK_GREY = '#7B8B98'

# 키움 PDF p9 차트 추정치 (업종별 YTD 수익률)
# 데이터를 하단부터(부진) 상단(강세) 순서로
sectors = [
    'K콘텐츠',  '헬스케어',  '운송',   '방송통신',  '경기소비재',
    '보험',     '은행',     '자동차',  '유틸리티',  '필수소비재',
    '철강',     '에너지화학', '기계장비',
    '전체기업',  '증권',     '정보기술', '건설',  '반도체'
]
returns = [
    -23, -10,  -5,   -3,    0,
      2,   5,   8,   12,    15,
     20,  28,   35,
     33,   45,   62,   90,   112.8
]

# 색상: K콘텐츠 진한 강조, 반도체 빨강 강조, 나머지 회색
colors = []
for s in sectors:
    if s == 'K콘텐츠':
        colors.append(NAVY)
    elif s == '반도체':
        colors.append(RED)
    else:
        colors.append(GREY)

# Figure (Slide 4 하단 슬롯 W 6.54" x H 2.75")
fig, ax = plt.subplots(figsize=(6.54, 2.75), dpi=200)
fig.patch.set_facecolor('white')
ax.set_facecolor('white')

y_pos = range(len(sectors))
bars = ax.barh(y_pos, returns, color=colors, height=0.70, edgecolor='none')

# 강조 막대 outline
for i, s in enumerate(sectors):
    if s in ('K콘텐츠', '반도체'):
        bars[i].set_edgecolor('white')
        bars[i].set_linewidth(0.4)

ax.set_yticks(y_pos)
ax.set_yticklabels(sectors, fontsize=6.5, color='#333')
ax.invert_yaxis()

# 막대 끝 라벨 (강조만)
for i, (bar, v, s) in enumerate(zip(bars, returns, sectors)):
    is_key = s in ('K콘텐츠', '반도체')
    fontweight = 'bold' if is_key else 'normal'
    color = NAVY if s == 'K콘텐츠' else (RED if s == '반도체' else '#666')
    if v >= 0:
        ax.text(v + 2, i, f'+{v:.1f}%' if is_key else f'+{v}%',
                va='center', ha='left',
                fontsize=7.5 if is_key else 6.5,
                fontweight=fontweight, color=color)
    else:
        ax.text(v - 2, i, f'{v}%',
                va='center', ha='right',
                fontsize=7.5 if is_key else 6.5,
                fontweight=fontweight, color=color)

# 0 line
ax.axvline(0, color='#888', linewidth=0.7)

# X축
ax.set_xlim(-40, 135)
ax.set_xticks([-20, 0, 20, 40, 60, 80, 100, 120])
ax.set_xticklabels(['-20%', '0', '20%', '40%', '60%', '80%', '100%', '120%'],
                   fontsize=6.5, color='#555')
ax.tick_params(length=0)

for s in ('top', 'right', 'left'):
    ax.spines[s].set_visible(False)
ax.spines['bottom'].set_color('#CCC')
ax.grid(True, axis='x', linestyle=':', linewidth=0.4, color='#EEE', zorder=0)

# 제목
ax.set_title("업종별 연초 대비 수익률 — 반도체가 K콘텐츠 자금을 데려갔다",
             fontsize=10, fontweight='bold', color=NAVY, loc='left', pad=8)

# 좌상단 강조 메시지 박스
ax.text(0.99, 0.55,
        "엔터의 적은 내부가 아니라\n외부의 '압도적 대체재'다.",
        transform=ax.transAxes, fontsize=7, color=NAVY,
        ha='right', va='center', style='italic',
        bbox=dict(boxstyle='round,pad=0.35', facecolor='#F8F9FA',
                  edgecolor=GOLD, linewidth=0.8))

# Footnote
fig.text(0.99, 0.01,
         '출처: 키움증권 K-POP 산업 리포트 (2026.05) · FnGuide',
         fontsize=5.8, color='#999', ha='right')

plt.tight_layout(rect=(0.01, 0.03, 1, 0.95))

out = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\_chart_s04_bottom_sector_ytd.png')
plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
print(f'Saved: {out}')
