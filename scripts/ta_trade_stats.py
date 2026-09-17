# -*- coding: utf-8 -*-
"""관세청 품목별·국가별 수출입 실적 (data.go.kr 1220000/nitemtrade) -> data/{종목}/ta/trade_stats.json

IR협의회 산업현황 재료의 44%가 협회·정부 통계이고 그중 관세청이 가장 잦다
(docs/research-ta/kirs-construction.md 2절). 뉴스 대신 이것이 산업현황의 재료다.

입력: ta/trade_query.json {"hs": ["8486", "3701"], "countries": ["CN", "US"], "months": 24}
      HS 는 4~10자리. 메인이 사업보고서 II장(제품·수출 지역)을 보고 쓴다.
usage: python scripts/ta_trade_stats.py {종목명}
"""
import io
import os
import sys
import urllib.parse
import urllib.request
from datetime import date

from defusedxml import ElementTree as ET

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:/Users/hsh/Desktop')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ta_common import ta_dir, manifest_update, write_json, read_json  # noqa: E402

URL = 'https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList'


def parse_items(xml_text):
    """총계 행(hsCd/statCd 가 '-')을 빼고 [{'ym','hs','country','exp_usd','imp_usd'}]."""
    root = ET.fromstring(xml_text)
    code = root.findtext('.//resultCode')
    if code not in (None, '00'):  # 빈 응답을 '데이터 없음'으로 오해하지 않는다
        raise RuntimeError(f"관세청 API resultCode={code} {root.findtext('.//resultMsg') or ''}".strip())
    out = []
    for it in root.iter('item'):
        g = lambda k: (it.findtext(k) or '').strip()  # noqa: E731
        if g('hsCd') in ('', '-') or g('statCd') in ('', '-'):
            continue
        out.append({'ym': g('year').replace('.', ''), 'hs': g('hsCd'), 'country': g('statCd'),
                    'exp_usd': int(g('expDlr') or 0), 'imp_usd': int(g('impDlr') or 0)})
    return out


def ttm_yoy(series, end_ym):
    """end_ym 까지 최근 12개월 수출 합과 직전 12개월 합. 24개월 미만이면 None."""
    rows = sorted((r for r in series if r['ym'] <= end_ym), key=lambda r: r['ym'])[-24:]
    if len(rows) < 24:
        return None
    cur = sum(r['exp_usd'] for r in rows[12:])
    prev = sum(r['exp_usd'] for r in rows[:12])
    icur = sum(r.get('imp_usd', 0) for r in rows[12:])
    iprev = sum(r.get('imp_usd', 0) for r in rows[:12])
    # 수입 종목(식자재·원재료)은 imp 쪽이 본체 -- 수출만 보면 0 이라 yoy 가 None 이 된다(CJ프레시웨이 실측)
    return {'exp_ttm': cur, 'exp_ttm_prev': prev, 'yoy': (cur / prev - 1) if prev else None,
            'imp_ttm': icur, 'imp_ttm_prev': iprev, 'imp_yoy': (icur / iprev - 1) if iprev else None}


def _fetch_once(hs, country, start_ym, end_ym, key):
    q = urllib.parse.urlencode({'serviceKey': key, 'strtYymm': start_ym, 'endYymm': end_ym,
                                'hsSgn': hs, 'cntyCd': country})
    with urllib.request.urlopen(URL + '?' + q, timeout=30) as r:
        return r.read().decode('utf-8', 'ignore')


def windows(start_ym, end_ym):
    """API 는 조회기간 1년 이내만 허용 -- [(s, e), ...] 12개월 창으로 나눈다."""
    sy, sm, ey, em = int(start_ym[:4]), int(start_ym[4:]), int(end_ym[:4]), int(end_ym[4:])
    out, y, m = [], sy, sm
    while (y, m) <= (ey, em):
        y2, m2 = y, m + 11
        if m2 > 12:
            y2, m2 = y + 1, m2 - 12
        if (y2, m2) > (ey, em):
            y2, m2 = ey, em
        out.append((f'{y}{m:02d}', f'{y2}{m2:02d}'))
        y, m = (y2, m2 + 1) if m2 < 12 else (y2 + 1, 1)
    return out


def fetch(hs, country, start_ym, end_ym, key):
    """창마다 받아 행을 합친다(parse_items 결과 리스트)."""
    rows = []
    for s, e in windows(start_ym, end_ym):
        rows += parse_items(_fetch_once(hs, country, s, e, key))
    return rows


def main(argv=None):
    stock = (argv or sys.argv[1:])[0]
    from env_loader import load_env
    load_env()
    key = os.environ.get('DATA_GO_KR_API_KEY')
    d = ta_dir(stock)
    q = read_json(os.path.join(d, 'trade_query.json'))
    if not key or not q:
        manifest_update(stock, 'trade_stats', 'failed', reason='DATA_GO_KR_API_KEY 또는 ta/trade_query.json 없음')
        print('[FAIL] trade_stats: 키 또는 trade_query.json 없음')
        return 1
    today = date.today()
    months = int(q.get('months', 24)) + 1
    ey, em = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)  # 당월은 미집계 -- 전월까지
    end_ym = f'{ey}{em:02d}'
    sy, sm = ey, em - months
    while sm <= 0:
        sy, sm = sy - 1, sm + 12
    out = {'asof': today.isoformat(), 'query': q, 'series': {}, 'yoy': {}, 'failed': []}
    for hs in q['hs']:
        for c in q['countries']:
            try:
                rows = fetch(hs, c, f'{sy}{sm:02d}', end_ym, key)
            except Exception as e:  # 실패 이유를 남긴다 -- 조용한 실패 금지
                out['failed'].append({'hs': hs, 'country': c, 'reason': repr(e)[:200]})
                continue
            # 응답 검증: 요청한 HS 로 시작하는 행만 (무엇을 넣어도 같은 페이지를 주던 구 FnGuide 사고)
            rows = [r for r in rows if r['hs'].startswith(hs)]
            agg = {}
            for r in rows:
                a = agg.setdefault(r['ym'], {'ym': r['ym'], 'exp_usd': 0, 'imp_usd': 0})
                a['exp_usd'] += r['exp_usd']
                a['imp_usd'] += r['imp_usd']
            ser = sorted(agg.values(), key=lambda r: r['ym'])
            out['series'].setdefault(hs, {})[c] = ser
            out['yoy'].setdefault(hs, {})[c] = ttm_yoy(ser, ser[-1]['ym']) if ser else None
    write_json(os.path.join(d, 'trade_stats.json'), out)
    status = 'ok' if out['series'] else 'failed'
    manifest_update(stock, 'trade_stats', status, hs=len(q['hs']), failed=len(out['failed']))
    n = sum(len(v) for v in out['series'].values())
    print(f"[{status.upper()}] trade_stats: {n} 시리즈, 실패 {len(out['failed'])} -> ta/trade_stats.json")
    return 0 if status == 'ok' else 1


if __name__ == '__main__':
    sys.exit(main())
