"""문제 도표 일괄 수정 — 글자 겹침·범례 위치 해결"""
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
OUT = Path('output/와이지엔터/_charts')


def save(fig, name):
    fig.savefig(OUT / f'{name}.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); print(f'  saved: {name}.png (수정)')


# m10: 제목·범례 충돌 해결 + 점 분리
def fix_m10():
    ips = [
        ('지누션', 1997, 'finished', 'bot1'),
        ('1TYM', 2000, 'finished', 'top1'),
        ('세븐', 2003, 'finished', 'bot1'),
        ('빅뱅', 2006, 'mega', 'top1'),
        ('2NE1', 2009, 'finished', 'bot1'),
        ('위너', 2014, 'finished', 'top1'),
        ('아이콘', 2015, 'finished', 'bot2'),
        ('블랙핑크', 2016, 'mega', 'top2'),
        ('트레저', 2020, 'active', 'bot1'),
        ('베이비몬스터', 2023, 'mega', 'top1'),
        ('신인 보이', 2026.0, 'upcoming', 'bot2'),
        ('NEXT MONSTER', 2027.5, 'upcoming', 'top2'),
    ]
    y_map = {'top1': 0.35, 'top2': 0.62, 'bot1': -0.35, 'bot2': -0.62}
    cmap = {'mega': RED, 'active': NAVY, 'finished': GREY, 'upcoming': GOLD}
    fig, ax = plt.subplots(figsize=(7.5, 3.5))
    for name, year, status, lp in ips:
        color = cmap[status]
        size = 250 if status in ('mega', 'upcoming') else 100
        ax.scatter(year, 0, s=size, color=color, zorder=5,
                  edgecolors='black' if status == 'mega' else None,
                  linewidths=1.5 if status == 'mega' else 0)
        y = y_map[lp]
        ax.text(year, y, name, ha='center', fontsize=8,
               weight='bold' if status == 'mega' else 'normal',
               color=RED if status == 'mega' else 'black')
        ax.plot([year, year], [0, y * 0.7], color='lightgray', linewidth=0.5, linestyle=':', zorder=1)
    ax.axhline(0, color='black', linewidth=0.8)
    ax.set_xlim(1995, 2030); ax.set_ylim(-1.0, 1.0); ax.set_yticks([])
    ax.set_xticks([1997, 2006, 2016, 2023, 2026]); ax.tick_params(labelsize=8)
    for s in ['top', 'right', 'left']: ax.spines[s].set_visible(False)
    ax.set_title('YG 28년 데뷔 IP 타임라인 — 메가 IP 빅뱅·블핑·베몬 3종', fontsize=10, color=NAVY)
    # 범례를 도표 안 (오른쪽 위 빈 공간)으로
    legend = [Patch(color=RED, label='메가 IP'), Patch(color=NAVY, label='활동 중'),
              Patch(color=GOLD, label='데뷔 예정'), Patch(color=GREY, label='활동 종료')]
    ax.legend(handles=legend, fontsize=7, loc='lower left', ncol=4, frameon=False)
    save(fig, 'm10_28y_timeline')


# m35: 사이클 비교 — symlog 척도에서 작은 값(2·5·1·2) 거의 안 보임 → 그룹 나누기
def fix_m35():
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3))
    # 좌: 시총 비교 (큰 값)
    cats1 = ['시작 시총', '도달 시총']
    prev1 = [6916, 20074]; this1 = [8981, 17500]
    x1 = np.arange(len(cats1)); w = 0.35
    axes[0].bar(x1 - w/2, prev1, w, label='24.10~25.08', color=GREY, alpha=0.8)
    axes[0].bar(x1 + w/2, this1, w, label='26.08~27.07', color=NAVY)
    for i in range(len(cats1)):
        axes[0].text(i-w/2, prev1[i]+400, f'{prev1[i]:,}', ha='center', fontsize=8)
        axes[0].text(i+w/2, this1[i]+400, f'{this1[i]:,}', ha='center', fontsize=8, weight='bold', color=NAVY)
    axes[0].set_xticks(x1); axes[0].set_xticklabels(cats1, fontsize=9)
    axes[0].set_ylabel('시총 (억원)', fontsize=8); axes[0].tick_params(labelsize=8)
    axes[0].legend(fontsize=7); axes[0].set_title('시총 비교', fontsize=9, color=NAVY)
    axes[0].spines['top'].set_visible(False); axes[0].spines['right'].set_visible(False)
    # 우: 동시 가동 IP / 메가 IP (작은 값)
    cats2 = ['동시 가동 IP', '메가 IP 종류']
    prev2 = [2, 1]; this2 = [5, 2]
    x2 = np.arange(len(cats2))
    axes[1].bar(x2 - w/2, prev2, w, label='24.10~25.08', color=GREY, alpha=0.8)
    axes[1].bar(x2 + w/2, this2, w, label='26.08~27.07', color=NAVY)
    for i in range(len(cats2)):
        axes[1].text(i-w/2, prev2[i]+0.15, f'{prev2[i]}', ha='center', fontsize=9, weight='bold')
        axes[1].text(i+w/2, this2[i]+0.15, f'{this2[i]}', ha='center', fontsize=9, weight='bold', color=NAVY)
    axes[1].set_xticks(x2); axes[1].set_xticklabels(cats2, fontsize=9)
    axes[1].set_ylabel('IP 개수', fontsize=8); axes[1].tick_params(labelsize=8)
    axes[1].legend(fontsize=7); axes[1].set_title('IP 개수 비교', fontsize=9, color=NAVY)
    axes[1].spines['top'].set_visible(False); axes[1].spines['right'].set_visible(False)
    fig.suptitle('24.10~25.08 vs 26.08~27.07 사이클 비교 매트릭스', fontsize=10, color=NAVY)
    fig.tight_layout()
    save(fig, 'm35_cycle_compare')


# m86: 양성 시스템 검증 — log scale에서 값이 너무 작아 비교 어려움 + 글자 잘림
def fix_m86():
    fig, axes = plt.subplots(1, 4, figsize=(8, 3))
    cats = ['음반판매\n(만장)', '주요차트\n진입(개)', 'MV 1주\n조회수(억뷰)', '팬덤 YT\n구독(만)']
    baemon = [50, 4, 1.5, 1200]
    target = [40, 3, 1.0, 800]
    fail = [20, 0.5, 0.3, 300]
    for i, (cat, b, t, f) in enumerate(zip(cats, baemon, target, fail)):
        ax = axes[i]
        labels = ['베몬 실제', '9월 목표', '실패 임계']
        vals = [b, t, f]
        colors = [NAVY, BLUE, RED]
        bars = ax.bar(labels, vals, color=colors, alpha=0.85)
        for j, bar in enumerate(bars):
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()*1.05,
                   f'{vals[j]:g}', ha='center', fontsize=8, weight='bold')
        ax.set_title(cat, fontsize=8, color=NAVY)
        ax.tick_params(labelsize=7); ax.tick_params(axis='x', rotation=15)
        ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    fig.suptitle('양성 시스템 검증 매트릭스 — 베몬 vs 9월 보이그룹', fontsize=10, color=NAVY)
    fig.tight_layout()
    save(fig, 'm86_system_validation')


# m45: 4사 세대별 IP — 표 안 글자 작아서 안 보일 수 있음 / 컬러바 누락
def fix_m45():
    fig, ax = plt.subplots(figsize=(6, 3))
    companies = ['YG', '하이브', 'SM', 'JYP']
    gens = ['2세대', '3세대', '4세대', '5세대']
    data = np.array([[1, 1, 2, 2], [0, 1, 2, 1], [0, 0, 3, 1], [0, 1, 2, 1]])
    im = ax.imshow(data, cmap='Blues', aspect='auto', vmin=0, vmax=3)
    ax.set_xticks(range(4)); ax.set_xticklabels(gens, fontsize=10)
    ax.set_yticks(range(4)); ax.set_yticklabels(companies, fontsize=11, weight='bold')
    for i in range(4):
        for j in range(4):
            v = data[i, j]
            if v > 0:
                c = 'white' if v >= 2 else 'black'
                ax.text(j, i, f'{v}팀', ha='center', va='center', fontsize=11, color=c, weight='bold')
            else:
                ax.text(j, i, '-', ha='center', va='center', fontsize=11, color='lightgray')
    ax.set_title('K-POP 4사 세대별 IP 보유 — YG 분산 최대 (총 6팀)', fontsize=10, color=NAVY, pad=10)
    save(fig, 'm45_4comp_gen_ip')


# m83: IP × 분기 매출 — 컬러바 안 보일 수도, 글자 작음
def fix_m83():
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ips = ['빅뱅 BIGSHOW', '베몬 정규2집·월투', '트레저 일본 돔', '9월 신인 보이', 'NEXT MONSTER', '블랙핑크']
    quarters = ['1Q26', '2Q26', '3Q26', '4Q26', '1Q27', '2Q27', '3Q27', '4Q27', '1Q28', '2Q28', '3Q28', '4Q28']
    data = np.array([
        [0, 0, 0.3, 0.6, 1.0, 0.4, 0.3, 0.2, 0, 0, 0, 0],
        [0.2, 0.4, 0.5, 0.9, 0.7, 0.8, 0.6, 0.5, 0.5, 0.5, 0.5, 0.5],
        [0, 0.3, 0.5, 0.3, 0.2, 0.4, 0.6, 0.4, 0.3, 0.3, 0.3, 0.3],
        [0, 0, 0, 0.2, 0.3, 0.4, 0.4, 0.45, 0.5, 0.5, 0.5, 0.5],
        [0, 0, 0, 0, 0, 0, 0.2, 0.25, 0.25, 0.3, 0.3, 0.3],
        [0.5, 0.2, 0.2, 0.2, 0.3, 0.5, 0.4, 0.3, 0.2, 0.2, 0.2, 0.2],
    ])
    im = ax.imshow(data, cmap='Blues', aspect='auto', vmin=0, vmax=1)
    ax.set_yticks(range(len(ips))); ax.set_yticklabels(ips, fontsize=9)
    ax.set_xticks(range(len(quarters))); ax.set_xticklabels(quarters, fontsize=8)
    # 각 셀에 숫자 표기
    for i in range(len(ips)):
        for j in range(len(quarters)):
            v = data[i, j]
            if v > 0:
                c = 'white' if v >= 0.5 else 'black'
                ax.text(j, i, f'{int(v*100)}', ha='center', va='center', fontsize=7, color=c)
    ax.set_title('IP × 분기 매출 시간표 (1Q26~4Q28, 진행률 %)', fontsize=10, color=NAVY, pad=10)
    cbar = plt.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cbar.ax.tick_params(labelsize=8)
    cbar.set_label('매출 기여 진행률', fontsize=8)
    save(fig, 'm83_ip_quarterly')


def main():
    print('=== 문제 도표 수정 ===\n')
    fix_m10()
    fix_m35()
    fix_m86()
    fix_m45()
    fix_m83()
    print('\n완료')


if __name__ == '__main__':
    main()
