"""
위닝펀드 18-1 YG Slide 15 도표 교체 (위 슬롯, 5.59" x 3.25"):
좌측 PER 밴드 + 우측 PBR 밴드 듀얼 차트 (증권사 표준 스타일)

- X축: 2021.07 ~ 2026.05 (월말)
- Y축: 주가 (원)
- 메인 라인: 월말 종가 (Navy 굵게)
- 멀티플 밴드 라인: 연간 EPS·BPS stairstep × 멀티플 배수
- 현재가 + 현재 멀티플 라벨링
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib import font_manager
from matplotlib.dates import DateFormatter, YearLocator
import pandas as pd
import numpy as np
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

# 색상 (위닝펀드 톤)
NAVY = '#1F3A5F'
GOLD = '#C9A961'
RED  = '#C0392B'
GREY = '#BBBBBB'
LIGHT = '#E5E5E5'

# === 데이터 구축 ===
df = fdr.DataReader('122870', '2021-07-01', '2026-05-19')

# 월말 가격 시계열
monthly = df['Close'].resample('M').last().dropna()

# 연간 회계 EPS, BPS (draft md / 사업보고서 기준)
annual = {
    2021: dict(eps=1790, bps=20000),  # 추정 (draft에 미포함)
    2022: dict(eps=1813, bps=22130),
    2023: dict(eps=3285, bps=25166),
    2024: dict(eps=991,  bps=26050),
    2025: dict(eps=1974, bps=27689),
    2026: dict(eps=3108, bps=30366),  # Forward 2026E
}

def get_eps(dt):
    y = dt.year
    return annual.get(y, annual[2026])['eps']

def get_bps(dt):
    y = dt.year
    return annual.get(y, annual[2026])['bps']

eps_series = monthly.index.map(get_eps)
bps_series = monthly.index.map(get_bps)

# 멀티플 배수
PER_MULT = [10, 15, 20, 25, 30]
PBR_MULT = [1.0, 1.5, 2.0, 2.5, 3.0]

# === Figure (Slide 15 위 슬롯 크기 5.59" x 3.25") ===
fig = plt.figure(figsize=(5.59, 3.25), dpi=200)
fig.patch.set_facecolor('white')
gs = fig.add_gridspec(1, 2, width_ratios=[1, 1], wspace=0.38)

# 공통 설정
def plot_band(ax, multipliers, base_series, multiple_label, title, current_mult, current_price):
    # 밴드 영역 (배수 라인 사이 음영)
    colors_band = ['#FFE5E5', '#FFF0D0', '#E5F0E5', '#D5E5F5', '#E5DAF0']  # 살짝 다른 톤
    for i, m in enumerate(multipliers):
        line = base_series * m
        ax.plot(monthly.index, line, color=GREY, linewidth=0.6, linestyle='--', zorder=2)
        # 우측 라벨
        ax.text(monthly.index[-1] + pd.Timedelta(days=20), line[-1],
                f'{m}{multiple_label}', fontsize=6.5, color='#777',
                va='center', ha='left')
    # 메인 주가 라인
    ax.plot(monthly.index, monthly.values, color=NAVY, linewidth=1.4, zorder=5)
    # 현재가 점 + 라벨
    ax.scatter([monthly.index[-1]], [monthly.values[-1]],
               color=RED, s=28, zorder=6, edgecolor='white', linewidth=0.8)
    # 좌상단 텍스트 박스: 현재 멀티플
    ax.text(0.02, 0.96,
            f'현재 {current_mult}\n(주가 {current_price:,}원)',
            transform=ax.transAxes, fontsize=7.5, fontweight='bold',
            color=RED, va='top', ha='left',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                      edgecolor=RED, linewidth=0.8))
    # 타이틀
    ax.set_title(title, fontsize=9, fontweight='bold', color=NAVY, loc='left', pad=6)
    # 축
    ax.xaxis.set_major_locator(YearLocator())
    ax.xaxis.set_major_formatter(DateFormatter('%y'))
    ax.tick_params(axis='x', labelsize=7, colors='#555')
    ax.tick_params(axis='y', labelsize=7, colors='#555')
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    ax.spines['left'].set_color('#CCC')
    ax.spines['bottom'].set_color('#CCC')
    ax.grid(True, axis='y', linestyle=':', linewidth=0.4, color='#EEE', zorder=0)
    # Y축 단위 (만원)
    ax.set_ylim(0, 130000)
    ax.set_yticks([0, 30000, 60000, 90000, 120000])
    ax.set_yticklabels(['0', '3만', '6만', '9만', '12만'])

# 좌측 PER 밴드
ax1 = fig.add_subplot(gs[0, 0])
plot_band(ax1, PER_MULT, eps_series, '배',
          'PER 밴드 (연간 EPS)',
          '24.3배', 48050)

# 우측 PBR 밴드
ax2 = fig.add_subplot(gs[0, 1])
plot_band(ax2, PBR_MULT, bps_series, '배',
          'PBR 밴드 (역사 -1.29σ)',
          '1.74배', 48050)

# Footnote
fig.text(0.99, 0.01,
         '출처: KRX 월말 종가(FDR) + 사업보고서 연간 EPS/BPS(2026E Forward), 5년 stairstep 기준',
         fontsize=5.5, color='#999', ha='right')

plt.tight_layout(rect=(0.01, 0.03, 0.98, 0.96))

out = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\_chart_s15_per_pbr_band.png')
plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
print(f'Saved: {out}')
