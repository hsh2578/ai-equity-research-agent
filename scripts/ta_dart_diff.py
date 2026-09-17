# -*- coding: utf-8 -*-
"""ta_dart_diff.py -- DART 정기보고서 전문을 장 단위로 쪼개고 직전 보고서 대비
바뀐 문단만 뽑는다 (Task 7, /research-ta).

한 편이 최대 98만 바이트라 에이전트 하나가 끝까지 못 읽는다. 그래서
- `data/{종목}/ta/dart/*.txt` 로 장/소장 단위 분할 (latest 만, 원본 줄번호 유지)
- `data/{종목}/ta/dart_diff.json` 로 latest vs previous 문단 단위 변경점

사용법: python scripts/ta_dart_diff.py {종목명}
"""
import argparse
import difflib
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import ta_common as tc                                          # noqa: E402

# ==================== 입력 파일명 파싱 ====================

FILE_RE = re.compile(
    r'^_dart_FULL_(?P<type>[^(]+)\((?P<period>\d{4}\.\d{2})\)_(?P<rcept>\d+)\.txt$'
)


def parse_filename(filename):
    """_dart_FULL_{보고서종류}({YYYY.MM})_{rcept_no}.txt -> dict. 불일치면 None."""
    m = FILE_RE.match(filename)
    if not m:
        return None
    return {'type': m.group('type'), 'period': m.group('period'), 'rcept': m.group('rcept')}


def find_reports(dir_path):
    """dir_path 안의 _dart_FULL_*.txt 를 기간(YYYY.MM) 오름차순으로 돌려준다."""
    if not os.path.isdir(dir_path):
        return []
    out = []
    for fn in os.listdir(dir_path):
        info = parse_filename(fn)
        if not info:
            continue
        out.append({'path': os.path.join(dir_path, fn), 'filename': fn,
                     'type': info['type'], 'period': info['period'], 'rcept': info['rcept']})
    out.sort(key=lambda r: r['period'])
    return out


# ==================== 장/소장 경계 ====================

# 길이 긴 로마숫자부터 -- 정규식 백트래킹 없이 바로 맞는 대안을 고른다
_MAJOR_ROMANS = ['VIII', 'III', 'VII', 'XII', 'II', 'IV', 'VI', 'IX', 'XI', 'I', 'V', 'X']
MAJOR_RE = re.compile(r'^\s*(' + '|'.join(_MAJOR_ROMANS) + r')\.\s+\S')
MINOR_RE = re.compile(r'^\s*\d{1,2}\.\s+\S')

NOTES_KEYWORDS = ('영업부문', '특수관계자', '우발', '약정', '위험관리', '차입금', '사채', '후속사건')


def _roman_of(title):
    m = MAJOR_RE.match(title)
    return m.group(1) if m else None


def get_chapters(lines):
    """대장(로마숫자) 경계 목록. 같은 제목이 두 번 나오면 뒤(본문) 것만 쓴다
    (목차 페이지에서 잘못 자르는 것 방지)."""
    hits = []
    for i, raw in enumerate(lines, 1):
        line = raw.rstrip('\n').rstrip('\r')
        if MAJOR_RE.match(line):
            hits.append((i, line.strip()))
    last_line_for_title = {}
    for ln, title in hits:
        last_line_for_title[title] = ln  # 나중 것이 이긴다
    kept = sorted(last_line_for_title.items(), key=lambda kv: kv[1])  # [(title, line), ...]
    n = len(lines)
    chapters = []
    for idx, (title, ln) in enumerate(kept):
        end = (kept[idx + 1][1] - 1) if idx + 1 < len(kept) else n
        chapters.append({'title': title, 'start': ln, 'end': end})
    return chapters


_MAX_HEADING_CHARS = 60
_MAX_GAP = 3
_RESET_NUMS = (1, 2, 3)  # 중첩 소장(주석이 1 부터 다시 시작하는 등)의 새 시작을 허용

# 표 각주/참조 문장이 "NN. ..." 로 시작해 소장처럼 보이는 것을 문장 끝맺음으로 거른다
# (에프에스티 실측: "34. 우발상황과 약정사항 내용을 참조하시기 바랍니다.(4) ...")
_SENTENCE_ENDINGS = ('니다.', '니다', '시기 바랍니다', '참조', '참고')
_SENTENCE_SUBSTRINGS = ('참조하시기', '바랍니다', '기재하였습니다')

# III 재무에 관한 사항의 최상위(장 수준) 소장 이름 -- "4. 재무제표"/"5. 재무제표 주석"
# 처럼 round 2 규칙(간격<=3, 리셋 1~3)으로는 소장으로 인정되지 않는 항목도 있다.
# 그래도 이 이름이 나오면 직전에 인정된 소장은 거기서 끝나야 한다(안 그러면 뒤 문서
# 전체가 그 소장 하나로 흡수돼 range 가 통째로 길어진다 -- round 2 실측에서 발견).
_STATEMENT_HEADER_KEYWORDS = ('요약재무정보', '연결재무제표', '재무제표 주석', '재무제표',
                              '배당에 관한', '증권의 발행', '기타 재무에 관한')


def _looks_like_sentence(heading):
    h = heading.strip()
    if any(h.endswith(e) for e in _SENTENCE_ENDINGS):
        return True
    if any(s in h for s in _SENTENCE_SUBSTRINGS):
        return True
    return False


def _is_statement_header(heading):
    return any(k in heading for k in _STATEMENT_HEADER_KEYWORDS)


def get_subsections(lines, start, end):
    """[start, end] (1-based, 포함) 범위 안의 소장(숫자) 경계 목록.

    본문 문장이 우연히 `NN. ...` 로 시작해도(표 각주 등) 소장으로 오인하지
    않도록 세 조건을 모두 만족해야 진짜 소장으로 인정한다 (fix round 2):
      (a) 번호가 직전으로 인정된 소장 번호보다 크고 그 차이가 3 이하 이거나,
          1~3 (중첩 소장 -- 예: III 주석이 1 부터 다시 시작하는 경우 -- 을 허용).
          직전 인정 번호+1 만 허용했던 round 1 은 "24 -> 26" 같은 실제 스킵까지
          막아버려서 진짜 소장(우발상황과 약정사항/특수관계자 거래)이 함께 사라졌다.
      (b) 번호 뒤 제목 텍스트가 60자 이하
      (c) 제목이 문장이 아니다 (`_looks_like_sentence`) -- "34. 우발상황과 약정사항
          내용을 참조하시기 바랍니다..." 는 (b) 없이도 이 조건 하나로 걸러진다
    하나라도 어기면 그 줄은 소장 경계가 아니라 본문으로 남는다.

    추가로 (fix round 3): "4. 재무제표"처럼 자기 자신은 위 세 조건에 걸려 소장으로
    인정되지 않는 장 수준 표제도, 직전에 인정된 소장의 끝은 거기서 끊는다
    (`_is_statement_header`). 안 그러면 그 표제 뒤 내용이 전부 직전 소장에 흡수돼
    range 가 실제보다 훨씬 길어진다."""
    candidates = []
    last = min(end, len(lines))
    for i in range(start, last + 1):
        line = lines[i - 1].rstrip('\n').rstrip('\r')
        if not MINOR_RE.match(line):
            continue
        title = line.strip()
        num, heading = _sub_num(title)
        if num is None:
            continue
        candidates.append((i, title, num, heading))

    hits = []
    prev_num = None
    for i, title, num, heading in candidates:
        if len(heading) > _MAX_HEADING_CHARS:
            continue
        if _looks_like_sentence(heading):
            continue
        is_reset = num in _RESET_NUMS
        is_growth = prev_num is not None and num > prev_num and (num - prev_num) <= _MAX_GAP
        if is_reset or is_growth:
            hits.append((i, title))
            prev_num = num
        # else: 순서를 벗어난 번호(너무 크게 건너뛰거나 작아짐)는 본문으로 남긴다

    # 소장으로는 인정되지 않아도 "여기서 끊어야 하는" 지점 -- 장 수준 표제 + (방어적으로)
    # 로마숫자 대장. 대장은 이미 [start,end] 범위 밖이라 보통 안 나오지만 명시적으로 체크한다.
    stop_lines = sorted(
        {i for i in range(start, last + 1) if MAJOR_RE.match(lines[i - 1].rstrip('\n').rstrip('\r'))}
        | {i for i, title, num, heading in candidates if _is_statement_header(heading)}
    )

    def _next_stop_after(line_no):
        for sl in stop_lines:
            if sl > line_no:
                return sl
        return None

    subs = []
    for idx, (ln, title) in enumerate(hits):
        sub_end = (hits[idx + 1][0] - 1) if idx + 1 < len(hits) else end
        stop = _next_stop_after(ln)
        if stop is not None and stop - 1 < sub_end:
            sub_end = stop - 1
        subs.append({'title': title, 'start': ln, 'end': sub_end})
    return subs


def slice_lines(lines, start, end):
    """[start, end] 범위를 (원본줄번호, 텍스트) 쌍 목록으로."""
    last = min(end, len(lines))
    return [(i, lines[i - 1].rstrip('\n').rstrip('\r')) for i in range(start, last + 1)]


def format_numbered_file(source_filename, content_lines):
    """content_lines: [(lineno, text), ...] -> (본문 문자열, start, end).
    첫 줄은 `# source: {파일명} lines {시작}-{끝}`, 이후 각 줄 `{원본줄번호}\t{텍스트}`."""
    start = content_lines[0][0]
    end = content_lines[-1][0]
    header = f'# source: {source_filename} lines {start}-{end}\n'
    body = '\n'.join(f'{ln}\t{txt}' for ln, txt in content_lines)
    return header + body + '\n', start, end


# ==================== 문단 분리 / 정규화 ====================

def _normalize_ws(s):
    return re.sub(r'\s+', ' ', s).strip()


# fix round 3: 숫자/기간 라벨 정규화 -- "104,756" vs "97,123", "제40기" vs "제39기" 처럼
# 표 값만 바뀐 문단을 같은 모양으로 만들어 문단 쌍 전체에서 numbers_only 여부를 판단한다.
# 기간 라벨을 먼저 '@' 로 치환해야 "제40기" 안의 "40" 이 숫자 패턴에 따로 안 걸린다.
_PERIOD_RE = re.compile(
    r'제\s*\d+\s*기'      # 제40기
    r'|\d{1,2}\s*분기'     # 4분기
    r'|\d{4}\s*년'         # 2026년
    r'|\d{1,2}\s*월'       # 06월
    r'|[당전](?:분기|반기|기)말?'   # 당분기말/당반기/전기말 -- '당@말' 로 남지 않게 통째로
    r'|반기|분기|당기|전기'
)
# 숫자(콤마/소수점/퍼센트/괄호/부호 포함)를 통째로 '#' 하나로 -- 자릿수가 달라도 같은 모양
_NUM_TOKEN_RE = re.compile(r'\(?[+-]?\d[\d,\.]*%?\)?')


def _digit_period_norm(text):
    t = _PERIOD_RE.sub('@', text)
    t = _NUM_TOKEN_RE.sub('#', t)
    return re.sub(r'\s+', ' ', t).strip()


# fix round 3: kind=table -- 표 행(품목/수치 나열)은 prose 로 세지 않는다
_UNIT_TOKENS = {'원', '억원', '백만원', '천원', '만원', '조원', '%', '주', '좌', '건', '명',
                '개', '천주', '백만주', '배', '포인트', 'pt', 'bp'}
_TOKEN_NUM_RE = re.compile(r'^[\d,\.%()+\-]+$')


def _is_numeric_token(tok):
    if tok == '-':
        return True
    if tok in _UNIT_TOKENS:
        return True
    return bool(_TOKEN_NUM_RE.match(tok)) and any(c.isdigit() for c in tok)


_IMAGE_RE = re.compile(r'^(.*?)\.(?:jpe?g|png|gif)(?:\s+(.*))?$', re.IGNORECASE)


def _is_image_caption(text):
    """'파일명.jpg' 로 끝나거나, DART 그림 캡션 관행인 '파일명.jpg 파일명' 뿐인 문단."""
    m = _IMAGE_RE.match(_normalize_ws(text))
    return bool(m) and (m.group(2) is None or m.group(2) == m.group(1))


def classify_kind(text):
    """'table' (표 행 -- 수치/단위 나열, 또는 숫자·기간 라벨을 지우면 12자 미만만 남음)
    또는 'text' (산문). numbers_only 매칭에 실패한 문단에만 적용한다."""
    tokens = text.split()
    if not tokens:
        return 'text'
    if _is_image_caption(text):  # 그림 캡션(파일명) -- 산문이 아니다 (round 5)
        return 'table'
    numeric_ratio = sum(1 for t in tokens if _is_numeric_token(t)) / len(tokens)
    if numeric_ratio >= 0.5:
        return 'table'
    normed = _digit_period_norm(text)
    if normed != text:  # 숫자/기간 라벨을 실제로 지웠을 때만 이 규칙을 적용한다
        leftover = re.sub(r'[#@\s]', '', normed)
        if len(leftover) < 12:
            return 'table'
    return 'text'


def split_paragraphs(content_lines):
    """content_lines: [(lineno, text), ...] -> 빈 줄로 구분된 문단 목록.
    각 문단: {'line': 시작 원본줄번호, 'norm': 공백정규화 텍스트, 'text': 원문 앞 200자}."""
    paras = []
    buf = []
    buf_start = None
    for lineno, text in content_lines:
        if text.strip() == '':
            if buf:
                joined = ' '.join(buf)
                paras.append({'line': buf_start, 'norm': _normalize_ws(joined), 'text': joined[:200]})
                buf = []
                buf_start = None
        else:
            if buf_start is None:
                buf_start = lineno
            buf.append(text.strip())
    if buf:
        joined = ' '.join(buf)
        paras.append({'line': buf_start, 'norm': _normalize_ws(joined), 'text': joined[:200]})
    return paras


def diff_paragraphs(section_label, prev_paras, latest_paras):
    """문단 목록 두 개를 비교해 변경점 목록을 낸다 (fix round 3 재작성).

    1. SequenceMatcher 로 진짜 동일(equal) 문단을 걸러내고, 나머지는 removed/added
       풀로 모은다 (opcode 가 delete/insert/replace 어느 것이었는지는 더 안 따진다).
    2. numbers_only 여부는 **쌍 전체에서** 결정한다 -- removed 풀의 문단마다 숫자/기간
       라벨을 정규화(`_digit_period_norm`)한 모양이 같은 added 풀 문단을 찾으면, 그
       둘을 text 2건이 아니라 kind=numbers_only 레코드 1건으로 합친다(change=changed).
    3. 매칭되지 않고 남은 문단만 각각 `classify_kind` 로 text/table 을 나눠
       added/removed 로 기록한다."""
    a = [p['norm'] for p in prev_paras]
    b = [p['norm'] for p in latest_paras]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)

    removed_pool = []
    added_pool = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        removed_pool.extend(prev_paras[i1:i2])
        added_pool.extend(latest_paras[j1:j2])

    changes = []
    remaining_added = list(added_pool)
    unmatched_removed = []
    for r in removed_pool:
        r_key = _digit_period_norm(r['norm'])
        match_idx = next(
            (idx for idx, ad in enumerate(remaining_added) if _digit_period_norm(ad['norm']) == r_key),
            None)
        if match_idx is not None:
            ad = remaining_added.pop(match_idx)
            changes.append({'section': section_label, 'kind': 'numbers_only', 'change': 'changed',
                             'text': ad['text'], 'line': ad['line'],
                             'prev_text': r['text'], 'prev_line': r['line']})
        else:
            unmatched_removed.append(r)

    # fix round 4: 산문끼리 비슷하면(ratio >= 0.6) modified 1건으로 짝짓는다 -- greedy best-first, 1:1
    rem_text = [r for r in unmatched_removed if classify_kind(r['text']) == 'text']
    add_text = [ad for ad in remaining_added if classify_kind(ad['text']) == 'text']
    cands = []
    for ri, r in enumerate(rem_text):
        rk = _digit_period_norm(r['norm'])
        for ai, ad in enumerate(add_text):
            sm2 = difflib.SequenceMatcher(None, rk, _digit_period_norm(ad['norm']), autojunk=False)
            if sm2.real_quick_ratio() < _PAIR_MIN or sm2.quick_ratio() < _PAIR_MIN:
                continue
            ratio = sm2.ratio()
            if ratio >= _PAIR_MIN:
                cands.append((ratio, ri, ai))
    # ponytail: 섹션당 O(removed x added) ratio -- 에프에스티 전체 0.5s, 섹션 문단 수천 건이면 느려짐 -> 그때 길이 버킷으로 후보를 자른다
    used_r, used_a, paired = set(), set(), set()
    for ratio, ri, ai in sorted(cands, key=lambda c: -c[0]):
        if ri in used_r or ai in used_a:
            continue
        used_r.add(ri)
        used_a.add(ai)
        r, ad = rem_text[ri], add_text[ai]
        paired.add(id(r))
        paired.add(id(ad))
        changes.append({'section': section_label, 'kind': 'text', 'change': 'modified',
                         'before': r['text'], 'after': ad['text'],
                         'line_before': r['line'], 'line': ad['line'],
                         'similarity': round(ratio, 3)})

    for r in unmatched_removed:
        if id(r) not in paired:
            changes.append({'section': section_label, 'kind': classify_kind(r['text']),
                             'change': 'removed', 'text': r['text'], 'line': r['line']})
    for ad in remaining_added:
        if id(ad) not in paired:
            changes.append({'section': section_label, 'kind': classify_kind(ad['text']),
                             'change': 'added', 'text': ad['text'], 'line': ad['line']})

    return changes


_PAIR_MIN = 0.55


# ==================== 문서 구조화 ====================

def _sub_num(title):
    m = re.match(r'^(\d{1,2})\.\s*(.*)$', title)
    if not m:
        return None, title
    return int(m.group(1)), m.group(2).strip()


def _strip_roman(title):
    m = MAJOR_RE.match(title)
    if not m:
        return title
    return title[len(m.group(1)) + 1:].strip()


def build_ta_sections(lines):
    """report 전문(lines) -> ta/dart/*.txt 후보 + 비교용 구조.
    반환 dict 키: business/risk_mgmt(옵션)/notes(list)/IV(옵션)/VII(옵션)/II_subs(list)."""
    chapters = get_chapters(lines)
    by_roman = {}
    for c in chapters:
        r = _roman_of(c['title'])
        if r and r not in by_roman:  # dedup 이 이미 끝났으니 첫 매칭이 유일함
            by_roman[r] = c

    result = {'II_subs': [], 'notes': [], 'IV': None, 'VII': None}

    ii = by_roman.get('II')
    if ii:
        result['business'] = {'title': ii['title'], 'start': ii['start'], 'end': ii['end'],
                               'content': slice_lines(lines, ii['start'], ii['end'])}
        subs = get_subsections(lines, ii['start'], ii['end'])
        result['II_subs'] = [
            {'title': s['title'], 'start': s['start'], 'end': s['end'],
             'paras': split_paragraphs(slice_lines(lines, s['start'], s['end']))}
            for s in subs
        ]
        risk = next((s for s in subs if '위험관리' in s['title']), None)
        if risk:
            result['risk_mgmt'] = {'title': risk['title'], 'start': risk['start'], 'end': risk['end'],
                                    'content': slice_lines(lines, risk['start'], risk['end'])}

    iii = by_roman.get('III')
    if iii:
        subs3 = get_subsections(lines, iii['start'], iii['end'])
        for s in subs3:
            if any(k in s['title'] for k in NOTES_KEYWORDS):
                content = slice_lines(lines, s['start'], s['end'])
                result['notes'].append({'title': s['title'], 'start': s['start'], 'end': s['end'],
                                         'content': content, 'paras': split_paragraphs(content)})

    iv = by_roman.get('IV')
    if iv:
        content = slice_lines(lines, iv['start'], iv['end'])
        result['IV'] = {'title': iv['title'], 'start': iv['start'], 'end': iv['end'],
                         'content': content, 'paras': split_paragraphs(content)}

    vii = by_roman.get('VII')
    if vii:
        content = slice_lines(lines, vii['start'], vii['end'])
        result['VII'] = {'title': vii['title'], 'start': vii['start'], 'end': vii['end'],
                          'content': content, 'paras': split_paragraphs(content)}

    return result


def write_sections(out_dir, source_filename, struct):
    """struct(latest) -> ta/dart/*.txt 로 저장. 없는 섹션은 생략. files 메타 목록 반환."""
    os.makedirs(out_dir, exist_ok=True)
    files_meta = []

    def _write(name, content_lines):
        if not content_lines:
            return
        body, start, end = format_numbered_file(source_filename, content_lines)
        with open(os.path.join(out_dir, name), 'w', encoding='utf-8') as f:
            f.write(body)
        files_meta.append({'name': name, 'chars': len(body), 'source_lines': [start, end]})

    if 'business' in struct:
        _write('business.txt', struct['business']['content'])
    if 'risk_mgmt' in struct:
        _write('risk_mgmt.txt', struct['risk_mgmt']['content'])
    if struct.get('notes'):
        merged = []
        for n in struct['notes']:
            merged.extend(n['content'])
        _write('notes_selected.txt', merged)
    if struct.get('IV'):
        _write('mdna.txt', struct['IV']['content'])
    if struct.get('VII'):
        _write('shareholders.txt', struct['VII']['content'])

    return files_meta


def compute_changes(prev, latest):
    """비교 단위: II 소장 1~7 / IV / VII / notes_selected 의 같은 제목 소장."""
    changes = []

    prev_by_num = {n: s for s in prev.get('II_subs', [])
                   for n in [_sub_num(s['title'])[0]] if n is not None}
    latest_by_num = {n: s for s in latest.get('II_subs', [])
                      for n in [_sub_num(s['title'])[0]] if n is not None}
    for num in sorted(set(prev_by_num) & set(latest_by_num)):
        l = latest_by_num[num]
        _, name = _sub_num(l['title'])
        label = f'II-{num} {name}'
        changes.extend(diff_paragraphs(label, prev_by_num[num]['paras'], l['paras']))

    if prev.get('IV') and latest.get('IV'):
        label = f"IV {_strip_roman(latest['IV']['title'])}"
        changes.extend(diff_paragraphs(label, prev['IV']['paras'], latest['IV']['paras']))

    if prev.get('VII') and latest.get('VII'):
        label = f"VII {_strip_roman(latest['VII']['title'])}"
        changes.extend(diff_paragraphs(label, prev['VII']['paras'], latest['VII']['paras']))

    prev_notes = {n['title']: n for n in prev.get('notes', [])}
    latest_notes = {n['title']: n for n in latest.get('notes', [])}
    for title in sorted(set(prev_notes) & set(latest_notes)):
        label = f'III 주석 {title}'
        changes.extend(diff_paragraphs(label, prev_notes[title]['paras'], latest_notes[title]['paras']))

    return changes


def _build_summary(changes):
    """kind/section 별 집계 (fix round 3) -- text_added/text_removed/numbers_only 는
    하위호환으로 유지하고, kind·section 교차 집계와 top_text_sections 를 더한다."""
    by_kind = {}
    by_section = {}
    for c in changes:
        kind, chg, sec = c['kind'], c['change'], c['section']
        by_kind.setdefault(kind, {'added': 0, 'removed': 0, 'changed': 0, 'modified': 0})
        by_kind[kind][chg] = by_kind[kind].get(chg, 0) + 1
        by_section.setdefault(sec, {'text': 0, 'table': 0, 'numbers_only': 0})
        by_section[sec][kind] = by_section[sec].get(kind, 0) + 1

    text_by_section = {sec: v.get('text', 0) for sec, v in by_section.items() if v.get('text', 0) > 0}
    top_text_sections = sorted(text_by_section, key=lambda s: -text_by_section[s])[:10]

    return {
        'text_added': by_kind.get('text', {}).get('added', 0),
        'text_removed': by_kind.get('text', {}).get('removed', 0),
        'text_modified': by_kind.get('text', {}).get('modified', 0),
        'table_added': by_kind.get('table', {}).get('added', 0),
        'table_removed': by_kind.get('table', {}).get('removed', 0),
        'numbers_only': by_kind.get('numbers_only', {}).get('changed', 0),
        'by_kind': by_kind,
        'by_section': by_section,
        'top_text_sections': top_text_sections,
    }


_HL_NOTE_KEYS = ('우발', '특수관계자', '사채', '차입금')
_HL_MAX = 30


def _chapter_key(section):
    if section.startswith('II-'):
        return 'II'
    if section.startswith('III'):
        return 'notes'
    return section.split(' ', 1)[0]  # IV / VII


def _chapter_texts(struct):
    """비교 구조 -> {장키: 공백정규화 전문}. 보일러플레이트(직전 보고서에 그대로 있던 문장) 판정용."""
    def _join(content):
        return _normalize_ws(' '.join(t for _, t in content))
    out = {}
    if 'business' in struct:
        out['II'] = _join(struct['business']['content'])
    if struct.get('notes'):
        out['notes'] = _normalize_ws(' '.join(_join(n['content']) for n in struct['notes']))
    for k in ('IV', 'VII'):
        if struct.get(k):
            out[k] = _join(struct[k]['content'])
    return out


def _is_boilerplate(text, prev_chapter_text):
    """문단의 문장이 전부 직전 보고서 같은 장 어딘가에 그대로 있으면 자리만 옮긴 문구다."""
    if not prev_chapter_text:
        return False
    sents = [x.strip() for x in re.split(r'(?<=[.다])\s+', _normalize_ws(text)) if len(x.strip()) >= 5]
    return bool(sents) and all(x in prev_chapter_text for x in sents)


def _hl_tier(section):
    m = re.match(r'^II-(\d+)', section)
    if (m and 2 <= int(m.group(1)) <= 7) or section.startswith(('IV ', 'VII ')):
        return 0
    if section.startswith('III') and any(k in section for k in _HL_NOTE_KEYS):
        return 1
    return 2


def build_highlights(changes, prev_struct):
    """분석가가 먼저 볼 text modified/added 최대 30건 -- 본문 장 > 핵심 주석 > 나머지."""
    prev_texts = _chapter_texts(prev_struct) if prev_struct else {}
    picked = []
    for c in changes:
        if c['kind'] != 'text' or c['change'] not in ('modified', 'added'):
            continue
        body = c['after'] if c['change'] == 'modified' else c['text']
        if _is_boilerplate(body, prev_texts.get(_chapter_key(c['section']))):
            continue
        picked.append(c)
    picked.sort(key=lambda c: (_hl_tier(c['section']), c['change'] != 'modified',
                               -len(c.get('after') or c.get('text') or '')))
    return picked[:_HL_MAX]


HIGHLIGHTS_NOTE = '전체 변경점은 ta/dart_diff.json 에서 grep'


def write_outputs(stock_name, result):
    """전체본 dart_diff.json + 분석가가 먼저 읽는 압축본 dart_diff_highlights.json (fix round 6)."""
    ta = tc.ta_dir(stock_name)
    tc.write_json(os.path.join(ta, 'dart_diff.json'), result)
    note = HIGHLIGHTS_NOTE if result['status'] == 'ok' else f"{HIGHLIGHTS_NOTE} (status={result['status']}: {result['reason']})"
    tc.write_json(os.path.join(ta, 'dart_diff_highlights.json'), {
        'latest': result['latest'],
        'previous': result['previous'],
        'summary': result['summary'],
        'top_text_sections': result['summary']['top_text_sections'],
        'highlights': result['highlights'],
        'modified': [c for c in result['changes'] if c['change'] == 'modified'],
        'note': note,
    })


# ==================== 실행 ====================

def run(stock_name):
    reports = find_reports(tc.data_dir(stock_name))
    if not reports:
        result = {'latest': None, 'previous': None, 'files': [], 'changes': [],
                   'summary': _build_summary([]), 'highlights': [],
                   'status': 'failed', 'reason': f'{stock_name}: _dart_FULL_*.txt 파일 없음'}
        write_outputs(stock_name, result)
        tc.manifest_update(stock_name, 'dart_diff', 'failed', reason=result['reason'])
        return result

    latest = reports[-1]
    previous = reports[-2] if len(reports) >= 2 else None

    with open(latest['path'], encoding='utf-8') as f:
        latest_lines = f.readlines()
    latest_struct = build_ta_sections(latest_lines)

    out_dir = os.path.join(tc.ta_dir(stock_name), 'dart')
    files_meta = write_sections(out_dir, latest['filename'], latest_struct)

    changes = []
    reason = ''
    prev_struct = None
    if previous:
        with open(previous['path'], encoding='utf-8') as f:
            prev_lines = f.readlines()
        prev_struct = build_ta_sections(prev_lines)
        changes = compute_changes(prev_struct, latest_struct)
    else:
        reason = '직전 보고서 없음 (보고서 1편만 존재) -- 장 분할만 수행'

    summary = _build_summary(changes)

    result = {
        'latest': {'file': latest['filename'], 'period': latest['period']},
        'previous': ({'file': previous['filename'], 'period': previous['period']} if previous else None),
        'files': files_meta,
        'changes': changes,
        'summary': summary,
        'highlights': build_highlights(changes, prev_struct if previous else None),
        'status': 'ok',
        'reason': reason,
    }
    write_outputs(stock_name, result)
    tc.manifest_update(stock_name, 'dart_diff', 'ok', files=len(files_meta), changes=len(changes))
    return result


def main():
    parser = argparse.ArgumentParser(description='DART 정기보고서 장 분할 + 직전 대비 변경점')
    parser.add_argument('stock_name')
    args = parser.parse_args()
    result = run(args.stock_name)
    print(f"[{'OK' if result['status'] == 'ok' else 'FAIL'}] {args.stock_name}: "
          f"files={len(result['files'])} changes={len(result['changes'])} "
          f"status={result['status']}")
    if result['reason']:
        print(f"  reason: {result['reason']}")
    if result['status'] != 'ok':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
