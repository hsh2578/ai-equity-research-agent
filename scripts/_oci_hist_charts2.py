# -*- coding: utf-8 -*-
"""OCI홀딩스 (2) 최근 5년 세부 분석 차트 + (3) Upside Momentum 도식화"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch, Patch
import matplotlib.gridspec as gridspec

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
NAVY='#16304c'; GREEN='#1f3a5c'; RED='#b23a2e'; BLUE='#33628f'; PINK='#f6d7d5'
OUT='data/OCI홀딩스'
D=lambda s: pd.Timestamp(s)
c = pd.read_csv(f'{OUT}/_price_hist.csv', index_col=0, parse_dates=True)['close']

def at(date):
    """해당일 근처 종가"""
    s = c[:date]
    return float(s.iloc[-1]) if len(s) else float(c.iloc[0])

# ═══════════ (2) 2003~2026 장기 주가 사이클 ═══════════
pa = c  # 전체 2003~2026 (수정주가)
fig, ax = plt.subplots(figsize=(13.4, 6.2))
UP_BG='#f6ebe6'; DOWN_BG='#eaeef3'
bands=[
 ('2003-01-02','2008-05-20','up'),('2008-05-20','2008-10-24','down'),
 ('2008-10-24','2011-04-29','up'),('2011-04-29','2016-01-21','down'),
 ('2016-01-21','2018-01-10','up'),('2018-01-10','2020-03-19','down'),
 ('2020-03-19','2021-09-30','up'),('2021-09-30','2022-12-29','down'),
 ('2022-12-29','2023-06-26','up'),('2023-06-26','2024-12-09','down'),
 ('2024-12-09','2026-05-27','up'),('2026-05-27',None,'down'),
]
for s_,e_,t_ in bands:
    ax.axvspan(D(s_), D(e_) if e_ else pa.index[-1], color=UP_BG if t_=='up' else DOWN_BG, alpha=0.55, zorder=0)
ax.plot(pa.index, pa.values, color=GREEN, lw=1.05, zorder=3)

# 주요 사이클 정점/바닥 (날짜, 값, 라벨, up?, dx/dy)
marks=[
 ('2008-05-20',345676,'2008 1차 붐\n(폴리 진출)',True ,(-8,22)),
 ('2011-04-29',508580,'2011 태양광\n슈퍼사이클 정점',True ,(2,12)),
 ('2016-01-21',48076,'중국 공급과잉\n대폭락 -90%',False,(-60,-4)),
 ('2020-03-19',21137,'코로나 바닥 2.1만',False,(-2,32)),
 ('2026-05-27',388000,'2026 테마\n버블 38.8만',True ,(-38,10)),
 (pa.index[-1].strftime('%Y-%m-%d'),float(c.iloc[-1]),'현재\n19.9만',False,(30,4)),
]
for ds,y,lab,up,(dx,dy) in marks:
    d=D(ds)
    ax.scatter([d],[y],s=52,facecolor='#fff',edgecolor=RED if up else BLUE,lw=2,zorder=6)
    ax.annotate(lab,(d,y),xytext=(dx,dy),textcoords='offset points',fontsize=8.4,ha='center',va='center',
                color=NAVY,weight='bold',
                arrowprops=dict(arrowstyle='-',color='#999',lw=0.6),zorder=8)
ax.set_ylim(0,560000)
ax.set_xlim(D('2002-08-01'), D('2027-07-01'))
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x,_:f'{int(x/10000)}만' if x>0 else '0'))
ax.xaxis.set_major_locator(mdates.YearLocator(2))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
for sp in ['top','right']: ax.spines[sp].set_visible(False)
ax.tick_params(labelsize=9); ax.grid(axis='y',alpha=0.25,lw=0.6)
ax.legend(handles=[Patch(fc=UP_BG,label='상승 사이클'),Patch(fc=DOWN_BG,label='하락 사이클'),
                   plt.Line2D([0],[0],color=GREEN,lw=1.5,label='주가(수정주가)')],
          loc='upper center',bbox_to_anchor=(0.62,1.0),fontsize=8.6,framealpha=0.92,ncol=3)
ax.annotate('(단위: 원)', xy=(0.005,1.015), xycoords='axes fraction', fontsize=8.5, color='#888', ha='left')
fig.subplots_adjust(bottom=0.08,top=0.955,left=0.065,right=0.985)
fig.savefig(f'{OUT}/_hist_5y_detail.png',dpi=300); print('저장: _hist_5y_detail.png (2003~2026 사이클)')

# ═══════════ (3) Upside Momentum 도식화 ═══════════
fig2=plt.figure(figsize=(13.8,8.0))
gs=gridspec.GridSpec(2,1,height_ratios=[2.5,2.5],hspace=0.06)
axp=fig2.add_subplot(gs[0]); axe=fig2.add_subplot(gs[1],sharex=axp)

recent=c['2024-06-01':]
now=c.index[-1]; p0=float(c.iloc[-1])
axp.plot(recent.index,recent.values,color=GREEN,lw=1.4,zorder=4)
# 단일 Upside Momentum 경로 (부드러운 상승)
fd=pd.date_range(now,D('2027-12-31'),freq='MS'); x=np.linspace(0,1,len(fd))
path=p0+(390000-p0)*(0.15*x+0.85*x**1.4)   # 완만→가속 상승
axp.axvspan(now,fd[-1],color=PINK,alpha=0.5,zorder=0)
axp.plot(fd,path,color=RED,lw=2.0,ls='--',zorder=5)
axp.annotate('Upside Momentum',(D('2027-03-15'),365000),fontsize=15,weight='bold',color=RED,ha='center')
axp.annotate('Section 232 통과 시 집중되는 상승 모멘텀',(D('2027-03-15'),342000),fontsize=9,color='#a3403a',ha='center')
axp.scatter([now],[p0],s=45,color=GREEN,zorder=7)
axp.annotate(f'현재 {p0/10000:.1f}만',(now,p0),xytext=(-6,-16),textcoords='offset points',fontsize=9,weight='bold',color=GREEN,ha='right')
# 경로 위 촉매 dot
for ds,lab,yy in [('2026-08','Section232',None),('2027-01','SpaceX 공식화',None),('2027-08','우주DC 수요',None)]:
    d=D(ds); yv=float(np.interp(mdates.date2num(d),mdates.date2num(fd),path))
    axp.scatter([d],[yv],s=30,facecolor='#fff',edgecolor=RED,lw=1.5,zorder=6)
axp.axvline(now,color='#888',lw=0.8,ls=':')
axp.set_ylim(0,430000)
axp.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,_:f'{int(v/10000)}만' if v>0 else '0'))
for sp in ['top','right']: axp.spines[sp].set_visible(False)
axp.tick_params(labelsize=9,labelbottom=False); axp.grid(axis='y',alpha=0.25,lw=0.6)
axp.annotate('(단위: 원)', xy=(0.005,1.02), xycoords='axes fraction', fontsize=8.5, color='#888', ha='left')

# 하단 이벤트 레인
lanes=[('① 폴리·업스트림',3.3,[('2025-08','중국\n공급개혁',13),('2026-09','2Q26 폴리\n정상화',13),('2026-12','5.66만톤\n증설 결정',13)]),
       ('② 다운스트림·미국',2.2,[('2025-10','NeoSilicon\n웨이퍼2.7GW',-21),('2026-07','웨이퍼5.4GW\n증설(3Q)',13),('2026-12','Mission Solar\n셀 1→2GW',13),('2027-06','OTSM\n준공',-21)]),
       ('③ 정책·테마',1.1,[('2025-07','Section232\n개시',-21),('2026-08','Section232\n결과(임박)',13),('2027-01','SpaceX\n공식화',13),('2027-09','SBSP·우주\n태양광',13)]),
       ('④ 리스크',0.0,[('2026-06','중대재해',-16),('2026-12','중국 감산\n완화',-27),('2027-07','폴리 약세\n지속',-27)])]
axe.axvspan(now,D('2027-12-31'),color=PINK,alpha=0.35,zorder=0)
axe.axvline(now,color='#888',lw=0.8,ls=':')
for name,y,evs in lanes:
    axe.annotate('',xy=(D('2027-12-15'),y),xytext=(D('2024-07-15'),y),
                 arrowprops=dict(arrowstyle='->',color='#c9c9c9',lw=1.2),zorder=1)
    axe.text(D('2024-06-25'),y+0.22,name,fontsize=8.5,weight='bold',color=NAVY,va='bottom')
    for ds,lab,dy in evs:
        d=D(ds); fut=d>=now
        axe.scatter([d],[y],s=32,facecolor='#fff' if fut else NAVY,edgecolor=RED if fut else NAVY,lw=1.4,zorder=4)
        axe.annotate(lab,(d,y),xytext=(0,dy),textcoords='offset points',
                     fontsize=7.0,ha='center',va='bottom' if dy>0 else 'top',color='#333',weight='bold')
axe.set_ylim(-1.2,4.2); axe.set_yticks([])
axe.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
axe.xaxis.set_major_formatter(mdates.DateFormatter("%y.%m"))
for sp in ['top','right','left']: axe.spines[sp].set_visible(False)
axe.tick_params(labelsize=8.5)
fig2.text(0.09,0.02,'주: 과거 이벤트(●)=검증된 사실, 미래 촉매(○)=예정/기대. 추가 촉매: DCRE 8·9단지 분양, 부광약품(지분17.1%) 신약, OCI파워 미국 인버터. Section232 결과가 방향을 가르며 통과 시 상승 모멘텀 집중.',
          fontsize=7.6,color='#666')
fig2.subplots_adjust(bottom=0.09,top=0.955,left=0.065,right=0.985)
fig2.savefig(f'{OUT}/_hist_momentum.png',dpi=300); print('저장: _hist_momentum.png')
