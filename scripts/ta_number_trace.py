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


# 출처 분류 (v5.26-b, 사용자 결정 2026-09-21 "수집한 뉴스·리포트를 쓴다 -- 옮기지 않고 논리와 내용을 참고해서")
# 본문 숫자가 재무·공시에서만 왔으면 '재무 나열' 신호다. 신세계 초판/재작성판으로 기준선을 잰다.
EXT, FIN, LEDGER = '외부', '재무공시', '장부시세'
_LEDGER_FILES = {'assumptions.json', 'calc_ledger.json', 'market_data.json', 'flow.json', 'macro.json', 'calendar.json'}
_SKIP = {'synthesis.md', 'decision.md', 'gates.json', 'coverage_report.json', 'calc_check.json', 'manifest.json',
         'questions.json', 'watchlist.json', 'agent_plan.json', 'dart_diff.json', 'dart_diff_highlights.json'}


def _category(path: str, ta: str) -> str | None:
    base = os.path.basename(path)
    if base in _SKIP or base.startswith('decision_draft') or os.sep + 'sections' + os.sep in path:
        return None
    rel = os.path.relpath(path, ta).replace('\\', '/')
    if rel.startswith('..'):  # data/{종목}/ 직하 -- financial_summary·data_kis·_dart_*·_wisereport·_peer·_per_band
        return FIN
    if rel.startswith('dart/') or base.startswith('dart_'):
        return FIN
    if base in _LEDGER_FILES:
        return LEDGER
    return EXT  # notes / reports / ir_materials / _ir_*.txt / _irtv_* / news* / news_body / board / company_voice / event_study / customer_docs / trade_stats


def corpus_files(stock: str):
    """-> [(path, category)]"""
    ta = tc.ta_dir(stock)
    root = os.path.dirname(ta)
    pats = [os.path.join(ta, 'notes', '*.md'), os.path.join(ta, '*.json'), os.path.join(ta, '*.md'),
            os.path.join(ta, '*.txt'), os.path.join(ta, '*.vtt'), os.path.join(ta, 'dart', '*.txt'),
            os.path.join(ta, 'news_body', '*.txt'), os.path.join(ta, 'customer_docs', '*'), os.path.join(ta, 'ir_site', '*.txt'),
            os.path.join(ta, 'reports', '*', '*.txt'), os.path.join(ta, 'reports', '*', '*.tables.md'),
            os.path.join(ta, 'ir_materials', '*.txt'), os.path.join(ta, 'ir_materials', '*.tables.md'),
            os.path.join(root, '*.json'), os.path.join(root, '_dart_FULL_*.txt')]
    out = []
    for p in pats:
        for f in glob.glob(p):
            if os.path.isfile(f):
                c = _category(f, ta)
                if c:
                    out.append((f, c))
    return out


def corpus_numbers(files) -> dict:
    """-> {정규화 숫자: set(카테고리)}. files 는 [(path, cat)] 또는 [path] (카테고리 없으면 EXT)."""
    seen: dict = {}
    for item in files:
        f, cat = item if isinstance(item, tuple) else (item, EXT)
        try:
            with open(f, encoding='utf-8', errors='ignore') as fh:
                txt = fh.read()
        except OSError:
            continue
        for m in _NUM.finditer(txt):
            n = _norm(m.group(1))
            keys = [n]
            if '.' in n:
                v = float(n)
                keys += [str(int(round(v))), f'{v:.1f}']
            for k in keys:
                seen.setdefault(k, set()).add(cat)
    return seen


def trace(stock: str, analysis_path: str | None = None):
    analysis_path = analysis_path or os.path.join(tc.PROJECT_ROOT, 'scripts', f'analysis_{stock}_ta.json')
    d = json.load(open(analysis_path, encoding='utf-8'))
    nums = body_numbers(d.get('sections', {}))
    have = corpus_numbers(corpus_files(stock))
    missing, seen = [], set()
    cats = {EXT: 0, FIN: 0, LEDGER: 0}  # 숫자마다 '가장 좋은' 출처 하나로 센다: 외부 > 재무공시 > 장부시세
    for sec, tok, ctx, alt in nums:
        n = _norm(tok)
        found = have.get(n) or (have.get(alt) if alt else None)
        if not found and '.' in n:  # 소수는 반올림 한 자리 차이도 근거로 인정(7.55 -> 7.6)
            for h, c in have.items():
                if _looks_float(h) and abs(len(h) - len(n)) <= 2 and abs(float(n) - float(h)) < 0.06:
                    found = c
                    break
        if found:
            cats[EXT if EXT in found else FIN if FIN in found else LEDGER] += 1
            continue
        if (sec, n) in seen:
            continue
        seen.add((sec, n))
        missing.append((sec, tok, ctx))
    return nums, missing, cats


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
    nums, missing, cats = trace(a.stock, a.analysis)
    for sec, tok, ctx in missing:
        print(f'  [?] {sec[:6]} {tok:>10}  ...{ctx}...')
    tot = max(1, len(nums))
    print(f'[number_trace] 출처: 외부(리포트·IR·뉴스·노트) {cats[EXT]} ({cats[EXT] / tot:.0%}) / 재무·공시만 {cats[FIN]} ({cats[FIN] / tot:.0%}) / 장부·시세만 {cats[LEDGER]}')
    print(f'[number_trace] 본문 숫자 {len(nums)}개 / 근거 없음 {len(missing)}개 (수집물에 그 숫자가 없다 -- 계산값이면 장부에, 오기면 본문을 고친다)')
    return 1 if missing else 0


if __name__ == '__main__':
    raise SystemExit(main())
