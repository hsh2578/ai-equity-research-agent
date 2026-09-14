# -*- coding: utf-8 -*-
"""wisereport_consensus.py -- 컨센서스를 **추이로** 받는다 (v5.21 신설).

배경(2026-09 에프에스티): 임시 코드로 Wisereport 를 긁어
`{"202612": {"영업이익": 88억}}` 를 저장했다. 88억은 **4분기 컨센서스**였는데
키가 연도(202612)여서 연간으로 읽혔고, 리포트가 "상반기 확정 110억이 연간 컨센
88억을 이미 넘었다 -- 컨센이 갱신되지 않는다"고 썼다. 실제 2026년 연간 컨센은
영업이익 277억이고, 3개월 전 231억에서 **상향**된 값이다. 결론이 정반대였다.

그래서 이 파일은 두 가지를 구조로 막는다.
  1) 모든 값에 `period_type`('annual'/'quarter')을 붙인다. 분기를 연간으로
     라벨링하는 것이 불가능해진다.
  2) 스냅샷이 아니라 **추이**(현재/1주전/1개월전/3개월전/1년전)를 받는다.
     컨센이 갱신되지 않았다는 주장은 추이를 봐야 할 수 있는 말이다.

엔드포인트 (c1050001 컨센서스 페이지가 쓰는 것 그대로):
    c1050001_data.aspx?flag=1   추정 가능한 기간 목록 (CK=1 이면 데이터 있음)
    c1050001_data.aspx?flag=4   기간별 컨센서스 표  (VAL1..VAL5 = 현재/1주/1개월/3개월/1년 전)
    cF5002.aspx                 항목별 컨센 추이 (avg + min_max -- min==max 면 추정기관 1곳)

사용: python scripts/wisereport_consensus.py {종목명} {6자리코드}
"""
import io
import json
import os
import sys
from datetime import datetime

import requests

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'https://comp.wisereport.co.kr/company'
PAGE = BASE + '/c1050001.aspx'
DATA = BASE + '/ajax/c1050001_data.aspx'
CHART = BASE + '/ajax/cF5002.aspx'

# VAL1~VAL5 의 뜻. 페이지 표 헤더가 "2026/09/14 / 1주전 / 1개월전 / 3개월전 / 1년전" 이다.
COLS = ('현재', '1주전', '1개월전', '3개월전', '1년전')
TREND_ITEMS = {'121000': '매출액', '121500': '영업이익', '312000': 'EPS'}


def _session(code):
    s = requests.Session()
    s.headers.update({'User-Agent': 'Mozilla/5.0',
                      'Referer': f'{PAGE}?cmp_cd={code}'})
    r = s.get(PAGE, params={'cmp_cd': code}, timeout=20)
    r.raise_for_status()
    return s


def periods(s, code, frq):
    """추정치가 있는 기간만 돌려준다. frq: '0' 연간 / '1' 분기."""
    r = s.get(DATA, params=dict(flag='1', cmp_cd=code, finGubun='MAIN', frq=frq,
                                sDT=datetime.now().strftime('%Y%m%d'), yymm='', acc_cd='121000'),
              timeout=20)
    r.raise_for_status()
    return [d['YYMM'] for d in r.json().get('JsonData', []) if d.get('CK')]


def table(s, code, frq, yymm):
    """한 기간의 컨센서스 표. 값은 {항목: {현재:.., 3개월전:..}}."""
    r = s.get(DATA, params=dict(flag='4', cmp_cd=code, finGubun='MAIN', frq=frq,
                                sDT=datetime.now().strftime('%Y%m%d'), yymm=yymm,
                                acc_cd='121000', chartType='svg'), timeout=20)
    r.raise_for_status()
    return parse_table(r.json())


def parse_table(payload):
    out = {}
    for d in payload.get('JsonData', []):
        name = d.get('ACC_NM')
        if not name:
            continue
        out[name] = {c: d.get(f'VAL{i}') for i, c in enumerate(COLS, start=1)}
    return out


def trend(s, code, yymm, acc_cd):
    r = s.get(CHART, params=dict(cmp_cd=code, dt=datetime.now().strftime('%Y%m%d'),
                                 yymm=yymm, frq='Y', acc_cd=acc_cd,
                                 fingubun='MAIN', chartType='svg'), timeout=20)
    r.raise_for_status()
    return parse_trend(r.json())


def parse_trend(payload):
    """chart2 = 선택 항목, chart1 = EPS. min==max 면 추정 기관이 1곳이다."""
    out = {}
    for key in ('chart1', 'chart2'):
        raw = payload.get(key)
        if not raw:
            continue
        c = json.loads(raw) if isinstance(raw, str) else raw
        if not c.get('categories'):
            continue
        mm = c.get('min_max') or []
        out[c.get('item_name') or key] = {
            'unit': c.get('item_unit'),
            'dates': c.get('categories'),
            'avg': c.get('avg'),
            'min_max': mm,
            # 마지막 시점의 min==max 이면 추정치를 낸 곳이 하나다
            'single_estimator': bool(mm) and mm[-1][0] == mm[-1][1],
        }
    return out


def collect(stock_name, code):
    s = _session(code)
    out = {'stock_name': stock_name, 'stock_code': code,
           'as_of': datetime.now().strftime('%Y-%m-%d'),
           'columns': list(COLS), 'source': PAGE,
           'annual': {}, 'quarter': {}, 'trend': {}}
    for frq, kind in (('0', 'annual'), ('1', 'quarter')):
        for yymm in periods(s, code, frq):
            out[kind][yymm] = {'period_type': kind, 'items': table(s, code, frq, yymm)}
    nearest = sorted(out['annual'])
    if nearest:
        y = nearest[0]
        for acc_cd, label in TREND_ITEMS.items():
            try:
                out['trend'][label] = trend(s, code, y, acc_cd)
            except Exception as e:           # 실패를 None 으로 삼키지 않는다
                out['trend'][label] = {'error': f'{type(e).__name__}: {e}'}
    return out


def _num(v):
    return f'{v:,.1f}' if isinstance(v, (int, float)) else '-'


def main(stock_name, code):
    d = collect(stock_name, code)
    path = os.path.join(ROOT, 'data', stock_name, '_wisereport_consensus.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(d, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    print('=' * 74)
    print(f'  Wisereport 컨센서스 추이: {stock_name}({code})  기준 {d["as_of"]}')
    print('=' * 74)
    for kind in ('annual', 'quarter'):
        for yymm, blk in sorted(d[kind].items()):
            items = blk['items']
            head = f'  [{kind:7s}] {yymm}'
            for name in ('매출액(억원)', '영업이익(억원)', 'EPS(원)'):
                v = items.get(name) or {}
                head += f"  {name.split('(')[0]} {_num(v.get('현재'))}"
                if v.get('3개월전') not in (None, v.get('현재')):
                    head += f"(3M전 {_num(v.get('3개월전'))})"
            print(head)
    solo = sorted({item for t in d['trend'].values()
                   for item, blk in (t or {}).items() if blk.get('single_estimator')})
    if solo:
        print(f"  [주의] 추정 기관이 1곳이다 ({', '.join(solo)} min==max). "
              f"'평균' 이라는 말을 쓰지 않는다")
    print(f'\n  저장: {os.path.relpath(path, ROOT)}')
    print('  ** 분기 값을 연간으로 인용하지 않는다. period_type 을 보고 쓴다 **')
    print('=' * 74)
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('사용: python scripts/wisereport_consensus.py {종목명} {6자리코드}')
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
