# -*- coding: utf-8 -*-
"""ta_coverage_check.py -- 분석가 brief 반영 게이트 (/research-ta Task 11).

/research 의 핵심 결함("받아 둔 뉴스·공시가 리포트에 안 들어간다")을
결정론적으로 잡는다. 날짜·수치 매칭은 오탐이 나서 쓰지 않는다 -- 분석가
brief 의 항목 ID 와 작성자가 채운 coverage_map(반영 지도)만으로 판정한다.

입력:
  1. data/{종목}/ta/brief_*.md -- ID/필수 열이 있는 markdown 표
  2. data/{종목}/ta/coverage_map.json -- {"ID": {"section","quote"} 또는 {"excluded"}}
  3. analysis json 의 "sections" (정규 12키 + alias 키, 전부 평평한 dict)

사용: python scripts/ta_coverage_check.py {종목명} [--analysis scripts/analysis_{종목명}_ta.json]
"""
import argparse
import glob
import io
import json
import os
import re
import sys

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta_common as tc  # noqa: E402

ID_RE = re.compile(r'^[A-Z]{1,2}\d{2,3}$')
_SEP_CELL_RE = re.compile(r'^:?-+:?$')


# ==================== markdown 표 파싱 ====================

def _split_row(line):
    line = line.strip()
    if line.startswith('|'):
        line = line[1:]
    if line.endswith('|'):
        line = line[:-1]
    return [c.strip() for c in line.split('|')]


def _is_separator_row(cells):
    if not cells:
        return False
    return all(_SEP_CELL_RE.match(c.strip()) for c in cells)


def parse_tables(text):
    """text 안의 모든 markdown 표에서 ID/필수 열이 있는 표만 골라 행을 뽑는다.
    반환: [{'id': str, 'required': bool}, ...] (ID 형식 아닌 행은 버린다)
    """
    lines = (text or '').splitlines()
    rows = []
    n = len(lines)
    i = 0
    while i < n - 1:
        if '|' not in lines[i]:
            i += 1
            continue
        header = _split_row(lines[i])
        sep = _split_row(lines[i + 1]) if '|' in lines[i + 1] else []
        if len(sep) != len(header) or not _is_separator_row(sep):
            i += 1
            continue
        try:
            id_idx = header.index('ID')
            req_idx = header.index('필수')
        except ValueError:
            i += 2
            continue
        j = i + 2
        while j < n and lines[j].strip() and '|' in lines[j]:
            cells = _split_row(lines[j])
            if len(cells) > max(id_idx, req_idx):
                cid = cells[id_idx].strip()
                if ID_RE.match(cid):
                    rows.append({'id': cid, 'required': cells[req_idx].strip().upper() == 'Y'})
            j += 1
        i = j
    return rows


def parse_briefs_text(files):
    """files: {파일명/경로: 원문 텍스트}. 반환: id -> [{'required':bool,'file':str}, ...]"""
    occ = {}
    for path, text in files.items():
        for row in parse_tables(text):
            occ.setdefault(row['id'], []).append({'required': row['required'], 'file': path})
    return occ


# ==================== 정독 노트 (v5.26-c) ====================
CORE_SECTIONS = ('s02_thesis_catalysts', 's03_company_overview', 's04_industry_competition')
_NOTE_ALIAS = {'s02_investment_points': 's02_thesis_catalysts', 's04_industry': 's04_industry_competition'}


def parse_notes(notes_dir):
    """ta/notes/*.md (앞에 _ 가 붙은 요약 파일 제외) -> id 'note:{stem}' 마다 필수 1건.
    노트 본문은 읽지 않는다 -- 정독한 리포트 한 편이 본문 어딘가에 논리로 들어갔는지만 묻는다."""
    occ = {}
    for path in sorted(glob.glob(os.path.join(notes_dir, '*.md'))):
        stem = os.path.splitext(os.path.basename(path))[0]
        if stem.startswith('_'):
            continue
        occ[f'note:{stem}'] = [{'required': True, 'file': path}]
    return occ


def parse_briefs(paths):
    files = {}
    for p in paths:
        with open(p, encoding='utf-8') as f:
            files[p] = f.read()
    return parse_briefs_text(files)


# ==================== quote 정규화 ====================

def _normalize(s):
    s = (s or '').replace('**', '').replace('__', '').replace('`', '')
    return re.sub(r'\s+', ' ', s).strip()


# ==================== 판정 ====================

def _evaluate_one(item_id, coverage_map, sections):
    entry = coverage_map.get(item_id)
    if entry is None:
        return {'id': item_id, 'status': 'FAIL', 'reason': 'missing', 'section': None}

    if 'excluded' in entry:
        reason_text = (entry.get('excluded') or '').strip()
        if len(reason_text) < 10:
            return {'id': item_id, 'status': 'FAIL', 'reason': 'weak_exclusion', 'section': None}
        return {'id': item_id, 'status': 'PASS', 'reason': 'excluded', 'section': None}

    section_key = entry.get('section') or ''
    body = sections.get(section_key) if section_key else None
    if not section_key or not body:
        return {'id': item_id, 'status': 'FAIL', 'reason': 'bad_section', 'section': section_key or None}

    quote = entry.get('quote') or ''
    if len(quote.strip()) < 20:
        return {'id': item_id, 'status': 'FAIL', 'reason': 'short_quote', 'section': section_key}

    if _normalize(quote) not in _normalize(body):
        return {'id': item_id, 'status': 'FAIL', 'reason': 'quote_not_found', 'section': section_key}

    return {'id': item_id, 'status': 'PASS', 'reason': 'covered', 'section': section_key}


def _prefix(item_id):
    if item_id.startswith('note:'):
        return 'note'
    m = re.match(r'^[A-Z]{1,2}', item_id)
    return m.group(0) if m else '?'


def note_core_stats(items):
    """종목·산업 리포트 노트(ir_ 제외) 가운데 s02·s03·s04 에 착지한 수. IR 덱 노트는 s05·s10 이 정상이라 뺀다."""
    reports = [it for it in items if it['id'].startswith('note:') and not it['id'].startswith('note:ir_')]
    in_core = [it for it in reports if it['status'] == 'PASS' and it['reason'] == 'covered'
               and _NOTE_ALIAS.get(it['section'], it['section']) in CORE_SECTIONS]
    return {'report_notes': len(reports), 'in_core': len(in_core),
            'outside_core': [it['id'] for it in reports if it not in in_core and it['status'] == 'PASS' and it['reason'] == 'covered']}


def evaluate(occurrences, coverage_map, sections):
    """occurrences: parse_briefs()/parse_briefs_text() 반환값.
    반환: coverage_report.json 스키마 dict.

    'failed' 는 필수(Y) 파이프라인에 속한 FAIL 만 센다(필수 비율 통계용).
    'fail_items' 는 items 전체의 FAIL 총수(순수 N/N 중복 FAIL 포함) -- 종료
    코드/manifest 상태는 반드시 이걸로 판정한다. "에러(중복 ID) -> FAIL" 은
    필수 여부와 무관하게 무조건 실패이기 때문.
    """
    coverage_map = coverage_map or {}
    sections = sections or {}
    brief_ids_all = set(occurrences.keys())
    duplicate_ids = {i for i, occ in occurrences.items() if len(occ) > 1}
    # 판단: required 는 "brief 가 필수=Y 로 지정한 ID" 전체(중복이라도 한 번이라도
    # Y 였으면 포함). 순수 중복(중복인데 한쪽도 필수가 아닌 경우)은 문서 오류로
    # FAIL 처리는 하되 필수 통계에는 넣지 않는다.
    required_ids_unique = {i for i, occ in occurrences.items()
                            if len(occ) == 1 and occ[0]['required']}
    required_dup_ids = {i for i in duplicate_ids if any(o['required'] for o in occurrences[i])}

    items = []
    for item_id in sorted(duplicate_ids):
        items.append({'id': item_id, 'status': 'FAIL', 'reason': 'duplicate_id', 'section': None})
    for item_id in sorted(required_ids_unique):
        items.append(_evaluate_one(item_id, coverage_map, sections))
    for item_id in sorted(coverage_map.keys()):
        if item_id not in brief_ids_all:
            items.append({'id': item_id, 'status': 'WARN', 'reason': 'unknown_id',
                          'section': (coverage_map.get(item_id) or {}).get('section')})

    required_pipeline_ids = required_ids_unique | required_dup_ids
    covered = sum(1 for it in items if it['id'] in required_pipeline_ids
                  and it['status'] == 'PASS' and it['reason'] == 'covered')
    excluded = sum(1 for it in items if it['id'] in required_pipeline_ids
                   and it['status'] == 'PASS' and it['reason'] == 'excluded')
    failed = sum(1 for it in items if it['id'] in required_pipeline_ids and it['status'] == 'FAIL')

    by_prefix = {}
    for item_id in required_pipeline_ids:
        it = next(x for x in items if x['id'] == item_id)
        bucket = by_prefix.setdefault(_prefix(item_id),
                                       {'required': 0, 'covered': 0, 'excluded': 0, 'failed': 0})
        bucket['required'] += 1
        if it['status'] == 'PASS' and it['reason'] == 'covered':
            bucket['covered'] += 1
        elif it['status'] == 'PASS' and it['reason'] == 'excluded':
            bucket['excluded'] += 1
        elif it['status'] == 'FAIL':
            bucket['failed'] += 1

    fail_items = sum(1 for it in items if it['status'] == 'FAIL')
    notes = note_core_stats(items)

    return {
        'notes': notes,
        'required': len(required_pipeline_ids),
        'covered': covered,
        'excluded': excluded,
        'failed': failed,
        'fail_items': fail_items,
        'by_prefix': by_prefix,
        'items': items,
    }


# ==================== CLI ====================

def _print_report(report):
    for it in report['items']:
        print(f"  [{it['status']}] {it['id']} {it['reason']}")
    print(f"  요약: 필수 {report['required']} / 반영 {report['covered']} / "
          f"제외 {report['excluded']} / 실패 {report['failed']}")
    n = report.get('notes') or {}
    if n.get('report_notes'):
        mark = 'ok' if n['in_core'] * 2 >= n['report_notes'] else 'WARN'
        print(f"  [{mark}] 정독 리포트 노트 {n['report_notes']}편 중 산업·기업·투자포인트(s02·s03·s04) 착지 {n['in_core']}편"
              + (f" -- 밖: {', '.join(n['outside_core'])}" if n['outside_core'] else ''))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('stock')
    ap.add_argument('--analysis', default=None)
    ap.add_argument('--map', default=None, help='반영 지도 경로 (기본 ta/coverage_map.json)')
    a = ap.parse_args(argv)

    brief_paths = sorted(glob.glob(os.path.join(tc.ta_dir(a.stock), 'brief_*.md')))
    occurrences = parse_briefs(brief_paths)
    occurrences.update(parse_notes(os.path.join(tc.ta_dir(a.stock), 'notes')))  # v5.26-c 정독 노트도 필수 ID

    coverage_map_path = a.map or os.path.join(tc.ta_dir(a.stock), 'coverage_map.json')
    coverage_map = tc.read_json(coverage_map_path, default={}) or {}

    analysis_path = a.analysis or os.path.join(tc.PROJECT_ROOT, 'scripts',
                                                f'analysis_{a.stock}_ta.json')
    analysis = tc.read_json(analysis_path, default={}) or {}
    sections = analysis.get('sections', {}) or {}

    report = evaluate(occurrences, coverage_map, sections)
    n_notes = sum(1 for k in occurrences if k.startswith('note:'))
    print(f'[ta_coverage_check] {a.stock} -- brief {len(brief_paths)}개, 정독 노트 {n_notes}편, ID {len(occurrences)}개')
    _print_report(report)

    out_path = os.path.join(tc.ta_dir(a.stock), 'coverage_report.json')
    tc.write_json(out_path, report)
    print(f'  -> {out_path}')

    status = 'ok' if report['fail_items'] == 0 else 'failed'
    tc.manifest_update(a.stock, 'coverage_check', status, required=report['required'],
                       failed=report['failed'], fail_items=report['fail_items'])
    return 0 if report['fail_items'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
