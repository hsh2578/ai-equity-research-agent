# -*- coding: utf-8 -*-
"""DART 수시공시 수집 (v5.21 신설).

배경(2026-09 에프에스티 실측): 정기보고서(사업/반기/분기) 4건만 읽고 리포트를
썼더니 아래가 통째로 빠졌다. 전부 같은 API 로 받을 수 있는 것이었다.

  - 자기주식 처분 결정: "처분목적 = EUV펠리클 확장 투자 재원 확보"
    -> 리포트는 "설비투자 목적을 공시가 말하지 않는다"고 썼다. 말하고 있었다.
  - 주식소각 결정: 51만주 소각으로 발행주식 21,956,348 -> 21,446,348
    -> 주당 지표 전부가 바뀌는데 옛 주식수로 계산했다.
  - 매출액/손익구조 변동: 회사가 적자 사유를 직접 적어 둔다
    ("R&D 확대 + 미국 Taylor 장비납품 준비로 인한 고정비 증가")
  - 소속부 변경: 우량기업부 -> 중견기업부

정기보고서는 '무엇을 했는가'를 말하고, 수시공시는 '왜 했는가'를 말한다.
후자가 없으면 리포트가 회사 내부 숫자만 재해석하는 글이 된다.

사용법:
    python scripts/collect_dart_filings.py {종목명} [시작일 YYYYMMDD] [종료일]

산출: data/{종목명}/_dart_filings.json   (목록 전체 + 핵심 공시 본문)
"""
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests                                            # noqa: E402
from dart_api import (get_corp_code, download_report_document,  # noqa: E402
                      html_to_text, DART_API_KEY)

# 본문까지 받아야 하는 공시. 리포트 서술을 바꾸는 것들만 고른다.
# (정기보고서는 collect_dart_full.py 가 따로 받으므로 여기서 제외)
BODY_KEYWORDS = (
    '자기주식', '주식소각', '유상증자', '무상증자', '전환사채', '신주인수권',
    '교환사채', '회사합병', '분할', '영업양수', '영업양도', '타법인주식',
    '공급계약', '수주', '단일판매', '시설투자', '신규시설',
    '매출액또는손익구조', '소속부변경', '관리종목', '투자판단',
    '배당결정', '기업설명회', '기업가치제고',
)

# 목록만 세면 되는 것 (본문을 받아도 정보가 거의 없다)
SKIP_BODY = ('주주명부폐쇄', '주주총회소집공고', '의결권대리행사',
             '감사보고서제출', '독립이사의선임')


def fetch_list(corp_code, bgn, end, key):
    """공시 목록. DART list.json 은 page_count 최대 100."""
    out, page = [], 1
    while True:
        r = requests.get('https://opendart.fss.or.kr/api/list.json', params={
            'crtfc_key': key, 'corp_code': corp_code,
            'bgn_de': bgn, 'end_de': end,
            'page_no': page, 'page_count': 100}, timeout=30).json()
        if r.get('status') != '000':
            if page == 1:
                # 조용한 실패 금지 -- 왜 비었는지 남긴다
                raise RuntimeError(f"DART list {r.get('status')}: {r.get('message')}")
            break
        out += r.get('list', [])
        if page >= int(r.get('total_page', 1)):
            break
        page += 1
    return out


def wants_body(name):
    if any(s in name for s in SKIP_BODY):
        return False
    return any(k in name.replace(' ', '') for k in BODY_KEYWORDS)


def main(argv=None):
    a = (argv or sys.argv[1:])
    if not a:
        print('사용법: python scripts/collect_dart_filings.py {종목명} [YYYYMMDD] [YYYYMMDD]')
        return 2
    name = a[0]
    end = a[2] if len(a) > 2 else datetime.now().strftime('%Y%m%d')
    bgn = a[1] if len(a) > 1 else (datetime.now() - timedelta(days=730)).strftime('%Y%m%d')

    cc = get_corp_code(name)
    corp = cc[0] if isinstance(cc, (list, tuple)) else cc
    if not corp:
        print(f'[ERR] {name} 고유번호 조회 실패')
        return 1
    key = os.environ.get('DART_API_KEY') or DART_API_KEY

    rows = fetch_list(corp, bgn, end, key)
    print(f'[OK] {name} 공시 {len(rows)}건 ({bgn}~{end})')

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'data', name)
    os.makedirs(out_dir, exist_ok=True)

    bodies, fails = [], []
    for it in rows:
        nm = (it.get('report_nm') or '').strip()
        if not wants_body(nm):
            continue
        rc = it.get('rcept_no')
        try:
            files = download_report_document(rc)
            if not files:
                fails.append((nm, rc, 'ZIP 없음'))
                continue
            top = sorted(files.items(), key=lambda kv: -len(kv[1]))[:2]
            txt = re.sub(r'\n{3,}', '\n\n', '\n'.join(html_to_text(v) for _, v in top))
            bodies.append({'date': it.get('rcept_dt'), 'name': nm,
                           'rcept_no': rc, 'text': txt[:12000]})
            print(f"  [본문] {it.get('rcept_dt')}  {nm[:38]}  {len(txt):,}자")
        except Exception as e:                              # noqa: BLE001
            fails.append((nm, rc, f'{type(e).__name__}: {e}'))

    data = {
        '_description': f'{name} DART 수시공시 (목록 전체 + 핵심 공시 본문)',
        '_collected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'stock': name, 'corp_code': corp, 'period': [bgn, end],
        'count': len(rows),
        'list': [{'date': x.get('rcept_dt'), 'name': (x.get('report_nm') or '').strip(),
                  'rcept_no': x.get('rcept_no')} for x in rows],
        'bodies': bodies,
        'failures': [{'name': n, 'rcept_no': r, 'why': w} for n, r, w in fails],
    }
    p = os.path.join(out_dir, '_dart_filings.json')
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)
    print(f'\n[OK] saved: {p}  (본문 {len(bodies)}건 / 실패 {len(fails)}건)')
    if fails:
        for n, r, w in fails[:5]:
            print(f'  [FAIL] {n[:34]} {r} -- {w}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
