# -*- coding: utf-8 -*-
"""피에스케이홀딩스 DART 전문 수집 (반기보고서 + 사업보고서).

v5.10 규칙 2 / v4.18 -- get_all_reports 요약본은 15,000자 truncate 라
「I. 회사의 개요」가 통째로 빠진다. download_report_document + html_to_text 로
전문을 받아 data/{종목}/_dart_FULL_*.txt 에 저장한다.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from dart_api import (get_corp_code, get_all_report_rcept_nos,   # noqa: E402
                      download_report_document, html_to_text)

NAME, CODE = '피에스케이홀딩스', '031980'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'data', NAME)
os.makedirs(OUT, exist_ok=True)

corp_code, _ = get_corp_code(NAME)
print(f'[OK] corp_code={corp_code}')

rows = get_all_report_rcept_nos(corp_code)
print(f'[OK] 정기보고서 {len(rows)}건')

saved = []
for r in rows:
    nm = r.get('report_nm', '').strip()
    rcept = r.get('rcept_no')
    if not any(k in nm for k in ('사업보고서', '반기보고서', '분기보고서')):
        continue
    try:
        files = download_report_document(rcept)
        if not files:
            print(f'[FAIL] {nm} ({rcept}): ZIP 없음')
            continue
        # 본문 HTML 을 크기순으로 합친다 (I. 회사의 개요 + II. 사업의 내용 확보)
        parts = sorted(files.items(), key=lambda kv: -len(kv[1]))[:6]
        text = '\n\n'.join(html_to_text(v) for _, v in parts)
    except Exception as e:                                    # noqa: BLE001
        # 조용한 실패 금지 -- 무엇이 왜 안 됐는지 남긴다
        print(f'[FAIL] {nm} ({rcept}): {type(e).__name__}: {e}')
        continue
    safe = nm.replace(' ', '').replace('/', '')[:24]
    p = os.path.join(OUT, f'_dart_FULL_{safe}_{rcept}.txt')
    with open(p, 'w', encoding='utf-8') as f:
        f.write(text)
    saved.append((nm, r.get('rcept_dt'), len(text), p))
    print(f'[OK] {nm} {r.get("rcept_dt")} {len(text):,}자')
    if len(saved) >= 4:
        break

with open(os.path.join(OUT, '_dart_rcept_nos.json'), 'w', encoding='utf-8') as f:
    json.dump([{'name': n, 'date': d, 'chars': c, 'path': p}
               for n, d, c, p in saved], f, ensure_ascii=False, indent=2)
print(f'\n[OK] {len(saved)}건 저장')
