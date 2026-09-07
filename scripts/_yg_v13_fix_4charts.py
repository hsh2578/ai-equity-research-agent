"""도표 11, 16, 23, 27 — 자의적 정성 점수 제거 + 사실 기반 재작성"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mp
from matplotlib.patches import FancyArrowPatch
import numpy as np
from pathlib import Path

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

TPL_BLUE = '#2683C6'
NAVY = '#1E3A6D'
RED = '#C8102E'
GREY = '#888888'
GREY_LIGHT = '#E0E0E0'
GREEN = '#27AE60'
ORANGE = '#F39C12'

OUT = Path('output/와이지엔터/_charts')


def save(fig, name):
    fig.savefig(OUT / f'{name}.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); print(f'  saved: {name}.png')


# 도표 11 — 4사 양성 시스템 사실 표
def chart_11_table():
    fig, ax = plt.subplots(figsize=(14, 6.2))  # 세로 확대 → 제목 공간 확보
    fig.subplots_adjust(top=0.88, bottom=0.02)
    ax.set_axis_off()
    headers = ['지표', 'HYBE', 'SM', 'JYP', 'YG']
    rows = [
        ['작곡가·프로듀서 풀',
         '레이블 분산\n(BIGHIT·Source 등 6곳)',
         '자체 A&R 대형\n(켄지 등 인하우스)',
         '박진영 직접 +\nA&R',
         '양현석 직접 + 인력 확충\n("최근 인터뷰 발표")'],
        ['안무 발주 (인터뷰 기준)',
         '비공개',
         '비공개',
         '비공개',
         '2~3팀 → 10팀\n(2026년 양현석 인터뷰)'],
        ['글로벌 트레이닝',
         '미국 LA\n(KATSEYE·BPS)',
         '일본·미국 등\n(NCT WISH·NCT 진행)',
         '도쿄·LA·뉴욕\n(NiziU·VCHA·NEXZ)',
         '서울 본사 +\n일본·태국·중국·서구권'],
        ['최근 메가 IP 데뷔',
         'NewJeans (2022)\n× 2024 어도어 분쟁',
         '에스파 (2020)\n→ 현재까지 신규 메가 부재',
         '스트레이키즈 (2018)\n→ 현재까지 신규 메가 부재',
         '베이비몬스터 (2024)\n+ 9월 5인조 + NEXT MONSTER'],
    ]
    # 표 그리기 (수동 — matplotlib table 한글 깨짐 방지)
    col_widths = [0.16, 0.21, 0.21, 0.20, 0.22]
    n_cols = len(headers)
    n_rows = len(rows) + 1
    row_h = 0.98 / n_rows  # axes 거의 전체 사용 (제목은 suptitle로 분리)
    x_starts = [sum(col_widths[:i]) for i in range(n_cols)]

    # 헤더 — 폰트 확대 (axes 상단 = y=1.0)
    for ci, h in enumerate(headers):
        col = TPL_BLUE if ci == n_cols - 1 else NAVY
        ax.add_patch(mp.Rectangle((x_starts[ci], 1 - row_h), col_widths[ci], row_h,
                                   fc=col, ec='white', linewidth=1))
        ax.text(x_starts[ci] + col_widths[ci]/2, 1 - row_h/2, h,
               ha='center', va='center', fontsize=12.5, color='white', weight='bold')
    # 데이터 행 — 폰트 확대 + 셀 폭 여유
    for ri, row in enumerate(rows):
        y = 1 - row_h * (ri + 2)
        ax.add_patch(mp.Rectangle((x_starts[0], y), col_widths[0], row_h,
                                   fc='#F0F0F2', ec='white', linewidth=1))
        ax.text(x_starts[0] + col_widths[0]/2, y + row_h/2, row[0],
               ha='center', va='center', fontsize=11, color=NAVY, weight='bold')
        for ci, val in enumerate(row[1:], start=1):
            is_yg = (ci == n_cols - 1)
            bg = '#E8F1FB' if is_yg else 'white'
            ax.add_patch(mp.Rectangle((x_starts[ci], y), col_widths[ci], row_h,
                                       fc=bg, ec='#D0D0D5', linewidth=0.6))
            text_color = TPL_BLUE if is_yg else 'black'
            text_weight = 'bold' if is_yg else 'normal'
            ax.text(x_starts[ci] + col_widths[ci]/2, y + row_h/2, val,
                   ha='center', va='center', fontsize=9.5, color=text_color, weight=text_weight)

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    # 제목을 figure 위쪽에 (suptitle — axes와 분리)
    fig.suptitle('K-POP 4사 양성 시스템 사실 비교 — 4지표 중 3개 YG 우위',
                 fontsize=14, weight='bold', color=NAVY, y=0.96)
    save(fig, 'm_4comp_system')


# 도표 16 — 사이클 비교 표 (단일, 글자 크게)
def chart_16_diagram():
    fig, ax = plt.subplots(figsize=(15, 6.5))
    fig.subplots_adjust(top=0.88, bottom=0.02)
    ax.set_axis_off()

    rows = [
        ['트리거', '24.10~25.08 (실제, +190%)', '26.08~27.07 (예상, 매핑)'],
        ['메가 IP 월드투어',
         '블랙핑크 DEADLINE\n16도시 33회 (2024.10~)',
         '빅뱅 20주년 BIGSHOW\n14도시 6개월 풀이어 (2026.08~2027.01)'],
        ['신인 메가 IP 데뷔/발표',
         '베이비몬스터 데뷔\n+ SEE YOU THERE 발표 (2024.04)',
         '9월 신인 5인조 보이그룹\n+ NEXT MONSTER 2027 1H'],
        ['월드투어 + MD 매출',
         '공연 매출 1년 만에 7배\n(170억 → 1,264억)',
         '베몬 18도시 27회 + 빅뱅 14도시\n합산 모객 70만+ (Hana 추정)'],
        ['동시 가동 IP 수',
         '4종 IP\n(블핑·베몬·트레저+α)',
         '5종 IP\n(빅뱅·블핑·베몬·트레저·신인2팀)'],
    ]

    col_widths = [0.20, 0.38, 0.42]
    n_rows = len(rows)
    row_h = 0.98 / n_rows  # axes 거의 전체 사용 (제목 suptitle로 분리)
    x_starts = [sum(col_widths[:i]) for i in range(3)]

    # 헤더 행 — 폰트 확대
    for ci, h in enumerate(rows[0]):
        col = TPL_BLUE if ci == 2 else GREY if ci == 1 else NAVY
        ax.add_patch(mp.Rectangle((x_starts[ci], 1 - row_h), col_widths[ci], row_h,
                                   fc=col, ec='white', linewidth=1))
        ax.text(x_starts[ci] + col_widths[ci]/2, 1 - row_h/2, h,
               ha='center', va='center', fontsize=14, color='white', weight='bold')

    # 데이터 행
    for ri, row in enumerate(rows[1:]):
        y = 1 - row_h * (ri + 2)
        # 트리거명 (좌측)
        ax.add_patch(mp.Rectangle((x_starts[0], y), col_widths[0], row_h,
                                   fc='#F0F0F2', ec='white', linewidth=1))
        ax.text(x_starts[0] + col_widths[0]/2, y + row_h/2, row[0],
               ha='center', va='center', fontsize=13, color=NAVY, weight='bold')
        ax.add_patch(mp.Rectangle((x_starts[1], y), col_widths[1], row_h,
                                   fc='white', ec='#D0D0D5', linewidth=0.6))
        ax.text(x_starts[1] + col_widths[1]/2, y + row_h/2, row[1],
               ha='center', va='center', fontsize=12, color='black')
        ax.add_patch(mp.Rectangle((x_starts[2], y), col_widths[2], row_h,
                                   fc='#E8F1FB', ec='#D0D0D5', linewidth=0.6))
        ax.text(x_starts[2] + col_widths[2]/2, y + row_h/2, row[2],
               ha='center', va='center', fontsize=12, color=NAVY, weight='bold')

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.suptitle('24.10~25.08 +190% 사이클 vs 26.08~27.07 예상 사이클 — 4 트리거 1:1 매핑',
                 fontsize=15, weight='bold', color=NAVY, y=0.96)
    save(fig, 'm_cycle_compare_v2')


# 도표 23 — 6종 IP 활동 캘린더 (강도 점수 제거)
def chart_23_calendar():
    fig, ax = plt.subplots(figsize=(11, 4.3))
    quarters = ['26.2Q', '26.3Q', '26.4Q', '27.1Q', '27.2Q', '27.3Q']
    ips = ['빅뱅', '블랙핑크', '트레저', '베이비몬스터', '신인 보이그룹', 'NEXT MONSTER']
    # 실제 사실 기반 활동: (이벤트, 종류)
    # 종류: 'tour'=투어, 'album'=앨범, 'debut'=데뷔, '' = 공백
    schedule = [
        # 빅뱅 (8월 투어 시작, 27.1까지)
        [('', ''), ('투어 시작', 'tour'), ('투어 진행', 'tour'), ('투어 마무리', 'tour'), ('', ''), ('', '')],
        # 블핑 (재계약 + 개별 활동)
        [('', ''), ('', ''), ('', ''), ('', ''), ('재계약 후 검토', 'tour'), ('재계약 후 검토', 'tour')],
        # 트레저
        [('신보', 'album'), ('월투', 'tour'), ('신보', 'album'), ('', ''), ('신보', 'album'), ('월투', 'tour')],
        # 베몬
        [('CHOOM·월투', 'album'), ('월투 18도시', 'tour'), ('정규 2집', 'album'), ('월투', 'tour'),
         ('월투', 'tour'), ('신보', 'album')],
        # 신인 보이 (9월 데뷔)
        [('', ''), ('', ''), ('★ 데뷔(9월)', 'debut'), ('활동·월투', 'tour'),
         ('활동', 'tour'), ('신보', 'album')],
        # NEXT MONSTER (27.1H 데뷔)
        [('', ''), ('', ''), ('', ''), ('★ 데뷔', 'debut'),
         ('활동', 'tour'), ('신보', 'album')],
    ]
    colors_map = {'tour': '#1E3A6D', 'album': '#2683C6', 'debut': '#C8102E', '': '#F0F0F2'}

    ax.set_xlim(-0.4, len(quarters))
    ax.set_ylim(-0.5, len(ips) + 0.5)
    # 셀 그리기
    for i, ip in enumerate(ips):
        y = len(ips) - 1 - i
        for j, (text, kind) in enumerate(schedule[i]):
            fc = colors_map[kind]
            ax.add_patch(mp.Rectangle((j, y), 1, 0.9, fc=fc, alpha=0.85 if kind else 0.4,
                                       ec='white', linewidth=1.5))
            if text:
                ax.text(j + 0.5, y + 0.45, text, ha='center', va='center',
                       fontsize=7.5, color='white' if kind else GREY, weight='bold')

    # 분기 헤더
    for j, q in enumerate(quarters):
        ax.text(j + 0.5, len(ips) + 0.15, q, ha='center', fontsize=9.5, color=NAVY, weight='bold')
    # IP 라벨
    for i, ip in enumerate(ips):
        y = len(ips) - 1 - i
        col = NAVY if i < 4 else RED  # 신인은 빨강
        ax.text(-0.05, y + 0.45, ip, ha='right', va='center', fontsize=9, color=col, weight='bold')

    # 분기별 활동 IP 수 (하단)
    for j in range(len(quarters)):
        active = sum(1 for i in range(len(ips)) if schedule[i][j][1])
        ax.text(j + 0.5, -0.30, f'{active}/6',
               ha='center', fontsize=10, color=RED, weight='bold')
    ax.text(-0.05, -0.30, '동시 활동:', ha='right', fontsize=9, color=RED, weight='bold')

    ax.set_axis_off()
    ax.text(len(quarters)/2, len(ips) + 0.85,
           'YG 6종 IP 분기별 활동 캘린더 — 26.4Q 5종 + 27.1Q 5종 동시 가동',
           ha='center', fontsize=10.5, weight='bold', color=NAVY)
    # 범례
    legend_y = -0.55
    legend_items = [('투어', '#1E3A6D'), ('앨범', '#2683C6'), ('★ 데뷔', '#C8102E'), ('공백', '#F0F0F2')]
    for k, (lbl, c) in enumerate(legend_items):
        ax.add_patch(mp.Rectangle((k * 1.6 + 1, legend_y), 0.3, 0.25, fc=c, alpha=0.85, ec='white'))
        ax.text(k * 1.6 + 1.45, legend_y + 0.12, lbl, fontsize=8, va='center')

    save(fig, 'm_6ip_matrix')


# 도표 27 — 리스크 표 (정성 4분면 제거)
def chart_27_risk_table():
    fig, ax = plt.subplots(figsize=(14, 5.5))
    fig.subplots_adjust(top=0.88, bottom=0.02)
    ax.set_axis_off()
    headers = ['', '리스크', '발생 신호', '시나리오 영향', '완화 요인']
    rows = [
        ['Risk 1\n(상)', '블랙핑크 활동 통제 불가',
         '그룹 활동 무산·연기\n(1Q26 상반기 추가 투어 무산)',
         '단일 IP 의존 노출\n(2024년형 -36% 재발 가능)',
         '5종 IP 동시 가동 → 매출 절벽\n확률 구조적으로 감소'],
        ['Risk 2\n(중)', '영업외 평가손익 (텐센트뮤직)',
         '분기 NI 하락\n(1Q26 평가손실 약 70억)',
         '시장 NI 위주 반응\n→ 주가 변동성',
         '본업 OPM 정상화\n(연결 9.6% → 13.4% 전망)'],
        ['Risk 3\n(중)', '신인 비용 선행',
         '상반기 마진 압박\n(보이그룹·베몬 비용 집중)',
         '연간 OPM -2~3%p\n(단기 비용 집중)',
         '3Q부터 매출 인식\n→ 4Q OPM 회복'],
        ['Risk 4\n(상)', '9월 신인 데뷔 실패 시\n시나리오 무효화',
         '음반 20만 미달·차트 미진입\n6개월 내 멤버 이슈',
         '시스템 가설 무효화\nTarget PER 24 → 22 회귀',
         '베몬 CHOOM 38.8만 자체 최고\n→ 시스템 1차 검증 완료'],
    ]
    col_widths = [0.10, 0.20, 0.23, 0.22, 0.25]
    n_cols = len(headers)
    n_rows = len(rows) + 1
    row_h = 0.98 / n_rows  # axes 거의 전체 사용 (제목 suptitle로)
    x_starts = [sum(col_widths[:i]) for i in range(n_cols)]

    # 헤더
    for ci, h in enumerate(headers):
        ax.add_patch(mp.Rectangle((x_starts[ci], 1 - row_h), col_widths[ci], row_h,
                                   fc=NAVY, ec='white', linewidth=1))
        if h:
            ax.text(x_starts[ci] + col_widths[ci]/2, 1 - row_h/2, h,
                   ha='center', va='center', fontsize=10, color='white', weight='bold')
    # 데이터 행
    severity_colors = {'(상)': RED, '(중)': ORANGE, '(하)': GREEN}
    for ri, row in enumerate(rows):
        y = 1 - row_h * (ri + 2)
        # Risk No 컬럼 (심각도 색)
        severity = '(상)' if '(상)' in row[0] else '(중)' if '(중)' in row[0] else '(하)'
        risk_color = severity_colors[severity]
        ax.add_patch(mp.Rectangle((x_starts[0], y), col_widths[0], row_h,
                                   fc=risk_color, alpha=0.85, ec='white', linewidth=1))
        ax.text(x_starts[0] + col_widths[0]/2, y + row_h/2, row[0],
               ha='center', va='center', fontsize=9, color='white', weight='bold')
        # 나머지 셀
        for ci, val in enumerate(row[1:], start=1):
            bg = '#F8F8FA' if ri % 2 == 0 else 'white'
            ax.add_patch(mp.Rectangle((x_starts[ci], y), col_widths[ci], row_h,
                                       fc=bg, ec='#D0D0D5', linewidth=0.5))
            color = NAVY if ci == 1 else 'black' if ci != n_cols-1 else GREEN
            weight = 'bold' if ci == 1 else 'normal'
            ax.text(x_starts[ci] + col_widths[ci]/2, y + row_h/2, val,
                   ha='center', va='center', fontsize=7.8, color=color, weight=weight)

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.suptitle('리스크 4종 매트릭스 — Risk 1·4 (블핑 통제·9월 데뷔) 가장 높은 영향, 모니터링 우선',
                 fontsize=13, weight='bold', color=NAVY, y=0.96)
    save(fig, 'm_risk_matrix')


def main():
    print('=== 4개 도표 사실 기반 재작성 ===\n')
    chart_11_table()
    chart_16_diagram()
    chart_23_calendar()
    chart_27_risk_table()
    print('\n완료')


if __name__ == '__main__':
    main()
