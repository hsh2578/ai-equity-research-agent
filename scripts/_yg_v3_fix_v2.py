"""문제 도표 2차 수정 — m38·m46·m69·m73 마이너 + m62"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from matplotlib.patches import Patch

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
NAVY = '#1E3A6D'; RED = '#C8102E'; BLUE = '#5DADE2'; GREY = '#888888'; GOLD = '#C9A961'
OUT = Path('output/와이지엔터/_charts')


def save(fig, name):
    fig.savefig(OUT / f'{name}.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); print(f'  saved: {name}.png')


# m38: 1월(27.1) 도시 데이터를 month=13 (=2027.01)로 변환
def fix_m38():
    fig, ax = plt.subplots(figsize=(7.5, 3.5))
    cities = ['서울', '도쿄', '오사카', '홍콩', '방콕', 'KL', '싱가포르', '자카르타',
              '시드니', '멜번', 'LA', '뉴욕', '런던', '파리']
    months = [8, 8, 9, 9, 10, 10, 11, 11, 11, 12, 12, 13, 13, 13]  # 1월 → 13
    regions = ['아시아']*8 + ['오세아니아']*2 + ['북미']*2 + ['유럽']*2
    rc = {'아시아': NAVY, '오세아니아': BLUE, '북미': RED, '유럽': GOLD}
    colors = [rc[r] for r in regions]
    y = np.arange(len(cities))
    ax.barh(y, [1]*len(cities), left=months, color=colors, alpha=0.8, height=0.7)
    ax.set_yticks(y); ax.set_yticklabels(cities, fontsize=8)
    ax.set_xticks([8, 9, 10, 11, 12, 13, 14])
    ax.set_xticklabels(['26.8', '9', '10', '11', '12', '27.1', '27.2'], fontsize=8)
    ax.invert_yaxis(); ax.set_xlim(7.5, 14.5)
    ax.set_title('빅뱅 BIGSHOW: REBORN 14개 도시 풀이어 (2026.08~2027.01)', fontsize=10, color=NAVY)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    legend = [Patch(color=rc[k], label=k) for k in rc]
    ax.legend(handles=legend, fontsize=7, ncol=4, loc='upper right')
    save(fig, 'm38_bigbang_tour')


# m46: 2014·2015 X축 라벨 겹침 — 라벨 위치 조정 (2014, 2016만 표기, 2015 제거)
def fix_m46():
    fig, ax = plt.subplots(figsize=(7.5, 3))
    events = [(2006, '빅뱅', NAVY, 200), (2014, '위너', GREY, 150),
              (2015.5, '아이콘', GREY, 150), (2020, '트레저', NAVY, 200),
              (2026, '신인 5인조', RED, 300)]
    ax.scatter([e[0] for e in events], [0]*len(events),
              s=[e[3] for e in events], color=[e[2] for e in events],
              zorder=5, edgecolors='black', linewidths=1)
    for i, (y, l, c, s) in enumerate(events):
        ax.text(y, 0.4 if i % 2 == 0 else -0.4, l, ha='center', fontsize=9,
               weight='bold' if i == 4 else 'normal',
               color=RED if i == 4 else 'black')
    # 6년 공백 표시
    ax.annotate('', xy=(2026, -0.15), xytext=(2020, -0.15),
                arrowprops=dict(arrowstyle='<->', color=RED, linewidth=2))
    ax.text(2023, -0.3, '6년 공백', fontsize=10, color=RED, weight='bold', ha='center')
    ax.axhline(0, color='black', linewidth=0.5)
    ax.set_xlim(2004, 2028); ax.set_ylim(-0.8, 0.8); ax.set_yticks([])
    ax.set_xticks([2006, 2014, 2016, 2020, 2026]); ax.tick_params(labelsize=8)
    for s in ['top', 'right', 'left']: ax.spines[s].set_visible(False)
    ax.set_title('YG 보이그룹 — 트레저 2020 → 6년 공백 → 2026.09 신인', fontsize=10, color=NAVY)
    save(fig, 'm46_boygroup_6y')


# m69: ROE 값을 본문 데이터로 직접 사용
def fix_m69():
    fig, ax = plt.subplots(figsize=(6, 3))
    years = ['2021', '2022', '2023', '2024', '2025', '2026E']
    roe = [1.83, 8.56, 14.0, 3.9, 7.4, 10.79]  # 본문 데이터
    npm = [7.1, 12.0, 13.5, 5.5, 6.8, 11.4]
    turn = [0.55, 0.71, 0.82, 0.50, 0.74, 0.78]
    ax.plot(years, roe, color=NAVY, marker='o', linewidth=2.5, markersize=8, label='ROE')
    ax.plot(years, npm, color=RED, marker='s', linewidth=1.5, linestyle='--', label='순이익률(%)')
    ax.plot(years, [t*10 for t in turn], color=BLUE, marker='^', linewidth=1.5, linestyle=':', label='자산회전율×10')
    for i, v in enumerate(roe):
        ax.text(i, v+0.5, f'{v:.1f}%', ha='center', fontsize=8, weight='bold', color=NAVY)
    ax.set_ylabel('비율 (%)', fontsize=8); ax.tick_params(labelsize=9)
    ax.legend(fontsize=7); ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.set_title('ROE 듀폰 분해 5년 — 2026E 10.8% 회복', fontsize=10, color=NAVY)
    save(fig, 'm69_roe_dupont')


# m73: "2023 정점 15.3%" 라벨 위치 조정 — 라벨을 아래로
def fix_m73():
    fig, ax = plt.subplots(figsize=(6, 3))
    years = ['2021', '2022', '2023', '2024', '2025', '2028E']
    opm = [7.9, 10.9, 15.3, -5.7, 13.1, 16.0]
    colors = [RED if v < 0 else NAVY if i == len(opm)-1 else GREY for i, v in enumerate(opm)]
    bars = ax.bar(years, opm, color=colors, alpha=0.85)
    for i, b in enumerate(bars):
        ypos = b.get_height() + (0.6 if opm[i] >= 0 else -1.5)
        ax.text(b.get_x()+b.get_width()/2, ypos, f'{opm[i]:.1f}%', ha='center', fontsize=9, weight='bold')
    ax.axhline(15.3, color=RED, linestyle='--', linewidth=0.8, alpha=0.6)
    ax.text(0.5, 13.6, '2023 활동기 정점 15.3%', fontsize=7, color=RED)  # 위치 변경
    ax.axhline(0, color='black', linewidth=0.5)
    ax.set_ylabel('OPM (%, 발표기준)', fontsize=8); ax.tick_params(labelsize=8)
    ax.set_title('YG 5년 OPM + 2028E 16% — 활동기 정점 상회', fontsize=10, color=NAVY)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.set_ylim(-9, 19)
    save(fig, 'm73_opm_2028e')


# m62: "현재 48,050원" 텍스트 위치 조정 (제목과 안 겹치게)
def fix_m62():
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    sc = [('성공', '음반 50만+', 89000, RED), ('보통', '음반 20~50만', 84000, NAVY),
          ('실패', '음반 20만 미만', 78000, GOLD), ('대실패', '데뷔 무산', 67000, GREY)]
    y_pos = np.arange(len(sc))
    prices = [s[2] for s in sc]
    labels = [f"{s[0]}\n({s[1]})" for s in sc]
    colors = [s[3] for s in sc]
    bars = ax.barh(y_pos, prices, color=colors, alpha=0.85)
    for i, b in enumerate(bars):
        ax.text(b.get_width()+800, b.get_y()+b.get_height()/2, f'{prices[i]:,}원',
               va='center', fontsize=10, weight='bold')
    ax.set_yticks(y_pos); ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel('적정주가 (원)', fontsize=8); ax.tick_params(labelsize=8)
    ax.set_xlim(0, 100000)
    ax.set_title('9월 보이그룹 결과별 적정주가 시나리오', fontsize=10, color=NAVY, pad=10)
    ax.axvline(48050, color='black', linestyle='--', linewidth=0.8)
    ax.text(48050, -0.7, '현재 48,050원', fontsize=8, ha='center')  # 위치 변경 — 그래프 아래
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    save(fig, 'm62_sept_scenario')


# m30: 이벤트 마커 글자 겹침 — y 위치 alternate
def fix_m30():
    try:
        import FinanceDataReader as fdr
        import pandas as pd
        df = fdr.DataReader('122870', '2021-01-01', '2026-05-27')
        fig, ax = plt.subplots(figsize=(8, 3.5))
        ax.plot(df.index, df['Close'], color=NAVY, linewidth=0.7)
        # (날짜, 가격, 라벨, y 오프셋)
        events = [
            ('2021-12-30', 55700, '①21말 정점', 'top'),
            ('2022-12-30', 43850, '②TME 평가손', 'bot'),
            ('2023-05-12', 60000, '③베몬 발표', 'top'),
            ('2023-12-29', 50900, '④BORN PINK', 'bot'),
            ('2024-09-10', 30200, '⑤절대저점', 'bot'),
            ('2024-10-15', 37000, '⑥24.10 시작', 'top'),
            ('2025-08-21', 107400, '⑥25.8 정점', 'top'),
            ('2025-12-30', 69400, '⑦25말', 'bot'),
            ('2026-03-31', 48050, '⑧1Q 무산', 'bot'),
        ]
        for d, p, lbl, pos in events:
            ax.scatter([pd.Timestamp(d)], [p], s=50, color=RED, zorder=5, edgecolors='black', linewidths=0.5)
            offset = (5, 7) if pos == 'top' else (5, -12)
            ax.annotate(lbl, (pd.Timestamp(d), p), fontsize=7, xytext=offset, textcoords='offset points')
        ax.set_ylabel('주가(원)', fontsize=8); ax.tick_params(labelsize=8)
        ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
        ax.set_title('YG 5년 일봉 + 9개 이벤트 마킹 (FDR 실측)', fontsize=10, color=NAVY)
        save(fig, 'm30_5y_events')
    except Exception as e:
        print(f'  m30 failed: {e}')


def main():
    print('=== 문제 도표 2차 수정 ===\n')
    fix_m38(); fix_m46(); fix_m69(); fix_m73(); fix_m62(); fix_m30()
    print('\n완료')


if __name__ == '__main__':
    main()
