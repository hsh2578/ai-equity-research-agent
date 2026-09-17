# -*- coding: utf-8 -*-
"""뉴스 본문 수집 -- 네이버 뉴스 API 는 요약(150자)만 주므로 기사 URL 을 열어 본문을 받는다.

네이버 기사(n.news.naver.com)는 #dic_area, 그 외 매체는 trafilatura(오픈소스 본문 추출기).
ta/news_relevant.json 의 items 에 body_full 을 채운다(원문은 ta/news_body/{nid}.txt).
usage: python scripts/ta_news_body.py {종목명} [--max 80] [--delay 0.5]
"""
import io
import os
import sys
import time

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ta_common import ta_dir, manifest_update, read_json, write_json  # noqa: E402

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def extract_body(html, url):
    """네이버는 #dic_area(#newsct_article), 그 외는 trafilatura. 못 찾으면 ''."""
    if 'news.naver.com' in url:
        from bs4 import BeautifulSoup
        s = BeautifulSoup(html, 'lxml')
        a = s.select_one('#dic_area') or s.select_one('#newsct_article')
        return ' '.join(a.get_text(' ', strip=True).split()) if a else ''
    import trafilatura
    return (trafilatura.extract(html, include_comments=False, include_tables=False) or '').strip()


def needs_fetch(item):
    if item.get('body_full'):
        return False
    return len(item.get('body') or '') < 400  # API 요약은 150자 안팎, 전문이 이미 들어온 기사는 건너뛴다


def main(argv=None):
    import requests
    a = argv or sys.argv[1:]
    stock = a[0]
    mx = int(a[a.index('--max') + 1]) if '--max' in a else 80
    delay = float(a[a.index('--delay') + 1]) if '--delay' in a else 0.5
    d = ta_dir(stock)
    p = os.path.join(d, 'news_relevant.json')
    n = read_json(p)
    if not n:
        manifest_update(stock, 'news_body', 'failed', reason='news_relevant.json 없음')
        print('[FAIL] news_relevant.json 없음')
        return 1
    out_dir = os.path.join(d, 'news_body')
    os.makedirs(out_dir, exist_ok=True)
    ok = fail = skip = 0
    for it in n.get('items', []):
        if not needs_fetch(it):
            skip += 1
            continue
        if ok + fail >= mx:
            break
        try:
            r = requests.get(it['url'], headers=HEADERS, timeout=15)
            r.raise_for_status()
            body = extract_body(r.text, it['url'])
        except Exception as e:  # 실패 이유를 남긴다
            it['body_fetch_error'] = repr(e)[:150]
            fail += 1
            continue
        if len(body) < 200:
            it['body_fetch_error'] = f'본문 추출 실패({len(body)}자)'
            fail += 1
            continue
        it['body_full'] = body
        with open(os.path.join(out_dir, f"{it.get('nid', ok)}.txt"), 'w', encoding='utf-8') as f:
            f.write(body)
        ok += 1
        time.sleep(delay)
    write_json(p, n)
    manifest_update(stock, 'news_body', 'ok' if ok else 'failed', ok=ok, failed=fail, skipped=skip)
    print(f'[{"OK" if ok else "FAIL"}] news_body: 본문 {ok}건, 실패 {fail}건, 건너뜀 {skip}건 -> ta/news_body/')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
