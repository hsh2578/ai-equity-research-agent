# -*- coding: utf-8 -*-
"""고객사·장비사·경쟁사 공개 자료 -> data/{종목}/ta/customer_docs/{name}.md

IR협의회 산업현황 재료의 22%가 고객사·경쟁사 공개자료(10-K/10-Q, 기업설명회 자료)다. 뉴스가 아니다
(docs/research-ta/kirs-construction.md 5절).

입력: ta/customers.json
  [{"name": "Lam Research", "kind": "US", "ticker": "LRCX", "keywords": ["capex", "Korea", "WFE"]},
   {"name": "삼성전자", "kind": "KR", "keywords": ["시설투자", "평택", "테일러"]}]
출력: customer_docs/{name}.md (인용 + 원문 파일:줄), customer_docs/index.json
usage: python scripts/ta_customer_docs.py {종목명} [--max-filings 2]
"""
import io
import os
import re
import sys
from datetime import date, timedelta

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:/Users/hsh/Desktop')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ta_common import ta_dir, manifest_update, read_json, write_json  # noqa: E402

BOILER = re.compile(r'forward-looking|safe harbor|투자판단 참고|본 자료는', re.I)


def is_boilerplate(line):
    return bool(BOILER.search(line))


def pick_paragraphs(text, keywords, window=600, max_n=12):
    """키워드가 든 줄(1-base)과 그 줄부터 window 자 인용. 보일러플레이트 줄 제외, 줄당 1회."""
    pat = re.compile('|'.join(re.escape(k) for k in keywords), re.I)
    lines = text.split('\n')
    out = []
    for i, line in enumerate(lines, 1):
        if pat.search(line) and not is_boilerplate(line):
            out.append({'line': i, 'quote': '\n'.join(lines[i - 1:i + 3])[:window].strip()})
            if len(out) >= max_n:
                break
    return out


def us_docs(entry, max_filings):
    """최근 10-Q·10-K 본문 텍스트. submissions JSON 의 primaryDocument 로 URL 을 만든다."""
    import requests
    import sec_edgar as se
    cik = se.get_cik(entry['ticker'])
    sub = requests.get(f'https://data.sec.gov/submissions/CIK{cik}.json', headers=se.HEADERS, timeout=30).json()
    rec = sub.get('filings', {}).get('recent', {})
    docs = []
    for form in ('10-Q', '10-K'):
        n = 0
        for i, f in enumerate(rec.get('form', [])):
            if f != form or n >= max_filings:
                continue
            acc = rec['accessionNumber'][i].replace('-', '')
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{rec['primaryDocument'][i]}"
            docs.append((f"SEC {form} {rec['filingDate'][i]}", se.download_filing_text(url)))
            n += 1
    return docs


def kr_docs(entry, max_filings):
    """DART 기업설명회 첨부 + 최근 분기·반기보고서 본문."""
    from dart_api import get_corp_code, download_report_document, html_to_text
    from collect_dart_filings import fetch_list
    cc = get_corp_code(entry['name'])
    corp = cc[0] if isinstance(cc, (list, tuple)) else cc  # (고유번호, 종목코드) 튜플
    end = date.today()
    bgn = end - timedelta(days=400)
    key = os.environ.get('DART_API_KEY')
    docs = []
    for it in fetch_list(corp, bgn.strftime('%Y%m%d'), end.strftime('%Y%m%d'), key):
        nm = it.get('report_nm', '')
        if not any(k in nm for k in ('기업설명회', '분기보고서', '반기보고서')):
            continue
        for _fn, html in (download_report_document(it['rcept_no']) or {}).items():
            docs.append((f"DART {nm} {it.get('rcept_dt', '')}", html_to_text(html)))
        if len(docs) >= max_filings:
            break
    return docs


def main(argv=None):
    a = argv or sys.argv[1:]
    stock = a[0]
    max_f = int(a[a.index('--max-filings') + 1]) if '--max-filings' in a else 2
    from env_loader import load_env
    load_env()
    d = ta_dir(stock)
    cust = read_json(os.path.join(d, 'customers.json')) or []
    out_dir = os.path.join(d, 'customer_docs')
    os.makedirs(out_dir, exist_ok=True)
    index = []
    for e in cust:
        try:
            docs = us_docs(e, max_f) if e.get('kind') == 'US' else kr_docs(e, max_f)
        except Exception as ex:  # 실패 이유를 남긴다
            index.append({'name': e['name'], 'status': 'failed', 'reason': repr(ex)[:200]})
            continue
        md = [f"# {e['name']} -- 공개 자료 발췌 ({date.today()})\n"]
        n = 0
        for label, txt in docs:
            raw = os.path.join(out_dir, re.sub(r'[^\w]+', '_', f"{e['name']}_{label}")[:80] + '.txt')
            with open(raw, 'w', encoding='utf-8') as f:
                f.write(txt)
            for h in pick_paragraphs(txt, e.get('keywords', [])):
                md.append(f"## {label} ({os.path.basename(raw)}:{h['line']})\n\n> {h['quote']}\n")
                n += 1
        with open(os.path.join(out_dir, f"{e['name']}.md"), 'w', encoding='utf-8') as f:
            f.write('\n'.join(md))
        index.append({'name': e['name'], 'status': 'ok' if n else 'empty', 'quotes': n, 'docs': len(docs)})
    write_json(os.path.join(out_dir, 'index.json'), index)
    ok = sum(1 for i in index if i['status'] == 'ok')
    manifest_update(stock, 'customer_docs', 'ok' if ok else 'failed', ok=ok, total=len(index))
    for i in index:
        print(f"  {i['name']}: {i['status']} {i.get('quotes', '')} {i.get('reason', '')}")
    print(f"[{'OK' if ok else 'FAIL'}] customer_docs: {ok}/{len(index)} 에서 인용 확보 -> ta/customer_docs/")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
