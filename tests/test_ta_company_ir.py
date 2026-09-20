# -*- coding: utf-8 -*-
"""ta_company_ir 테스트: IR 페이지 링크 파싱·기간 라벨·이미지 슬라이드 PNG 렌더 (네트워크 없음)."""
import io
import os
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
import ta_company_ir as c  # noqa: E402

_failed = []


def eq(a, b, msg):
    if a != b:
        _failed.append(msg)
        print(f'  [FAIL] {msg}\n      기대: {b!r}\n      실제: {a!r}')


HTML = '''<ul class="cards"><li><div class="card"><div class="card-subject">2026년 2분기 연결 실적발표</div>
<a class="audio-button" href="https://ircc.example/webcastCall.do?evntId=EV1"></a>
<a class="download-button" href="javascript:" onclick="front_file_download('irDataEarningsRelease', '50883_1_abc.pdf', '(HD현대중공업) 2026년 2분기 경영실적.pdf')"></a>
</div></li><li><div class="card"><div class="card-subject">2025년 4분기 연결 실적발표</div>
<a onclick="front_file_download('irDataEarningsRelease', '50001_1_def.pdf', 'HD현대중공업 2025년 4분기 경영실적 P&L.pdf')"></a></div></li>
<li><a href="/upload/ir/2025_annual_report.pdf?dl=1">연간보고서</a></li></ul>'''
links = c.parse_links(HTML, 'https://hd-hhi.com/kr/investors/ir-data/earnings-release')
eq(len(links), 3, '링크 3건 (front_file_download 2 + href pdf 1)')
eq(links[0]['title'], '2026년 2분기 연결 실적발표', '카드 제목이 링크 제목')
eq(links[0]['url'].startswith('https://hd-hhi.com/common/fileDownload?folderName=irDataEarningsRelease&fileName=50883_1_abc.pdf&originalFileName='), True, 'fileDownload URL 조립')
eq('%EF%BC%86' in links[1]['url'], True, '& 는 전각 ＆ 로 치환(사이트 JS 와 동일)')
eq(links[2]['url'], 'https://hd-hhi.com/upload/ir/2025_annual_report.pdf?dl=1', 'href .pdf 절대경로화(쿼리 유지)')
eq(c.period_of('2026년 2분기 연결 실적발표'), '2026Q2', '기간 라벨 분기')
eq(c.period_of('2025년 상반기 IR'), '2025H1', '기간 라벨 반기')
eq(c.period_of('IR 자료'), '', '기간 없으면 빈 문자열')

# 이미지 슬라이드 -> PNG 렌더
import fitz  # noqa: E402
doc = fitz.open()
for _ in range(2):
    page = doc.new_page(width=300, height=200)
    page.draw_rect(fitz.Rect(20, 20, 280, 180), color=(0, 0, 1), fill=(0.8, 0.8, 1))
buf = doc.tobytes()
with tempfile.TemporaryDirectory() as td:
    info = c.save_pdf(buf, td, '2026Q2_test', png_pages=20)
    eq(info['pages'], 2, '페이지 수')
    eq(info['png_dir'], '2026Q2_test', '텍스트 없으면 PNG 디렉터리 생성')
    eq(sorted(os.listdir(os.path.join(td, '2026Q2_test'))), ['p01.png', 'p02.png'], 'PNG 2장')
    eq('텍스트 레이어 없음' in open(os.path.join(td, '2026Q2_test.txt'), encoding='utf-8').read(), True, 'txt 에 PNG 안내')

HOME = '''<nav><a href="/kr/company/about">회사소개</a><a href="/kr/investors/ir-data/earnings-release">IR자료</a>
<a href="/kr/investors/fi">재무정보</a><a href="https://careers.example.com/ir">채용 IR</a><a href="/kr/news/press">보도자료</a>
<a href="/kr/investors/ir-data/earnings-release#top">IR자료 dup</a><a href="mailto:ir@x.com">IR 문의</a></nav>'''
c1 = c.ir_candidates(HOME, 'https://hd-hhi.com/kr/main', level=1)
eq([x['url'] for x in c1], ['https://hd-hhi.com/kr/investors/ir-data/earnings-release', 'https://hd-hhi.com/kr/investors/fi'], '1단계 후보: IR자료가 먼저, 다른 호스트·mailto·채용 제외, # 중복 제거')
eq(c.period_of('2026년 2분기 연결 실적발표') and True, True, 'sanity')
# (c) 한화오션형: download + onclick 토큰, URL 접두는 JS 정의에서
HWO = '''<div class="post"><a href="#" class="post-viewer"><div class="title m_h9"><span>한화오션 2026년 2분기 실적발표 (2026년 7월 27일)</span></div></a>
<div class="post-down"><a class="m_btn" download="한화오션_2Q26 실적발표 PPT.pdf" onclick="fileDownload(&quot;TOK%2B1&quot;)"></a></div></div>
<div class="post"><div class="title"><span>이사회 규정</span></div><a download="규정.pdf" onclick="fileDownload(&quot;TOK2&quot;)"></a></div>
<script src="/js/dev.common.js"></script>'''
JS = "function fileDownload(a,b,c){\n// var f = document.downloadFrm;\n// f.action = getContextPath() + \"/api/fileDownload\";\n}\nfunction fileDownload(param){\n let url = getContextPath() + \"/attach?et=\" + param;\n window.location.href = url;\n}"
hwo = c.parse_links(HWO, 'https://www.hanwhaocean.com/investors/ea', fetch=lambda u: JS)
eq([x['url'] for x in hwo], ['https://www.hanwhaocean.com/attach?et=TOK%2B1', 'https://www.hanwhaocean.com/attach?et=TOK2'], '(c) 토큰 -> JS 정의의 /attach?et= 접두 (주석 정의는 건너뜀)')
eq(hwo[0]['title'], '한화오션 2026년 2분기 실적발표 (2026년 7월 27일)', '(c) 제목은 .title span')
eq(bool(c._IR_TITLE.search(hwo[1]['title'] + ' ' + hwo[1]['filename'])), False, '"이사회 규정" 은 IR 자료 아님')
eq(bool(c._IR_TITLE.search('다운로드 다운로드.pdf')), False, '"다운로드" 만으로는 IR 자료 아님 (CJ 오탐)')
eq(bool(c._IR_TITLE.search('DIRECTORS.pdf')), False, 'DIRECTORS 의 IR 은 매칭 안 됨')
ENT = '''<a href="/ir/board/list.do">IR&nbsp;자료실</a><a href="/ir/management/directors.jsp">이사회</a><a href="/ir/info/list.do">전자공고</a>'''
ce = c.ir_candidates(ENT, 'https://www.cjfreshway.com/', level=1)
eq(ce[0]['url'], 'https://www.cjfreshway.com/ir/board/list.do', '엔티티(&nbsp;) 정규화 후 IR 자료실이 1위, 이사회 페이지는 제외')
# 게시판형(CJ): 목록 -> 게시글 -> 첨부(/down.do?path=...pdf&name=...pdf)
LIST = '''<table><tr><td class="title"><a href='view.do?seq=669'>메리츠증권 NDR</a></td></tr>
<tr><td class="title"><a href='view.do?seq=667'>2026년 2분기 경영실적발표</a></td></tr>
<tr><td class="title"><a href='view.do?seq=664'>[공고] 제38기 정기주주총회 소집 통지</a></td></tr></table>'''
VIEW = '''<p class="attachment"><a href="/down.do;jsessionid=X?path=%2fupload%2firDown%2fabc.pdf&name=CJ%ed%94%84_IR_2026.2Q.pdf">CJ프레시웨이_IR_2026.2Q.pdf</a></p>'''
pl = c.post_links(LIST, 'https://www.cjfreshway.com/ir/board/list.do')
eq([x['title'] for x in pl], ['2026년 2분기 경영실적발표'], '게시글 링크: IR 제목만(NDR·주총 소집 제외), 단따옴표 href')
def fake_fetch(u):
    return (LIST, u, 'http') if u.endswith('list.do') else (VIEW, u, 'http')
cl, how = c.collect_page('https://www.cjfreshway.com/ir/board/list.do', fetch_page=fake_fetch)
eq(len(cl), 1, '게시글 첨부 1건(두 게시글이 같은 첨부 URL 이면 1건)')
eq(cl[0]['filename'], 'CJ프_IR_2026.2Q.pdf', '쿼리 name= 에서 파일명')
eq(cl[0]['url'].startswith('https://www.cjfreshway.com/down.do?path='), True, '첨부 URL 절대경로 + jsessionid 제거')
eq(cl[0]['referer'], 'https://www.cjfreshway.com/ir/board/view.do?seq=667', '첨부의 Referer 는 게시글 URL')
eq(c.clean_url('https://x.com/a/down.do;jsessionid=ABC.node1?path=p.pdf&name=n.pdf'), 'https://x.com/a/down.do?path=p.pdf&name=n.pdf', 'clean_url')
print('=' * 66)
if _failed:
    print(f'  ta_company_ir 테스트: {len(_failed)}개 실패')
    sys.exit(1)
print('  ta_company_ir 테스트: 26개 통과 / 0개 실패')
