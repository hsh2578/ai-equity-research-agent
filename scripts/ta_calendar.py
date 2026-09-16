# -*- coding: utf-8 -*-
"""ta_calendar.py -- 날짜·근거가 있는 이벤트 캘린더 (/research-ta Task 6).

리포트 catalysts 가 "2026 H1" 같은 모호한 표현 대신 **날짜와 근거**를 갖게 한다.
네 가지 규칙으로 항목을 만들고 각 항목에 basis(법정기한/전년패턴/공시/뉴스)를 단다.

  1. 법정기한  -- 분기/반기/사업보고서 제출기한을 날짜 계산으로 (12월 결산 가정,
     결산월이 다르다는 근거가 있으면 건너뛰고 skipped 에 사유를 남긴다)
  2. 전년패턴  -- 작년 같은 시기 잠정실적/IR개최/주총소집결의 날짜 +1년(주말 보정)
  3. 공시      -- DART 공시 본문에서 확정 일정(주총 일시/배당기준일/전환·교환청구기간/
     자기주식 처분·취득예정기간)을 정규식으로 추출, 원문 한 줄을 quote 로 남긴다
  4. 뉴스      -- 뉴스 제목·본문의 today 이후 날짜 (news.json 없으면 규칙 자체를 건너뜀)

날짜 파싱/추출은 순수 함수(네트워크·파일 I/O 없음)라 테스트가 픽스처만으로 돈다.
`main()` 만 디스크에서 _dart_filings.json / ta/news.json / 결산월을 읽어 넘긴다.

사용:
    python scripts/ta_calendar.py {종목명} [--today YYYY-MM-DD] [--horizon-days 270]
"""
import argparse
import io
import os
import re
import sys
from datetime import date, datetime, timedelta

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta_common as tc  # noqa: E402

# ==================== 날짜 정규식 ====================
# 공시 본문: "2026 년 08 월 27 일" / "2026년 08월 27일" / "2026.08.27" / "2026-08-27"
_DATE_RE = re.compile(r'(\d{4})\s*(?:년|\.|-)\s*(\d{1,2})\s*(?:월|\.|-)\s*(\d{1,2})\s*일?')
# 뉴스: "YYYY년 M월 D일" / "M월 D일" (한글 표기만 -- 기사 본문에 점/대시 날짜는 드물고
# _DATE_RE 를 그대로 쓰면 전화번호·금액 같은 숫자열을 날짜로 오인하기 쉽다)
_NEWS_FULL_DATE_RE = re.compile(r'(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일')
_NEWS_MONTH_DAY_RE = re.compile(r'(\d{1,2})\s*월\s*(\d{1,2})\s*일')
# 주총/IR 일시 라벨. "개최일시" 또는 "일시"/"일 시"(공시 양식은 칸을 띄워 쓴다)
_MEETING_TIME_RE = re.compile(r'개최\s*일\s*시|일\s*시')


def normalize_filing_name(name):
    """공시명 정규화: 끝 공백 제거 + 앞 [기재정정]/[첨부정정] 류 접두 제거 + 내부 공백 축소."""
    s = (name or '').strip()
    s = re.sub(r'^(\[[^\]]*\])+', '', s).strip()
    s = re.sub(r'\s+', ' ', s)
    return s


def _quote(text, start, end, pad=80):
    seg = text[max(0, start - pad):min(len(text), end + pad)]
    return re.sub(r'\s+', ' ', seg).strip()


def _find_date(text, start, window=400):
    """text[start:start+window] 에서 첫 날짜 매치. 유효하지 않은 날짜(2/30 등)는 건너뛰지 않고
    다음 매치를 계속 찾는다."""
    end = min(len(text), start + window)
    pos = start
    while pos < end:
        m = _DATE_RE.search(text, pos, end)
        if not m:
            return None
        y, mo, da = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, da), m.start(), m.end()
        except ValueError:
            pos = m.end()
    return None


def adjust_weekend(d):
    """토(5)/일(6) 이면 다음 월요일로."""
    wd = d.weekday()
    if wd == 5:
        return d + timedelta(days=2)
    if wd == 6:
        return d + timedelta(days=1)
    return d


def _add_years(d, n):
    try:
        return d.replace(year=d.year + n)
    except ValueError:
        # 2/29 + 1년처럼 그 해에 없는 날짜 -> 3/1
        return date(d.year + n, 3, 1)


def _parse_yyyymmdd(s):
    s = str(s or '')
    try:
        return datetime.strptime(s[:8], '%Y%m%d').date()
    except ValueError:
        return None


# ==================== 1. 법정 제출기한 ====================

_QUARTER_RULES = ((3, 31, 45, '1분기 분기보고서 제출기한'), (9, 30, 45, '3분기 분기보고서 제출기한'))
_HALF_RULE = (6, 30, 45, '반기보고서 제출기한')
_ANNUAL_RULE = (12, 31, 90, '사업보고서 제출기한')


def _next_occurrence(today, month, day, offset_days):
    year = today.year
    d = date(year, month, day) + timedelta(days=offset_days)
    if d <= today:
        d = date(year + 1, month, day) + timedelta(days=offset_days)
    return d


def statutory_deadlines(today):
    """12월 결산 가정. today 이후 가장 가까운 분기/반기/사업보고서 제출기한 3건(필터 전)."""
    quarters = sorted((_next_occurrence(today, m, d, off), label) for m, d, off, label in _QUARTER_RULES)
    half_date = _next_occurrence(today, *_HALF_RULE[:3])
    annual_date = _next_occurrence(today, *_ANNUAL_RULE[:3])
    return [
        {'event': quarters[0][1], 'date': quarters[0][0]},
        {'event': _HALF_RULE[3], 'date': half_date},
        {'event': _ANNUAL_RULE[3], 'date': annual_date},
    ]


def fiscal_year_end_ok(settle_month):
    """결산월이 12월이 아니라는 근거가 있으면 (False, 사유). 근거 없으면 (True, None)(12월 가정)."""
    if not settle_month:
        return True, None
    digits = re.sub(r'\D', '', str(settle_month))
    if digits and digits != '12':
        return False, f'결산월 {settle_month} (12월 아님) -- 법정기한 규칙은 12월 결산 전용'
    return True, None


# ==================== 2. 전년 패턴 ====================

_PRIOR_YEAR_PATTERNS = (
    (re.compile(r'\(잠정\)\s*실적'), '잠정실적 발표'),
    (lambda n: n.startswith('기업설명회(IR)개최'), '기업설명회(IR) 개최'),
    (lambda n: n.startswith('주주총회소집결의'), '주주총회소집결의'),
)


def prior_year_items(filings_list):
    out = []
    for f in filings_list or []:
        norm = normalize_filing_name(f.get('name'))
        label = None
        for pred, lab in _PRIOR_YEAR_PATTERNS:
            hit = pred.search(norm) if hasattr(pred, 'search') else pred(norm)
            if hit:
                label = lab
                break
        if label is None:
            continue
        orig_date = _parse_yyyymmdd(f.get('date'))
        if orig_date is None:
            continue
        projected = adjust_weekend(_add_years(orig_date, 1))
        out.append({
            'event': f'{label} 예상(전년 패턴)',
            'date': projected,
            'ref': f.get('rcept_no') or '',
            'quote': f'{orig_date.isoformat()} {norm}',
        })
    return out


# ==================== 3. 공시 본문 확정 일정 ====================

_SINGLE_RULES = (('배당기준일', '배당기준일'),)
_PERIOD_RULES = (
    ('전환청구기간', '전환사채 전환청구기간'),
    ('교환청구기간', '교환사채 교환청구기간'),
    ('처분예정기간', '자기주식 처분'),
    ('취득예정기간', '자기주식 취득'),
)


def _meeting_kind(norm_name):
    if '정기' in norm_name:
        return '정기'
    if '임시' in norm_name:
        return '임시'
    return ''


def disclosure_items(bodies):
    out = []
    for b in bodies or []:
        text = b.get('text') or ''
        norm_name = normalize_filing_name(b.get('name'))
        ref = b.get('rcept_no') or ''

        for kw, label in _SINGLE_RULES:
            idx = text.find(kw)
            if idx == -1:
                continue
            found = _find_date(text, idx + len(kw))
            if not found:
                continue
            d, s, e = found
            out.append({'event': label, 'date': d, 'ref': ref, 'quote': _quote(text, s, e)})

        for kw, prefix in _PERIOD_RULES:
            idx = text.find(kw)
            if idx == -1:
                continue
            seg_end = min(len(text), idx + 400)
            seg = text[idx:seg_end]
            si = seg.find('시작일')
            if si != -1:
                found = _find_date(text, idx + si + len('시작일'), window=200)
                if found:
                    d, s, e = found
                    out.append({'event': f'{prefix} 시작', 'date': d, 'ref': ref, 'quote': _quote(text, s, e)})
            ei = seg.find('종료일')
            if ei != -1:
                found = _find_date(text, idx + ei + len('종료일'), window=200)
                if found:
                    d, s, e = found
                    out.append({'event': f'{prefix} 종료', 'date': d, 'ref': ref, 'quote': _quote(text, s, e)})

        is_meeting = '주주총회' in norm_name and ('소집' in norm_name or '개최' in norm_name)
        is_ir = ('기업설명회' in norm_name) or ('IR' in norm_name and '개최' in norm_name)
        if is_meeting or is_ir:
            m = _MEETING_TIME_RE.search(text)
            if m:
                found = _find_date(text, m.end())
                if found:
                    d, s, e = found
                    if is_meeting:
                        event = f'{_meeting_kind(norm_name)}주주총회 개최'
                    else:
                        event = '기업설명회(IR) 개최'
                    out.append({'event': event, 'date': d, 'ref': ref, 'quote': _quote(text, s, e)})
    return out


# ==================== 4. 뉴스 속 미래 날짜 ====================
#
# 최초 버전은 "M월 D일"(무연도) 의 해를 today 기준으로 추론했다 -- 과거 기사가
# 발행일을 오늘 기준 미래로 잘못 투사하는 결함이 있었다(예: 2026-01 발행 기사의
# "1월 29일" 이 today=2026-09-17 기준으로 2027-01-29 미래 이벤트가 됨).
# 지금은 기사의 **발행일**(datetime)을 기준으로 해를 추론하고, 아래 4개 관문을
# 모두 통과해야만 이벤트로 남는다.
#   1) 무연도 표기는 발행일 기준 "이후 가장 가까운 해"로 (오늘 기준 아님)
#   2) 추출한 날짜가 발행일 그 자체면 버린다 (보도이지 미래 일정이 아니다)
#   3) 날짜 앞뒤 25자 안에 미래 의도 단어가 없으면 버린다
#   4) 날짜가 today 이후가 아니면 버린다 (지난 기사의 지난 언급)
_FUTURE_CONTEXT_RE = re.compile(
    '예정|까지|개최|납입일|상장|만기|청구기간|기준일|목표|출시|양산|착공|준공|가동')
# 시황 집계/등락 결과 기사는 애초에 '일정'이 아니라 '결과' 보도라 제목 단계에서 거른다
_ROUNDUP_SUBSTRINGS = ('주요공시', '브리핑', '마감시황', '관련주')


def _is_roundup_title(title):
    t = title or ''
    return tc.is_reaction_title(t) or any(s in t for s in _ROUNDUP_SUBSTRINGS)


def _parse_news_dt(s):
    """news.json 의 ISO datetime 문자열 -> date. 없거나 깨졌으면 None."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s)).date()
    except ValueError:
        return None


def _news_dates(text, pub_date):
    """text 안의 날짜 후보. 무연도 "M월 D일" 은 today 가 아니라 **발행일(pub_date)**
    기준으로 이후 가장 가까운 해를 고른다."""
    text = text or ''
    results, full_spans = [], []
    for m in _NEWS_FULL_DATE_RE.finditer(text):
        y, mo, da = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            d = date(y, mo, da)
        except ValueError:
            continue
        results.append((d, m.start(), m.end()))
        full_spans.append((m.start(), m.end()))
    for m in _NEWS_MONTH_DAY_RE.finditer(text):
        if any(s <= m.start() < e for s, e in full_spans):
            continue  # "YYYY년 M월 D일" 안의 "M월 D일" 조각은 이미 셌다
        mo, da = int(m.group(1)), int(m.group(2))
        try:
            cand = date(pub_date.year, mo, da)
        except ValueError:
            continue
        if cand < pub_date:
            try:
                cand = date(pub_date.year + 1, mo, da)
            except ValueError:
                continue
        results.append((cand, m.start(), m.end()))
    return results


def _sentence_window(text, s, e, pad=25):
    """날짜 매치(s:e) 앞뒤 pad 자 안에서, **문장 경계(마침표)를 넘지 않는** 부분만 돌려준다.
    실측(에프에스티 N0248)에서 "소각 예정 금액은...다. 이는 3월9일 종가..." 처럼 앞 문장의
    '예정' 이 마침표 너머 다음 문장의 날짜에 달라붙어 오탐을 냈다 -- 문장 경계로 끊는다."""
    before = text[max(0, s - pad):s]
    last_dot = before.rfind('.')
    if last_dot != -1:
        before = before[last_dot + 1:]
    after = text[e:min(len(text), e + pad)]
    first_dot = after.find('.')
    if first_dot != -1:
        after = after[:first_dot + 1]
    return before + text[s:e] + after


def news_calendar_items(news_items, today):
    out = []
    for it in news_items or []:
        if not it.get('relevant', True):
            continue  # 무관 기사 제외 (news_relevant.json 은 이미 필터돼 있어 키가 없을 수 있다)
        title = it.get('title') or ''
        if _is_roundup_title(title):
            continue  # 시황/공시집계/등락 결과 기사는 '일정'이 아니라 '결과' 보도
        pub_date = _parse_news_dt(it.get('datetime'))
        if pub_date is None:
            continue  # 발행일 없이는 무연도 날짜의 해를 안전하게 추론할 수 없다
        nid = it.get('nid') or ''
        event = title or '뉴스 언급 일정'
        for text in (title, it.get('body') or ''):
            for d, s, e in _news_dates(text, pub_date):
                if d == pub_date:
                    continue  # 기사 자신의 발행일 언급 -- 미래 일정이 아니라 보도 시점
                if d <= today:
                    continue  # today 이후만 (지난 기사의 지난 언급 배제)
                window = _sentence_window(text, s, e)
                if not _FUTURE_CONTEXT_RE.search(window):
                    continue  # 미래 의도 단어 없이는 우연히 매칭된 숫자로 본다
                out.append({'event': event, 'date': d, 'ref': nid, 'quote': _quote(text, s, e)})
    return out


# ==================== 조합 ====================

def build_calendar(stock_name, today, horizon_days, filings=None, news=None, settle_month=None):
    """순수 함수(파일 I/O 없음). filings/news 는 이미 읽어들인 dict 또는 None(없음)."""
    horizon_end = today + timedelta(days=horizon_days)
    skipped = []
    raw = []

    fiscal_ok, fiscal_reason = fiscal_year_end_ok(settle_month)
    if fiscal_ok:
        for it in statutory_deadlines(today):
            raw.append({'event': it['event'], 'date': it['date'], 'basis': '법정기한',
                        'confidence': 'high', 'sources': []})
    else:
        skipped.append({'rule': '법정기한', 'reason': fiscal_reason})

    if filings is None:
        skipped.append({'rule': '전년패턴', 'reason': '_dart_filings.json 없음'})
        skipped.append({'rule': '공시', 'reason': '_dart_filings.json 없음'})
    else:
        for it in prior_year_items(filings.get('list')):
            raw.append({'event': it['event'], 'date': it['date'], 'basis': '전년패턴',
                        'confidence': 'medium', 'sources': [{'ref': it['ref'], 'quote': it['quote']}]})
        for it in disclosure_items(filings.get('bodies')):
            raw.append({'event': it['event'], 'date': it['date'], 'basis': '공시',
                        'confidence': 'high', 'sources': [{'ref': it['ref'], 'quote': it['quote']}]})

    if news is None:
        skipped.append({'rule': '뉴스', 'reason': 'news.json 없음'})
    else:
        for it in news_calendar_items(news.get('items'), today):
            raw.append({'event': it['event'], 'date': it['date'], 'basis': '뉴스',
                        'confidence': 'low', 'sources': [{'ref': it['ref'], 'quote': it['quote']}]})

    filtered = [x for x in raw if today <= x['date'] <= horizon_end]

    merged, order = {}, []
    for x in filtered:
        key = (x['date'], x['event'])
        if key not in merged:
            merged[key] = dict(x, sources=list(x['sources']))
            order.append(key)
        else:
            merged[key]['sources'].extend(x['sources'])

    result = sorted((merged[k] for k in order), key=lambda x: (x['date'], x['event']))
    items = []
    for i, it in enumerate(result, start=1):
        items.append({'cid': f'C{i:02d}', 'date': it['date'].isoformat(), 'event': it['event'],
                       'basis': it['basis'], 'confidence': it['confidence'], 'sources': it['sources']})

    return {'stock': stock_name, 'today': today.isoformat(), 'items': items, 'skipped': skipped}


# ==================== CLI ====================

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('stock')
    ap.add_argument('--today', default=None)
    ap.add_argument('--horizon-days', type=int, default=270)
    a = ap.parse_args(argv)

    today = datetime.strptime(a.today, '%Y-%m-%d').date() if a.today else tc.now_kst().date()

    print('=' * 74)
    print(f'  일정 캘린더: {a.stock} (오늘 {today.isoformat()})')
    print('=' * 74)

    filings_path = os.path.join(tc.data_dir(a.stock), '_dart_filings.json')
    filings = tc.read_json(filings_path, None)
    print(f"  [dart_filings] {'ok' if filings is not None else '없음'} ({filings_path})")

    # news_relevant.json(있으면) 을 우선한다 -- 무관 기사까지 실은 news.json 은 뉴스 규칙에
    # 굳이 다 필요하지 않고(news_calendar_items 가 relevant 로 다시 거르긴 한다), 이미
    # 걸러진 파일을 우선 쓰는 편이 더 정직하다.
    news_relevant_path = os.path.join(tc.ta_dir(a.stock), 'news_relevant.json')
    news_path = news_relevant_path if os.path.exists(news_relevant_path) else \
        os.path.join(tc.ta_dir(a.stock), 'news.json')
    news = tc.read_json(news_path, None)
    print(f"  [news] {'ok' if news is not None else '없음'} ({news_path})")

    settle_month = None
    try:
        settle_month = tc.resolve_stock(a.stock).get('settle_month')
    except LookupError as e:
        print(f'  [WARN] 종목 식별 실패(결산월 확인 불가, 12월 결산 가정): {e}')
    if not settle_month:
        fs = tc.read_json(os.path.join(tc.data_dir(a.stock), 'financial_summary.json'), {}) or {}
        meta = fs.get('meta', {}) or {}
        settle_month = meta.get('settle_month') or meta.get('결산월')

    payload = build_calendar(a.stock, today, a.horizon_days, filings=filings, news=news,
                              settle_month=settle_month)

    out_path = os.path.join(tc.ta_dir(a.stock), 'calendar.json')
    tc.write_json(out_path, payload)
    print(f'  -> {out_path}')
    print(f"  일정 {len(payload['items'])}건 (건너뜀 {len(payload['skipped'])}건)")

    tc.manifest_update(a.stock, 'calendar', 'ok', count=len(payload['items']))
    print('=' * 74)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
