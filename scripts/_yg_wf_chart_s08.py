"""
위닝펀드 18-1 YG Slide 8 도표 교체:
기존 5개 연말 종가 점 그래프 → 진짜 5년 일봉 주가 차트 + IP 이벤트 어노테이션

핵심 thesis: 24.10~25.08 베몬+BP 재계약·DEADLINE 으로 +190% 상승.
            다음 라인업(26.08 빅뱅 + 26.09 신인 보이그룹 + 10월 걸그룹)으로 같은 패턴 재현.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch
from matplotlib.dates import DateFormatter, YearLocator
import pandas as pd
import FinanceDataReader as fdr
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

# 데이터
df = fdr.DataReader('122870', '2020-01-01', '2026-05-19')

# 색상 (위닝펀드 톤)
NAVY = '#1F3A5F'
GOLD = '#C9A961'
RED  = '#C0392B'
GREEN = '#27AE60'
GREY = '#8B95A1'

# Figure (Slide 8 기존 도표 크기 5.48" x 3.06")
fig, ax = plt.subplots(figsize=(5.48, 3.06), dpi=200)
fig.patch.set_facecolor('white')
ax.set_facecolor('white')

# 메인 라인
ax.plot(df.index, df['Close'], color=NAVY, linewidth=1.3, zorder=3)
ax.fill_between(df.index, df['Close'], 0, color=NAVY, alpha=0.05, zorder=1)

# 24.10 ~ 25.08 상승 구간 음영 (Gold)
shade_start = pd.Timestamp('2024-10-01')
shade_end   = pd.Timestamp('2025-08-21')
mask = (df.index >= shade_start) & (df.index <= shade_end)
ax.fill_between(df.index[mask], df['Close'][mask], 0,
                color=GOLD, alpha=0.22, zorder=2, label='_nolegend_')

# 미래 예측 박스 (26.05~26.12) - 점선 영역
future_start = pd.Timestamp('2026-05-19')
future_end   = pd.Timestamp('2026-12-31')
ax.axvspan(future_start, future_end, color=GREEN, alpha=0.08, zorder=1)

# 주요 이벤트 어노테이션 (좌→우 시간 순)
events = [
    ('2022-10-04', 42000,  '활동 공백',                       NAVY, (0,  -28)),
    ('2024-10-02', 37000,  '베몬 활동 본격\n+ BP 재계약',     GOLD, (-30, 30)),
    ('2025-05-30', 81000,  'DEADLINE 발매',                   GOLD, (-25, 22)),
    ('2025-08-21', 107400, '정점 107,400\n(+190% from 24.10)', RED,  (-50, 8)),
    ('2026-05-19', 48700,  '1Q26 -27%\n현재 48,700',          NAVY, (-45, -28)),
]
for date_str, price, label, color, offset in events:
    dt = pd.Timestamp(date_str)
    ax.scatter([dt], [price], color=color, s=22, zorder=5, edgecolor='white', linewidth=0.8)
    ax.annotate(label, xy=(dt, price), xytext=offset,
                textcoords='offset points',
                fontsize=7, color=color, fontweight='bold',
                ha='center',
                arrowprops=dict(arrowstyle='-', color=color, lw=0.6,
                                connectionstyle='arc3,rad=0'),
                zorder=6)

# 24.10~25.08 구간 라벨 (음영 구간 중앙 상단)
ax.text(pd.Timestamp('2025-02-15'), 60000, '+190%\n(1년 미만)',
        fontsize=9, color=GOLD, fontweight='bold', ha='center',
        bbox=dict(boxstyle='round,pad=0.35', facecolor='white',
                  edgecolor=GOLD, linewidth=1.0))

# 미래 라벨 박스 (우측 녹색 영역)
ax.text(pd.Timestamp('2026-09-15'), 90000,
        '26.08 빅뱅 투어\n26.09 보이그룹 (확정)\n4Q26~1Q27 걸그룹\n→ 패턴 재현?',
        fontsize=6.8, color=GREEN, fontweight='bold', ha='center',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                  edgecolor=GREEN, linewidth=1.0))
# 화살표 (현재가에서 미래 예측 영역으로)
ax.annotate('', xy=(pd.Timestamp('2026-08-01'), 78000),
            xytext=(pd.Timestamp('2026-05-25'), 55000),
            arrowprops=dict(arrowstyle='->', color=GREEN, lw=1.2,
                            connectionstyle='arc3,rad=-0.25'))

# 축
ax.set_ylim(20000, 125000)
ax.set_yticks([30000, 50000, 70000, 90000, 110000])
ax.set_yticklabels(['3만', '5만', '7만', '9만', '11만'], fontsize=8, color='#555')
ax.xaxis.set_major_locator(YearLocator())
ax.xaxis.set_major_formatter(DateFormatter('%Y'))
ax.tick_params(axis='x', labelsize=8, colors='#555')

# 제목
ax.set_title('라인업이 채워지면 주가는 오른다 — 24.10~25.08 +190% 사례\n→ 26.08 빅뱅·9월 보이그룹(확정)이 같은 패턴 재현',
             fontsize=10, fontweight='bold', color=NAVY, loc='left', pad=10)

# Spine 정리
for s in ('top', 'right'):
    ax.spines[s].set_visible(False)
ax.spines['left'].set_color('#CCC')
ax.spines['bottom'].set_color('#CCC')
ax.grid(True, axis='y', linestyle=':', linewidth=0.5, color='#DDD', zorder=0)

# Footnote
fig.text(0.99, 0.01, '출처: FinanceDataReader (KRX 일봉)',
         fontsize=6, color='#999', ha='right')

plt.tight_layout(rect=(0, 0.02, 1, 0.96))

out = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\_chart_s08_real_price_chart.png')
plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
print(f'Saved: {out}')
