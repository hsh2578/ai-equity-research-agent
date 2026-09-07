# -*- coding: utf-8 -*-
"""OCI홀딩스 주가 History Appendix 도표 (사이클 밴드 + Forward 타임라인)"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch
import datetime as dt

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

NAVY='#123a6b'; GREEN='#1a5c38'; RED='#c0272d'; BLUE='#2f5fa6'
UP_BG='#f6d7d5'; DOWN_BG='#d6e0f0'
OUT='data/OCI홀딩스'

c = pd.read_csv(f'{OUT}/_price_hist.csv', index_col=0, parse_dates=True)['close']

# ── 사이클 밴드 정의 (전환점 데이터 기반) ──
D=lambda s: pd.Timestamp(s)
bands=[
 (D('2014-04-28'),D('2016-01-21'),'down'),
 (D('2016-01-21'),D('2018-01-10'),'up'),
 (D('2018-01-10'),D('2020-03-19'),'down'),
 (D('2020-03-19'),D('2021-09-30'),'up'),
 (D('2021-09-30'),D('2022-12-29'),'down'),
 (D('2022-12-29'),D('2023-06-26'),'up'),
 (D('2023-06-26'),D('2024-12-09'),'down'),
 (D('2024-12-09'),D('2026-05-27'),'up'),
 (D('2026-05-27'),c.index[-1],'down'),
]
# 이벤트 주석 (검증된 것만)
events=[
 (D('2018-01-10'),148204,'폴리 고점\n5분기 적자 진입',18),
 (D('2020-03-19'),21138,'코로나 바닥 2.1만\n(2020.2 군산 감산)',-42),
 (D('2021-09-30'),127940,'폴리 $4→$32\n2021 흑전',20),
 (D('2023-05-01'),100000,'2023.5 인적분할',30),
 (D('2024-12-09'),54900,'중국 증설·저점 5.5만',-40),
 (D('2026-04-14'),300000,'SpaceX 단독보도',-70),
 (D('2026-05-27'),388000,'테마 정점 38.8만',10),
 (D('2026-06-26'),194000,'-50% 급락\n(7/3 현재 21.3만, 조정 지속)',-48),
]

fig,ax=plt.subplots(figsize=(12.6,5.6))
for s,e,t in bands:
    ax.axvspan(s,e,color=UP_BG if t=='up' else DOWN_BG,alpha=0.9,zorder=0)
ax.plot(c.index,c.values,color=GREEN,lw=1.15,zorder=3)
ax.set_ylim(0,430000)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x,_:f'{int(x/10000)}만' if x>0 else '0'))
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("'%y"))
for sp in ['top','right']: ax.spines[sp].set_visible(False)
ax.tick_params(labelsize=10); ax.grid(axis='y',alpha=0.25,lw=0.6)
for d,y,t,dy in events:
    ax.scatter([d],[y],s=22,color=NAVY,zorder=5)
    ax.annotate(t,(d,y),xytext=(0,dy),textcoords='offset points',fontsize=8.3,
                ha='center',va='center',color=NAVY,weight='bold',
                arrowprops=dict(arrowstyle='-',color=NAVY,lw=0.6,alpha=0.6))
leg=[Patch(fc=UP_BG,label='상승 사이클'),Patch(fc=DOWN_BG,label='하락 사이클'),
     plt.Line2D([0],[0],color=GREEN,lw=1.5,label='주가(종가)')]
ax.legend(handles=leg,loc='upper left',fontsize=9,framealpha=0.9,ncol=3)
ax.set_title('OCI홀딩스(010060) 주가 사이클 History (2014~2026)  ·  단위: 원',
             fontsize=13,weight='bold',color=NAVY,loc='left',pad=10)
fig.text(0.125,0.02,'자료: FinanceDataReader(수정주가 종가) · 이벤트는 WebSearch+DART 공시 다중 검증  |  *2011 장중 65.7만원 슈퍼사이클은 데이터 이전(각주)',
         fontsize=7.6,color='#666')
fig.subplots_adjust(bottom=0.13,top=0.9,left=0.075,right=0.975)
fig.savefig(f'{OUT}/_hist_cycle_band.png',dpi=200)
print('저장: _hist_cycle_band.png')

# ── Forward 타임라인 (현재~2027.12) ──
fig2,ax2=plt.subplots(figsize=(12.6,5.4))
recent=c['2025-01-01':]
ax2.plot(recent.index,recent.values,color=GREEN,lw=1.3,zorder=4,label='실제 주가')
now=c.index[-1]; p0=float(c.iloc[-1])
fdates=pd.date_range(now,D('2027-12-31'),freq='MS')
n=len(fdates); x=np.linspace(0,1,n)
bull=p0+(430000-p0)*x**0.85
base=p0+(255000-p0)*np.sqrt(x)
bear=p0+(158000-p0)*x**0.7
for arr,col,lab,tgt in [(bull,RED,'Bull 43만+',430000),(base,NAVY,'Base 25.5만',255000),(bear,BLUE,'Bear 16만',158000)]:
    ax2.plot(fdates,arr,color=col,lw=1.6,ls='--',zorder=3)
    ax2.annotate(lab,(fdates[-1],arr[-1]),xytext=(6,0),textcoords='offset points',
                 fontsize=9,weight='bold',color=col,va='center')
ax2.fill_between(fdates,bear,bull,color='#e9eef5',alpha=0.7,zorder=1)
ax2.axvline(now,color='#999',lw=0.8,ls=':')
# 카탈리스트 마커
cats=[(D('2026-07-15'),'Section 232\n발표(임박)'),(D('2026-10-01'),'2Q26 폴리\n가동률 정상화'),
      (D('2027-03-01'),'SpaceX 공식화\n여부'),(D('2027-09-01'),'우주DC·증설\n수요 구체화')]
for d,t in cats:
    ax2.axvline(d,color='#bbb',lw=0.6,ls=':',zorder=1)
    ax2.annotate(t,(d,415000),fontsize=7.8,ha='center',va='top',color='#555',weight='bold')
ax2.scatter([now],[p0],s=40,color=GREEN,zorder=6)
ax2.annotate(f'현재 {int(p0/10000)}.0만',(now,p0),xytext=(-4,-16),textcoords='offset points',
             fontsize=9,weight='bold',color=GREEN,ha='right')
ax2.set_ylim(0,470000)
ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x,_:f'{int(x/10000)}만' if x>0 else '0'))
ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%y.%m"))
for sp in ['top','right']: ax2.spines[sp].set_visible(False)
ax2.tick_params(labelsize=9); ax2.grid(axis='y',alpha=0.25,lw=0.6)
ax2.legend(loc='upper left',fontsize=9,framealpha=0.9)
ax2.set_title('OCI홀딩스 Forward 주가 시나리오 (현재~2027.12)  ·  단위: 원',
              fontsize=13,weight='bold',color=NAVY,loc='left',pad=10)
fig2.text(0.125,0.02,'주: 시나리오는 폴리 ASP·Section232·SpaceX 공식화 조합 가정. Section232 결과가 방향을 가르는 binary 촉매.',
          fontsize=7.6,color='#666')
fig2.subplots_adjust(bottom=0.12,top=0.9,left=0.075,right=0.9)
fig2.savefig(f'{OUT}/_hist_forward.png',dpi=200)
print('저장: _hist_forward.png')
