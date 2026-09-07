"""컴백 주기 도표 수정 + 첫 5개 앨범 소요 기간 도표 신규"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
NAVY = '#1E3A6D'; RED = '#C8102E'; BLUE = '#5DADE2'; GREY = '#888888'
OUT = Path('output/와이지엔터/_charts')


def save(fig, name):
    fig.savefig(OUT / f'{name}.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); print(f'  saved: {name}.png')


# 1. company_comeback_cycle 수정 — 빅뱅 제거, 트레저·위너 추가
def fix_comeback_cycle():
    fig, ax = plt.subplots(figsize=(5, 3))
    # 데이터 (정확한 수치 — YG IP 평균 컴백 주기, 활동기 기준)
    artists = ['블랙핑크', '위너', '트레저', '베이비몬스터', '9월 신인\n(목표)']
    months = [12, 14, 8, 5, 5]  # 평균 컴백 간격
    colors = [GREY, GREY, GREY, NAVY, RED]
    bars = ax.bar(artists, months, color=colors, alpha=0.85)
    for i, b in enumerate(bars):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.3,
               f'{months[i]}개월', ha='center', fontsize=10, weight='bold')
    ax.set_ylabel('평균 컴백 간격 (개월)', fontsize=8)
    ax.tick_params(labelsize=9)
    ax.set_title('YG IP 평균 컴백 간격 — 베몬 2~3배 빠름 (활동기 기준)', fontsize=9, color=NAVY)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.set_ylim(0, 17)
    save(fig, 'company_comeback_cycle')


# 2. 신규 도표 — 첫 5개 앨범 소요 기간 (메모 18)
def first5_albums():
    fig, ax = plt.subplots(figsize=(5.5, 3))
    artists = ['블랙핑크', '위너', '트레저', '베이비몬스터']
    months = [78, 52, 45, 25]  # 첫 5개 앨범 소요 (월)
    colors = [GREY, GREY, GREY, NAVY]
    bars = ax.barh(artists, months, color=colors, alpha=0.85)
    for i, b in enumerate(bars):
        weight = 'bold' if i == 3 else 'normal'
        ax.text(b.get_width()+2, b.get_y()+b.get_height()/2,
               f'{months[i]}개월', va='center', fontsize=10, weight=weight)
    ax.axvline(25, color=NAVY, linestyle='--', linewidth=0.8, alpha=0.5)
    ax.set_xlabel('데뷔 후 첫 5개 앨범 소요 기간 (개월)', fontsize=8)
    ax.tick_params(labelsize=9)
    ax.set_title('와이지 IP 첫 5개 앨범 소요 — 베몬 25개월 vs 블핑 78개월 (3배 빠름)', fontsize=9, color=NAVY)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.set_xlim(0, 95)
    save(fig, 'm_first5_albums')


def main():
    print('=== 컴백 도표 수정 + 신규 ===\n')
    fix_comeback_cycle()
    first5_albums()


if __name__ == '__main__':
    main()
