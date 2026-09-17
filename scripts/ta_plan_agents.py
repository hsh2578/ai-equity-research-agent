"""ta_plan_agents.py -- /research-ta 분석가 서브에이전트 호출 계획 (Task 9).

분석가 인원을 고정하지 않는다. 역할별 입력 자료 묶음이 한 에이전트 맥락
(max-chars)에 온전히 들어가는지로 호출 수를 정한다:
  - 자료가 작으면 역할당 1호출.
  - 넘치면 파일 단위로 순서대로 채워 여러 호출로 나눈다.
  - 파일 하나가 혼자 넘치면 그 파일만 줄 경계에서 잘라 여러 호출에 나눠 담는다.
  - sellside/industry 는 둘 다 자료가 적으면(합계 < merge-under) 한 호출로 합친다.

CLI: python scripts/ta_plan_agents.py {종목명} [--max-chars 120000] [--merge-under 40000]
출력: data/{종목}/ta/agent_plan.json
"""
import argparse
import io
import os
import sys

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta_common as tc  # noqa: E402

DEFAULT_MAX_CHARS = 120000
DEFAULT_MERGE_UNDER = 40000

# 역할별 고정 입력 목록 (data/{종목}/ 기준 상대경로). 없는 파일은 그냥 빠진다.
ROLE_FILES = {
    'news': [
        'ta/news_relevant.json', 'ta/event_study.json', 'ta/calendar.json', '_dart_filings.json',
    ],
    'fundamentals': [
        'ta/dart/business.txt', 'ta/dart/risk_mgmt.txt', 'ta/dart/notes_selected.txt',
        'ta/dart/mdna.txt', 'ta/dart_diff_highlights.json', '_dart_quarterly.json', '_fnguide.json',
        'financial_summary.json', '_drivers.md', '_evidence_scan.json',
    ],
    'macro': [
        'ta/dart/risk_mgmt.txt', 'ta/macro.json',
    ],
    'market': [
        'ta/market_data.json', 'ta/board.json', 'ta/flow.json',
        '_price_cycles.json', '_volatility_beta.json', 'ta/telegram.json',
    ],
}

# manifest 를 따라가는 역할: (manifest 상대경로, manifest 외 추가 파일)
REPORT_ROLES = {
    'sellside': ('ta/reports/company/_manifest.json', '_wisereport_consensus.json'),
    'industry': ('ta/reports/industry/_manifest.json', '_peer_snapshot.json'),
}

ROLE_ORDER = ['news', 'fundamentals', 'sellside', 'industry', 'macro', 'market']


def _exists(stock, rel):
    return os.path.exists(os.path.join(tc.data_dir(stock), rel))


def _fixed_inputs(stock, files):
    return [f for f in files if _exists(stock, f)]


def _report_inputs(stock, manifest_rel, extra_rel):
    """manifest_rel 을 읽어 reports[].txt 를 따라간다.
    반환: (존재하는 파일 순서대로, manifest 엔트리는 있는데 파일이 실제로 없는 것들).
    후자를 조용히 빼먹지 않는다 -- 수집기 경로 불일치를 숨기면 분석가가 그 리포트를
    아예 못 본 채로 넘어간다."""
    inputs = []
    missing = []
    if _exists(stock, manifest_rel):
        inputs.append(manifest_rel)
        manifest = tc.read_json(os.path.join(tc.data_dir(stock), manifest_rel), {}) or {}
        for rep in manifest.get('reports', []) or []:
            txt = rep.get('txt')
            if not txt:
                continue
            if _exists(stock, txt):
                inputs.append(txt)
            else:
                missing.append({'file': txt, 'reason': 'manifest 에 있으나 파일 없음'})
    if extra_rel and _exists(stock, extra_rel):
        inputs.append(extra_rel)
    return inputs, missing


def _read_text(stock, rel):
    with open(os.path.join(tc.data_dir(stock), rel), encoding='utf-8') as f:
        return f.read()


def _split_lines_by_size(lines, max_chars):
    """lines: splitlines(keepends=True) 결과. (start, end, chars) 1-indexed 포함구간 목록.
    한 줄이 max_chars 보다 커도 무한루프 없이 그 줄 하나로 청크를 만든다."""
    chunks = []
    n = len(lines)
    i = 0
    while i < n:
        start = i
        chars = 0
        while i < n and (chars + len(lines[i]) <= max_chars or i == start):
            chars += len(lines[i])
            i += 1
        chunks.append((start + 1, i, chars))
    return chunks


TINY_REMAINDER_UNDER = 10000    # 이보다 작은 마지막 조각은 앞 호출에 얹는다
TINY_REMAINDER_OVER_ALLOW = 10000  # 그렇게 얹었을 때 max_chars 를 이만큼까지는 넘겨도 된다


def _pack_files(stock, files, max_chars):
    """존재하는 파일 목록(순서대로)을 max_chars 이하 그룹으로 채운다.
    반환: (groups, tiny_merged). groups 는 [(items, chars), ...]. items 원소는
      {'file':rel,'chars':n} 또는 {'file':rel,'lines':[s,e],'chars':n}.
    마지막 조각이 TINY_REMAINDER_UNDER 자 미만이면(호출 하나가 그것만 담는 낭비를 막기
    위해) 직전 호출에 붙인다 -- 단, 합계가 max_chars + TINY_REMAINDER_OVER_ALLOW 를
    넘지 않을 때만."""
    groups = []
    current, current_chars = [], 0

    def _flush():
        nonlocal current, current_chars
        if current:
            groups.append((current, current_chars))
            current, current_chars = [], 0

    for rel in files:
        text = _read_text(stock, rel)
        total = len(text)
        if total <= max_chars:
            if current and current_chars + total > max_chars:
                _flush()
            current.append({'file': rel, 'chars': total})
            current_chars += total
        else:
            _flush()
            lines = text.splitlines(keepends=True)
            for start, end, chars in _split_lines_by_size(lines, max_chars):
                if current and current_chars + chars > max_chars:
                    _flush()
                current.append({'file': rel, 'lines': [start, end], 'chars': chars})
                current_chars += chars
    _flush()

    tiny_merged = False
    if len(groups) >= 2:
        last_items, last_chars = groups[-1]
        if last_chars < TINY_REMAINDER_UNDER:
            prev_items, prev_chars = groups[-2]
            if prev_chars + last_chars <= max_chars + TINY_REMAINDER_OVER_ALLOW:
                groups[-2:] = [(prev_items + last_items, prev_chars + last_chars)]
                tiny_merged = True
    return groups, tiny_merged


def _finalize_calls(role, groups, merge_reason=None, missing_inputs=None, tiny_merged=False):
    n = len(groups)
    calls = []
    for i, (items, chars) in enumerate(groups, start=1):
        is_last = (i == n)
        if is_last and tiny_merged:
            call_id = role if n == 1 else f'{role}#{i}'
            reason = '잔여 소량 병합'
        elif n == 1:
            call_id = role
            reason = merge_reason or '단일'
        else:
            call_id = f'{role}#{i}'
            reason = f'{merge_reason}, 분할 {i}/{n}' if merge_reason else f'용량 초과로 분할 {i}/{n}'
        call = {'call_id': call_id, 'role': role, 'inputs': items, 'chars': chars, 'reason': reason}
        if missing_inputs:
            call['missing_inputs'] = missing_inputs
        calls.append(call)
    return calls


def _sum_chars(stock, files):
    return sum(len(_read_text(stock, f)) for f in files)


def build_plan(stock, max_chars=DEFAULT_MAX_CHARS, merge_under=DEFAULT_MERGE_UNDER):
    role_files = {r: _fixed_inputs(stock, ROLE_FILES[r]) for r in ROLE_FILES}
    role_missing = {}
    for role, (manifest_rel, extra_rel) in REPORT_ROLES.items():
        role_files[role], role_missing[role] = _report_inputs(stock, manifest_rel, extra_rel)

    special_skip_reasons = {}
    if not _exists(stock, 'ta/news_relevant.json') and _exists(stock, 'ta/news.json'):
        # ta_collect_news 는 news.json(원본) 다음 news_relevant.json(관련 항목만)을 만든다.
        # 후자가 없으면 필터링이 아직 안 끝난 것이므로 원본으로 조용히 대체하지 않는다.
        role_files['news'] = []
        special_skip_reasons['news'] = 'news_relevant.json 없음 (ta_collect_news 재실행 필요)'

    if not _exists(stock, 'ta/dart_diff_highlights.json') and _exists(stock, 'ta/dart_diff.json'):
        # ta_dart_diff 는 전문(dart_diff.json) 다음 하이라이트본(dart_diff_highlights.json)을
        # 만든다. 하이라이트본이 없으면 전문으로 조용히 대체하지 않고(전문은 grep 용으로만
        # 남긴다) 그 입력만 빼고 경고를 남긴다 -- fundamentals 역할 자체는 계속 돈다.
        role_missing.setdefault('fundamentals', []).append({
            'file': 'ta/dart_diff_highlights.json',
            'reason': 'dart_diff_highlights.json 없음 (ta_dart_diff 재실행 필요)',
        })

    warnings = []
    for role, missing in role_missing.items():
        for m in missing:
            warnings.append({'role': role, 'file': m['file'], 'reason': m['reason']})

    merged = False
    merged_groups, merged_tiny = [], False
    merged_missing = []
    if role_files['sellside'] and role_files['industry']:
        combined = role_files['sellside'] + role_files['industry']
        if _sum_chars(stock, combined) < merge_under:
            merged = True
            merged_groups, merged_tiny = _pack_files(stock, combined, max_chars)
            merged_missing = role_missing['sellside'] + role_missing['industry']

    calls, skipped = [], []
    for role in ROLE_ORDER:
        if role == 'industry' and merged:
            continue
        if role == 'sellside' and merged:
            calls.extend(_finalize_calls('sellside+industry', merged_groups,
                                          merge_reason='자료 적음으로 병합', missing_inputs=merged_missing,
                                          tiny_merged=merged_tiny))
            continue
        files = role_files[role]
        if not files:
            skipped.append({'role': role, 'reason': special_skip_reasons.get(role, '입력 파일 없음')})
            continue
        groups, tiny_merged = _pack_files(stock, files, max_chars)
        calls.extend(_finalize_calls(role, groups, missing_inputs=role_missing.get(role),
                                      tiny_merged=tiny_merged))

    total_chars = sum(c['chars'] for c in calls)
    return {
        'stock': stock,
        'params': {'max_chars': max_chars, 'merge_under': merge_under},
        'calls': calls,
        'skipped': skipped,
        'warnings': warnings,
        'totals': {'calls': len(calls), 'chars': total_chars},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stock')
    ap.add_argument('--max-chars', type=int, default=DEFAULT_MAX_CHARS)
    ap.add_argument('--merge-under', type=int, default=DEFAULT_MERGE_UNDER)
    args = ap.parse_args()

    try:
        plan = build_plan(args.stock, args.max_chars, args.merge_under)
        out_path = os.path.join(tc.ta_dir(args.stock), 'agent_plan.json')
        tc.write_json(out_path, plan)
        tc.manifest_update(args.stock, 'agent_plan', 'ok',
                            calls=plan['totals']['calls'], chars=plan['totals']['chars'],
                            skipped=len(plan['skipped']), warnings=len(plan['warnings']))
        for w in plan['warnings']:
            print(f"[WARN] agent_plan {w['role']}: {w['file']} - {w['reason']}")
        print(f"agent_plan: 호출 {plan['totals']['calls']}개, 총 {plan['totals']['chars']}자, "
              f"skipped {len(plan['skipped'])}개, warnings {len(plan['warnings'])}개 -> {out_path}")
        return 0
    except Exception as e:
        tc.manifest_update(args.stock, 'agent_plan', 'failed', reason=f'{type(e).__name__}: {e}')
        print(f'[실패] agent_plan: {type(e).__name__}: {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
