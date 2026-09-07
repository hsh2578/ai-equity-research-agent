# -*- coding: utf-8 -*-
"""
위닝펀드 18-1 와이지엔터테인먼트(122870) 기업분석 리포트 빌더.
scripts/_yg_wf_content.py (콘텐츠 SSOT) -> 차트 PNG + 본문 .md + 완성 .pptx 3종 동시 생성.
실행: python scripts/build_yg_wf_report.py
"""
import sys, io, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import _yg_wf_content as C

OUT = os.path.join(ROOT, "output", "와이지엔터")
CHARTS = os.path.join(OUT, "charts")
os.makedirs(CHARTS, exist_ok=True)

# ===========================================================================
# 팔레트
# ===========================================================================
NAVY = "#1B355E"
BLUE = "#2E5C8A"
SKY = "#5B8FC2"
LBLUE = "#D7E3F0"
GOLD = "#C2992E"
GRAY = "#5A5A5A"
LGRAY = "#EEF1F5"
RED = "#C0392B"
GREEN = "#2E7D52"

# ===========================================================================
# 차트 (matplotlib)
# ===========================================================================
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrow

rcParams["font.family"] = "Malgun Gothic"
rcParams["axes.unicode_minus"] = False
rcParams["figure.dpi"] = 200


def _save(fig, name):
    path = os.path.join(CHARTS, name + ".png")
    fig.savefig(path, bbox_inches="tight", facecolor="white", dpi=200)
    plt.close(fig)
    return path


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#BBBBBB")
    ax.tick_params(colors=GRAY, labelsize=9)
    ax.grid(axis="y", color="#E3E6EA", lw=0.8)
    ax.set_axisbelow(True)


def chart_intro_returns():
    fig, ax = plt.subplots(figsize=(6.6, 3.5))
    labels = ["1Q26 매출\n(YoY)", "1Q26 영업이익\n(YoY)", "최근 3개월\n주가"]
    vals = [46.9, 103.9, -26.8]
    colors = [SKY, BLUE, RED]
    bars = ax.bar(labels, vals, color=colors, width=0.55)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + (4 if v > 0 else -9),
                f"{v:+.1f}%", ha="center", fontsize=11, fontweight="bold",
                color=GRAY)
    ax.axhline(0, color="#888888", lw=1)
    ax.set_ylim(-45, 125)
    _style(ax)
    ax.set_title("실적은 두 배 성장, 주가는 역주행", fontsize=11,
                 fontweight="bold", color=NAVY, pad=10)
    return _save(fig, "intro_returns")


def chart_ind_music():
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    sizes = [220, 97]
    labels = ["스트리밍\n220억$ (69.6%)", "기타\n97억$ (30.4%)"]
    ax.pie(sizes, labels=labels, colors=[BLUE, LBLUE], startangle=90,
           wedgeprops=dict(width=0.42, edgecolor="white"),
           textprops=dict(fontsize=9.5, color=GRAY))
    ax.text(0, 0, "317억$\n2025", ha="center", va="center",
            fontsize=13, fontweight="bold", color=NAVY)
    ax.set_title("글로벌 음악산업 매출 구성 (11년 연속 성장)", fontsize=11,
                 fontweight="bold", color=NAVY, pad=8)
    return _save(fig, "ind_music")


def chart_ind_valuechain():
    fig, ax = plt.subplots(figsize=(7.0, 2.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3)
    ax.axis("off")
    steps = ["연습생\n발굴", "트레이닝\n(3~5년)", "데뷔·음반", "콘서트·MD", "글로벌\n라이선싱"]
    for i, s in enumerate(steps):
        x = 0.2 + i * 1.95
        box = FancyBboxPatch((x, 0.9), 1.55, 1.2,
                             boxstyle="round,pad=0.03,rounding_size=0.08",
                             facecolor=NAVY if i in (1, 3) else BLUE,
                             edgecolor="none")
        ax.add_patch(box)
        ax.text(x + 0.775, 1.5, s, ha="center", va="center",
                color="white", fontsize=9.5, fontweight="bold")
        if i < 4:
            ax.annotate("", xy=(x + 1.93, 1.5), xytext=(x + 1.75, 1.5),
                        arrowprops=dict(arrowstyle="-|>", color=GOLD, lw=2))
    ax.text(5.0, 0.35, "와이지엔터테인먼트는 5단계 전 과정을 외주 없이 자체 수행하는 인하우스 제작사",
            ha="center", fontsize=9, color=GRAY, style="italic")
    ax.set_title("K-POP 산업 밸류체인", fontsize=11, fontweight="bold",
                 color=NAVY, y=1.02)
    return _save(fig, "ind_valuechain")


def chart_ind_peer():
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    names = ["와이지엔터", "JYP", "SM", "HYBE"]
    caps = [0.90, 2.17, 2.00, 10.13]
    colors = [GOLD, SKY, SKY, SKY]
    bars = ax.bar(names, caps, color=colors, width=0.56)
    for b, v in zip(bars, caps):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.25,
                f"{v:.2f}조", ha="center", fontsize=10, fontweight="bold",
                color=GRAY)
    ax.set_ylim(0, 11.8)
    _style(ax)
    ax.set_title("4대 기획사 시가총액 비교 (와이지엔터가 최소 규모)", fontsize=11,
                 fontweight="bold", color=NAVY, pad=10)
    return _save(fig, "ind_peer")


def chart_ind_peer_per():
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    names = ["와이지엔터", "JYP", "SM", "HYBE"]
    pbr = [1.74, 3.26, 2.00, 3.07]
    x = range(len(names))
    bars = ax.bar(x, pbr, color=[GOLD, SKY, SKY, SKY], width=0.55)
    for b, v in zip(bars, pbr):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.08,
                f"{v:.2f}배", ha="center", fontsize=10, fontweight="bold",
                color=GRAY)
    ax.set_xticks(list(x))
    ax.set_xticklabels(names)
    ax.set_ylim(0, 3.9)
    _style(ax)
    ax.set_title("4대 기획사 PBR 비교 (와이지엔터가 최저)", fontsize=11,
                 fontweight="bold", color=NAVY, pad=10)
    return _save(fig, "ind_peer_per")


def chart_comp_seg_pie():
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    sizes = [37, 23, 16, 24]
    labels = ["음반·상품 37%", "공연 23%", "음원 16%", "기타 24%"]
    ax.pie(sizes, labels=labels, colors=[NAVY, BLUE, SKY, LBLUE], startangle=90,
           autopct="", wedgeprops=dict(edgecolor="white", linewidth=1.5),
           textprops=dict(fontsize=9.5, color=GRAY, fontweight="bold"))
    ax.set_title("2025년 사업부문별 매출 비중", fontsize=11,
                 fontweight="bold", color=NAVY, pad=8)
    return _save(fig, "comp_seg_pie")


def chart_comp_seg_trend():
    fig, ax = plt.subplots(figsize=(6.6, 3.5))
    years = ["2023", "2024", "2025"]
    음반 = [1974, 1522, 2018]
    공연 = [1115, 170, 1264]
    음원 = [889, 786, 872]
    기타 = [1714, 1172, 1300]
    b = [0, 0, 0]
    for data, c, lab in [(음반, NAVY, "음반·상품"), (공연, BLUE, "공연"),
                         (음원, SKY, "음원"), (기타, LBLUE, "기타")]:
        ax.bar(years, data, bottom=b, color=c, label=lab, width=0.5)
        b = [x + y for x, y in zip(b, data)]
    for i, t in enumerate(b):
        ax.text(i, t + 130, f"{t:,}", ha="center", fontsize=9.5,
                fontweight="bold", color=GRAY)
    ax.set_ylim(0, 6400)
    _style(ax)
    ax.legend(fontsize=8, ncol=4, loc="upper center", frameon=False,
              bbox_to_anchor=(0.5, -0.08))
    ax.set_title("부문별 매출 추이 (억원) - 공연이 1년 만에 7배", fontsize=11,
                 fontweight="bold", color=NAVY, pad=10)
    return _save(fig, "comp_seg_trend")


def chart_comp_debut():
    fig, ax = plt.subplots(figsize=(7.0, 2.7))
    ax.set_xlim(2004, 2028)
    ax.set_ylim(0, 2)
    ax.axis("off")
    ax.annotate("", xy=(2028, 1), xytext=(2004, 1),
                arrowprops=dict(arrowstyle="-|>", color="#BBBBBB", lw=1.5))
    debuts = [(2006, "빅뱅"), (2009, "2NE1"), (2014, "위너"), (2016, "블랙핑크"),
              (2020, "트레저"), (2024, "베이비\n몬스터"), (2026, "신인\n보이·걸그룹")]
    for i, (yr, nm) in enumerate(debuts):
        up = i % 2 == 0
        y = 1.42 if up else 0.58
        new = yr >= 2024
        ax.plot([yr, yr], [1, y], color=GOLD if new else BLUE, lw=1.3)
        ax.scatter([yr], [1], s=46, color=GOLD if new else BLUE, zorder=3)
        ax.text(yr, y + (0.16 if up else -0.16), f"{nm}\n{yr}", ha="center",
                va="bottom" if up else "top", fontsize=8.4,
                fontweight="bold", color=NAVY if not new else GOLD)
    ax.set_title("와이지엔터테인먼트 데뷔 타임라인 - 적지만 대부분 메가 IP",
                 fontsize=11, fontweight="bold", color=NAVY, y=1.0)
    return _save(fig, "comp_debut")


def chart_comp_system():
    fig, ax = plt.subplots(figsize=(7.0, 3.1))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")
    # before
    b1 = FancyBboxPatch((0.2, 0.5), 4.3, 2.9,
                        boxstyle="round,pad=0.05,rounding_size=0.1",
                        facecolor=LGRAY, edgecolor="#CCCCCC")
    ax.add_patch(b1)
    ax.text(2.35, 3.0, "기존 시스템", ha="center", fontsize=10.5,
            fontweight="bold", color=GRAY)
    for i, t in enumerate(["감당 가능한 아티스트 수 제한", "긴 컴백 주기 / 적은 IP 수",
                           "한 팀 공백 = 회사 전체 공백"]):
        ax.text(2.35, 2.4 - i * 0.6, "- " + t, ha="center", fontsize=8.7,
                color=GRAY)
    # after
    b2 = FancyBboxPatch((5.5, 0.5), 4.3, 2.9,
                        boxstyle="round,pad=0.05,rounding_size=0.1",
                        facecolor=NAVY, edgecolor="none")
    ax.add_patch(b2)
    ax.text(7.65, 3.0, "바뀐 시스템", ha="center", fontsize=10.5,
            fontweight="bold", color="white")
    for i, t in enumerate(["작곡가·프로듀서 인력 증원", "프로듀서 센터 / 글로벌 트레이닝 센터",
                           "베이비몬스터 = 첫 결과물"]):
        ax.text(7.65, 2.4 - i * 0.6, "- " + t, ha="center", fontsize=8.7,
                color="white")
    ax.annotate("", xy=(5.45, 1.95), xytext=(4.55, 1.95),
                arrowprops=dict(arrowstyle="-|>", color=GOLD, lw=2.4))
    ax.set_title("메가 IP DNA는 유지, 처리량(throughput)을 끌어올리는 전환",
                 fontsize=11, fontweight="bold", color=NAVY, y=1.0)
    return _save(fig, "comp_system")


def chart_comp_history():
    fig, ax = plt.subplots(figsize=(6.8, 3.4))
    years = ["2020", "2021", "2022", "2023", "2024", "2025", "2026"]
    closes = [44700, 55700, 43850, 50900, 45800, 69400, 48050]
    ax.plot(years, closes, color=BLUE, lw=2.4, marker="o", ms=6,
            markerfacecolor=NAVY, markeredgecolor="white")
    for x, y in zip(years, closes):
        ax.text(x, y + 3200, f"{y:,}", ha="center", fontsize=8.4, color=GRAY)
    notes = {"2021": "블랙핑크\n흥행", "2022": "활동\n공백", "2024": "매출\n절벽",
             "2025": "DEADLINE\n투어"}
    for x, n in notes.items():
        i = years.index(x)
        ax.annotate(n, (x, closes[i]), textcoords="offset points",
                    xytext=(0, -34), ha="center", fontsize=7.6, color=GOLD,
                    fontweight="bold")
    ax.set_ylim(35000, 80000)
    _style(ax)
    ax.set_title("5개년 연말 종가 추이 (원) - 주가는 IP 사이클을 따라간다",
                 fontsize=11, fontweight="bold", color=NAVY, pad=10)
    return _save(fig, "comp_history")


def chart_ip_consensus_op():
    fig, ax = plt.subplots(figsize=(6.6, 3.5))
    years = ["2024", "2025", "2026E", "2027E"]
    op = [-186, 522, 806, 764]
    colors = [RED, SKY, BLUE, BLUE]
    bars = ax.bar(years, op, color=colors, width=0.55)
    for b, v in zip(bars, op):
        ax.text(b.get_x() + b.get_width() / 2, v + (40 if v > 0 else -75),
                f"{v:,}", ha="center", fontsize=9.6, fontweight="bold",
                color=GRAY)
    ax.axhline(935, color=GOLD, lw=1.8, ls="--")
    ax.text(3.45, 935, " Hana 추정\n 935", va="center", fontsize=8.4,
            color=GOLD, fontweight="bold")
    ax.axhline(0, color="#888888", lw=1)
    ax.set_ylim(-330, 1080)
    _style(ax)
    ax.set_title("영업이익 컨센서스 (억원) - 2027E가 2026E보다 낮다",
                 fontsize=11, fontweight="bold", color=NAVY, pad=10)
    return _save(fig, "ip_consensus_op")


def chart_ip_lineup():
    fig, ax = plt.subplots(figsize=(7.0, 3.0))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")
    ax.text(2.3, 3.55, "2024년", ha="center", fontsize=11, fontweight="bold",
            color=GRAY)
    ax.text(7.5, 3.55, "2026년 하반기", ha="center", fontsize=11,
            fontweight="bold", color=NAVY)
    left = ["베이비몬스터(데뷔)"]
    right = ["빅뱅 20주년", "블랙핑크", "베이비몬스터", "트레저",
             "신인 보이그룹", "신인 걸그룹"]
    ax.add_patch(FancyBboxPatch((0.3, 2.4), 4.0, 0.62,
                 boxstyle="round,pad=0.03,rounding_size=0.06",
                 facecolor=LGRAY, edgecolor="#CCCCCC"))
    ax.text(2.3, 2.71, left[0], ha="center", va="center", fontsize=9,
            color=GRAY)
    ax.text(2.3, 1.7, "IP 1팀\n매출 -36% 절벽", ha="center", fontsize=9,
            color=RED, fontweight="bold")
    for i, nm in enumerate(right):
        col = i % 2
        row = i // 2
        x = 5.4 + col * 2.35
        y = 2.4 - row * 0.74
        ax.add_patch(FancyBboxPatch((x, y), 2.15, 0.6,
                     boxstyle="round,pad=0.03,rounding_size=0.06",
                     facecolor=NAVY, edgecolor="none"))
        ax.text(x + 1.07, y + 0.3, nm, ha="center", va="center",
                fontsize=8.2, color="white", fontweight="bold")
    ax.text(7.5, 0.25, "IP 6팀 동시 가동 = 포트폴리오 헤지 작동", ha="center",
            fontsize=9, color=GREEN, fontweight="bold")
    ax.annotate("", xy=(5.3, 1.9), xytext=(4.5, 1.9),
                arrowprops=dict(arrowstyle="-|>", color=GOLD, lw=2.4))
    ax.set_title("IP 라인업 비교 - 단일 IP에서 6종 포트폴리오로",
                 fontsize=11, fontweight="bold", color=NAVY, y=1.0)
    return _save(fig, "ip_lineup")


def chart_ip_catalyst():
    fig, ax = plt.subplots(figsize=(7.0, 2.9))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3)
    ax.axis("off")
    ax.annotate("", xy=(9.7, 1.4), xytext=(0.3, 1.4),
                arrowprops=dict(arrowstyle="-|>", color="#BBBBBB", lw=1.5))
    cats = [("26.05", "베이비몬스터\n'CHOOM'"), ("26.06", "트레저 신보\n베몬 2차 투어"),
            ("26.08", "빅뱅 20주년\n투어 개막"), ("26.09", "신인 보이그룹\n데뷔"),
            ("26.10", "베몬 정규 2집\n신인 걸그룹"), ("27.01", "빅뱅 투어 종료\n컨센 재산정")]
    for i, (d, e) in enumerate(cats):
        x = 0.9 + i * 1.62
        up = i % 2 == 0
        y = 2.0 if up else 0.8
        big = i == 2
        ax.plot([x, x], [1.4, y], color=GOLD if big else BLUE, lw=1.4)
        ax.scatter([x], [1.4], s=70 if big else 44,
                   color=GOLD if big else BLUE, zorder=3)
        ax.text(x, y + (0.14 if up else -0.14), e, ha="center",
                va="bottom" if up else "top", fontsize=7.7,
                fontweight="bold", color=NAVY)
        ax.text(x, 1.4 + (0.0 if up else 0.0), "", ha="center")
        ax.text(x, 1.12 if up else 1.68, d, ha="center", fontsize=7.2,
                color=GRAY)
    ax.set_title("12개월 카탈리스트 타임라인 (8월 빅뱅이 단일 최대 트리거)",
                 fontsize=11, fontweight="bold", color=NAVY, y=1.0)
    return _save(fig, "ip_catalyst")


def chart_risk_matrix():
    fig, ax = plt.subplots(figsize=(6.6, 3.0))
    risks = ["블랙핑크 활동\n시기 불확실", "영업외 평가손익\n변동성", "신인 비용\n선행 부담"]
    prob = [35, 50, 60]
    bars = ax.barh(risks, prob, color=[RED, GOLD, SKY], height=0.5)
    for b, v in zip(bars, prob):
        ax.text(v + 2, b.get_y() + b.get_height() / 2, f"발생확률 {v}%",
                va="center", fontsize=9, fontweight="bold", color=GRAY)
    ax.set_xlim(0, 80)
    ax.invert_yaxis()
    for s in ("top", "right", "bottom"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#BBBBBB")
    ax.set_xticks([])
    ax.tick_params(colors=GRAY, labelsize=9)
    ax.set_title("Top 3 리스크 - 모두 인정하되 가격에 반영", fontsize=11,
                 fontweight="bold", color=NAVY, pad=10)
    return _save(fig, "risk_matrix")


def chart_fin_quarterly():
    fig, ax = plt.subplots(figsize=(6.6, 3.5))
    q = ["1Q25", "2Q25", "3Q25", "4Q25", "1Q26"]
    rev = [1002, 1004, 1731, 1718, 1471]
    op = [53, 74, 235, 159, 194]
    x = range(len(q))
    ax.bar([i - 0.2 for i in x], rev, width=0.4, color=NAVY, label="매출액")
    ax.bar([i + 0.2 for i in x], op, width=0.4, color=GOLD, label="영업이익")
    for i, v in enumerate(rev):
        ax.text(i - 0.2, v + 55, f"{v:,}", ha="center", fontsize=8, color=GRAY)
    for i, v in enumerate(op):
        ax.text(i + 0.2, v + 55, f"{v}", ha="center", fontsize=8, color=GRAY)
    ax.set_xticks(list(x))
    ax.set_xticklabels(q)
    ax.set_ylim(0, 2050)
    _style(ax)
    ax.legend(fontsize=8.5, frameon=False, loc="upper left")
    ax.set_title("분기 실적 추이 (억원) - 1Q26 매출·이익 동반 급증",
                 fontsize=11, fontweight="bold", color=NAVY, pad=10)
    return _save(fig, "fin_quarterly")


def chart_fin_supply():
    fig, ax = plt.subplots(figsize=(6.6, 3.3))
    who = ["외국인", "기관", "개인"]
    val = [-5.95, -38.5, 44.1]
    colors = [RED, RED, GREEN]
    bars = ax.bar(who, val, color=colors, width=0.5)
    for b, v in zip(bars, val):
        ax.text(b.get_x() + b.get_width() / 2, v + (3 if v > 0 else -5),
                f"{v:+.1f}만주", ha="center", fontsize=9.6,
                fontweight="bold", color=GRAY)
    ax.axhline(0, color="#888888", lw=1)
    ax.set_ylim(-52, 56)
    _style(ax)
    ax.set_title("최근 20일 투자자별 순매수 - 개인이 매물 흡수",
                 fontsize=11, fontweight="bold", color=NAVY, pad=10)
    return _save(fig, "fin_supply")


def chart_fin_revenue():
    fig, ax = plt.subplots(figsize=(6.8, 3.5))
    years = ["2022", "2023", "2024", "2025", "2026E", "2027E", "2028E"]
    rev = [3912, 5692, 3649, 5454, 6010, 5660, 6132]
    op = [426, 795, -186, 522, 806, 764, 864]
    opm = [10.9, 14.0, -5.1, 9.6, 13.4, 13.5, 14.1]
    x = range(len(years))
    ax.bar([i - 0.2 for i in x], rev, width=0.38, color=NAVY, label="매출액")
    ax.bar([i + 0.2 for i in x], op, width=0.38, color=GOLD, label="영업이익")
    ax.set_xticks(list(x))
    ax.set_xticklabels(years)
    ax.set_ylim(-800, 7200)
    _style(ax)
    ax2 = ax.twinx()
    ax2.plot(list(x), opm, color=RED, lw=2, marker="o", ms=5, label="영업이익률")
    ax2.set_ylim(-12, 22)
    ax2.set_ylabel("영업이익률(%)", color=RED, fontsize=8.5)
    ax2.tick_params(colors=RED, labelsize=8)
    for s in ("top",):
        ax2.spines[s].set_visible(False)
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    ax.set_title("매출·영업이익·영업이익률 추이 (억원, %)", fontsize=11,
                 fontweight="bold", color=NAVY, pad=10)
    return _save(fig, "fin_revenue")


def chart_fin_netcash():
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    years = ["2022", "2023", "2024", "2025", "2026E", "2027E", "2028E"]
    nc = [1667, 2086, 1740, 2737, 2950, 3150, 3380]
    dr = [35.5, 26.8, 21.7, 28.9, 27.3, 26.5, 25.8]
    x = range(len(years))
    bars = ax.bar(x, nc, color=SKY, width=0.55, label="순현금")
    for b, v in zip(bars, nc):
        ax.text(b.get_x() + b.get_width() / 2, v + 90, f"{v:,}",
                ha="center", fontsize=7.8, color=GRAY)
    ax.set_xticks(list(x))
    ax.set_xticklabels(years)
    ax.set_ylim(0, 4000)
    _style(ax)
    ax2 = ax.twinx()
    ax2.plot(list(x), dr, color=GOLD, lw=2, marker="s", ms=5, label="부채비율")
    ax2.set_ylim(0, 60)
    ax2.set_ylabel("부채비율(%)", color=GOLD, fontsize=8.5)
    ax2.tick_params(colors=GOLD, labelsize=8)
    ax2.spines["top"].set_visible(False)
    ax.set_title("순현금·부채비율 추이 (억원, %) - 사실상 무차입", fontsize=11,
                 fontweight="bold", color=NAVY, pad=10)
    return _save(fig, "fin_netcash")


def chart_val_band():
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    years = ["2021", "2022", "2023", "2024", "2025", "현재"]
    pbr = [2.70, 1.98, 2.02, 1.76, 2.51, 1.74]
    ax.plot(years, pbr, color=BLUE, lw=2.3, marker="o", ms=6,
            markerfacecolor=NAVY, markeredgecolor="white")
    ax.axhline(2.19, color=GRAY, ls="--", lw=1.3)
    ax.text(0.05, 2.24, "5년 평균 2.19배", fontsize=8.4, color=GRAY)
    ax.axhline(2.19 - 1.29 * 0.35, color=RED, ls=":", lw=1.3)
    ax.text(0.05, 2.19 - 1.29 * 0.35 - 0.13, "-1.29σ (저점권)", fontsize=8.4,
            color=RED)
    ax.scatter([5], [1.74], s=120, color=GOLD, zorder=5, edgecolor="white")
    ax.text(5, 1.74 - 0.18, "현재 1.74배", ha="center", fontsize=8.6,
            color=GOLD, fontweight="bold")
    ax.set_ylim(1.3, 3.0)
    _style(ax)
    ax.set_title("5년 PBR 밴드 - 현재는 역사적 저점권", fontsize=11,
                 fontweight="bold", color=NAVY, pad=10)
    return _save(fig, "val_band")


def chart_val_scenario():
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    labels = ["Bear", "현재가", "Base", "Bull"]
    vals = [42000, 48050, 67000, 92000]
    colors = [RED, GRAY, BLUE, GOLD]
    bars = ax.bar(labels, vals, color=colors, width=0.56)
    notes = ["-12.6%", "48,050", "+39.4%", "+91.4%"]
    for b, v, n in zip(bars, vals, notes):
        ax.text(b.get_x() + b.get_width() / 2, v + 2600,
                f"{v:,}\n{n}", ha="center", fontsize=9, fontweight="bold",
                color=GRAY)
    ax.set_ylim(0, 108000)
    _style(ax)
    ax.set_title("시나리오별 목표주가 (원) - 하방은 현금, 상방은 빅뱅",
                 fontsize=11, fontweight="bold", color=NAVY, pad=10)
    return _save(fig, "val_scenario")


CHART_FUNCS = {
    "intro_returns": chart_intro_returns, "ind_music": chart_ind_music,
    "ind_valuechain": chart_ind_valuechain, "ind_peer": chart_ind_peer,
    "ind_peer_per": chart_ind_peer_per, "comp_seg_pie": chart_comp_seg_pie,
    "comp_seg_trend": chart_comp_seg_trend, "comp_debut": chart_comp_debut,
    "comp_system": chart_comp_system, "comp_history": chart_comp_history,
    "ip_consensus_op": chart_ip_consensus_op, "ip_lineup": chart_ip_lineup,
    "ip_catalyst": chart_ip_catalyst, "risk_matrix": chart_risk_matrix,
    "fin_quarterly": chart_fin_quarterly, "fin_supply": chart_fin_supply,
    "fin_revenue": chart_fin_revenue, "fin_netcash": chart_fin_netcash,
    "val_band": chart_val_band, "val_scenario": chart_val_scenario,
    "cover_price": None,
}


def chart_cover_price():
    import json
    fig, ax = plt.subplots(figsize=(5.0, 2.0))
    try:
        with open(os.path.join(ROOT, "data", "와이지엔터", "data_kis.json"),
                  encoding="utf-8") as f:
            dp = json.load(f)["daily_prices"]
        dp = list(reversed(dp))
        closes = [d["종가"] for d in dp]
        ax.plot(range(len(closes)), closes, color=BLUE, lw=1.8)
        ax.fill_between(range(len(closes)), closes, min(closes) * 0.96,
                        color=LBLUE, alpha=0.6)
    except Exception as e:
        print("  [WARN] cover_price:", e)
    _style(ax)
    ax.grid(False)
    ax.set_xticks([])
    ax.tick_params(labelsize=7)
    ax.set_title("주가 추이 (최근 100거래일)", fontsize=8.5, color=GRAY)
    return _save(fig, "cover_price")


def make_charts():
    print("[1/3] 차트 생성")
    n = 0
    for name, fn in CHART_FUNCS.items():
        if fn is None:
            continue
        fn()
        n += 1
    chart_cover_price()
    n += 1
    print(f"  -> 차트 {n}종 생성 완료 ({CHARTS})")


# ===========================================================================
# 마크다운 본문
# ===========================================================================
def write_md():
    print("[2/3] 본문 마크다운 생성")
    L = []
    m = C.META
    L.append(f"# {m['company']} ({m['code']}) 기업분석 리포트")
    L.append("")
    L.append(f"> **{C.COVER['title']}** - {C.COVER['subtitle']}")
    L.append("")
    L.append(f"- {m['report_no']} | {m['date']}")
    L.append(f"- 투자의견 **{m['rating']}** | 목표주가 **{m['target_price']:,}원** | "
             f"현재주가 {m['current_price']:,}원 | 상승여력 **+{m['upside']}%**")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## [슬라이드 1] 커버")
    L.append("")
    L.append("**Summary**")
    for s in C.COVER["summary"]:
        L.append(f"- {s}")
    L.append("")
    L.append("**Investment Highlight**")
    for i, (t, b) in enumerate(C.COVER["highlights"], 1):
        L.append(f"{i}) **{t}** - {b}")
    L.append("")
    L.append(f"**Valuation** - {C.COVER['valuation']}")
    L.append("")
    L.append("| 구분 | 값 |  | 구분 | 값 |")
    L.append("|---|---|---|---|---|")
    sd = C.COVER["stock_data"]
    for i in range(0, len(sd), 2):
        a = sd[i]
        b = sd[i + 1] if i + 1 < len(sd) else ("", "")
        L.append(f"| {a[0]} | {a[1]} | | {b[0]} | {b[1]} |")
    L.append("")
    L.append("---")
    L.append("")
    # 목차
    L.append("## [슬라이드 2] 목차")
    L.append("")
    toc = [("0. Introduction", 3), ("1. 산업분석 Industry Overview", 4),
           ("2. 기업분석 Company Overview", 6),
           ("3. 투자포인트 Investment Highlights", 9), ("4. 리스크 Risk", 12),
           ("5. 재무분석 Financial Overview", 13),
           ("6. 밸류에이션 Valuation", 15), ("재무제표 Appendix", 16)]
    for t, p in toc:
        L.append(f"- {t} ...... p{p}")
    L.append("")
    L.append("---")
    L.append("")
    # 본문
    slide_idx = 3
    for sl in C.SLIDES:
        sec = sl["section"] + (f" {sl['section_en']}" if sl["section_en"] else "")
        L.append(f"## [슬라이드 {sl['no']}] {sec}")
        if sl.get("headline"):
            L.append("")
            L.append(f"### {sl['headline']}")
        L.append("")
        for bl in sl["blocks"]:
            L.append(f"**[{bl['label']}]**")
            L.append("")
            L.append(f"#### {bl['subtitle']}")
            L.append("")
            L.append(bl["body"])
            if bl.get("chart"):
                L.append("")
                L.append(f"`[도표: charts/{bl['chart']}.png]`")
            L.append("")
        L.append("---")
        L.append("")
    # 재무제표
    ft = C.FIN_TABLE
    L.append("## [슬라이드 16] 재무제표 Appendix")
    L.append("")
    L.append("| " + " | ".join(ft["headers"]) + " |")
    L.append("|" + "---|" * len(ft["headers"]))
    for row in ft["rows"]:
        cells = [str(row[0])] + [f"{v:,}" if isinstance(v, int) else str(v)
                                 for v in row[1:]]
        L.append("| " + " | ".join(cells) + " |")
    L.append("")
    L.append(f"_{ft['source']}_")
    L.append("")

    path = os.path.join(OUT, "와이지엔터테인먼트_리포트_본문.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"  -> {path}")


# ===========================================================================
# PPTX - 위닝펀드 18-1 양식 파일 직접 채우기 (PowerPoint COM)
# ===========================================================================
import _yg_wf_pptx


def build_pptx():
    print("[3/3] PPTX 생성 (양식 파일 직접 채우기)")
    tpl = os.path.join(OUT, "18-1_기업분석 리포트 양식.pptx")
    out = os.path.join(OUT, "18-1_와이지엔터테인먼트_기업분석리포트.pptx")
    if not os.path.exists(tpl):
        print("  [ERROR] 양식 파일 없음:", tpl)
        return None
    n = _yg_wf_pptx.build(tpl, out, CHARTS)
    print(f"  -> {out}  (슬라이드 {n}장)")
    return out


# ===========================================================================
if __name__ == "__main__":
    print("=" * 60)
    print(" 위닝펀드 18-1 와이지엔터테인먼트 리포트 빌드")
    print("=" * 60)
    make_charts()
    write_md()
    build_pptx()
    print("=" * 60)
    print(" 완료")
    print("=" * 60)
