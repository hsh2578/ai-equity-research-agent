# -*- coding: utf-8 -*-
"""ta_news_window.py -- 날짜 창으로 뉴스를 받는다 (Google News RSS, 키 불필요).

네이버 종목뉴스 API 는 최근 약 2개월(HD현대중공업 실측 2,121건, 7/9~)까지만 준다. 그래서 그 이전의
급등락일(event_study top_moves)은 재료가 비어 있었다. 이 스크립트는 그 날짜들에 대해
`{종목명} after:{d-2} before:{d+1}` 로 Google News RSS 를 받아 news_relevant.json 에 type='window' 로 넣는다.
결과: HD현대중공업 4/1 -11.8% 의 재료가 "최대주주 HD한국조선해양의 20억달러 교환사채(교환가 54만원)" 였다 --
수시공시 제목('최대주주등소유주식변동신고서')만으로는 읽을 수 없던 것.

usage: python scripts/ta_news_window.py {종목명} [--dates 2026-04-01,2026-05-06] [--top N] [--days-before 2] [--days-after 1]
  --dates 없으면 ta/event_study.json 의 top_moves 상위 N(기본 8)개 날짜를 쓴다.
"""
import argparse
import io
import json
import os
import sys
import time
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import requests
from defusedxml import ElementTree as ET

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta_common as tc  # noqa: E402

RSS = 'https://news.google.com/rss/search'
DELAY = 1.0


def parse_rss(xml_text):
    """RSS -> [{title, url, source, datetime(ISO)}]. 제목 끝의 ' - 매체' 는 source 로 분리한다."""
    root = ET.fromstring(xml_text)
    out = []
    for it in root.findall('.//item'):
        title = (it.findtext('title') or '').strip()
        src = (it.findtext('source') or '').strip()
        if not src and ' - ' in title:
            title, src = title.rsplit(' - ', 1)
        try:
            dt = parsedate_to_datetime(it.findtext('pubDate') or '')
            dts = dt.astimezone().isoformat(timespec='minutes') if dt.tzinfo else dt.isoformat(timespec='minutes')
        except (TypeError, ValueError):
            dts = ''
        out.append({'title': title.strip(), 'url': (it.findtext('link') or '').strip(), 'source': src, 'datetime': dts})
    return out


def window_query(stock, d0, before=2, after=1):
    d = datetime.strptime(d0, '%Y-%m-%d')
    return f'{stock} after:{(d - timedelta(days=before)).date()} before:{(d + timedelta(days=after + 1)).date()}'


def fetch_window(stock, d0, before=2, after=1, fetch=None):
    fetch = fetch or (lambda q: requests.get(RSS, params={'q': q, 'hl': 'ko', 'gl': 'KR', 'ceid': 'KR:ko'}, timeout=20).text)
    return parse_rss(fetch(window_query(stock, d0, before, after)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('stock')
    ap.add_argument('--dates', default=None)
    ap.add_argument('--top', type=int, default=8)
    ap.add_argument('--days-before', type=int, default=2)
    ap.add_argument('--days-after', type=int, default=1)
    a = ap.parse_args(argv)
    ta = os.path.join(tc.ROOT if hasattr(tc, 'ROOT') else os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', a.stock, 'ta')
    if a.dates:
        dates = [d.strip() for d in a.dates.split(',') if d.strip()]
    else:
        es = json.load(open(os.path.join(ta, 'event_study.json'), encoding='utf-8'))
        dates = [m['d0'] for m in es.get('top_moves', [])[:a.top]]
    rel_path = os.path.join(ta, 'news_relevant.json')
    rel = json.load(open(rel_path, encoding='utf-8'))
    items = rel if isinstance(rel, list) else rel.setdefault('items', [])
    have = {(x.get('title') or '')[:30] for x in items}
    added, log = 0, {}
    for i, d0 in enumerate(dates):
        rows = fetch_window(a.stock, d0, a.days_before, a.days_after)
        new = 0
        for r in rows:
            if r['title'][:30] in have:
                continue
            have.add(r['title'][:30])
            items.append({'nid': f'W{len(items):04d}', 'source': 'google_rss', 'office': r['source'], 'datetime': r['datetime'],
                          'title': r['title'], 'body': '', 'url': r['url'], 'mention': True, 'list_mention': True,
                          'relevant': True, 'type': 'window', 'window_date': d0})
            new += 1
        added += new
        log[d0] = {'fetched': len(rows), 'added': new}
        print(f'  {d0}: RSS {len(rows)}건, 신규 {new}건')
        if i < len(dates) - 1:
            time.sleep(DELAY)
    json.dump(rel, open(rel_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    # event_study 는 ta/news.json 만 읽는다 -- 같은 항목을 거기에도 넣는다
    all_path = os.path.join(ta, 'news.json')
    if os.path.exists(all_path):
        alln = json.load(open(all_path, encoding='utf-8'))
        seen = {x.get('nid') for x in alln.get('items', [])}
        alln['items'].extend(x for x in items if x.get('type') == 'window' and x.get('nid') not in seen)
        json.dump(alln, open(all_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump({'stock': a.stock, 'collected_at': datetime.now().isoformat(timespec='minutes'), 'windows': log},
              open(os.path.join(ta, 'news_window.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    tc.manifest_update(a.stock, 'news_window', 'ok' if added else 'skipped', windows=len(dates), added=added)
    print(f'[OK] news_window: 날짜 {len(dates)}개, 추가 {added}건 -> ta/news_relevant.json')


if __name__ == '__main__':
    main()
