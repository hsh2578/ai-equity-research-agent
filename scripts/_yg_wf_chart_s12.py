"""
위닝펀드 18-1 YG Slide 12 도표 교체:
기존 'Top 3 리스크 발생확률' 막대 → '역사 충격 7건 비교' 막대그래프

- 위닝펀드 양식 톤: Navy/Gold/Red, Pretendard/Malgun Gothic
- 1Q26 -27% 강조 (다른 색 + 굵게)
- 출력: PNG, Slide 12 기존 도표와 동일 크기 (W 6.54" x H 2.87" @ 200dpi)
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

# 데이터 (시간 순, 위→아래)
events = [
    ('사드 한한령 발표',         '2017.3',   'YG',    -22, '회복 18개월'),
    ('YG 마약 사건',              '2019.8',   'YG',    -35, '회복 24개월'),
    ('COVID 공연 취소',           '2020.3',   'YG',    -28, '회복 9개월'),
    ('BTS 군입대 발표',           '2022.6',   'HYBE',  -25, '회복 6개월'),
    ('BLACKPINK 재계약 우려',     '2023.9',   'YG',    -13, '회복 4개월'),
    ('BLACKPINK 공백 + 매출 -36%', '2024.1',  'YG',    -44, '진행 중'),
    ('1Q26 컨센 -10% 실망',        '2026.5',  'YG',    -27, '현재'),
]

# 색상: 위닝펀드 Navy/Gold/Red 톤
NAVY = '#1F3A5F'
GOLD = '#C9A961'
RED  = '#C0392B'
GREY = '#8B95A1'
CURR = '#E67E22'  # 1Q26 강조 (오렌지)

# 시간순 정렬 (위→아래 = 옛것→최신)
labels = [f'{e[0]}\n({e[1]} · {e[2]})' for e in events]
values = [e[3] for e in events]
recovers = [e[4] for e in events]
colors = [GREY] * 6 + [CURR]  # 마지막 1Q26만 강조색

# Figure
fig, ax = plt.subplots(figsize=(6.54, 2.87), dpi=200)
fig.patch.set_facecolor('white')
ax.set_facecolor('white')

y_pos = range(len(events))
bars = ax.barh(y_pos, values, color=colors, height=0.62, edgecolor='none')

# 1Q26은 outline 강조
bars[-1].set_edgecolor(NAVY)
bars[-1].set_linewidth(1.5)

# Y축
ax.set_yticks(y_pos)
ax.set_yticklabels(labels, fontsize=8.5, color='#222')
ax.invert_yaxis()

# X축
ax.set_xlim(-50, 5)
ax.set_xticks([0, -10, -20, -30, -40])
ax.set_xticklabels(['0%', '-10%', '-20%', '-30%', '-40%'], fontsize=8, color='#666')
ax.axvline(0, color='#999', linewidth=0.8)

# 막대 끝 값 라벨
for i, (bar, v, r) in enumerate(zip(bars, values, recovers)):
    is_curr = (i == len(events) - 1)
    color = CURR if is_curr else NAVY
    weight = 'bold' if is_curr else 'normal'
    ax.text(v - 1.5, i, f'{v}%', va='center', ha='right',
            fontsize=9.5 if is_curr else 9, fontweight=weight, color=color)
    # 회복 기간 라벨 (오른쪽)
    ax.text(1, i, r, va='center', ha='left',
            fontsize=7.5, color='#888', style='italic')

# 제목
ax.set_title('역사 충격 7건 — 1Q26은 2024년 -44% 충격의 60% 수준',
             fontsize=12, fontweight='bold', color=NAVY, loc='left', pad=10)

# Spine 정리
for s in ('top', 'right', 'bottom', 'left'):
    ax.spines[s].set_visible(False)
ax.tick_params(left=False, bottom=False)
ax.grid(False)

# Footnote
fig.text(0.99, 0.02, '출처: SK증권·키움증권 K-POP 산업 리포트 정량 트래킹',
         fontsize=6.5, color='#999', ha='right')

plt.tight_layout(rect=(0, 0.03, 1, 0.97))

out = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\_chart_s12_history_shocks.png')
plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
print(f'Saved: {out}')
print(f'Size: 6.54" x 2.87" @ 200dpi')
