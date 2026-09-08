# -*- coding: utf-8 -*-
"""Bloom Energy(BE) SEC 재무 + 10-K/10-Q 본문 덤프.

STEP 2.5-US -- 본문을 data/BE/_sec_*.txt 로 떨어뜨려야 필수 grep 10종을
돌릴 수 있다. 요약본만으로는 reportable segments 를 직접 인용할 수 없다
(v4.17 AMD "SEC 4 segments" 거짓 진술 사고).
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sec_edgar as se                                        # noqa: E402

TICKER = 'BE'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'data', TICKER)
os.makedirs(OUT, exist_ok=True)

cik = se.get_cik(TICKER)
print(f'[OK] CIK={cik}')

# --- 재무 (XBRL companyfacts) ---
try:
    facts = se.get_company_facts(cik)
    fin = se.extract_financials(facts)
    q = se.extract_quarterly_financials(facts) if hasattr(
        se, 'extract_quarterly_financials') else None
    with open(os.path.join(OUT, 'data_sec.json'), 'w', encoding='utf-8') as f:
        json.dump({'annual': fin, 'quarterly': q}, f,
                  ensure_ascii=False, indent=2, default=str)
    print(f'[OK] data_sec.json ({len(fin)} 지표)')
except Exception as e:                                        # noqa: BLE001
    print(f'[FAIL] XBRL: {type(e).__name__}: {e}')

# --- 본문 ---
saved = 0
for form in ('10-K', '10-Q'):
    try:
        filings = se.get_recent_filings(cik, form, count=2)
    except Exception as e:                                    # noqa: BLE001
        print(f'[FAIL] {form} 목록: {type(e).__name__}: {e}')
        continue
    for i, f_ in enumerate(filings):
        acc = f_.get('accessionNumber') or f_.get('accession')
        date = f_.get('filingDate') or f_.get('date') or ''
        if not acc:
            print(f'[FAIL] {form}[{i}] accession 없음: {list(f_)[:6]}')
            continue
        try:
            docs = se.get_filing_documents(cik, acc)
            htm = [d for d in docs
                   if str(d.get('name', '')).lower().endswith(('.htm', '.html'))]
            if not htm:
                print(f'[FAIL] {form}[{i}] HTM 없음')
                continue
            best = max(htm, key=lambda d: d.get('size', 0))
            text = se.download_filing_text(best['url'])
        except Exception as e:                                # noqa: BLE001
            print(f'[FAIL] {form}[{i}] {acc}: {type(e).__name__}: {e}')
            continue
        p = os.path.join(OUT, f'_sec_{form.replace("-", "")}_{date}.txt')
        with open(p, 'w', encoding='utf-8') as fh:
            fh.write(text)
        saved += 1
        print(f'[OK] {form} {date} {len(text):,}자 -> {os.path.basename(p)}')

print(f'\n[OK] 본문 {saved}건')
