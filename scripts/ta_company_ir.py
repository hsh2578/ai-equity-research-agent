# -*- coding: utf-8 -*-
"""회사 IR 홈페이지에서 실적발표·IR 자료 PDF 를 받는다 -> data/{종목}/ta/ir_site/ + ir_materials/index.json 에 합류.

KIND IR자료실(ta_kind_ir)은 중소형주만 쓴다. 대형주는 자사 IR 페이지에 올린다(HD현대중공업 실측: KIND 0건, 홈페이지에 분기 실적발표 8건+).
페이지 주소는 세 경로로 정한다: --url > docs/research-ta/ir_sites.json 등록 > **자동 탐색**
(DART company.json 의 홈페이지 주소 -> 'IR/투자정보/Investors' 링크 -> 그 안의 '실적/IR자료/presentation' 링크, 최대 2단계).
자동 탐색이 성공하면 registry 에 "auto" 로 저장해 다음부터는 바로 간다. JS 로만 그려지는 홈페이지는 Playwright 로 렌더한다.
링크 패턴 2종: (a) href 가 .pdf 로 끝나는 것 (b) HD현대 계열 CMS 의 front_file_download('folder','file','orig') -> /common/fileDownload
슬라이드가 이미지뿐이면(텍스트 0자) 페이지를 PNG 로 렌더해 둔다 -- 작성자가 Read 로 직접 본다(OCR 없음).
usage: python scripts/ta_company_ir.py {종목명} [--url URL ...] [--max 6] [--png-pages 20] [--no-discover] [--rediscover]
"""
import html as html_lib
import io
import os
import re
import sys
import time
import urllib.parse
from datetime import date

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ta_common import ta_dir, manifest_update, read_json, write_json  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, 'docs', 'research-ta', 'ir_sites.json')
HEADERS = {'User-Agent': 'Mozilla/5.0'}
_SESSION = None
_JSESSION = re.compile(r';jsessionid=[^?&#/]*', re.I)


def _sess():
    global _SESSION
    if _SESSION is None:
        import requests
        _SESSION = requests.Session()
        _SESSION.headers.update(HEADERS)
    return _SESSION


def clean_url(url):
    """URL 경로의 ';jsessionid=...' 를 뗀다. 세션은 쿠키로 유지되므로 경로의 옛 세션 ID 는 오히려 실패 원인이다."""
    return _JSESSION.sub('', url)
_FFD = re.compile(r"front_file_download\(\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*\)")
_PDF = re.compile(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', re.I)
_SUBJECT = re.compile(r'card-subject"[^>]*>\s*([^<]{3,80}?)\s*<')
_QTR = re.compile(r'(20\d\d)\s*년?\s*(?:(\d)\s*분기|([1-4])Q|(상반기|하반기))')
_ANCHOR = re.compile(r'<a[^>]+href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', re.S | re.I)
# 게시판형(CJ프레시웨이 /ir/board/list.do): 목록 -> 게시글 -> 첨부. 게시글 링크는 제목이 IR 자료 패턴이고 href 가 상세 페이지 모양
_POST_HREF = re.compile(r'view|detail|read|seq=|idx=|\bno=|articleId|bbsId|nttId', re.I)
# 1단계: 홈페이지에서 IR 섹션으로 가는 링크 / 2단계: IR 섹션 안에서 자료 목록으로 가는 링크
_IR_L1 = re.compile(r'\bir\b|invest|투자정보|주주|investor|ir-data|earning|실적|기업설명', re.I)
_IR_L2 = re.compile(r'실적|earning|ir-data|presentation|자료|material|발표|설명회|ir\b|invest', re.I)
# PDF 제목 수락 기준 -- 강한 패턴만 (지배구조·정관·'다운로드' 같은 것은 IR 자료가 아니다)
_IR_TITLE = re.compile(r'실적|(?<![A-Za-z])IR(?![A-Za-z])|설명회|earning|presentation|기업설명|annual\s*report|투자설명|경영실적|수주잔고|backlog', re.I)
_SKIP = re.compile(r'login|join|recruit|career|채용|news|보도|mailto:|javascript:|management|directors|committee|auditor|shareholder|dividend|rule|governance|정관|이사회|\.(?:jpg|png|gif|zip|hwp|xlsx?|docx?)$', re.I)
_STRONG_L1 = re.compile(r'자료실|IR\s*자료|실적\s*발표|earnings?|presentation|ir-data', re.I)
# (c) 한화오션형: <a download="파일.pdf" onclick="fileDownload(&quot;TOKEN&quot;)"> -- 토큰을 URL 로 바꾸는 규칙은 사이트 JS 에서 읽는다
_DL_ANCHOR = re.compile(r'<a\b[^>]*>', re.I)
_DL_ATTR = re.compile(r'\bdownload="([^"]+\.pdf)"', re.I)
_DL_ONCLICK = re.compile(r'onclick="(\w+)\((?:&quot;|\')([^&\'"]+)(?:&quot;|\')\)"', re.I)
_POST_TITLE = re.compile(r'class="title[^"]*"[^>]*>\s*(?:<span[^>]*>)?\s*([^<]{3,120}?)\s*<')
_SCRIPT_SRC = re.compile(r'<script[^>]+src="([^"]+)"', re.I)
_JS_CACHE = {}


def _title_near(html, pos):
    m = None
    for m in _SUBJECT.finditer(html, max(0, pos - 800), pos):
        pass
    return m.group(1).strip() if m else ''


def download_prefix(html, base_url, fn_name, fetch=None):
    """onclick 함수(fileDownload 등)의 정의를 페이지·외부 JS 에서 찾아 '/attach?et=' 같은 URL 접두를 돌려준다. 못 찾으면 ''.
    주석 처리된 정의(한화오션 dev.common.js 첫 정의)는 건너뛴다."""
    import requests
    fetch = fetch or (lambda u: requests.get(u, headers=HEADERS, timeout=20).text)
    sources = [html]
    for src in _SCRIPT_SRC.findall(html):
        u = urllib.parse.urljoin(base_url, src)
        if u not in _JS_CACHE:
            try:
                _JS_CACHE[u] = fetch(u)
            except Exception:
                _JS_CACHE[u] = ''
        sources.append(_JS_CACHE[u])
    pat = re.compile(r'function\s+' + re.escape(fn_name) + r'\s*\(([^)]*)\)\s*\{')
    for js in sources:
        for m in pat.finditer(js):
            body = js[m.end():m.end() + 800]
            live = '\n'.join(l for l in body.split('\n') if not l.strip().startswith('//'))
            q = re.search(r'["\']((?:https?://[^"\']+)?/[A-Za-z0-9_./-]*\?[A-Za-z_]+=)["\']\s*\+', live)
            if q:
                return q.group(1)
    return ''


def parse_links(html, base_url, fetch=None):
    """[{'title','url','filename'}] -- 문서 순서대로, 중복 URL 제거. 패턴 (a) href .pdf (b) HD현대 CMS (c) download+onclick 토큰."""
    out, seen = [], set()
    items = []
    prefixes = {}
    for m in _DL_ANCHOR.finditer(html):
        tag = m.group(0)
        d, o = _DL_ATTR.search(tag), _DL_ONCLICK.search(tag)
        if not (d and o):
            continue
        fn, token = o.group(1), o.group(2)
        if fn not in prefixes:
            prefixes[fn] = download_prefix(html, base_url, fn, fetch)
        if not prefixes[fn]:
            continue
        url = urllib.parse.urljoin(base_url, prefixes[fn] + token)
        tm = None
        for tm in _POST_TITLE.finditer(html, max(0, m.start() - 1500), m.start()):
            pass
        title = html_lib.unescape(tm.group(1)).strip() if tm else d.group(1)
        items.append((m.start(), title, url, d.group(1)))
    for m in _FFD.finditer(html):
        folder, fname, orig = m.groups()
        url = urllib.parse.urljoin(base_url, '/common/fileDownload?' + urllib.parse.urlencode(
            {'folderName': folder, 'fileName': fname, 'originalFileName': orig.replace('#', '＃').replace('&', '＆')}))
        items.append((m.start(), _title_near(html, m.start()) or orig, url, orig))
    for m in _PDF.finditer(html):
        url = urllib.parse.urljoin(base_url, html_lib.unescape(m.group(1)))
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        fname = os.path.basename(urllib.parse.urlparse(url).path)
        if not fname.lower().endswith('.pdf'):  # 쿼리의 name=/path= 에서 파일명
            fname = os.path.basename(next((v[0] for k, v in q.items() if v and v[0].lower().endswith('.pdf') and k.lower() in ('name', 'filename', 'orgnm', 'originalfilename')),
                                          next((v[0] for v in q.values() if v and v[0].lower().endswith('.pdf')), fname)))
        title = _title_near(html, m.start())
        if not title:  # 앵커 텍스트를 제목으로
            a = html.rfind('<a', 0, m.start())
            e = html.find('</a>', m.start())
            if 0 <= a < m.start() and e > 0:
                title = re.sub(r'<[^>]+>|\s+', ' ', html[html.find('>', m.start()) + 1:e]).strip()
        items.append((m.start(), title or fname, url, fname))
    for _pos, title, url, fname in sorted(items):
        if url in seen:
            continue
        seen.add(url)
        out.append({'title': title, 'url': url, 'filename': fname})
    return out


def post_links(html, base_url, limit=6):
    """목록 페이지에서 IR 자료 제목을 가진 게시글 링크 [{'title','url'}] (최신순 = 문서 순서)."""
    host = urllib.parse.urlparse(base_url).netloc.split(':')[0].removeprefix('www.')
    out, seen = [], set()
    for href, inner in _ANCHOR.findall(html):
        text = re.sub(r'<[^>]+>|\s+', ' ', html_lib.unescape(inner).replace('\xa0', ' ')).strip()
        url = urllib.parse.urljoin(base_url, html_lib.unescape(href.strip()))
        u = urllib.parse.urlparse(url)
        if u.netloc.split(':')[0].removeprefix('www.') != host or url in seen:
            continue
        if not _POST_HREF.search(url) or not _IR_TITLE.search(text) or _SKIP.search(text):
            continue
        seen.add(url)
        out.append({'title': text, 'url': url})
        if len(out) >= limit:
            break
    return out


def collect_page(url, fetch_page=None, posts=6, log=None):
    """한 페이지의 IR PDF 링크 + (게시판이면) 게시글 안의 첨부까지. -> (links, how)"""
    fetch_page = fetch_page or fetch_html
    h, b, how = fetch_page(url)
    links = [lk for lk in parse_links(h, b) if _IR_TITLE.search(lk['title'] + ' ' + lk['filename'])]
    for lk in links:
        lk['url'] = clean_url(lk['url']); lk.setdefault('referer', b)
    for post in post_links(h, b, limit=posts):
        try:
            ph, pb, _ = fetch_page(post['url'])
        except Exception as e:
            if log:
                log(f'  [게시글] {post["url"]}: {e!r}'[:140])
            continue
        for lk in parse_links(ph, pb):
            if lk['url'] in {x['url'] for x in links}:
                continue
            if not _IR_TITLE.search(lk['title'] + ' ' + lk['filename'] + ' ' + post['title']):
                continue
            lk['title'] = post['title'] if not _IR_TITLE.search(lk['title']) or len(lk['title']) < 6 else lk['title']
            lk['url'] = clean_url(lk['url']); lk['referer'] = post['url']
            links.append(lk)
        time.sleep(0.3)
    return links, how


def period_of(title):
    """'2026년 2분기 연결 실적발표' -> '2026Q2', '2025년 상반기' -> '2025H1', 없으면 ''."""
    m = _QTR.search(title or '')
    if not m:
        return ''
    y, q, q2, half = m.groups()
    if q or q2:
        return f'{y}Q{q or q2}'
    return f"{y}{'H1' if half == '상반기' else 'H2'}"


def slug(s):
    return re.sub(r'[^0-9A-Za-z가-힣]+', '_', s).strip('_')[:60] or 'ir'


def ir_candidates(html, base_url, level=1, limit=10):
    """홈페이지(level 1) 또는 IR 섹션(level 2)에서 다음 단계 링크를 고른다. 같은 호스트만, 점수순."""
    pat = _IR_L1 if level == 1 else _IR_L2
    host = urllib.parse.urlparse(base_url).netloc.split(':')[0].removeprefix('www.')
    scored, seen = [], set()
    for href, inner in _ANCHOR.findall(html):
        text = re.sub(r'<[^>]+>|\s+', ' ', html_lib.unescape(inner).replace('\xa0', ' ')).strip()
        url = urllib.parse.urljoin(base_url, html_lib.unescape(href.strip()))
        u = urllib.parse.urlparse(url)
        if u.scheme not in ('http', 'https') or u.netloc.split(':')[0].removeprefix('www.') != host:
            continue
        if _SKIP.search(url) or _SKIP.search(text):
            continue
        key = url.split('#')[0].rstrip('/')
        if key in seen or key.rstrip('/') == base_url.rstrip('/'):
            continue
        hay = url + ' ' + text
        if not pat.search(hay):
            continue
        seen.add(key)
        score = 0
        score += 4 if _STRONG_L1.search(text) else 0
        score += 3 if re.search(r'IR\s*자료|실적\s*발표|earnings?\s*release|presentation|ir-data', hay, re.I) else 0
        score += 2 if re.search(r'\bIR\b|investors?', hay, re.I) else 0
        score += 1 if re.search(r'실적|earning|자료|material', hay, re.I) else 0
        scored.append((-score, len(url), key, text))
    scored.sort()
    return [{'url': u, 'text': t} for _s, _l, u, t in scored[:limit]]


def homepage_url(stock):
    """DART company.json 의 hm_url. 없으면 ''."""
    from dart_api import get_corp_code  # .env 자동 로드
    import requests
    cc = get_corp_code(stock)
    corp = cc[0] if isinstance(cc, (list, tuple)) else cc
    r = requests.get('https://opendart.fss.or.kr/api/company.json',
                     params={'crtfc_key': os.environ.get('DART_API_KEY', ''), 'corp_code': corp}, timeout=20).json()
    hm = (r.get('hm_url') or '').strip()
    if not hm:
        return ''
    return hm if hm.startswith('http') else 'https://' + hm


def _render(url, timeout=30000):
    """JS 로만 그려지는 페이지 -- Playwright 로 렌더한 HTML 과 최종 URL."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(user_agent=HEADERS['User-Agent'])
        pg.goto(url, wait_until='networkidle', timeout=timeout)
        html, final = pg.content(), pg.url
        b.close()
    return html, final


def fetch_html(url, min_anchors=5):
    """requests 로 받고 앵커가 너무 적으면(SPA) Playwright 로 다시 받는다. -> (html, final_url, how)."""
    r = _sess().get(url, timeout=30, allow_redirects=True)
    r.raise_for_status()
    html, final = r.text, r.url
    if len(_ANCHOR.findall(html)) >= min_anchors:
        return html, final, 'http'
    try:
        html, final = _render(final)
        return html, final, 'render'
    except Exception as e:  # 렌더 실패면 있는 것으로 간다
        return html, final, f'render-failed:{type(e).__name__}'


def discover(stock, max_fetch=14, log=print):
    """홈페이지 -> IR 링크 -> 자료 목록 페이지. PDF 링크가 있는 페이지 URL 목록을 돌려준다(없으면 [])."""
    home = homepage_url(stock)
    if not home:
        log('  [탐색] DART 에 홈페이지 주소 없음')
        return []
    try:
        html, base, how = fetch_html(home)
    except Exception as e:
        log(f'  [탐색] 홈페이지 실패 {home}: {e!r}'[:160])
        return []
    log(f'  [탐색] 홈페이지 {base} ({how})')
    queue = [(c['url'], 1) for c in ir_candidates(html, base, level=1, limit=6)]
    found, visited, fetched = [], {base.rstrip('/')}, 0
    while queue and fetched < max_fetch:
        url, level = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        try:
            h, b, how = fetch_html(url)
            pdfs, _ = collect_page(url, fetch_page=lambda u, _h=h, _b=b, _w=how: (_h, _b, _w) if u == url else fetch_html(u), posts=3, log=log)
        except Exception as e:
            log(f'  [탐색] {url}: {e!r}'[:140])
            continue
        fetched += 1
        page_ok = bool(_IR_L2.search(url)) or bool(re.search(r'<(?:h1|h2|title)[^>]*>[^<]*(?:IR|실적|투자|Investor)[^<]*<', h, re.I))
        log(f'  [탐색] L{level} {url} ({how}) PDF {len(pdfs)}건' + ('' if page_ok else ' (IR 페이지 아님, 제외)'))
        if pdfs and page_ok:
            found.append({'url': b, 'pdfs': len(pdfs)})
        if level == 1:
            queue += [(c['url'], 2) for c in ir_candidates(h, b, level=2, limit=6) if c['url'] not in visited]
    found.sort(key=lambda x: -x['pdfs'])
    return [f['url'] for f in found[:3]]


def save_pdf(content, out_dir, name, png_pages):
    """PDF 저장 + 텍스트 추출; 텍스트가 없으면 PNG 렌더. -> dict(pages, chars, txt, png_dir)."""
    import fitz
    pdf = os.path.join(out_dir, name + '.pdf')
    with open(pdf, 'wb') as f:
        f.write(content)
    doc = fitz.open(pdf)
    text = '\n'.join(f'[p{i + 1}]\n' + p.get_text() for i, p in enumerate(doc))
    chars = len(re.sub(r'\[p\d+\]|\s', '', text))
    txt = os.path.join(out_dir, name + '.txt')
    png_dir = ''
    if chars < 100 * len(doc):  # 이미지 슬라이드 -- 눈으로 읽을 PNG
        png_dir = os.path.join(out_dir, name)
        os.makedirs(png_dir, exist_ok=True)
        for i in range(min(len(doc), png_pages)):
            doc[i].get_pixmap(matrix=fitz.Matrix(1.4, 1.4)).save(os.path.join(png_dir, f'p{i + 1:02d}.png'))
        text += f'\n\n[텍스트 레이어 없음 -- 슬라이드 이미지. PNG {min(len(doc), png_pages)}장: {os.path.basename(png_dir)}/pNN.png 을 Read 로 본다]'
    with open(txt, 'w', encoding='utf-8') as f:
        f.write(text)
    n = len(doc)
    doc.close()
    return {'pages': n, 'chars': chars, 'txt': os.path.basename(txt), 'png_dir': os.path.basename(png_dir) if png_dir else ''}


def _save_registry(stock, urls, auto):
    reg = read_json(REGISTRY, {}) or {}
    reg[stock] = urls if not auto else {'auto': True, 'found': date.today().isoformat(), 'urls': urls}
    write_json(REGISTRY, reg)


def _registry_urls(stock):
    v = (read_json(REGISTRY, {}) or {}).get(stock)
    if isinstance(v, dict):
        return v.get('urls', [])
    return v or []


def main(argv=None):
    import requests
    a = argv or sys.argv[1:]
    stock = a[0]
    urls = [a[i + 1] for i, x in enumerate(a) if x == '--url' and i + 1 < len(a)]
    mx = int(a[a.index('--max') + 1]) if '--max' in a else 6
    png_pages = int(a[a.index('--png-pages') + 1]) if '--png-pages' in a else 20
    source = 'arg' if urls else ''
    reg_entry = (read_json(REGISTRY, {}) or {}).get(stock)
    if not urls and not ('--rediscover' in a and isinstance(reg_entry, dict)):  # 수동 등록(list)은 --rediscover 로도 안 덮는다
        urls = _registry_urls(stock)
        source = 'registry' if urls else ''
    if not urls and '--no-discover' not in a:
        try:
            urls = discover(stock)
            source = 'auto' if urls else ''
        except Exception as e:
            print(f'  [탐색] 실패 {e!r}'[:160])
        if urls:
            _save_registry(stock, urls, auto=True)
    if not urls:
        manifest_update(stock, 'company_ir', 'skipped', reason=f'IR 페이지를 못 찾음 -- {os.path.relpath(REGISTRY, ROOT)} 에 등록하거나 --url')
        print(f'[SKIP] company_ir: IR 페이지를 못 찾음 ({os.path.relpath(REGISTRY, ROOT)} 에 "{stock}" 을 등록하거나 --url)')
        return 0
    d = ta_dir(stock)
    out_dir = os.path.join(d, 'ir_site')
    os.makedirs(out_dir, exist_ok=True)
    links, failed = [], []
    for u in urls:
        try:
            found, how = collect_page(u, posts=mx, log=print)
            if not found:
                failed.append({'url': u, 'reason': f'PDF 링크 0건 ({how}) -- 파일 링크 패턴이 (a)href .pdf (b)front_file_download (c)download+onclick 셋 다 아님'})
            print(f'  {u}: 링크 {len(found)}건 ({how})')
            links += found
        except Exception as e:  # 실패 이유를 남긴다
            failed.append({'url': u, 'reason': repr(e)[:150]})
    picked, seen = [], set()
    for lk in links:  # 페이지 순서 = 최신순 (사이트 관행)
        if lk['url'] in seen:
            continue
        seen.add(lk['url'])
        picked.append(lk)
        if len(picked) >= mx:
            break
    index_path = os.path.join(d, 'ir_materials', 'index.json')
    idx = read_json(index_path, None) or {'asof': date.today().isoformat(), 'code': '', 'items': []}
    have = {i.get('url') for i in idx['items']}
    added = []
    for lk in picked:
        if lk['url'] in have:
            continue
        try:
            r = _sess().get(clean_url(lk['url']), headers={'Referer': lk.get('referer') or lk['url']}, timeout=60)
            r.raise_for_status()
            if r.content[:4] != b'%PDF':
                failed.append({'url': lk['url'], 'reason': f'PDF 아님 ({r.content[:12]!r})'})
                continue
            name = slug((period_of(lk['title']) + '_' if period_of(lk['title']) else '') + lk['title'])
            info = save_pdf(r.content, out_dir, name, png_pages)
            item = {'date': period_of(lk['title']), 'file': name + '.pdf', 'txt': 'ir_site/' + info['txt'], 'pages': info['pages'],
                    'chars': info['chars'], 'status': 'ok', 'source': 'site', 'title': lk['title'], 'url': lk['url'],
                    'png_dir': ('ir_site/' + info['png_dir']) if info['png_dir'] else ''}
            idx['items'].append(item)
            added.append(item)
            print(f"  [OK] {lk['title']} -> {item['file']} {info['pages']}p {info['chars']:,}자" + (f" (이미지 슬라이드, PNG {info['png_dir']}/)" if info['png_dir'] else ''))
            time.sleep(0.5)
        except Exception as e:
            failed.append({'url': lk['url'], 'reason': repr(e)[:150]})
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    write_json(index_path, idx)
    have_site = [i for i in idx['items'] if i.get('source') == 'site' and i.get('status') == 'ok']
    status = 'ok' if (added or (have_site and links)) else ('failed' if failed else 'skipped')
    manifest_update(stock, 'company_ir', status, source=source, pages=len(urls), links=len(links), added=len(added), failed=failed[:5])
    print(f'[{status.upper()}] company_ir({source}): 링크 {len(links)}건 중 {len(added)}건 저장 -> ta/ir_site/ (index: ta/ir_materials/index.json)'
          + (f', 실패 {len(failed)}건' if failed else ''))
    return 0 if status != 'failed' else 1


if __name__ == '__main__':
    sys.exit(main())
