# -*- coding: utf-8 -*-
"""OCI홀딩스 사이클별 증권가 목표주가·투자논거 히스토리 (2021~2026)"""
import sys, io, pathlib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

# (시기, 사이클, 대표 목표주가, 당시 투자 논거)
rows = [
 ("2021", 'Up', 'KB·대신 20만→21.5만', '폴리 ASP +15%QoQ·반도체폴리 2→4천톤·2021 흑전(OP 6,260억)'),
 ("2022", 'Up→Down', '폴리 강세 지속 전망(고점)', '상반기 폴리 $39 고점 낙관 → 하반기 공급계약 해지·조정'),
 ("2023", 'Up', '인적분할 SOTP 재평가', '지주 SOTP(미래에셋 지주 영업가치 2.1조)·기업가치 재평가'),
 ("2024~25", 'Down', '현대차 11만→<b>9만</b> 하향', '폴리 $6.55 부진·중국 증설. 단 "미국 태양광 핵심 공급망" 구조 긍정'),
 ("2026상", 'Up(버블)', '삼성 24.5→유진 40→<b>하나 55만</b>·교보 26→43만(<b>열흘 +65%</b>)', '우주태양광(SBSP)·미국셀 3.2→20GW·Non-PFE 웨이퍼·Section232·SpaceX'),
 ("2026.6~", 'Down', '급락 후 목표가 산재', 'Section232 발표 지연·테마 과열 되돌림(-50%)'),
]

def tr(r):
    t, ud, tp, logic = r
    if ud.startswith('Up') and 'Down' not in ud:
        col, bg = '#c0272d', '#fbeceb'
    elif ud == 'Down':
        col, bg = '#2f5fa6', '#eaf0f8'
    else:
        col, bg = '#8a6d00', '#fbf6e3'
    badge = f'<span style="color:#fff;background:{col};padding:2px 8px;border-radius:3px;font-weight:700;font-size:10.5px">{ud}</span>'
    return (f'<tr style="background:{bg}"><td class=pd>{t}</td><td>{badge}</td>'
            f'<td class=tp>{tp}</td><td class=l>{logic}</td></tr>')

html = '''<!DOCTYPE html><html><head><meta charset=utf-8><style>
body{font-family:"Malgun Gothic",sans-serif;padding:24px;background:#fff;color:#1a1a1a;display:inline-block;}
h2{font-size:15.5px;color:#123a6b;border-left:5px solid #123a6b;padding-left:10px;margin:0 0 3px;}
.sub{font-size:10.5px;color:#666;margin:0 0 12px 15px;}
table{border-collapse:collapse;font-size:11.8px;width:1150px;}
td,th{border:1px solid #c2ccd8;padding:6px 10px;vertical-align:middle;}
th{background:#123a6b;color:#fff;font-weight:600;text-align:center;}
td.pd{white-space:nowrap;font-weight:700;text-align:center;}
td:nth-child(2){text-align:center;white-space:nowrap;}
td.tp{text-align:left;font-size:11.3px;}
td.l{text-align:left;line-height:1.45;font-size:11.3px;}
.key{margin-top:11px;padding:9px 12px;background:#f4f7fb;border-left:4px solid #c0272d;font-size:11.3px;line-height:1.5;}
.foot{font-size:10px;color:#777;margin-top:8px;}
</style></head><body>
<h2>증권가 목표주가·투자논거 히스토리 -- 사이클별 (2021~2026)</h2>
<p class=sub>사이클 구간별로 당시 애널리스트들이 무엇을 상승·하락 논거로 봤는지 재구성 (증권사 리포트·언론 종합)</p>
<table><tr><th style="width:90px">시기</th><th style="width:82px">사이클</th><th style="width:360px">대표 증권가 목표주가</th><th>당시 투자 논거</th></tr>
''' + ''.join(tr(r) for r in rows) + '''
</table>
<div class=key><b>핵심 인사이트 -- 목표주가는 사이클을 "증폭"한다:</b> 하락기(2025) 현대차가 9만원까지 하향했다가 상승기(2026)엔 하나 55만원까지 상향(교보는 열흘 만에 +65%). 즉 街 목표가는 <b>후행·증폭 지표</b>이며, 역발상 관점에서 <b>하향 정점(9만)이 오히려 저점 부근</b>이었고 <b>상향 정점(55만)이 고점 부근</b>이었다. 목표가를 좇기보다 사이클 위치로 판단해야 한다.</div>
<p class=foot>자료: KB·대신·현대차·삼성·유진·교보·키움·미래에셋·하나증권 리포트 및 언론 종합. 목표가는 각 시점 대표치이며 이후 변경됨.</p>
</body></html>'''

fp = 'data/OCI홀딩스/_hist_analyst_table.html'
open(fp, 'w', encoding='utf-8').write(html)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(device_scale_factor=2)
    pg.goto(pathlib.Path(fp).resolve().as_uri()); pg.wait_for_timeout(400)
    pg.query_selector('body').screenshot(path='data/OCI홀딩스/_hist_analyst_table.png')
    b.close()
print('저장: _hist_analyst_table.png')
