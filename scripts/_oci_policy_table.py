# -*- coding: utf-8 -*-
"""미국 4대 비중국 폴리실리콘 정책 + 반도체 수요 x OCI홀딩스 주가 영향 검증
   (deep-research 19개 검증 클레임 기반 -- 인과: 실제 주가 반응만 discrete 촉매로 인정)"""
import sys, io, pathlib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

# (이슈, 시점·내용, 주가영향 등급, 검증된 영향 서술)
rows = [
 ('Section 232', '2025.7.1 조사 개시 · 폴리 및 파생제품 · 발표 반복 지연(미결)', 'discrete',
  '<b>주가를 실제 움직인 유일한 촉매.</b> 통과 기대에 2026 급등(1/2 10.55만→4/27 37.7만, +257%), 발표 지연에 6월 하락. UFLPA 대비 공급망 전반 차단 가능'),
 ('Section 301', '2024.12 발표·2025.1.1 발효 · 중국산 웨이퍼·폴리 관세 50% · 2026 비중국 폴리 제외 확정', 'structural',
  '중국산 폴리 50% 관세로 비중국 프리미엄 강화. 2026 USTR가 비중국 고순도 폴리 추가관세 제외 확정 → OCI 직접 수혜. 단 발효 자체는 discrete 급등 촉매가 아닌 구조적 우호'),
 ('UFLPA', '2021.12 서명·2022.6 시행 · 2024~ Entity List 78개사 추가', 'structural',
  '시행 자체는 주가 무반응(당시 폴리 하락기). 효과는 누적 -- 한화큐셀 통관지연(2025.6~4개월) 이후 OCI가 4Q25 한화 주요 고객사로 편입'),
 ('AD/CVD', '반덤핑·상계관세(중국·동남아산 태양광)', 'none',
  '발표-주가 직접 반응 확인 안 됨. 비중국 프리미엄의 배경 요인이나 discrete 촉매 아님'),
 ('FEOC / Non-PFE', '해외우려기관 배제 → Non-PFE 공급망 수요 구조화', 'structural',
  '2025~26 비중국 프리미엄 재평가의 축(구조적). OCI, Mission Solar용 베트남 웨이퍼 공장 지분 인수로 Non-PFE 공급 확보'),
 ('반도체 수요', 'AI·데이터센터發 · OCI 11-Nine급 · OTSM(도쿠야마, 8,000톤/2029) · 반도체 소재 증설', 'forward',
  '2026 랠리는 태양광 테마 주도 -- 반도체·OTSM은 forward/구조 모멘텀이며 2026 급등의 discrete 원인은 아님'),
]

GRADE = {
 'discrete': ('#c0272d', '주가 촉매 O'),
 'structural': ('#8a6d00', '구조적(누적)'),
 'forward': ('#2f5fa6', 'Forward'),
 'none': ('#888888', '영향 없음'),
}

def tr(r):
    name, when, grade, desc = r
    col, lab = GRADE[grade]
    bg = '#fbeceb' if grade=='discrete' else ('#f6f7f9' if grade=='none' else '#f4f7fb')
    badge = f'<span style="color:#fff;background:{col};padding:2px 9px;border-radius:3px;font-weight:700;font-size:10.5px">{lab}</span>'
    return (f'<tr style="background:{bg}"><td class=nm>{name}</td><td class=w>{when}</td>'
            f'<td class=g>{badge}</td><td class=l>{desc}</td></tr>')

html = '''<!DOCTYPE html><html><head><meta charset=utf-8><style>
body{font-family:"Malgun Gothic",sans-serif;padding:24px;background:#fff;color:#1a1a1a;display:inline-block;}
h2{font-size:15.5px;color:#123a6b;border-left:5px solid #123a6b;padding-left:10px;margin:0 0 3px;}
.sub{font-size:10.5px;color:#666;margin:0 0 12px 15px;}
table{border-collapse:collapse;font-size:11.6px;width:1180px;}
td,th{border:1px solid #c2ccd8;padding:6px 10px;vertical-align:middle;}
th{background:#123a6b;color:#fff;font-weight:600;text-align:center;}
td.nm{white-space:nowrap;font-weight:700;text-align:center;}
td.w{text-align:left;font-size:11px;}
td.g{text-align:center;white-space:nowrap;}
td.l{text-align:left;line-height:1.45;font-size:11.2px;}
.key{margin-top:11px;padding:9px 12px;background:#f4f7fb;border-left:4px solid #c0272d;font-size:11.3px;line-height:1.5;}
.foot{font-size:10px;color:#777;margin-top:8px;}
</style></head><body>
<h2>미국 비중국 폴리실리콘 정책(5종) + 반도체 수요 -- OCI홀딩스 주가 영향 검증</h2>
<p class=sub>deep-research 다중 검증(발표일 ↔ 실제 주가 반응 대조) · 실제 가격이 움직인 것만 "주가 촉매 O"로 인정 · 상관관계·구조적 배경은 별도 분류</p>
<table><tr><th style="width:110px">이슈</th><th style="width:330px">시점·내용</th><th style="width:96px">주가 영향</th><th>검증된 영향</th></tr>
''' + ''.join(tr(r) for r in rows) + '''
</table>
<div class=key><b>결론:</b> 5대 정책 중 <b>주가를 실제로 움직인 것은 Section 232 하나</b>다. Section 301·UFLPA·AD/CVD·FEOC는 비중국 프리미엄을 떠받친 <b>구조적 배경</b>이지 발표 시점에 주가를 움직인 discrete 촉매가 아니었다(그래서 주가 History에 Section 232만 등장하는 것이 정당하다). 반도체 수요·OTSM도 forward 모멘텀이며 2026 급등의 원인은 태양광 테마였다.</div>
<p class=foot>자료: 미 의회조사국(CRS)·strtrade·pv-tech·하나증권 Initiation·아시아경제·이투데이·뉴스핌 등 deep-research 검증. 주가: 2026.1.2 10.55만 → 4.27 37.7만(+257%).</p>
</body></html>'''

fp = 'data/OCI홀딩스/_hist_policy_table.html'
open(fp, 'w', encoding='utf-8').write(html)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(device_scale_factor=2)
    pg.goto(pathlib.Path(fp).resolve().as_uri()); pg.wait_for_timeout(400)
    pg.query_selector('body').screenshot(path='data/OCI홀딩스/_hist_policy_table.png')
    b.close()
print('저장: _hist_policy_table.png')
