# -*- coding: utf-8 -*-
"""KIND IR자료실 -- 기업설명회(IR) 발표자료 PDF 를 받는다 -> data/{종목}/ta/ir_materials/

DART 의 '기업설명회(IR) 개최' 공시는 개최 안내문뿐이고 발표 자료는 KIND IR자료실에 올라간다
(공시 본문 "IR 자료게재: 당사 홈페이지 / 한국거래소 KIND"). IR협의회 투자포인트 재료의 26%인 '회사 설명'의 1차 대체재.
usage: python scripts/ta_kind_ir.py {종목명} [--years 3]
"""
import io
import os
import re
import sys
import time
from datetime import date

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ta_common import ta_dir, manifest_update, write_json, resolve_stock  # noqa: E402

URL = 'https://kind.krx.co.kr/corpgeneral/irschedule.do'
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': URL + '?method=searchIRScheduleMain&gubun=iRMaterials'}
ROW = re.compile(r'<td class="txc">\s*(\d{4}-\d{2}-\d{2})\s*</td>.*?href="(/external/dst/irReference/(\d+)/([^"]+?\.pdf))"', re.S | re.I)


def parse_rows(html):
    """[{'date','seq','url_path','filename'}] -- 첨부 PDF 가 있는 행만."""
    return [{'date': d, 'seq': s, 'url_path': p, 'filename': f.strip()} for d, p, s, f in ROW.findall(html)]


def search(code, name, from_date, to_date, session):
    data = {'method': 'searchIRMaterialsSub', 'forward': 'searchirmaterials_sub', 'currentPageSize': '100', 'pageIndex': '1',
            'repIsuSrtCd': f'A{code}', 'searchCorpName': name, 'searchName': name,
            'fromDate': from_date, 'toDate': to_date, 'searchFromDate': from_date, 'searchToDate': to_date}
    r = session.post(URL, data=data, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def main(argv=None):
    import requests
    a = argv or sys.argv[1:]
    stock = a[0]
    years = int(a[a.index('--years') + 1]) if '--years' in a else 3
    info = resolve_stock(stock)
    code = info['code'] if isinstance(info, dict) else info[0]
    d = ta_dir(stock)
    out_dir = os.path.join(d, 'ir_materials')
    os.makedirs(out_dir, exist_ok=True)
    today = date.today()
    s = requests.Session()
    s.get(URL + '?method=searchIRScheduleMain&gubun=iRMaterials', headers=HEADERS, timeout=30)  # 세션 쿠키
    try:
        rows = parse_rows(search(code, stock, f'{today.year - years}-{today.month:02d}-{today.day:02d}', today.isoformat(), s))
    except Exception as e:
        manifest_update(stock, 'kind_ir', 'failed', reason=repr(e)[:200])
        print(f'[FAIL] kind_ir: {e!r}')
        return 1
    index = []
    for r in rows:
        pdf = os.path.join(out_dir, f"{r['date']}_{re.sub(r'[^\w.()-]+', '_', r['filename'])}")
        txt = pdf[:-4] + '.txt'
        try:
            if not os.path.exists(pdf):
                b = s.get('https://kind.krx.co.kr' + requests.utils.quote(r['url_path']), headers=HEADERS, timeout=60).content
                if not b.startswith(b'%PDF'):  # 에러 페이지가 200 으로 온다
                    raise RuntimeError(f'PDF 아님 ({len(b)} bytes)')
                with open(pdf, 'wb') as f:
                    f.write(b)
                time.sleep(0.5)
            import fitz
            doc = fitz.open(pdf)
            text = '\n'.join(pg.get_text() for pg in doc)
            with open(txt, 'w', encoding='utf-8') as f:
                f.write(text)
            index.append({'date': r['date'], 'file': os.path.basename(pdf), 'txt': os.path.basename(txt), 'pages': len(doc), 'chars': len(text), 'status': 'ok'})
        except Exception as e:
            index.append({'date': r['date'], 'file': r['filename'], 'status': 'failed', 'reason': repr(e)[:150]})
    write_json(os.path.join(out_dir, 'index.json'), {'asof': today.isoformat(), 'code': code, 'items': index})
    ok = sum(1 for i in index if i['status'] == 'ok')
    manifest_update(stock, 'kind_ir', 'ok' if ok else ('empty' if not rows else 'failed'), found=len(rows), ok=ok)
    for i in index:
        print(f"  {i['date']} {i['file']} {i['status']} {i.get('pages', '')}p {i.get('chars', '')}자 {i.get('reason', '')}")
    print(f"[{'OK' if ok else 'FAIL'}] kind_ir: {ok}/{len(rows)} PDF -> ta/ir_materials/")
    return 0 if ok or not rows else 1


if __name__ == '__main__':
    sys.exit(main())
