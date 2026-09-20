# -*- coding: utf-8 -*-
"""ta_number_trace -- 본문의 숫자가 수집물 어딘가에 있는지 역추적한다 (v5.26, 2026-09-21, WARN 전용).

gpt-researcher 는 "문장마다 인용"을 프롬프트로 강제한다. 우리는 그것을 검사로 한다: 본문 정규 11절의
숫자 토큰을 뽑아 수집물 전체(정독 노트·ta/*.json·리포트 원문·IR 텍스트·DART 전문·financial_summary·장부)에서
찾고, 어디에도 없는 숫자를 절·숫자·앞뒤 문맥으로 출력한다. 계산값(합·비율)은 장부나 assumptions 에
있으면 통과하고, 없으면 목록에 남아 사람이 본다. critic 이 손으로 하던 grep 의 절반이다.

사용: python scripts/ta_number_trace.py {종목명}
출력 마지막 줄: [number_trace] 본문 숫자 N개 / 근거 없음 M개  (M>0 이면 exit 1 -- ta_gates 는 FORM 으로 warn 처리)
"""
from __future__ import annotations

import glob
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta_common as tc  # noqa: E402

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

CANON = ['s01_opinion_thesis', 's02_thesis_catalysts', 's03_company_overview', 's04_industry_competition',
         's05_management_fieldcheck', 's06_financial', 's07_valuation', 's08_esg', 's09_scenarios_risks',
         's10_earnings_consensus', 's11_supply_shareholder']
_NUM = re.compile(r'(?<![\d.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d+)(?!\d|,\d)')  # '7.55, ' 의 쉼표는 막지 않는다(JSON·산문)
_YEAR = re.compile(r'^(19|20)\d\d$')
_JO = re.compile(r'(\d+)조\s?$')
_DATE_CTX = re.compile(r'(월|일|년|분기|Q|H|시|번|회|개|명|건|위|층|호|점|차|째|권|편|행|열|장|주간|년간|개월)')


def _norm(tok: str) -> str:
    return tok.replace(',', '')


def body_numbers(sections: dict):
    """-> [(section, token, context, alt)] -- 두 자리 이하·연도·날짜/서수 문맥은 뺀다. alt 는 조+억 복합 표기의 결합값."""
    out = []
    for k in CANON:
        text = sections.get(k, '')
        for m in _NUM.finditer(text):
            tok = m.group(1)
            n = _norm(tok)
            if _YEAR.match(n) or len(n.replace('.', '')) <= 2:
                continue
            after = text[m.end():m.end() + 2]
            if _DATE_CTX.match(after) and '.' not in n and ',' not in tok and len(n) <= 4:
                continue  # 9월 30일, 2분기, 13개 점포 같은 서수·단위
            ctx = text[max(0, m.start() - 20):m.end() + 12].replace('\n', ' ')
            jo = _JO.search(text[max(0, m.start() - 4):m.start()])
            alt = (jo.group(1) + n.zfill(4)) if (jo and text[m.end():m.end() + 1] == '억') else None  # 7조7,579억 -> 77579
            out.append((k, tok, ctx, alt))
    return out


def corpus_files(stock: str):
    ta = tc.ta_dir(stock)
    root = os.path.dirname(ta)
    pats = [os.path.join(ta, 'notes', '*.md'), os.path.join(ta, '*.json'), os.path.join(ta, '*.md'),
            os.path.join(ta, 'reports', '*', '*.txt'), os.path.join(ta, 'reports', '*', '*.tables.md'),
            os.path.join(ta, 'ir_materials', '*.txt'), os.path.join(ta, 'ir_materials', '*.tables.md'),
            os.path.join(root, '*.json'), os.path.join(root, '_dart_FULL_*.txt')]
    files = []
    for p in pats:
        files += glob.glob(p)
    skip = {'synthesis.md', 'decision.md', 'gates.json'}  # 본문에서 나온 파일은 근거가 아니다
    return [f for f in files if os.path.basename(f) not in skip and os.sep + 'sections' + os.sep not in f]


def corpus_numbers(files) -> set:
    seen = set()
    for f in files:
        try:
            with open(f, encoding='utf-8', errors='ignore') as fh:
                txt = fh.read()
        except OSError:
            continue
        for m in _NUM.finditer(txt):
            n = _norm(m.group(1))
            seen.add(n)
            if '.' in n:  # 443970.25 -> 443970 / 5631.0 -> 5631 / 7.55 -> 7.6
                f = float(n)
                seen.add(str(int(round(f))))
                seen.add(f'{f:.1f}')
    return seen


def trace(stock: str, analysis_path: str | None = None):
    analysis_path = analysis_path or os.path.join(tc.PROJECT_ROOT, 'scripts', f'analysis_{stock}_ta.json')
    d = json.load(open(analysis_path, encoding='utf-8'))
    nums = body_numbers(d.get('sections', {}))
    have = corpus_numbers(corpus_files(stock))
    missing, seen = [], set()
    for sec, tok, ctx, alt in nums:
        n = _norm(tok)
        if n in have or (sec, n) in seen or (alt and alt in have):
            continue
        # 소수는 반올림 한 자리 차이도 근거로 인정(7.55 -> 7.6)
        if '.' in n and any(abs(float(n) - float(h)) < 0.06 for h in have if _looks_float(h) and abs(len(h) - len(n)) <= 2):
            continue
        seen.add((sec, n))
        missing.append((sec, tok, ctx))
    return nums, missing


def _looks_float(s: str) -> bool:
    try:
        float(s)
        return '.' in s
    except ValueError:
        return False


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('stock')
    ap.add_argument('--analysis')
    a = ap.parse_args(argv)
    nums, missing = trace(a.stock, a.analysis)
    for sec, tok, ctx in missing:
        print(f'  [?] {sec[:6]} {tok:>10}  ...{ctx}...')
    print(f'[number_trace] 본문 숫자 {len(nums)}개 / 근거 없음 {len(missing)}개 (수집물에 그 숫자가 없다 -- 계산값이면 장부에, 오기면 본문을 고친다)')
    return 1 if missing else 0


if __name__ == '__main__':
    raise SystemExit(main())
