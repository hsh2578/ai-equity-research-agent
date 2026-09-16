# -*- coding: utf-8 -*-
"""ta_collect_news.py -- 종목 뉴스 전수 수집 (/research-ta Task 2).

/research 가 검색어 몇 개로만 뉴스를 훑다가 최신·주요 뉴스를 빠뜨린 사고에
대응한다. 검색에 맡기지 않고 네이버 종목뉴스(전수) + 네이버 검색(보완) +
텔레그램(로컬, 선택) 세 소스를 각각 끝까지 훑는다.

    소스1  GET https://m.stock.naver.com/api/news/stock/{code}  (전수, 페이지네이션)
    소스2  GET https://openapi.naver.com/v1/search/news.json    (날짜순 보완)
    소스3  텔레그램 로컬 DB (모듈 없으면 skipped)

소스 하나가 죽어도 나머지는 계속 돈다 -- sources 블록에 실패 사유를 구조화해
남기고(`except: return None` 금지), 실패 직전까지 모은 항목은 보존한다.

사용:
    python scripts/ta_collect_news.py {종목명} [--code 036810] [--days 365]
        [--max-pages 20] [--no-telegram]
"""
import argparse
import calendar
import html
import io
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime

import requests

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta_common as tc  # noqa: E402

NAVER_STOCK_URL = 'https://m.stock.naver.com/api/news/stock/{code}'
NAVER_STOCK_HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://m.stock.naver.com/'}
NAVER_SEARCH_URL = 'https://openapi.naver.com/v1/search/news.json'
SEARCH_HEADERS = {'User-Agent': 'Mozilla/5.0'}
NAVER_SEARCH_MAX_START = 1000
TG_LIB_DIR = 'C:/Users/hsh/Desktop/vibecoding/주식 블로그 자동화'
ENV_LOADER_DIR = 'C:/Users/hsh/Desktop'
DELAY = 0.3
TIMEOUT = 15

_TAG_RE = re.compile(r'<[^>]+>')
_NORM_RE = re.compile(r'[\s\W_]+')


def _strip_tags(s):
    return _TAG_RE.sub('', s or '')


def _norm_title(title):
    """중복 판정용: 공백·특수문자 제거."""
    return _NORM_RE.sub('', title or '')


def _default_fetch(url, params=None, headers=None):
    return requests.get(url, params=params, headers=headers, timeout=TIMEOUT)


def _parse_stock_dt(s):
    """'YYYYMMDDHHMM' (KST) -> tz-aware datetime. 실패하면 None."""
    s = str(s or '')
    if len(s) < 12:
        return None
    try:
        return datetime.strptime(s[:12], '%Y%m%d%H%M').replace(tzinfo=tc.KST)
    except ValueError:
        return None


def _parse_pubdate(s):
    """RFC822 pubDate -> KST tz-aware datetime. 실패하면 None."""
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=tc.KST)
    return d.astimezone(tc.KST)


def _parse_stock_item(it):
    dtv = _parse_stock_dt(it.get('datetime'))
    if dtv is None:
        return None
    title = html.unescape(it.get('titleFull') or it.get('title') or '')
    body = html.unescape(it.get('body') or '')
    url = it.get('mobileNewsUrl') or ''
    if not url:
        url = f"https://n.news.naver.com/mnews/article/{it.get('officeId')}/{it.get('articleId')}"
    return {
        'source': 'naver_stock',
        'datetime': dtv,
        'office': it.get('officeName') or '',
        'title': title,
        'body': body[:300],
        'url': url,
    }


def _parse_search_item(it):
    dtv = _parse_pubdate(it.get('pubDate'))
    if dtv is None:
        return None
    title = html.unescape(_strip_tags(it.get('title')))
    body = html.unescape(_strip_tags(it.get('description')))
    url = it.get('link') or it.get('originallink') or ''
    return {
        'source': 'naver_search',
        'datetime': dtv,
        'office': '',
        'title': title,
        'body': body[:300],
        'url': url,
    }


def collect_naver_stock(code, cutoff, max_pages=20, fetch=None, delay=DELAY):
    """네이버 종목뉴스 전수 수집. 실패해도 그때까지 모은 items 는 남긴다."""
    fetch = fetch or _default_fetch
    items, pages = [], 0
    stop_reason = 'max_pages'
    for page in range(1, max_pages + 1):
        try:
            resp = fetch(NAVER_STOCK_URL.format(code=code),
                         params={'pageSize': 20, 'page': page}, headers=NAVER_STOCK_HEADERS)
        except Exception as e:
            return {'status': 'failed', 'reason': f'{type(e).__name__}: {e}',
                    'items': items, 'pages': pages}
        if resp.status_code != 200:
            return {'status': 'failed', 'reason': f'HTTP {resp.status_code}',
                    'items': items, 'pages': pages}
        try:
            data = resp.json()
        except Exception as e:
            return {'status': 'failed', 'reason': f'JSON 파싱 실패: {type(e).__name__}: {e}',
                    'items': items, 'pages': pages}
        pages += 1
        if not isinstance(data, list) or not data:
            stop_reason = 'empty'
            break
        page_items = []
        for group in data:
            page_items.extend((group or {}).get('items') or [])
        if not page_items:
            stop_reason = 'empty'
            break
        oldest = None
        for it in page_items:
            parsed = _parse_stock_item(it)
            if parsed is None:
                continue
            # cutoff 이전 아이템은 경계 페이지라도 담지 않는다 -- naver_search 와
            # 동일 규칙. 페이지 전체를 통째로 넣으면 pageSize(20)만큼 오래된
            # 기사가 선언된 cutoff 를 넘어 items/counts 에 섞여 들어간다.
            if parsed['datetime'] >= cutoff:
                items.append(parsed)
            if oldest is None or parsed['datetime'] < oldest:
                oldest = parsed['datetime']
        if oldest is not None and oldest < cutoff:
            stop_reason = 'cutoff'
            break
        if page < max_pages:
            time.sleep(delay)
    result = {'status': 'ok', 'items': items, 'pages': pages}
    if stop_reason == 'max_pages':
        # cutoff 도 빈 페이지도 만나지 못한 채 max_pages 로 끊었다 -- 활발한
        # 종목이면 전수 수집이 조용히 잘릴 수 있다. 침묵시키지 않는다.
        result['truncated'] = True
        result['truncated_reason'] = f'max_pages={max_pages} 도달, cutoff 미도달'
    return result


def collect_naver_search(query, cutoff, fetch=None, delay=DELAY, max_start=NAVER_SEARCH_MAX_START):
    """네이버 검색 뉴스 API, 날짜순 보완. 실패해도 그때까지 모은 items 는 남긴다."""
    fetch = fetch or _default_fetch
    client_id = os.environ.get('NAVER_CLIENT_ID')
    client_secret = os.environ.get('NAVER_CLIENT_SECRET')
    if not client_id or not client_secret:
        return {'status': 'failed', 'reason': 'NAVER_CLIENT_ID/NAVER_CLIENT_SECRET 환경변수 없음',
                'items': [], 'pages': 0}
    headers = dict(SEARCH_HEADERS, **{'X-Naver-Client-Id': client_id,
                                       'X-Naver-Client-Secret': client_secret})
    items, pages, start = [], 0, 1
    stop_reason = 'max_start'
    while start <= max_start:
        try:
            resp = fetch(NAVER_SEARCH_URL,
                         params={'query': query, 'display': 100, 'start': start, 'sort': 'date'},
                         headers=headers)
        except Exception as e:
            return {'status': 'failed', 'reason': f'{type(e).__name__}: {e}',
                    'items': items, 'pages': pages}
        if resp.status_code != 200:
            return {'status': 'failed', 'reason': f'HTTP {resp.status_code}',
                    'items': items, 'pages': pages}
        try:
            data = resp.json()
        except Exception as e:
            return {'status': 'failed', 'reason': f'JSON 파싱 실패: {type(e).__name__}: {e}',
                    'items': items, 'pages': pages}
        pages += 1
        raw_items = (data or {}).get('items') or []
        if not raw_items:
            stop_reason = 'empty'
            break
        hit_cutoff = False
        for it in raw_items:
            parsed = _parse_search_item(it)
            if parsed is None:
                continue
            if parsed['datetime'] < cutoff:
                hit_cutoff = True
                continue
            items.append(parsed)
        if hit_cutoff:
            stop_reason = 'cutoff'
            break
        start += 100
        if start <= max_start:
            time.sleep(delay)
    result = {'status': 'ok', 'items': items, 'pages': pages}
    if stop_reason == 'max_start':
        # start 가 1000 을 넘어 멈췄고 cutoff 도 빈 결과도 못 봤다 -- 활발한
        # 종목이면 검색 보완 소스도 조용히 잘릴 수 있다.
        result['truncated'] = True
        result['truncated_reason'] = f'start<={max_start} 도달, cutoff 미도달'
    return result


def _month_ranges(today, n=12):
    """(라벨, 시작일, 종료일) 최근 n개월, 과거 -> 현재 순."""
    out = []
    y, m = today.year, today.month
    for i in range(n):
        mm, yy = m - i, y
        while mm <= 0:
            mm += 12
            yy -= 1
        start = date(yy, mm, 1)
        end = min(today, date(yy, mm, calendar.monthrange(yy, mm)[1]))
        out.append((f'{yy:04d}-{mm:02d}', start.isoformat(), end.isoformat()))
    return list(reversed(out))


def collect_telegram(stock_name, tg_lib_dir=TG_LIB_DIR):
    """텔레그램 로컬 DB. 모듈이 없으면 skipped(치명 실패 아님)."""
    inserted = tg_lib_dir not in sys.path
    if inserted:
        sys.path.insert(0, tg_lib_dir)
    try:
        from pipeline.lib import tgdb
    except Exception as e:
        return {'status': 'skipped', 'reason': f'{type(e).__name__}: {e}'}
    finally:
        if inserted and tg_lib_dir in sys.path:
            sys.path.remove(tg_lib_dir)

    keywords = tc.name_variants(stock_name)
    today = tc.now_kst().date()
    try:
        monthly = {label: tgdb.count_range(keywords, start, end, min_len=200)
                  for label, start, end in _month_ranges(today, 12)}
        start90 = (today - timedelta(days=90)).isoformat()
        raw_posts = tgdb.search_range(keywords, start90, today.isoformat(), min_len=400, limit=30)
    except Exception as e:
        return {'status': 'failed', 'reason': f'{type(e).__name__}: {e}'}

    posts = [{'channel_name': m.get('channel_name'), 'timestamp': m.get('timestamp'),
             'date': m.get('date'), 'text': (m.get('text') or '')[:500]} for m in raw_posts]
    return {'status': 'ok', 'keywords': keywords, 'monthly': monthly, 'posts': posts}


def _dedupe(items):
    """같은 url 또는 정규화된 제목이 같으면 먼저 온 것만 남긴다(입력 순서가 우선순위).

    url 도 제목도 없는 아이템은 원래 키(url/제목)에 안 걸려 무제한 통과했다 --
    (datetime, office) 로 대신 걸러 중복만 없앤다(둘 다 비어도 서로 다른 시각의
    별개 기사는 남긴다).
    """
    seen_url, seen_title, seen_fallback, out = set(), set(), set(), []
    for it in items:
        url = it.get('url') or ''
        nt = _norm_title(it.get('title'))
        if not url and not nt:
            key = (it.get('datetime'), it.get('office') or '')
            if key in seen_fallback:
                continue
            seen_fallback.add(key)
            out.append(it)
            continue
        if (url and url in seen_url) or (nt and nt in seen_title):
            continue
        if url:
            seen_url.add(url)
        if nt:
            seen_title.add(nt)
        out.append(it)
    return out


_SENT_SPLIT_RE = re.compile(r'[.!?\n]')
_SEG_SPLIT_RE = re.compile(r'[,·]')  # 콤마 / 가운뎃점(·)


def _is_list_mention(body, variant):
    """종목명이 들어간 문장(세그먼트)이 콤마·가운뎃점으로 4개 이상 나열됐는가.

    "반도체 관련주 강세, 네오셈, 에프에스티, 에스티아이, ..." 같은 단순 언급을
    이벤트 스터디에 넣으면 재료가 아닌 노이즈로 오염된다.
    """
    if not body or not variant or variant not in body:
        return False
    for sent in _SENT_SPLIT_RE.split(body):
        if variant not in sent:
            continue
        parts = [p.strip() for p in _SEG_SPLIT_RE.split(sent) if p.strip()]
        if len(parts) >= 4:
            return True
    return False


def _mention_of(title, body, variants):
    """title 에 있으면 'title', body 에만 있으면 'body' (+ 매칭된 variant), 없으면 'none'."""
    if any(v in title for v in variants):
        return 'title', None
    hit = next((v for v in variants if v in body), None)
    if hit:
        return 'body', hit
    return 'none', None


def _finalize(items, stock_name):
    """정렬 + nid 부여 + mention/list_mention/relevant/type 태깅.

    relevant 판정(controller fix round 1, 오탐 방지):
      - title 언급 -> relevant
      - naver_stock 의 body 단독 언급이면서 나열형이 아니면 -> relevant
      - naver_search 의 body 단독 언급은 (나열형이든 아니든) -> not relevant
        (관련주 리스트/약세 동반언급이 검색 결과 본문에 압도적으로 많다)
      - 언급 없음 -> not relevant
    항목은 relevant 와 무관하게 전부 남긴다(분석가가 직접 볼 수 있도록).
    """
    variants = tc.name_variants(stock_name)
    ordered = sorted(items, key=lambda x: x['datetime'], reverse=True)
    out = []
    for i, it in enumerate(ordered, start=1):
        title, body = it.get('title') or '', it.get('body') or ''
        mention, hit_variant = _mention_of(title, body, variants)
        list_mention = mention == 'body' and _is_list_mention(body, hit_variant)
        if mention == 'title':
            relevant = True
        elif mention == 'body' and it['source'] == 'naver_stock' and not list_mention:
            relevant = True
        else:
            relevant = False
        out.append({
            'nid': f'N{i:04d}',
            'source': it['source'],
            'datetime': it['datetime'].isoformat(),
            'office': it.get('office') or '',
            'title': title,
            'body': body,
            'url': it.get('url') or '',
            'mention': mention,
            'list_mention': list_mention,
            'relevant': relevant,
            'type': 'reaction' if tc.is_reaction_title(title) else 'news',
        })
    return out


def _relevant_payload(payload):
    """news.json 과 같은 모양이되 items 를 relevant==true 만 남긴 요약본.

    분석 에이전트가 전체(비관련 포함) news.json(수백 KB)을 쓰다가 컨텍스트가
    쪼개진 사고(2026-09) 대응. news.json 자체는 그대로 두고 별도 파일로만 제공.
    """
    out = dict(payload)
    out['items'] = [it for it in payload['items'] if it.get('relevant')]
    out['counts'] = dict(payload['counts'])
    out['note'] = '비관련 항목을 포함한 전체 목록은 news.json 을 본다'
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('stock')
    ap.add_argument('--code', default=None)
    ap.add_argument('--days', type=int, default=365)
    ap.add_argument('--max-pages', type=int, default=20)
    ap.add_argument('--no-telegram', action='store_true')
    a = ap.parse_args(argv)

    print('=' * 74)
    print(f'  종목뉴스 전수 수집: {a.stock}')
    print('=' * 74)

    now = tc.now_kst()
    cutoff = now - timedelta(days=a.days)

    code = a.code
    if not code:
        try:
            code = tc.resolve_stock(a.stock, code=a.code)['code']
        except LookupError as e:
            print(f'  [WARN] 종목코드 확인 실패: {e}')
            code = None

    if code:
        stock_r = collect_naver_stock(code, cutoff, max_pages=a.max_pages)
    else:
        stock_r = {'status': 'failed', 'reason': '종목코드 없음', 'items': [], 'pages': 0}
    print(f"  [naver_stock] {stock_r['status']} - {len(stock_r['items'])}건 / {stock_r['pages']}p")
    if stock_r.get('truncated'):
        print(f"  [WARN] naver_stock: {stock_r['truncated_reason']}")

    try:
        sys.path.insert(0, ENV_LOADER_DIR)
        from env_loader import load_env
        load_env()
    except Exception as e:
        search_r = {'status': 'failed', 'reason': f'env_loader 로드 실패: {type(e).__name__}: {e}',
                   'items': [], 'pages': 0}
    else:
        search_r = collect_naver_search(a.stock, cutoff)
    print(f"  [naver_search] {search_r['status']} - {len(search_r['items'])}건 / {search_r['pages']}p")
    if search_r.get('truncated'):
        print(f"  [WARN] naver_search: {search_r['truncated_reason']}")

    if a.no_telegram:
        tg_r = {'status': 'skipped', 'reason': '--no-telegram'}
    else:
        tg_r = collect_telegram(a.stock)
    print(f"  [telegram] {tg_r['status']}")

    combined = _dedupe(stock_r['items'] + search_r['items'])
    items = _finalize(combined, a.stock)
    counts = {
        'total': len(items),
        'relevant': sum(1 for i in items if i['relevant']),
        'reaction': sum(1 for i in items if i['type'] == 'reaction'),
        'by_mention': {
            'title': sum(1 for i in items if i['mention'] == 'title'),
            'body': sum(1 for i in items if i['mention'] == 'body'),
            'none': sum(1 for i in items if i['mention'] == 'none'),
        },
    }

    sources = {
        'naver_stock': {'status': stock_r['status'], 'count': len(stock_r['items']),
                        'pages': stock_r['pages'],
                        **({'reason': stock_r['reason']} if 'reason' in stock_r else {}),
                        **({'truncated': True, 'truncated_reason': stock_r['truncated_reason']}
                           if stock_r.get('truncated') else {})},
        'naver_search': {'status': search_r['status'], 'count': len(search_r['items']),
                         'pages': search_r['pages'],
                         **({'reason': search_r['reason']} if 'reason' in search_r else {}),
                         **({'truncated': True, 'truncated_reason': search_r['truncated_reason']}
                            if search_r.get('truncated') else {})},
        'telegram': {'status': tg_r['status'],
                    **({'reason': tg_r['reason']} if 'reason' in tg_r else {}),
                    **({'long_posts': len(tg_r['posts']),
                        'monthly_total': sum(tg_r['monthly'].values())} if tg_r['status'] == 'ok' else {})},
    }

    payload = {
        'stock': a.stock, 'code': code or '', 'collected_at': now.isoformat(),
        'cutoff': cutoff.date().isoformat(), 'sources': sources, 'counts': counts, 'items': items,
    }
    news_path = os.path.join(tc.ta_dir(a.stock), 'news.json')
    tc.write_json(news_path, payload)
    print(f'  -> {news_path}')
    print(f"  뉴스 {counts['total']}건 (relevant {counts['relevant']} / reaction {counts['reaction']})")

    rel_path = os.path.join(tc.ta_dir(a.stock), 'news_relevant.json')
    tc.write_json(rel_path, _relevant_payload(payload))
    print(f'  -> {rel_path}')

    if tg_r['status'] == 'ok':
        tg_path = os.path.join(tc.ta_dir(a.stock), 'telegram.json')
        tc.write_json(tg_path, {'stock': a.stock, 'collected_at': now.isoformat(), **tg_r})
        print(f'  -> {tg_path}')

    overall = 'ok' if stock_r['status'] == 'ok' or search_r['status'] == 'ok' else 'failed'
    tc.manifest_update(a.stock, 'news', overall, counts=counts)
    print('=' * 74)
    return 0 if overall == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
