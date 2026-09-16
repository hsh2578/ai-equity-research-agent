# -*- coding: utf-8 -*-
"""네이버 종목토론방 + KIS 투자자별 수급 (Task 5, /research-ta).

TradingAgents 원본의 StockTwits/Reddit 심리 소스 자리를 한국 종목에 맞게
채운다 -- 개인 심리는 네이버 종목토론방, 수급은 KIS 투자자별 매매동향.

개인정보: 게시글 writer 객체(nickname/profileId 등)는 파싱 단계에서 통째로
버리고 절대 재조립하지 않는다 (tests/test_ta_board_flow.py 로 강제).

사용법:
    python scripts/ta_board_flow.py {종목명} [--code 036810] [--limit 2000] [--flow-days 20]

산출:
    data/{종목명}/ta/board.json
    data/{종목명}/ta/flow.json
"""
import argparse
import io
import os
import statistics
import sys
import time
from datetime import date, timedelta

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests                                             # noqa: E402
import ta_common as tc                                      # noqa: E402

BOARD_URL = 'https://m.stock.naver.com/front-api/discussion/list'
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://m.stock.naver.com/'}
SPIKE_WINDOW = 20
SAMPLE_TOP_N = 30
SAMPLE_SIDE_N = 10
_SHARES_KEYS = ('shares_outstanding', '발행주식수', '상장주식수')


# ==================== 소스 1: 네이버 종목토론방 ====================

def _default_fetch(url, params, headers, timeout=15):
    return requests.get(url, params=params, headers=headers, timeout=timeout)


def _sanitize_post(p):
    """writer(닉네임/profileId 등)를 통째로 버린다. 이 함수를 거치지 않은
    raw post 는 절대 파일로 쓰지 않는다."""
    return {
        'id': p.get('id'),
        'writtenAt': p.get('writtenAt'),
        'title': p.get('title'),
        'content': p.get('contentSwReplaced'),
        'isHolderVerified': bool(p.get('isHolderVerified')),
        'isCleanbotPassed': bool(p.get('isCleanbotPassed')),
        'replyDepth': p.get('replyDepth') or 0,
        'recommendCount': p.get('recommendCount') or 0,
        'notRecommendCount': p.get('notRecommendCount') or 0,
        'viewCount': p.get('viewCount') or 0,
    }


_REASON_MAX = 200
_API_REASON_FIELDS = ('resultCode', 'code', 'message', 'detailCode', 'errorMessage', 'errorCode')


def _safe_api_reason(data, prefix='isSuccess=false'):
    """API 응답 실패 사유를 화이트리스트 필드만 골라 만든다.

    data 전체를 문자열화하면 안 된다 -- isSuccess=false 여도 posts 가 같이 오는
    응답 형태를 코드가 배제하지 않으므로, 그 posts[].writer.nickname/profileId 가
    그대로 reason -> board.json 에 실려 개인정보가 샐 수 있다(리뷰 지적). 이 함수를
    거치지 않은 raw dict 를 reason 문자열에 절대 직접 넣지 않는다."""
    if not isinstance(data, dict):
        return f'{prefix}: (파싱 불가 응답)'
    parts = [f'{k}={data[k]!r}' for k in _API_REASON_FIELDS if data.get(k) is not None]
    detail = ', '.join(parts) if parts else '상세 없음'
    return f'{prefix}: isSuccess={data.get("isSuccess")!r}, {detail}'[:_REASON_MAX]


def fetch_board_posts(item_code, limit=2000, delay=0.3, fetch=None):
    """offset 페이지네이션으로 종목토론방 글을 모은다. 결과는 이미 privacy-safe
    (raw 응답을 그대로 쌓지 않고 매 페이지 즉시 _sanitize_post 를 거친다)."""
    fetch = fetch or _default_fetch
    posts = []
    offset = None
    pages = 0
    while len(posts) < limit:
        params = {
            'discussionType': 'domesticStock', 'itemCode': item_code, 'pageSize': 100,
            'isHolderOnly': 'false', 'excludesItemNews': 'false',
            'isItemNewsOnly': 'false', 'isCleanbotPassedOnly': 'false',
        }
        if offset is not None:
            params['offset'] = offset
        r = fetch(BOARD_URL, params, HEADERS, 15)
        if getattr(r, 'status_code', 200) != 200:
            return {'status': 'failed', 'reason': f'HTTP {r.status_code}', 'posts': posts}
        try:
            data = r.json()
        except Exception as e:
            return {'status': 'failed',
                    'reason': f'JSON 파싱 실패: {type(e).__name__}: {e}'[:_REASON_MAX],
                    'posts': posts}
        if not data.get('isSuccess'):
            # data 를 통째로 넣지 않는다 -- _safe_api_reason 이 화이트리스트 필드만 뽑는다.
            return {'status': 'failed', 'reason': _safe_api_reason(data), 'posts': posts}
        result = data.get('result') or {}
        page_posts = result.get('posts') or []
        if not page_posts:
            break
        posts.extend(_sanitize_post(p) for p in page_posts)
        pages += 1
        if len(posts) >= limit:
            break
        offset = result.get('lastOffset')
        if offset is None:
            break
        time.sleep(delay)
    return {'status': 'ok', 'reason': None, 'posts': posts[:limit], 'pages': pages}


def _date_range(from_d, to_d):
    d0, d1 = date.fromisoformat(from_d), date.fromisoformat(to_d)
    n = (d1 - d0).days
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n + 1)]


def compute_spikes(daily):
    """daily: [{'date','posts'}, ...] 날짜 오름차순 연속(빠지는 날 없이).
    직전 SPIKE_WINDOW 일 평균 + 3xstd 를 초과하는 날을 찾는다.
    전체 일수가 SPIKE_WINDOW 미만이면 계산을 생략하고 사유를 돌려준다.
    정확히 SPIKE_WINDOW 일이면(= 직전 20일 lookback 을 채울 수 있는 날이 하루도
    없음) 루프가 조용히 0회 도는 대신 마찬가지로 사유를 남긴다(리뷰 지적)."""
    if len(daily) < SPIKE_WINDOW:
        return [], f'기간이 {SPIKE_WINDOW}일 미만이라 급증일 계산을 생략함(실제 {len(daily)}일)'
    if len(daily) == SPIKE_WINDOW:
        return [], f'판정 가능한 날짜 없음: 기간 {len(daily)}일'
    spikes = []
    for i in range(SPIKE_WINDOW, len(daily)):
        window = [d['posts'] for d in daily[i - SPIKE_WINDOW:i]]
        mean = statistics.mean(window)
        std = statistics.pstdev(window)
        threshold = mean + 3 * std
        if daily[i]['posts'] > threshold:
            spikes.append({'date': daily[i]['date'], 'posts': daily[i]['posts'],
                           'threshold': round(threshold, 2)})
    return spikes, None


def _sample(p):
    return {
        'title': p.get('title'),
        'content': (p.get('content') or '')[:200],
        'writtenAt': p.get('writtenAt'),
        'isHolderVerified': p.get('isHolderVerified', False),
        'recommendCount': p.get('recommendCount') or 0,
        'notRecommendCount': p.get('notRecommendCount') or 0,
    }


def aggregate_board(posts):
    """posts 는 이미 _sanitize_post 를 거친(writer 없는) dict 리스트."""
    replies = [p for p in posts if (p.get('replyDepth') or 0) > 0]
    articles = [p for p in posts if not (p.get('replyDepth') or 0) > 0]

    if not articles:
        return {
            'coverage': {'from': None, 'to': None, 'days': 0, 'posts': 0,
                         'replies_excluded': len(replies)},
            'daily': [], 'totals': {}, 'spikes': [], 'spikes_note': '게시글 없음',
            'samples': {'top': [], 'holder_top': [], 'nonholder_top': []},
        }

    dated = [p for p in articles if p.get('writtenAt')]
    dates = sorted(p['writtenAt'][:10] for p in dated)
    from_d, to_d = dates[0], dates[-1]

    by_date = {}
    for p in dated:
        d = p['writtenAt'][:10]
        by_date.setdefault(d, []).append(p)

    daily = []
    for d in sorted(by_date):
        ps = by_date[d]
        holder = sum(1 for p in ps if p.get('isHolderVerified'))
        daily.append({'date': d, 'posts': len(ps), 'holder_ratio': round(holder / len(ps), 4)})

    counts_by_date = {d['date']: d['posts'] for d in daily}
    continuous = [{'date': d, 'posts': counts_by_date.get(d, 0)} for d in _date_range(from_d, to_d)]
    spikes, spikes_note = compute_spikes(continuous)

    total_holder = sum(1 for p in articles if p.get('isHolderVerified'))
    total_cleanbot = sum(1 for p in articles if p.get('isCleanbotPassed'))
    totals = {
        'posts': len(articles),
        'holder_verified': total_holder,
        'holder_ratio': round(total_holder / len(articles), 4),
        'recommend_sum': sum(p.get('recommendCount') or 0 for p in articles),
        'not_recommend_sum': sum(p.get('notRecommendCount') or 0 for p in articles),
        'cleanbot_passed': total_cleanbot,
        'cleanbot_ratio': round(total_cleanbot / len(articles), 4),
    }

    ranked = sorted(articles, key=lambda p: -(p.get('recommendCount') or 0))
    holder_ranked = [p for p in ranked if p.get('isHolderVerified')]
    nonholder_ranked = [p for p in ranked if not p.get('isHolderVerified')]

    return {
        'coverage': {'from': from_d, 'to': to_d,
                     'days': (date.fromisoformat(to_d) - date.fromisoformat(from_d)).days + 1,
                     'posts': len(articles), 'replies_excluded': len(replies)},
        'daily': daily,
        'totals': totals,
        'spikes': spikes,
        'spikes_note': spikes_note,
        'samples': {
            'top': [_sample(p) for p in ranked[:SAMPLE_TOP_N]],
            'holder_top': [_sample(p) for p in holder_ranked[:SAMPLE_SIDE_N]],
            'nonholder_top': [_sample(p) for p in nonholder_ranked[:SAMPLE_SIDE_N]],
        },
    }


def collect_board(item_code, limit=2000, fetch=None):
    fr = fetch_board_posts(item_code, limit=limit, fetch=fetch)
    if fr['status'] != 'ok':
        return {'status': 'failed', 'reason': fr.get('reason')}
    out = {'status': 'ok', 'reason': None}
    out.update(aggregate_board(fr['posts']))
    return out


# ==================== 소스 2: KIS 투자자별 수급 ====================

def _find_shares_outstanding(fs):
    """financial_summary.json 에서 발행주식수를 찾는다(폴백 4단계 최후 수단).
    실측(2026-09): KR 종목(financial_summary.py 산출)에는 이 키가 없다 --
    US 종목(financial_summary_us.py)만 financials.{year}.shares_outstanding 로
    연도별로 있다. 최상위 스칼라 키도 방어적으로 함께 본다."""
    if not isinstance(fs, dict) or not fs:
        return None, 'financial_summary.json 없음 또는 비어있음'
    for k in _SHARES_KEYS:
        v = fs.get(k)
        if isinstance(v, (int, float)) and v:
            return v, None
    fin = fs.get('financials')
    if isinstance(fin, dict):
        for year in sorted(fin.keys(), reverse=True):
            yd = fin.get(year)
            if isinstance(yd, dict):
                v = yd.get('shares_outstanding')
                if isinstance(v, (int, float)) and v:
                    return v, None
    return None, 'financial_summary.json 에 발행주식수 키 없음'


def _derive_shares_from_price(price):
    """시가총액(억원)/현재가 로 발행주식수 역산.
    단위는 CLAUDE.md 확정: get_current_price()['시가총액'] 은 억원 (kis_api.py 510줄
    print('억원'), financial_summary.py 449~450줄이 동일 공식을 쓴다).
    v5.4 규칙: shares_outstanding 은 시총/현재가로 통일해야 한다(한미반도체 critic
    결함 #2 사고 차단)."""
    price = price or {}
    cap_eok = price.get('시가총액')
    cur = price.get('현재가')
    if cap_eok and cur:
        return round(cap_eok * 1e8 / cur)
    return None


def _read_analysis_json(stock_name):
    if not stock_name:
        return None
    p = os.path.join(tc.PROJECT_ROOT, 'scripts', f'analysis_{stock_name}.json')
    return tc.read_json(p, None)


def _read_data_kis_json(stock_name):
    if not stock_name:
        return None
    p = os.path.join(tc.data_dir(stock_name), 'data_kis.json')
    return tc.read_json(p, None)


def _read_financial_summary_json(stock_name):
    if not stock_name:
        return {}
    p = os.path.join(tc.data_dir(stock_name), 'financial_summary.json')
    return tc.read_json(p, {}) or {}


def resolve_shares(stock_name, live_price, read_analysis=None, read_data_kis=None,
                   read_financial_summary=None):
    """발행주식수 4단 폴백. 실패해도 예외를 삼키지 않고 사유를 attempts 에 남긴다.

    1) 이번 호출에서 이미 받은 KIS 현재가 응답(live_price) -- 시가총액(억원) x 1e8
       / 현재가 로 역산. 별도 API 호출이 필요 없다(v5.4 통일 규칙과 동일 공식).
    2) scripts/analysis_{종목}.json 의 price.shares_outstanding (실측: KR 종목도
       이 파일에는 스칼라로 있다 -- 에프에스티 21,649,789)
    3) data/{종목}/data_kis.json 의 current_price 블록 -- 1)과 동일 공식으로 역산
    4) data/{종목}/financial_summary.json (US 전용 키, _find_shares_outstanding)

    반환: (value|None, source|None, attempts: list[str])"""
    attempts = []

    v = _derive_shares_from_price(live_price)
    if v:
        return v, 'kis_market_cap', []
    attempts.append('kis_market_cap: 이번 조회 응답에 시가총액/현재가 없음')

    read_analysis = read_analysis or (lambda: _read_analysis_json(stock_name))
    try:
        d = read_analysis()
    except Exception as e:
        d = None
        attempts.append(f'analysis_json: 읽기 실패 {type(e).__name__}: {e}')
    else:
        if d is None:
            attempts.append('analysis_json: 파일 없음')
        else:
            v = (d.get('price') or {}).get('shares_outstanding')
            if isinstance(v, (int, float)) and v:
                return v, 'analysis_json', []
            attempts.append('analysis_json: price.shares_outstanding 없음')

    read_data_kis = read_data_kis or (lambda: _read_data_kis_json(stock_name))
    try:
        d = read_data_kis()
    except Exception as e:
        d = None
        attempts.append(f'data_kis_json: 읽기 실패 {type(e).__name__}: {e}')
    else:
        if d is None:
            attempts.append('data_kis_json: 파일 없음')
        else:
            v = _derive_shares_from_price(d.get('current_price'))
            if v:
                return v, 'data_kis_json', []
            attempts.append('data_kis_json: current_price 에 시가총액/현재가 없음')

    read_financial_summary = read_financial_summary or (lambda: _read_financial_summary_json(stock_name))
    try:
        fs = read_financial_summary()
    except Exception as e:
        fs = None
        attempts.append(f'financial_summary_json: 읽기 실패 {type(e).__name__}: {e}')
    else:
        v, reason = _find_shares_outstanding(fs or {})
        if v:
            return v, 'financial_summary_json', []
        attempts.append(f'financial_summary_json: {reason}')

    return None, None, attempts


def collect_flow(code, stock_name=None, flow_days=20, get_trend=None, get_price=None,
                 read_analysis=None, read_data_kis=None, read_financial_summary=None):
    """KIS 투자자별 수급을 주식수 -> 금액(현재가 근사)으로 환산한다.
    get_trend/get_price/read_* 를 주입하면 kis_api 나 실제 파일 없이도 테스트 가능."""
    if get_trend is None or get_price is None:
        import kis_api
        get_trend = get_trend or kis_api.get_investor_trend
        get_price = get_price or kis_api.get_current_price

    trend = get_trend(code, days=flow_days)
    if 'error' in trend:
        return {'status': 'failed', 'reason': trend['error']}
    price = get_price(code)
    if 'error' in price:
        return {'status': 'failed', 'reason': f"현재가 조회 실패: {price['error']}"}

    cur_price = price.get('현재가') or 0
    net_shares = {'외국인': trend.get('외국인_순매수', 0), '기관': trend.get('기관_순매수', 0),
                 '개인': trend.get('개인_순매수', 0)}
    net_krw = {k: v * cur_price for k, v in net_shares.items()}

    shares_out, shares_source, attempts = resolve_shares(
        stock_name, price, read_analysis=read_analysis, read_data_kis=read_data_kis,
        read_financial_summary=read_financial_summary)
    pct = None
    if shares_out:
        pct = {k: round(v / shares_out * 100, 4) for k, v in net_shares.items()}

    return {
        'status': 'ok', 'reason': None, 'days': flow_days,
        'unit_note': ('KIS get_investor_trend 반환 단위는 주식수(CLAUDE.md 경고). '
                      '금액은 주식수 x 현재가 -- 일별 체결가가 아닌 조회 시점 현재가 기준 근사치.'),
        'price_used': cur_price,
        'net_shares': net_shares,
        'net_krw': net_krw,
        'shares_outstanding': shares_out,
        'shares_source': shares_source,
        'pct_of_shares': pct,
        'pct_of_shares_reason': None if pct is not None else '; '.join(attempts),
        'detail': trend.get('detail', []),
    }


# ==================== CLI ====================

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('stock')
    ap.add_argument('--code', default=None)
    ap.add_argument('--limit', type=int, default=2000)
    ap.add_argument('--flow-days', type=int, default=20)
    a = ap.parse_args(argv)

    try:
        info = tc.resolve_stock(a.stock, code=a.code)
    except LookupError as e:
        print(f'[FATAL] 종목코드를 찾을 수 없음: {e}')
        return 1
    code = info['code']

    print('=' * 70)
    print(f'  게시판+수급: {a.stock} ({code})')
    print('=' * 70)

    board = collect_board(code, limit=a.limit)
    tc.write_json(os.path.join(tc.ta_dir(a.stock), 'board.json'), board)
    tc.manifest_update(a.stock, 'board', 'ok' if board['status'] == 'ok' else 'failed',
                       reason=board.get('reason'))
    cov = board.get('coverage', {})
    print(f"  [board] status={board['status']} posts={cov.get('posts')} "
         f"기간={cov.get('from')}~{cov.get('to')}({cov.get('days')}일) "
         f"댓글제외={cov.get('replies_excluded')}")
    if board.get('reason'):
        print(f"          사유: {board['reason']}")

    flow = collect_flow(code, a.stock, flow_days=a.flow_days)
    tc.write_json(os.path.join(tc.ta_dir(a.stock), 'flow.json'), flow)
    tc.manifest_update(a.stock, 'flow', 'ok' if flow['status'] == 'ok' else 'failed',
                       reason=flow.get('reason'))
    print(f"  [flow] status={flow['status']}")
    if flow.get('reason'):
        print(f"         사유: {flow['reason']}")
    print('=' * 70)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
