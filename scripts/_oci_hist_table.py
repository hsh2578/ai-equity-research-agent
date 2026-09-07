# -*- coding: utf-8 -*-
"""OCI홀딩스 주가 사이클 변동요인 표 -- 3~6개월 세분 (참고 리포트 granularity)."""
import sys, io, pathlib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

# (기간, Up/Down, [불릿1, 불릿2], 가격이동)
rows = [
 ("'20.03~'21.09",'Up',['코로나 저점 후 폴리 $4→$32/kg[시장]·중국 감산[정책]+친환경 수요','[공시]2020.2 군산 폴리 생산중단→말레이 이전·2021 흑전(OP 6,260억)'],'2.7만→12.7만'),
 ("'21.09~'22.01",'Down',['폴리 고점 후 차익실현','코스피 전반 조정'],'12.7만→7.0만'),
 ("'22.01~'22.06",'Up',['폴리 강세 지속(→8월 $39 고점)·2021 사상최대 실적','말레이 3.5만톤 증설·원가 15%↓'],'7.0만→11.4만'),
 ("'22.06~'22.12",'Down',['<b>[공시]폴리 공급계약 해지(Wafer Works 1,784억, 8/18)</b>·폴리 급락','<b>[공시]포항공장 태풍 힌남노 침수 생산중단(9/6)</b>·금리인상'],'11.4만→6.4만'),
 ("'22.12~'23.06",'Up',['폴리 반등 + <b>[공시]회사분할결정(2022.11)→2023.5 재상장</b>','지주 SOTP 기업가치 재평가 기대'],'6.4만→11.3만'),
 ("'23.06~'24.12",'Down',['중국 대증설·폴리 $6.55/kg[시장](BEP $8 하회)·적자','미 규제 불확실[정책]·수요 관망'],'11.3만→5.5만'),
 ("'24.12~'25.08",'Up',['폴리 바닥 통과[시장]·흑자전환 기대','미국 비중국 프리미엄 부각[정책]'],'5.5만→~9만'),
 ("'25.08~'25.12",'Up',['<b>중국 공급개혁(8월·100만톤 감축)[정책]→폴리 +50% 반등[시장]</b>','흑전 가시화 + [공시]자사주 이익소각(주주환원)'],'~9만→12.9만'),
 ("'26.01~'26.04",'Up',['다보스 우주DC(1월)·에너지안보 테마[테마]·Section232 기대[정책]','비중국 폴리 프리미엄 $12/kg+[시장]'],'12.9만→30만'),
 ("'26.04~'26.05",'Up',['<b>SpaceX 폴리 공급 단독보도(4/14)[보도]</b>·목표가 상향','<b>257% YTD 급등·테마 정점 38.8만</b>'],'30만→38.8만'),
 ("'26.05말~'26.06.26",'Down',['<b>테마-펀더멘털 괴리 되돌림</b>·중대재해(6/8)[공시]','<b>Section232 발표 지연[정책]</b> (어닝쇼크는 원인 아님)'],'38.8만→19.4만(-50%)'),
 ("'26.06.26~현재",'조정',['7/1 24.0만 반등 시도 후 <b>7/3 21.3만 되밀림</b>','저점권 고변동·추세 미확정 (지속 반등 아님)'],'19.4만↔24.0만→21.3만'),
]

def tr(r):
    p, ud, bl, mv = r
    if ud == 'Up':
        color, bg = '#c0272d', '#fbeceb'
    elif ud == 'Down':
        color, bg = '#2f5fa6', '#eaf0f8'
    else:  # 반등(추세 미확정)
        color, bg = '#8a6d00', '#fbf6e3'
    badge = f'<span style="color:#fff;background:{color};padding:2px 8px;border-radius:3px;font-weight:700;font-size:10.5px">{ud}</span>'
    TAGCOL = {'공시':'#c0272d','정책':'#1a7a3a','시장':'#8a6d00','보도':'#7a3aa0','테마':'#7a3aa0'}
    def colorize(s):
        for t, col in TAGCOL.items():
            s = s.replace(f'[{t}]', f'<b style="color:{col}">[{t}]</b>')
        return s
    bul = '<br>'.join(f'· {colorize(b)}' for b in bl)
    return (f'<tr style="background:{bg}"><td class=pd>{p}</td><td>{badge}</td>'
            f'<td class=l>{bul}</td><td class=mv>{mv}</td></tr>')

html = '''<!DOCTYPE html><html><head><meta charset=utf-8><style>
body{font-family:"Malgun Gothic",sans-serif;padding:24px;background:#fff;color:#1a1a1a;display:inline-block;}
h2{font-size:15.5px;color:#123a6b;border-left:5px solid #123a6b;padding-left:10px;margin:0 0 3px;}
.sub{font-size:10.5px;color:#666;margin:0 0 12px 15px;}
table{border-collapse:collapse;font-size:11.5px;width:1180px;}
td,th{border:1px solid #c2ccd8;padding:5px 10px;vertical-align:middle;}
th{background:#123a6b;color:#fff;font-weight:600;text-align:center;}
td.pd{white-space:nowrap;font-weight:600;text-align:center;font-size:11px;}
td:nth-child(2){text-align:center;white-space:nowrap;}
td.l{text-align:left;line-height:1.5;}
td.mv{white-space:nowrap;text-align:center;font-size:10.5px;color:#333;font-weight:600;}
.foot{font-size:10px;color:#777;margin-top:9px;}
</style></head><body>
<p class=sub>3~6개월 스윙 세분 · 출처 태그 <b style="color:#c0272d">[공시]</b>DART 수시공시 · <b style="color:#1a7a3a">[정책]</b>미·중 정책(공시 대상 아님) · <b style="color:#8a6d00">[시장]</b>폴리 국제가 · <b style="color:#7a3aa0">[보도]</b>언론(회사 미공시) &nbsp;→ 공시가 유일 동인이 아님을 명시</p>
<table><tr><th style="width:118px">기간</th><th style="width:62px">Up/Down</th><th>주가 변동 요인</th><th style="width:135px">주가 이동</th></tr>
''' + ''.join(tr(r) for r in rows) + '''
</table>
<p class=foot>자료: FinanceDataReader·DART 전자공시·언론 종합 &nbsp;|&nbsp; <b>*최근 폴리 공급계약 DART 공시 없음 → SpaceX(4/14 급등 촉매)는 언론 단독보도·회사 미공시</b> &nbsp;|&nbsp; *각주(데이터 이전): 2011 장중 65.7만원 슈퍼사이클→중국 공급과잉 폭락</p>
</body></html>'''

fp = 'data/OCI홀딩스/_hist_driver_table.html'
open(fp, 'w', encoding='utf-8').write(html)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(device_scale_factor=3)
    pg.goto(pathlib.Path(fp).resolve().as_uri()); pg.wait_for_timeout(400)
    pg.query_selector('body').screenshot(path='data/OCI홀딩스/_hist_driver_table.png')
    b.close()
print('저장: _hist_driver_table.png (3~6개월 세분, 12구간)')
