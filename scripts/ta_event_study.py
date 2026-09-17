"""ta_event_study.py -- 뉴스/공시 이벤트에 시장 대비 초과수익(AR/CAR)을 붙인다 (Task 3).

TradingAgents 원본은 호재/악재 판정을 LLM 감에 맡겼다. 이 스크립트는 그 대신
"이벤트가 난 날 벤치마크 대비 실제로 초과수익이 났는가"를 계산해 옆에 둔다.
초과수익은 상관일 뿐 인과가 아니다 -- 같은 날 다른 재료가 있었을 수 있다.

CLI: python scripts/ta_event_study.py {종목명} [--code 036810] [--top 10]

입력:
  - data/{종목}/ta/news.json           (Task 2 산출, 없으면 뉴스 이벤트 0건)
  - data/{종목}/_dart_filings.json     (기존, 없으면 공시 이벤트 0건)
  - data/{종목}/_price_cycles.json     (기존, 없으면 사이클 매칭 생략)
  - 가격: FinanceDataReader DataReader(code, start) 종가. load_prices 로 주입 가능.

출력: data/{종목}/ta/event_study.json
"""
import argparse
import io
import os
import sys
from datetime import date, datetime, time as dtime, timedelta

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta_common as tc  # noqa: E402

NOTE = '초과수익은 이벤트와 같은 날의 상관이며 인과가 아니다. 같은 날 다른 재료가 있었을 수 있다.'
MARKET_CLOSE = dtime(15, 30)


# ==================== 가격 로더 (주입 가능) ====================

def load_prices(code, start):
    """FinanceDataReader 종가 Series. 테스트에서는 이 함수를 다른 함수로 교체해 주입한다."""
    import FinanceDataReader as fdr
    df = fdr.DataReader(code, start)
    return df['Close']


def compute_ar(stock_close, bench_close):
    """두 종가 Series -> 일간 초과수익 AR Series (index: datetime.date, 교집합 날짜만)."""
    s = stock_close.sort_index()
    b = bench_close.sort_index()
    idx = s.index.intersection(b.index).sort_values()
    if len(idx) == 0:
        raise ValueError('주가/벤치마크 종가 날짜 교집합이 비어 있음')
    r_s = s.reindex(idx).pct_change()
    r_b = b.reindex(idx).pct_change()
    ar = r_s - r_b
    ar.index = [d.date() if hasattr(d, 'date') else d for d in idx]
    return ar


def compute_car(ar, d0):
    """AR Series + D0(date) -> (car_d0, car_d1, car_d5, incomplete)."""
    trading_days = list(ar.index)
    if d0 not in trading_days:
        return None, None, None, True
    i0 = trading_days.index(d0)

    def val(i):
        if i < 0 or i >= len(trading_days):
            return None
        v = ar.iloc[i]
        return None if v != v else float(v)  # v != v -> NaN

    v0 = val(i0)
    incomplete = v0 is None
    car_d0 = v0

    v1 = val(i0 + 1)
    car_d1 = (v0 + v1) if (v0 is not None and v1 is not None) else None
    if car_d1 is None:
        incomplete = True

    window = [val(i0 + k) for k in range(6)]
    car_d5 = sum(window) if all(v is not None for v in window) else None
    if car_d5 is None:
        incomplete = True

    return car_d0, car_d1, car_d5, incomplete


# ==================== 거래일 헬퍼 (가격 없을 때 주말만 건너뛰는 폴백) ====================

def _weekday_on_or_after(d):
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _weekday_strictly_after(d):
    return _weekday_on_or_after(d + timedelta(days=1))


def resolve_d0(ev_date, ev_time, trading_days):
    """이벤트 날짜/시각 -> (D0, time_basis).
    ev_time 이 None 이면 공시(다음 거래일 보수적). 아니면 뉴스(15:30 경계).
    trading_days 가 비어 있으면(가격 로드 실패) 주말만 건너뛰는 폴백을 쓴다.
    """
    if trading_days:
        def on_or_after(d):
            cands = [td for td in trading_days if td >= d]
            return min(cands) if cands else _weekday_on_or_after(d)

        def strictly_after(d):
            cands = [td for td in trading_days if td > d]
            return min(cands) if cands else _weekday_strictly_after(d)
    else:
        on_or_after = _weekday_on_or_after
        strictly_after = _weekday_strictly_after

    if ev_time is None:
        return strictly_after(ev_date), 'next_day_conservative'
    if ev_time < MARKET_CLOSE:
        d0 = on_or_after(ev_date)
        return d0, ('same_day' if d0 == ev_date else 'next_trading_day')
    return strictly_after(ev_date), 'next_trading_day'


# ==================== 입력 로드 ====================

def _parse_news_dt(s):
    if not s:
        return None
    dt = datetime.fromisoformat(s)
    dt = dt.astimezone(tc.KST) if dt.tzinfo is not None else dt.replace(tzinfo=tc.KST)
    return dt


def load_news_events(path):
    """news.json -> (events, reaction_excluded_count). relevant==false 항목은 둘 다 무시."""
    data = tc.read_json(path, None)
    if not data:
        return [], 0
    events, reaction_excluded = [], 0
    for it in data.get('items', []) or []:
        if not it.get('relevant'):
            continue
        kind = it.get('type')
        if kind == 'reaction':
            reaction_excluded += 1
            continue
        if kind not in ('news', 'window'):
            continue
        dt = _parse_news_dt(it.get('datetime'))
        if dt is None:
            continue
        events.append({
            'eid': it.get('nid'), 'kind': 'news',
            'date': dt.date(), 'time': dt.time(),
            'title': it.get('title', ''), 'raw': it.get('datetime'),
        })
    return events, reaction_excluded


def load_filing_events(path):
    """_dart_filings.json -> 공시 이벤트 전체 (필터 없음)."""
    data = tc.read_json(path, None)
    if not data:
        return []
    events = []
    for it in data.get('list', []) or []:
        date_s = it.get('date')
        try:
            d = datetime.strptime(str(date_s), '%Y%m%d').date()
        except (TypeError, ValueError):
            continue
        rcept = it.get('rcept_no', '')
        events.append({
            'eid': f'D{rcept}', 'kind': 'filing',
            'date': d, 'time': None,
            'title': it.get('name', ''), 'raw': date_s,
        })
    return events


def load_cycles(path):
    data = tc.read_json(path, None)
    if not data:
        return []
    return data.get('cycles', []) or []


# ==================== 그룹/랭킹/사이클 ====================

def _build_groups(events, ar):
    by_d0 = {}
    for e in events:
        by_d0.setdefault(e['d0'], []).append(e)
    groups = []
    for d0 in sorted(by_d0):
        evs = by_d0[d0]
        if ar is not None:
            car_d0, car_d1, car_d5, incomplete = compute_car(ar, d0)
        else:
            car_d0 = car_d1 = car_d5 = None
            incomplete = True
        groups.append({
            'd0': d0.isoformat(),
            'car_d0': car_d0, 'car_d1': car_d1, 'car_d5': car_d5,
            'incomplete': incomplete,
            'events': [
                {'eid': e['eid'], 'kind': e['kind'], 'datetime_or_date': e['raw'],
                 'title': e['title'], 'time_basis': e['time_basis']}
                for e in evs
            ],
        })
    return groups


def _top_moves(groups, top):
    ranked = sorted(groups, key=lambda g: abs(g['car_d0']) if g['car_d0'] is not None else -1,
                     reverse=True)
    return ranked[:top]


def _window_around(center, trading_days, n):
    if center not in trading_days:
        cands = [td for td in trading_days if td >= center]
        if not cands:
            return set()
        center = min(cands)
    i = trading_days.index(center)
    lo, hi = max(0, i - n), min(len(trading_days), i + n + 1)
    return set(trading_days[lo:hi])


def _match_cycles(cycles, groups, trading_days):
    if not cycles or not trading_days:
        return []
    triggers = []
    for c in cycles:
        try:
            start = datetime.strptime(c['start'], '%Y-%m-%d').date()
        except (KeyError, ValueError, TypeError):
            continue
        window = _window_around(start, trading_days, 5)
        matched = [g for g in groups if date.fromisoformat(g['d0']) in window]
        if matched:
            triggers.append({
                'cycle': {'start': c.get('start'), 'end': c.get('end'),
                          'change_pct': c.get('change_pct'), 'direction': c.get('direction')},
                'groups': matched,
            })
    return triggers


# ==================== 메인 로직 ====================

def run(stock_name, code=None, top=10, load_prices=load_prices):
    news_events, reaction_excluded = load_news_events(
        os.path.join(tc.ta_dir(stock_name), 'news.json'))
    filing_events = load_filing_events(
        os.path.join(tc.data_dir(stock_name), '_dart_filings.json'))
    cycles = load_cycles(
        os.path.join(tc.data_dir(stock_name), '_price_cycles.json'))

    info = tc.resolve_stock(stock_name, code=code)
    bench_code = info['benchmark_code']

    all_events = news_events + filing_events
    if all_events:
        start = (min(e['date'] for e in all_events) - timedelta(days=10)).strftime('%Y-%m-%d')
    else:
        start = (tc.now_kst().date() - timedelta(days=365)).strftime('%Y-%m-%d')

    ar = None
    try:
        stock_close = load_prices(info['code'], start)
        bench_close = load_prices(bench_code, start)
        ar = compute_ar(stock_close, bench_close)
        price_status = {
            'status': 'ok', 'reason': None,
            'first': ar.index[0].isoformat(), 'last': ar.index[-1].isoformat(),
        }
    except Exception as e:
        price_status = {'status': 'failed', 'reason': f'{type(e).__name__}: {e}',
                         'first': None, 'last': None}
        ar = None

    trading_days = list(ar.index) if ar is not None else []
    for e in all_events:
        e['d0'], e['time_basis'] = resolve_d0(e['date'], e.get('time'), trading_days)

    groups = _build_groups(all_events, ar)
    top_moves = _top_moves(groups, top)
    cycle_triggers = _match_cycles(cycles, groups, trading_days)

    return {
        'stock': stock_name,
        'benchmark': {'code': bench_code, 'name': info['benchmark_name']},
        'note': NOTE,
        'counts': {
            'news_events': len(news_events),
            'filing_events': len(filing_events),
            'reaction_excluded': reaction_excluded,
            'groups': len(groups),
        },
        'groups': groups,
        'top_moves': top_moves,
        'cycle_triggers': cycle_triggers,
        'price_status': price_status,
    }


def main():
    ap = argparse.ArgumentParser(description='뉴스/공시 이벤트 초과수익(AR/CAR) 계산')
    ap.add_argument('stock_name')
    ap.add_argument('--code', default=None)
    ap.add_argument('--top', type=int, default=10)
    args = ap.parse_args()

    try:
        result = run(args.stock_name, code=args.code, top=args.top)
    except Exception as e:
        try:
            tc.manifest_update(args.stock_name, 'event_study', 'failed',
                                reason=f'{type(e).__name__}: {e}')
        except Exception:
            pass
        print(f'[FAIL] {type(e).__name__}: {e}')
        sys.exit(1)

    out_path = os.path.join(tc.ta_dir(args.stock_name), 'event_study.json')
    tc.write_json(out_path, result)
    tc.manifest_update(args.stock_name, 'event_study', 'ok',
                        counts=result['counts'], price_status=result['price_status'])
    print(f"event_study.json 저장 -- groups={result['counts']['groups']} "
          f"news={result['counts']['news_events']} filing={result['counts']['filing_events']} "
          f"price={result['price_status']['status']}")
    sys.exit(0)


if __name__ == '__main__':
    main()
