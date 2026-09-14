# -*- coding: utf-8 -*-
"""collect_kirs_reports.py -- 한국IR협의회 기업분석보고서를 받는다 (v5.22 신설).

왜 필요한가(2026-09 CJ프레시웨이 실측). 이 종목의 IR협의회 리포트를 뒤늦게
찾아 읽고 나서 우리 리포트의 결함 네 개가 한꺼번에 드러났다.

    투자포인트 방향   우리 6개가 전부 현재 재무  <-  IR협의회는 2개, 전부 미래
    키친리스 정의     '반조리 식자재' 로 오해     <-  이동식 급식 + 간편식 자판기
    단체급식 시장     6조(언론 보도)             <-  16조(한국급식학회), 1일 1,700만명
    리스크 비중       7개 / 분량의 20.6%          <-  1개 / 1페이지

넷 다 우리가 이미 가진 자료로는 알 수 없었다. **같은 회사를 먼저 쓴 사람의
글을 읽는 것**이 가장 싼 교정이다.

IR협의회 보고서는 kirs.or.kr 본사이트가 아니라 네이버 금융 리서치에 올라온다
(kirs.or.kr 의 tech2020_* 은 NICE디앤비 기술분석보고서로 별개다).

    목록  GET https://m.stock.naver.com/api/research/company?page={N}&pageSize=100
          -> brokerName == '한국IR협의회' 만 남기고, title 이 '[AI]' 로 시작하면
             단문 요약이라 제외한다
    상세  GET https://m.stock.naver.com/api/research/company/{rid}
          -> researchContent.attachUrl 이 PDF 직링크
    검증  응답이 %PDF 매직으로 시작하는지 확인 (에러 페이지가 200 으로 온다)

사용:
    python scripts/collect_kirs_reports.py {종목명} [--code 051500] [--pages 40]
    python scripts/collect_kirs_reports.py {종목명} --keyword 급식 식자재 --limit 3
"""
import argparse
import io
import json
import os
import re
import sys
import time

import datetime as _dt

import requests

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_DIR = os.path.join(ROOT, 'data', '_ref', 'kirs')
LIST_URL = 'https://m.stock.naver.com/api/research/company'
ITEM_URL = 'https://m.stock.naver.com/api/research/company/{rid}'
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://m.stock.naver.com/'}
BROKER = '한국IR협의회'


def _age_months(datestr, today):
    """발간 후 몇 달 지났는가. 참조 리포트는 시점이 반이다."""
    if not datestr:
        return None
    m = re.search(r'(\d{4})[.\-/]?(\d{2})', str(datestr))
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    return (today.year - y) * 12 + (today.month - mo)


def fetch_list(pages=40, delay=0.15):
    """IR협의회 정식 기업분석보고서 목록. [AI] 단문은 제외한다."""
    s = requests.Session()
    s.headers.update(HEADERS)
    out, seen = [], set()
    for p in range(1, pages + 1):
        r = s.get(LIST_URL, params={'page': p, 'pageSize': 100}, timeout=20)
        r.raise_for_status()
        items = r.json() if isinstance(r.json(), list) else r.json().get('list', [])
        if not items:
            break
        for it in items:
            if it.get('brokerName') != BROKER:
                continue
            title = (it.get('title') or '').strip()
            if title.startswith('[AI]'):        # 단문 요약본
                continue
            rid = it.get('researchId') or it.get('id')
            if rid in seen:
                continue
            seen.add(rid)
            # 종목명 키는 itemName 이다. stockName 을 읽으면 조용히 빈 문자열이
            # 되어 (a) 이름으로 자체 리포트를 못 찾고 (b) 파일명이 '_{rid}.pdf'
            # 가 되며 (c) --keyword 가 제목에만 걸린다. 에프에스티 재작성에서
            # 네 편을 받고서야 드러났다 -- 세 증상 모두 에러가 아니라 침묵이다.
            out.append({'rid': rid,
                        'name': (it.get('itemName') or it.get('stockName') or '').strip(),
                        'code': it.get('itemCode'), 'title': title,
                        'date': it.get('writeDate') or it.get('date')})
        time.sleep(delay)
    return out


def download(rid, name, out_dir=REF_DIR):
    """PDF 한 편. 실패 이유는 구조화해 돌려준다 (except: pass 금지)."""
    s = requests.Session()
    s.headers.update(HEADERS)
    r = s.get(ITEM_URL.format(rid=rid), timeout=20)
    if r.status_code != 200:
        return {'rid': rid, 'stage': 'detail', 'status': r.status_code}
    d = r.json()
    # 상세 응답은 researchContent 안에 본문이 들어 있다 (목록과 스키마가 다르다)
    c = d.get('researchContent') or d
    if isinstance(c, str):
        import ast
        c = ast.literal_eval(c)
    if c.get('brokerName') != BROKER:
        return {'rid': rid, 'stage': 'broker', 'got': c.get('brokerName')}
    url = c.get('attachUrl')
    if not url:
        return {'rid': rid, 'stage': 'attach', 'err': 'attachUrl 없음'}
    pdf = s.get(url, timeout=60)
    if pdf.status_code != 200:
        return {'rid': rid, 'stage': 'pdf', 'status': pdf.status_code}
    if not pdf.content.startswith(b'%PDF'):
        return {'rid': rid, 'stage': 'magic', 'err': 'PDF 가 아니다(에러 페이지)'}
    os.makedirs(out_dir, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|]', '', name) or str(rid)
    path = os.path.join(out_dir, f'{safe}_{rid}.pdf')
    open(path, 'wb').write(pdf.content)
    return {'rid': rid, 'path': os.path.relpath(path, ROOT), 'bytes': len(pdf.content)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('stock')
    ap.add_argument('--code', default=None)
    ap.add_argument('--keyword', nargs='*', default=None,
                    help='자체 리포트가 없을 때 동종을 찾을 키워드(제목·종목명 대상)')
    ap.add_argument('--pages', type=int, default=40)
    ap.add_argument('--limit', type=int, default=3)
    a = ap.parse_args(argv)

    print('=' * 74)
    print(f'  한국IR협의회 기업분석보고서: {a.stock}')
    print('=' * 74)
    lst = fetch_list(a.pages)
    print(f'  목록 {len(lst)}편 확보 (IR협의회 정식 보고서)')

    exact = [x for x in lst if x['name'] == a.stock
             or (a.code and str(x.get('code')) == a.code)]
    picked = list(exact)
    if exact:
        print(f'  [자체] {a.stock} 리포트 {len(exact)}편 -- 이것이 정답지다')
    else:
        print(f'  [자체] {a.stock} 리포트 없음')

    if a.keyword:
        kw = [k for k in a.keyword if k]
        peer = [x for x in lst if x not in picked
                and any(k in x['title'] or k in x['name'] for k in kw)]
        picked += peer[:max(0, a.limit - len(picked))]
        print(f'  [동종] 키워드 {kw} 로 {len(peer)}편 발견, {len(picked)-len(exact)}편 채택')

    picked = picked[:a.limit] if not exact else picked[:max(a.limit, len(exact))]
    got, fail = [], []
    for it in picked:
        r = download(it['rid'], it['name'])
        if 'path' in r:
            got.append((it, r))
            print(f"  [OK] {it['date']} {it['name']:<12} {it['title'][:38]:<40} {r['bytes']//1024:,}KB")
        else:
            fail.append(r)
            print(f"  [FAIL] rid={r['rid']} stage={r['stage']} {r.get('err') or r.get('status')}")

    meta_path = os.path.join(REF_DIR, '_meta.json')
    meta = []
    if os.path.exists(meta_path):
        meta = json.load(open(meta_path, encoding='utf-8'))
    have = {m.get('rid') for m in meta}
    for it, r in got:
        if it['rid'] not in have:
            meta.append({'name': it['name'], 'title': it['title'], 'date': it['date'],
                         'rid': it['rid'], 'path': r['path']})
    if got:
        os.makedirs(REF_DIR, exist_ok=True)
        json.dump(sorted(meta, key=lambda m: -(m.get('rid') or 0)),
                  open(meta_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print(f'\n  받음 {len(got)}편 / 실패 {len(fail)}건')
    if got:
        print('  ** 정독 의무 -- 투자포인트와 리스크 섹션을 먼저 읽는다 **')
        print('     같은 회사를 먼저 쓴 글이 우리 오해를 가장 싸게 잡아낸다')
        print()
        print('  ** 발간 시점을 먼저 본다 **')
        today = _dt.date.today()
        for it, _r in got:
            months = _age_months(it.get('date'), today)
            tag = '최신' if months is not None and months <= 6 else '오래됨'
            m = f'{months}개월 전' if months is not None else '시점 불명'
            print(f"    [{tag}] {it['date']}  {it['name']}  ({m})")
        print('    형식·구성·서술 방식은 시점과 무관하게 배운다.')
        print('    사실·전망·시장 규모는 그대로 쓰지 않는다 -- 발간 이후 바뀐 것을 대조한다.')
        print('    그 리포트가 기대한 것이 실제로 어떻게 됐는지가 오히려 좋은 재료다')
        print('    (CJ프레시웨이 실측: 2024-12 전망 OP 949억 -> 실제 940억, 주가 18,500 -> 22,850원).')
    else:
        print('  동종도 없으면 그 사실을 리포트 한계에 적는다')
    print('=' * 74)
    return 0 if got else 1


if __name__ == '__main__':
    raise SystemExit(main())
