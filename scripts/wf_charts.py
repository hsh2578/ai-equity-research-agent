"""wf_charts.py -- 위닝펀드 Word 리포트용 generic 도표 12 아키타입 라이브러리.

모든 함수 시그니처: func(data: dict, title: str, out_dir: str|Path, name: str) -> str(png path)
- 종목 무관 generic. 데이터는 analysis.json(financials/price/peers/segments/quarterly/catalysts)에서 추출해 dict로 전달.
- 제목은 fig.suptitle 로 분리(헤더 충돌 방지). 출처선("자료 : ...")은 PNG에 굽지 않고 Word 문서에서 도표 아래 추가한다.
- 팔레트/폰트는 위닝펀드 양식(_yg_v11_pdf.py)과 통일.

import 전용이지만, 직접 실행하면 샘플 데이터로 12종 전부 렌더해 시각 QA용 PNG를 output/_wf_chart_test/ 에 생성한다.
"""
import sys, io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# === 위닝펀드 양식 팔레트 (#2683C6) ===
TPL_BLUE = '#2683C6'
NAVY = '#1E3A6D'
RED = '#C8102E'
GREY = '#888888'
GREY_LIGHT = '#E0E0E0'
GREEN = '#27AE60'
ORANGE = '#F39C12'
PURPLE = '#8E44AD'
SERIES_COLORS = [TPL_BLUE, NAVY, ORANGE, GREY, GREEN, PURPLE, RED]


def _save(fig, out_dir, name, title=None):
    if title:
        fig.suptitle(title, fontsize=12.5, color=NAVY, weight='bold', y=0.99)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f'{name}.png'
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor='white', pad_inches=0.18)
    plt.close(fig)
    return str(path)


def _strip_spines(ax):
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)


# 1. 매출 부문 5년 스택바 (+OPM 듀얼 패널)
def revenue_composition_5y(data, title, out_dir, name='wf_revenue_5y'):
    years = data['years']
    segments = data['segments']  # {label: [vals per year]}
    opm = data.get('opm')
    if opm:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.2, 4.2),
                                       gridspec_kw={'width_ratios': [3, 1.6]})
    else:
        fig, ax1 = plt.subplots(figsize=(8.0, 4.2))
    bottom = np.zeros(len(years))
    for i, (label, vals) in enumerate(segments.items()):
        v = np.array(vals, dtype=float)
        ax1.bar(years, v, bottom=bottom, label=label,
                color=SERIES_COLORS[i % len(SERIES_COLORS)], alpha=0.88, width=0.62)
        bottom += v
    totals = bottom
    for i, t in enumerate(totals):
        ax1.text(i, t + totals.max() * 0.02, f'{t:,.0f}', ha='center',
                 fontsize=8.5, weight='bold', color=NAVY)
    ax1.set_ylabel('매출액 (억원)', fontsize=9.5)
    ax1.set_ylim(0, totals.max() * 1.16)
    ax1.legend(loc='upper left', fontsize=8.5, frameon=False, ncol=2)
    ax1.tick_params(labelsize=9.5)
    _strip_spines(ax1)
    if opm:
        cols = [TPL_BLUE if v >= 0 else RED for v in opm]
        ax2.bar(years, opm, color=cols, alpha=0.88, width=0.5)
        for i, v in enumerate(opm):
            ax2.text(i, v + (0.6 if v >= 0 else -1.6), f'{v:+.1f}%', ha='center',
                     fontsize=8.5, weight='bold', color=cols[i])
        ax2.axhline(0, color='black', linewidth=0.6)
        ax2.set_ylabel('영업이익률 (%)', fontsize=9.5)
        ax2.set_ylim(min(opm) * 1.5 - 2, max(opm) * 1.35 + 2)
        ax2.tick_params(labelsize=9)
        _strip_spines(ax2)
    return _save(fig, out_dir, name, title)


# 2. 컨센 vs 실적/주가 그룹바
def consensus_gap(data, title, out_dir, name='wf_consensus_gap'):
    cats = data['categories']
    series = data['series']  # {label: [vals]}
    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    x = np.arange(len(cats))
    n = len(series)
    w = 0.8 / n
    for i, (label, vals) in enumerate(series.items()):
        offset = (i - (n - 1) / 2) * w
        bars = ax.bar(x + offset, vals, w, label=label,
                      color=SERIES_COLORS[i % len(SERIES_COLORS)], alpha=0.88)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + (abs(max(vals)) * 0.02 if v >= 0 else -abs(max(vals)) * 0.05),
                    f'{v:,.0f}', ha='center', fontsize=8, weight='bold',
                    color=SERIES_COLORS[i % len(SERIES_COLORS)])
    ax.axhline(0, color='black', linewidth=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(cats, fontsize=9.5)
    ax.legend(loc='best', fontsize=9, frameon=False)
    ax.tick_params(labelsize=9.5)
    _strip_spines(ax)
    if 'ylabel' in data:
        ax.set_ylabel(data['ylabel'], fontsize=9.5)
    return _save(fig, out_dir, name, title)


# 3. Peer 멀티플 비교 (PER/PBR), 본 종목 하이라이트
def peer_multiples(data, title, out_dir, name='wf_peer_multiples'):
    names = data['names']
    per = data.get('per')
    pbr = data.get('pbr')
    hl = data.get('highlight_idx', 0)
    has_pbr = pbr is not None and any(v is not None for v in pbr)
    fig, axes = plt.subplots(1, 2 if has_pbr else 1, figsize=(9.0 if has_pbr else 6.0, 4.2))
    if not has_pbr:
        axes = [axes]

    def _bars(ax, vals, label):
        cols = [TPL_BLUE if i == hl else GREY for i in range(len(names))]
        b = ax.bar(range(len(names)), vals, color=cols, alpha=0.9, width=0.62)
        for i, v in enumerate(vals):
            if v is None:
                continue
            ax.text(i, v + max([x for x in vals if x is not None]) * 0.02, f'{v:.1f}',
                    ha='center', fontsize=8.5, weight='bold',
                    color=TPL_BLUE if i == hl else NAVY)
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, fontsize=8.5, rotation=0)
        ax.set_title(label, fontsize=10, color=NAVY, weight='bold')
        _strip_spines(ax)
        ax.tick_params(labelsize=8.5)

    _bars(axes[0], per, 'PER (배)')
    if has_pbr:
        _bars(axes[1], pbr, 'PBR (배)')
    return _save(fig, out_dir, name, title)


# 4. 가격/지표 추이 라인 + fill
def price_history(data, title, out_dir, name='wf_price_history'):
    x = data['x']
    y = data['y']
    fig, ax = plt.subplots(figsize=(8.0, 3.8))
    ax.plot(range(len(x)), y, color=NAVY, linewidth=2.0)
    ax.fill_between(range(len(x)), y, min(y) * 0.98, color=TPL_BLUE, alpha=0.12)
    ax.set_xticks(range(0, len(x), max(1, len(x) // 8)))
    ax.set_xticklabels([x[i] for i in range(0, len(x), max(1, len(x) // 8))],
                       fontsize=8.5, rotation=0)
    ax.set_ylabel(data.get('ylabel', '값'), fontsize=9.5)
    ax.tick_params(labelsize=9)
    ax.grid(axis='y', alpha=0.25, linestyle='--')
    _strip_spines(ax)
    for mx in data.get('markers', []):  # [{idx, label}]
        i = mx['idx']
        ax.scatter([i], [y[i]], color=RED, s=45, zorder=5)
        ax.annotate(mx['label'], (i, y[i]), textcoords='offset points',
                    xytext=(0, 10), ha='center', fontsize=8, color=RED, weight='bold')
    return _save(fig, out_dir, name, title)


# 5. 이벤트 세로 타임라인
def event_timeline(data, title, out_dir, name='wf_event_timeline'):
    events = data['events']  # [{date, label, impact?}]
    n = len(events)
    fig, ax = plt.subplots(figsize=(8.5, max(3.6, n * 0.72)))
    ax.plot([0.5, 0.5], [0, n + 0.5], color=GREY, linewidth=2, zorder=1)
    for i, ev in enumerate(events):
        y = n - i
        ax.scatter([0.5], [y], s=160, color=TPL_BLUE, zorder=3, edgecolors='white', linewidths=1.5)
        ax.text(0.46, y, ev['date'], ha='right', va='center', fontsize=9,
                weight='bold', color=NAVY)
        label = ev['label']
        if ev.get('impact'):
            label += f"\n{ev['impact']}"
        ax.text(0.56, y, label, ha='left', va='center', fontsize=9, color='black')
    ax.set_xlim(0, 1.6)
    ax.set_ylim(0, n + 0.8)
    ax.axis('off')
    return _save(fig, out_dir, name, title)


# 6. 리스크 매트릭스 (확률 x 영향)
def risk_matrix(data, title, out_dir, name='wf_risk_matrix'):
    risks = data['risks']  # [{name, prob(1-5), impact(1-5)}]
    fig, ax = plt.subplots(figsize=(7.2, 5.6))
    ax.add_patch(mpatches.Rectangle((3, 3), 2.2, 2.2, color=RED, alpha=0.10))
    ax.add_patch(mpatches.Rectangle((0.8, 0.8), 2.2, 2.2, color=GREEN, alpha=0.10))
    ax.axhline(3, color=GREY, linewidth=0.7, linestyle='--', alpha=0.6)
    ax.axvline(3, color=GREY, linewidth=0.7, linestyle='--', alpha=0.6)
    for r in risks:
        p, im = r['prob'], r['impact']
        c = RED if (p >= 3 and im >= 3) else (ORANGE if (p >= 3 or im >= 3) else GREEN)
        ax.scatter([p], [im], s=480, color=c, alpha=0.55, edgecolors=NAVY, linewidths=1.2, zorder=3)
        ax.annotate(r['name'], (p, im), textcoords='offset points', xytext=(0, 0),
                    ha='center', va='center', fontsize=8, weight='bold', color=NAVY, zorder=4)
    ax.set_xlim(0.8, 5.2)
    ax.set_ylim(0.8, 5.2)
    ax.set_xlabel('발생 확률 →', fontsize=10, color=NAVY)
    ax.set_ylabel('영향도 →', fontsize=10, color=NAVY)
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.tick_params(labelsize=9)
    _strip_spines(ax)
    return _save(fig, out_dir, name, title)


def _waterfall_core(ax, labels, values, is_total):
    small = max(abs(v) for v in values) < 100  # PER 등 소수값은 1자리 표시
    def _fmt(v, signed=False):
        if small:
            return f'{v:+.1f}' if signed else f'{v:.1f}'
        return f'{v:+,.0f}' if signed else f'{v:,.0f}'
    pad = abs(max(values)) * 0.02
    cum = 0.0
    y_lo, y_hi = 0.0, 0.0  # 막대·라벨이 닿는 최저/최고 y (ylim 여백 계산용)
    for i, (lab, v) in enumerate(zip(labels, values)):
        if is_total[i]:
            ax.bar(i, v, color=NAVY, alpha=0.9, width=0.6)
            lbl_y = v + pad if v >= 0 else v - pad * 2.5
            ax.text(i, lbl_y, _fmt(v), ha='center',
                    fontsize=8.5, weight='bold', color=NAVY)
            cum = v
            y_lo = min(y_lo, v, lbl_y); y_hi = max(y_hi, v, lbl_y)
        else:
            col = TPL_BLUE if v >= 0 else RED
            ax.bar(i, v, bottom=cum, color=col, alpha=0.88, width=0.6)
            top = cum + v
            lbl_y = top + (pad if v >= 0 else -pad * 2.5)
            ax.text(i, lbl_y, _fmt(v, signed=True), ha='center',
                    fontsize=8, weight='bold', color=col)
            if i > 0:
                ax.plot([i - 1 + 0.3, i - 0.3], [cum, cum], color=GREY, linewidth=0.8, linestyle='--')
            cum += v
            y_lo = min(y_lo, cum, top, lbl_y); y_hi = max(y_hi, cum, top, lbl_y)
    span = (y_hi - y_lo) or 1.0
    ax.set_ylim(y_lo - span * 0.08, y_hi + span * 0.08)  # 라벨이 x축/상단과 안 겹치게 여백
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=8.5, rotation=0)
    _strip_spines(ax)
    ax.tick_params(labelsize=9)


# 7. 워터폴 (EPS/PER/목표가 분해)
def waterfall(data, title, out_dir, name='wf_waterfall'):
    labels = data['labels']
    values = data['values']
    is_total = data.get('is_total', [False] * len(labels))
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    _waterfall_core(ax, labels, values, is_total)
    if 'ylabel' in data:
        ax.set_ylabel(data['ylabel'], fontsize=9.5)
    return _save(fig, out_dir, name, title)


# 8. 활동 매트릭스 히트맵 (N행 x M열)
def activity_matrix(data, title, out_dir, name='wf_activity_matrix'):
    rows = data['rows']
    cols = data['cols']
    mat = np.array(data['matrix'], dtype=float)  # 0~5 강도
    fig, ax = plt.subplots(figsize=(max(7.5, len(cols) * 1.1), max(3.6, len(rows) * 0.6)))
    ax.imshow(mat, cmap='Blues', aspect='auto', vmin=0, vmax=max(5, mat.max()))
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, fontsize=9)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(rows, fontsize=9)
    for i in range(len(rows)):
        for j in range(len(cols)):
            v = mat[i, j]
            if v > 0:
                ax.text(j, i, '●', ha='center', va='center',
                        color='white' if v >= 3 else NAVY, fontsize=11)
    ax.set_xticks(np.arange(-0.5, len(cols), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(rows), 1), minor=True)
    ax.grid(which='minor', color='white', linewidth=2)
    ax.tick_params(which='minor', length=0)
    return _save(fig, out_dir, name, title)


# 9. 경쟁사 팩트 비교 표형 도표
def fact_comparison(data, title, out_dir, name='wf_fact_comparison'):
    columns = data['columns']          # 헤더 N개
    rows = data['rows']                # [[cell0, cell1, ...], ...]
    hl = data.get('highlight_col')     # 강조 열 인덱스(본 종목)
    ncol = len(columns)
    nrow = len(rows) + 1
    fig, ax = plt.subplots(figsize=(max(9.0, ncol * 2.2), max(3.2, nrow * 0.62)))
    ax.set_xlim(0, ncol)
    ax.set_ylim(0, nrow)
    ax.axis('off')
    rh = 1.0
    # 헤더
    for j, c in enumerate(columns):
        bg = TPL_BLUE if (hl is not None and j == hl) else NAVY
        ax.add_patch(mpatches.Rectangle((j, nrow - rh), 1, rh, color=bg))
        ax.text(j + 0.5, nrow - rh / 2, c, ha='center', va='center',
                color='white', fontsize=9, weight='bold', wrap=True)
    # 데이터
    for r, row in enumerate(rows):
        y = nrow - rh * (r + 2)
        for j, cell in enumerate(row):
            if hl is not None and j == hl:
                bg = '#E8F1FB'
            else:
                bg = '#F4F5F7' if r % 2 == 0 else 'white'
            ax.add_patch(mpatches.Rectangle((j, y), 1, rh, color=bg, ec=GREY_LIGHT, lw=0.6))
            txt_col = TPL_BLUE if (hl is not None and j == hl) else 'black'
            weight = 'bold' if j == 0 or (hl is not None and j == hl) else 'normal'
            ax.text(j + 0.5, y + rh / 2, str(cell), ha='center', va='center',
                    fontsize=8.5, color=txt_col, weight=weight, wrap=True)
    return _save(fig, out_dir, name, title)


# 10. 분기/구성 파이차트
def quarterly_composition(data, title, out_dir, name='wf_quarterly_composition'):
    labels = data['labels']
    values = data['values']
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    colors = [SERIES_COLORS[i % len(SERIES_COLORS)] for i in range(len(labels))]
    wedges, _, autotexts = ax.pie(
        values, labels=labels, colors=colors, autopct='%1.1f%%',
        startangle=90, counterclock=False,
        wedgeprops=dict(width=0.55, edgecolor='white', linewidth=1.5),
        textprops=dict(fontsize=9.5))
    for at in autotexts:
        at.set_color('white')
        at.set_fontsize(9)
        at.set_weight('bold')
    ax.axis('equal')
    return _save(fig, out_dir, name, title)


# 11. 순현금 Bridge (워터폴 변형, 시작점 total)
def cashflow_bridge(data, title, out_dir, name='wf_cashflow_bridge'):
    labels = data['labels']
    values = data['values']            # [시작값(절대), +delta, +delta, ..., 끝값(절대)]
    is_total = data.get('is_total')
    if is_total is None:
        is_total = [False] * len(labels)
        is_total[0] = True
        is_total[-1] = True
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    _waterfall_core(ax, labels, values, is_total)
    ax.set_ylabel(data.get('ylabel', '순현금 (억원)'), fontsize=9.5)
    return _save(fig, out_dir, name, title)


# 12. ROE 듀폰 (연도별 막대 + 선택 구성요소)
def dupont_roe(data, title, out_dir, name='wf_dupont_roe'):
    years = data['years']
    roe = data['roe']
    fig, ax = plt.subplots(figsize=(7.6, 4.0))
    cols = [TPL_BLUE if v >= 0 else RED for v in roe]
    ax.bar(years, roe, color=cols, alpha=0.9, width=0.58)
    for i, v in enumerate(roe):
        ax.text(i, v + (max(roe) * 0.02 if v >= 0 else -max(roe) * 0.06), f'{v:.1f}%',
                ha='center', fontsize=9, weight='bold', color=cols[i])
    ax.axhline(0, color='black', linewidth=0.6)
    ax.set_ylabel('ROE (%)', fontsize=9.5)
    ax.tick_params(labelsize=9.5)
    ax.grid(axis='y', alpha=0.25, linestyle='--')
    _strip_spines(ax)
    return _save(fig, out_dir, name, title)


# === 아키타입 레지스트리 (planner/word-gen 공용) ===
ARCHETYPES = {
    'revenue_composition_5y': revenue_composition_5y,
    'consensus_gap': consensus_gap,
    'peer_multiples': peer_multiples,
    'price_history': price_history,
    'event_timeline': event_timeline,
    'risk_matrix': risk_matrix,
    'waterfall': waterfall,
    'activity_matrix': activity_matrix,
    'fact_comparison': fact_comparison,
    'quarterly_composition': quarterly_composition,
    'cashflow_bridge': cashflow_bridge,
    'dupont_roe': dupont_roe,
}


def render(archetype, data, title, out_dir, name):
    """planner 가 만든 chart_plan 항목을 렌더. 알 수 없는 아키타입이면 None."""
    fn = ARCHETYPES.get(archetype)
    if fn is None:
        return None
    return fn(data, title, out_dir, name)


# === 직접 실행: 샘플 데이터로 12종 전부 렌더 (시각 QA) ===
def _demo():
    out = 'output/_wf_chart_test'
    paths = []
    paths.append(revenue_composition_5y(
        {'years': ['2022', '2023', '2024', '2025', '2026E'],
         'segments': {'음반·MD': [1456, 2018, 1100, 2018, 2200],
                      '공연': [421, 1500, 170, 1264, 1500],
                      '음원': [530, 728, 600, 872, 950],
                      '기타': [850, 1446, 1779, 1300, 1360]},
         'opm': [10.9, 14.0, -5.1, 9.6, 13.4]},
        '도표 1. 매출 부문별 5년 + OPM 정상화', out, 't01_revenue'))
    paths.append(consensus_gap(
        {'categories': ['2026E', '2027E', '2028E'],
         'series': {'컨센서스': [806, 764, 864], '본 리포트': [820, 900, 1010]},
         'ylabel': '영업이익 (억원)'},
        '도표 2. 영업이익 컨센 vs 본 리포트', out, 't02_consensus'))
    paths.append(peer_multiples(
        {'names': ['YG', 'HYBE', 'SM', 'JYP'], 'per': [15.9, 28.5, 12.3, 14.1],
         'pbr': [1.74, 4.2, 1.9, 2.3], 'highlight_idx': 0},
        '도표 3. K-POP 4사 PER·PBR 비교', out, 't03_peer'))
    paths.append(price_history(
        {'x': ['21', '22', '23', '24', '25', '26'], 'y': [55000, 62000, 88000, 38000, 47000, 48050],
         'ylabel': '주가 (원)', 'markers': [{'idx': 2, 'label': '블핑 컴백'}, {'idx': 3, 'label': '공백기'}]},
        '도표 4. 5년 주가 추이', out, 't04_price'))
    paths.append(event_timeline(
        {'events': [{'date': '26.05', 'label': 'BABYMONSTER CHOOM', 'impact': '초동 38.8만'},
                    {'date': '26.08', 'label': '빅뱅 20주년 투어'},
                    {'date': '26.09', 'label': '6년만 보이그룹 데뷔'},
                    {'date': '27.1H', 'label': 'NEXT MONSTER'}]},
        '도표 5. 하반기 카탈리스트 타임라인', out, 't05_timeline'))
    paths.append(risk_matrix(
        {'risks': [{'name': '블핑\n일정', 'prob': 4, 'impact': 5},
                   {'name': '9월신인\n실패', 'prob': 3, 'impact': 4},
                   {'name': '한한령', 'prob': 2, 'impact': 3},
                   {'name': '환율', 'prob': 3, 'impact': 2}]},
        '도표 6. 리스크 매트릭스', out, 't06_risk'))
    paths.append(waterfall(
        {'labels': ['4사 Median', 'IP 분산', '메가IP', 'Target PER'],
         'values': [13.5, 5.0, 5.5, 24.0], 'is_total': [True, False, False, True],
         'ylabel': 'PER (배)'},
        '도표 7. Target PER 24배 워터폴', out, 't07_waterfall'))
    paths.append(activity_matrix(
        {'rows': ['블랙핑크', '베몬', '트레저', '빅뱅', '신인'],
         'cols': ['26.2Q', '26.3Q', '26.4Q', '27.1Q', '27.2Q'],
         'matrix': [[1, 0, 3, 2, 0], [4, 3, 2, 1, 0], [2, 4, 3, 2, 1],
                    [0, 5, 4, 3, 2], [0, 0, 4, 3, 2]]},
        '도표 8. 6종 IP 분기별 활동 매트릭스', out, 't08_matrix'))
    paths.append(fact_comparison(
        {'columns': ['지표', 'YG', 'HYBE', 'SM', 'JYP'],
         'rows': [['작곡가 풀', '10팀', '8팀', '6팀', '5팀'],
                  ['글로벌 트레이닝', '◎', '◎', '○', '○'],
                  ['최근 신인 성공', '베몬', '아일릿', 'NCT', '엔믹스'],
                  ['순현금/시총', '30.5%', '12%', '18%', '22%']],
         'highlight_col': 1},
        '도표 9. K-POP 4사 시스템 비교', out, 't09_fact'))
    paths.append(quarterly_composition(
        {'labels': ['상제품', '공연', '음악서비스', '기타'], 'values': [44.4, 21.0, 13.9, 20.6]},
        '도표 10. 1Q26 부문별 매출 구성', out, 't10_pie'))
    paths.append(cashflow_bridge(
        {'labels': ['2024 순현금', '+OCF', '-CapEx', '-배당', '2025 순현금'],
         'values': [1740, 1300, -200, -103, 2737]},
        '도표 11. 순현금 Bridge', out, 't11_cash'))
    paths.append(dupont_roe(
        {'years': ['2022', '2023', '2024', '2025', '2026E'], 'roe': [8.6, 14.0, 3.9, 7.4, 10.8]},
        '도표 12. ROE 5년 추이', out, 't12_roe'))
    print(f'\n{len(paths)}종 렌더 완료 -> {out}/')
    for p in paths:
        print(' ', p)


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    _demo()
