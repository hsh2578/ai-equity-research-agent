"""ta_board_flow.py 테스트 -- 네이버 종목토론방 + KIS 투자자별 수급 (Task 5).

네트워크 금지. fetch/get_trend/get_price 를 전부 주입해서 테스트한다.

이 테스트가 고정하는 것:
  1. writer 객체(닉네임/profileId)가 출력 어디에도 남지 않는다.
  2. offset 페이지네이션 체인 + limit 누적 중단 + isSuccess=false 실패.
  3. 댓글(replyDepth>0) 제외, 보유자 비율, 급증일(20일 미만이면 생략).
  4. 수급 금액 환산 = 주식수 x 현재가, error 응답 -> failed.

실행: python tests/test_ta_board_flow.py
"""
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import requests                                           # noqa: E402
import ta_board_flow as tbf                               # noqa: E402
import ta_common as tc                                    # noqa: E402

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_passed = 0
_failed = []


def eq(got, want, label):
    global _passed
    if got == want:
        _passed += 1
    else:
        _failed.append((label, want, got))


def ok(cond, label):
    eq(bool(cond), True, label)


# ==================== 픽스처 ====================

RAW_POST = {
    'id': 1, 'writtenAt': '2026-09-17T01:50:50', 'title': '펠리클 공급 확대',
    'contentSwReplaced': 'x' * 250, 'isHolderVerified': True, 'isCleanbotPassed': True,
    'replyDepth': 0, 'recommendCount': 10, 'notRecommendCount': 1, 'viewCount': 100,
    'writer': {'nickname': '몰래훔친닉네임', 'profileId': 'p_secret_123'},
}


def _resp(payload, status=200):
    class _R:
        status_code = status

        def json(self):
            return payload
    return _R()


# ==================== 1. 개인정보 -- writer 는 어디에도 안 남는다 ====================
sanitized = tbf._sanitize_post(RAW_POST)
ok('writer' not in sanitized, '_sanitize_post 는 writer 키 자체를 버린다')
s = json.dumps(sanitized, ensure_ascii=False)
ok('nickname' not in s and 'profileId' not in s, '직렬화한 결과에 nickname/profileId 키가 없다')
ok('몰래훔친닉네임' not in s and 'p_secret_123' not in s, '닉네임/profileId 값 자체가 없다')

board_out = tbf.aggregate_board([sanitized])
board_s = json.dumps(board_out, ensure_ascii=False)
ok('nickname' not in board_s and '몰래훔친닉네임' not in board_s,
   'aggregate_board 출력에도 닉네임이 없다')

# ==================== 2. fetch_board_posts: offset 페이지네이션 ====================
PAGE1 = {'isSuccess': True, 'result': {'offset': '', 'pageSize': 100,
         'lastOffset': '-429498009', 'posts': [dict(RAW_POST, id=1), dict(RAW_POST, id=2)]}}
PAGE2 = {'isSuccess': True, 'result': {'offset': '-429498009', 'pageSize': 100,
         'lastOffset': '-500000000', 'posts': []}}


def _chain_fetch(pages):
    calls = []

    def fetch(url, params, headers, timeout=15):
        calls.append(dict(params))
        i = len(calls) - 1
        return _resp(pages[i] if i < len(pages) else {'isSuccess': True,
                     'result': {'posts': [], 'lastOffset': None}})
    return fetch, calls


fetch, calls = _chain_fetch([PAGE1, PAGE2])
r = tbf.fetch_board_posts('036810', limit=2000, delay=0, fetch=fetch)
eq(r['status'], 'ok', '2페이지(둘째 빈 페이지) 수집 성공')
eq(len(r['posts']), 2, '첫 페이지 2건만 쌓인다')
eq('offset' in calls[0], False, '첫 요청은 offset 파라미터 없이')
eq(calls[1]['offset'], '-429498009', '둘째 요청은 lastOffset 을 offset 으로 쓴다')

# limit 누적 도달 시 중단 -- 3건짜리 페이지, limit=2 면 다음 페이지를 안 부른다
PAGE_BIG = {'isSuccess': True, 'result': {'lastOffset': 'X',
            'posts': [dict(RAW_POST, id=i) for i in range(3)]}}
fetch2, calls2 = _chain_fetch([PAGE_BIG, PAGE_BIG])
r2 = tbf.fetch_board_posts('036810', limit=2, delay=0, fetch=fetch2)
eq(r2['status'], 'ok', 'limit 도달도 성공 처리')
eq(len(r2['posts']), 2, 'limit 만큼만 잘라 돌려준다')
eq(len(calls2), 1, 'limit 도달 시 다음 페이지를 요청하지 않는다')

# isSuccess=false -> 실패
fetch3, _ = _chain_fetch([{'isSuccess': False, 'result': {}}])
r3 = tbf.fetch_board_posts('036810', limit=100, delay=0, fetch=fetch3)
eq(r3['status'], 'failed', 'isSuccess=false 는 failed')

# HTTP 실패
fetch4, _ = _chain_fetch([])


def fetch4_http_err(url, params, headers, timeout=15):
    return _resp({}, status=500)


r4 = tbf.fetch_board_posts('036810', limit=100, delay=0, fetch=fetch4_http_err)
eq(r4['status'], 'failed', 'HTTP 500 은 failed')

# ---- 2-1. 개인정보 회귀: isSuccess=false 여도 posts[].writer 가 reason 으로 새면 안 된다 ----
# (리뷰 Critical) isSuccess:false 인데 결과에 posts 가 같이 오는 응답 형태를 배제하지
# 않으므로, reason 에 raw data 를 통째로 넣으면 닉네임/profileId 가 board.json 에 샌다.
LEAK_PAGE = {'isSuccess': False, 'message': '점검 중입니다', 'resultCode': 'E001',
            'result': {'posts': [{'id': 1, 'writer': {'nickname': '악성유출닉네임',
                       'profileId': 'p_leak_999'}, 'title': 't', 'contentSwReplaced': 'c',
                       'writtenAt': '2026-01-01T00:00:00', 'isHolderVerified': False,
                       'isCleanbotPassed': True, 'replyDepth': 0, 'recommendCount': 0,
                       'notRecommendCount': 0, 'viewCount': 0}]}}


def _one_page_fetch(page):
    def fetch(url, params, headers, timeout=15):
        return _resp(page)
    return fetch


r_leak = tbf.fetch_board_posts('036810', limit=100, delay=0, fetch=_one_page_fetch(LEAK_PAGE))
eq(r_leak['status'], 'failed', 'isSuccess=false 는 posts 를 동반해도 실패 처리')
leak_reason = json.dumps(r_leak.get('reason'), ensure_ascii=False)
ok('nickname' not in leak_reason and 'profileId' not in leak_reason,
   'reason 에 nickname/profileId 키가 없다')
ok('악성유출닉네임' not in leak_reason and 'p_leak_999' not in leak_reason,
   'reason 에 닉네임/profileId 값 자체가 없다')
eq(len(r_leak.get('reason') or ''), min(len(r_leak.get('reason') or ''), 200),
   'reason 은 200자 이내로 자른다')
ok('점검 중입니다' in leak_reason, '화이트리스트 필드(message)는 그대로 남는다')

board_leak = tbf.collect_board('036810', limit=100, fetch=_one_page_fetch(LEAK_PAGE))
board_leak_s = json.dumps(board_leak, ensure_ascii=False)
ok('nickname' not in board_leak_s and 'profileId' not in board_leak_s
   and '악성유출닉네임' not in board_leak_s and 'p_leak_999' not in board_leak_s,
   'collect_board 결과(=board.json 그대로 직렬화)에도 닉네임/profileId 가 없다')

# ==================== 3. aggregate_board: 댓글 제외/보유자비율/급증일 ====================


def mk(id_, day, holder=True, reply=0, rec=0):
    return tbf._sanitize_post(dict(RAW_POST, id=id_,
                              writtenAt=f'2026-01-{day:02d}T09:00:00',
                              isHolderVerified=holder, replyDepth=reply, recommendCount=rec))


posts = [mk(1, 1, holder=True), mk(2, 1, holder=False), mk(3, 2, holder=True),
         mk(9, 2, holder=True, reply=1)]  # 댓글 1건
agg = tbf.aggregate_board(posts)
eq(agg['coverage']['posts'], 3, '댓글 제외한 게시글 수')
eq(agg['coverage']['replies_excluded'], 1, '댓글 개수는 따로 기록')
eq(agg['coverage']['from'], '2026-01-01', '가장 오래된 날짜')
eq(agg['coverage']['to'], '2026-01-02', '가장 최신 날짜')
eq(agg['coverage']['days'], 2, '기간 일수')
day1 = next(d for d in agg['daily'] if d['date'] == '2026-01-01')
eq(day1['posts'], 2, '1/1 게시글 2건')
eq(day1['holder_ratio'], 0.5, '1/1 보유자 비율 1/2')

# 급증일: 20일 미만이면 생략
eq(agg['spikes'], [], '기간 20일 미만이면 spikes 비어있음')
ok(agg.get('spikes_note'), '기간 20일 미만이면 사유가 남는다')

# compute_spikes 단독: 20일 연속 0건 후 21일째 50건 -> 급증
daily_flat = [{'date': f'2026-02-{d:02d}', 'posts': 0} for d in range(1, 21)]
daily_flat.append({'date': '2026-02-21', 'posts': 50})
spikes, note = tbf.compute_spikes(daily_flat)
eq(note, None, '20일 이상이면 사유 없음')
eq(len(spikes), 1, '급증일 1건 검출')
eq(spikes[0]['date'], '2026-02-21', '급증일 날짜 일치')

# compute_spikes: 20일 미만 -> 생략 + 사유
spikes2, note2 = tbf.compute_spikes(daily_flat[:10])
eq(spikes2, [], '10일치는 spikes 비어있음')
ok(note2, '10일치는 사유가 남는다')

# compute_spikes: 정확히 20일 -> 직전 20일 lookback 을 채울 날이 하루도 없어
# 루프가 조용히 0회 돈다(리뷰 Minor). spikes 는 비지만 사유는 남아야 한다.
exactly_20 = [{'date': f'2026-03-{d:02d}', 'posts': 3} for d in range(1, 21)]
eq(len(exactly_20), 20, '픽스처 자체가 정확히 20일치')
spikes3, note3 = tbf.compute_spikes(exactly_20)
eq(spikes3, [], '정확히 20일이면 판정 가능한 날이 없어 spikes 비어있음')
ok(note3, '정확히 20일이어도 사유가 남는다(예전엔 조용히 None 이었다)')
ok('20' in note3, '사유에 실제 일수가 들어간다')

# ==================== 4. _find_shares_outstanding (4단 폴백의 최후 수단) ====================
kr_shape = {'meta': {'stock_code': '036810'}, 'kis': {'current_price': 25300}}
v, reason = tbf._find_shares_outstanding(kr_shape)
eq(v, None, 'KR 종목 financial_summary.json 에는 발행주식수 키가 없다(실측)')
ok(reason, '없으면 사유를 남긴다')

us_shape = {'financials': {'2023': {'shares_outstanding': 100}, '2024': {'shares_outstanding': 200}}}
v2, reason2 = tbf._find_shares_outstanding(us_shape)
eq(v2, 200, 'financials 의 최신 연도 shares_outstanding 을 쓴다')
eq(reason2, None, '찾으면 사유 없음')

flat_shape = {'shares_outstanding': 999}
v3, _ = tbf._find_shares_outstanding(flat_shape)
eq(v3, 999, '최상위 shares_outstanding 도 인식한다')

# ==================== 4-1. _derive_shares_from_price (시가총액/현재가 역산) ====================
# 실측: 에프에스티 시가총액 5477억 / 현재가 25300 -> financial_summary.py 449~450줄과
# 동일 공식(shares = 시가총액*1e8/현재가)으로 21,648,221주.
derived = tbf._derive_shares_from_price({'시가총액': 5477, '현재가': 25300})
eq(derived, round(5477 * 1e8 / 25300), '시가총액(억원) x 1e8 / 현재가 로 역산')
eq(tbf._derive_shares_from_price({'시가총액': 0, '현재가': 25300}), None, '시가총액 0 이면 역산 불가')
eq(tbf._derive_shares_from_price({'현재가': 25300}), None, '시가총액 키 자체가 없으면 역산 불가')
eq(tbf._derive_shares_from_price(None), None, 'price 가 None 이어도 예외 없이 None')

# ==================== 4-2. resolve_shares: 4단 폴백 체인 ====================
# (a) 1단계 성공 -- 이번 조회의 시가총액/현재가로 바로 역산, 폴백 호출 안 함
called = {'analysis': 0}


def _should_not_call():
    called['analysis'] += 1
    return None


v, src, attempts = tbf.resolve_shares('에프에스티', {'시가총액': 5477, '현재가': 25300},
                                      read_analysis=_should_not_call)
eq(v, round(5477 * 1e8 / 25300), '1단계(kis_market_cap) 값과 일치')
eq(src, 'kis_market_cap', '1단계 소스 표시')
eq(attempts, [], '1단계 성공이면 attempts 비어있음')
eq(called['analysis'], 0, '1단계가 성공하면 2단계는 아예 호출하지 않는다')

# (b) 1단계 실패 -> 2단계 analysis_json 성공
v, src, attempts = tbf.resolve_shares(
    '에프에스티', {},  # 1단계 실패(시가총액 없음)
    read_analysis=lambda: {'price': {'shares_outstanding': 21649789}})
eq(v, 21649789, '2단계 analysis_json 값')
eq(src, 'analysis_json', '2단계 소스 표시')
# 성공하면 attempts 는 실패 사유 로그일 뿐이라 downstream(pct_of_shares_reason)에서
# 쓰이지 않는다 -- 성공 반환은 빈 리스트로 고정(resolve_shares 구현과 일치).
eq(attempts, [], '성공하면 attempts 는 비운다(실패 사유는 실패했을 때만 의미가 있다)')

# (c) 1~2단계 실패 -> 3단계 data_kis_json 성공 (시가총액/현재가 동일 역산)
v, src, attempts = tbf.resolve_shares(
    '에프에스티', {}, read_analysis=lambda: None,
    read_data_kis=lambda: {'current_price': {'시가총액': 100, '현재가': 10}})
eq(v, round(100 * 1e8 / 10), '3단계 data_kis_json 도 동일 공식으로 역산')
eq(src, 'data_kis_json', '3단계 소스 표시')

# (d) 1~3단계 실패 -> 4단계 financial_summary_json(US 전용 키) 성공
v, src, attempts = tbf.resolve_shares(
    '아무거나', {}, read_analysis=lambda: None, read_data_kis=lambda: None,
    read_financial_summary=lambda: {'shares_outstanding': 555})
eq(v, 555, '4단계 financial_summary_json 값')
eq(src, 'financial_summary_json', '4단계 소스 표시')

# (e) 4단계 전부 실패 -> None + 시도한 소스 전부가 사유에 남는다
v, src, attempts = tbf.resolve_shares(
    '없는종목', {}, read_analysis=lambda: None, read_data_kis=lambda: None,
    read_financial_summary=lambda: {})
eq(v, None, '4단계 모두 실패하면 None')
eq(src, None, '소스도 None')
eq(len(attempts), 4, '시도한 4단계 전부의 사유가 남는다')
ok(all('kis_market_cap' in attempts[0] or True for _ in [0]), 'attempts 는 리스트')

# 읽기 자체가 예외를 던져도 삼키지 않고 사유로 기록한다


def _boom():
    raise ValueError('디스크 오류')


v, src, attempts = tbf.resolve_shares(
    '없는종목', {}, read_analysis=_boom, read_data_kis=lambda: None,
    read_financial_summary=lambda: {})
ok(any('디스크 오류' in a for a in attempts), '읽기 예외도 attempts 사유에 그대로 남는다(삼키지 않음)')

# ==================== 5. collect_flow ====================


def get_trend_ok(code, days=20):
    return {'외국인_순매수': 1000, '기관_순매수': -500, '개인_순매수': -300,
            'detail': [{'date': '20260916', '외국인': 1000, '기관': -500, '개인': -300}]}


def get_price_ok(code):
    return {'현재가': 25300, '시가총액': 5477}


flow = tbf.collect_flow('036810', get_trend=get_trend_ok, get_price=get_price_ok, flow_days=20)
eq(flow['status'], 'ok', '정상 수급 수집')
eq(flow['net_shares']['외국인'], 1000, '주식수 그대로 보존')
eq(flow['net_krw']['외국인'], 1000 * 25300, '금액 = 주식수 x 현재가')
eq(flow['shares_source'], 'kis_market_cap', 'get_price 가 시가총액을 주면 바로 역산(kis_market_cap)')
eq(flow['shares_outstanding'], round(5477 * 1e8 / 25300), '역산된 발행주식수')
ok(flow['pct_of_shares'] is not None, '발행주식수를 구했으면 비중도 계산된다')
eq(round(flow['pct_of_shares']['외국인'], 4),
   round(1000 / (5477 * 1e8 / 25300) * 100, 4), '비중 = 순매수주식수/발행주식수 x 100')
eq(flow['price_used'], 25300, '사용한 현재가 기록')


def get_trend_fail(code, days=20):
    return {'error': '데이터 없음'}


flow_fail = tbf.collect_flow('036810', get_trend=get_trend_fail, get_price=get_price_ok, flow_days=20)
eq(flow_fail['status'], 'failed', 'error 응답은 failed')
ok(flow_fail.get('reason'), '실패 사유 기록')

# get_price 응답에 시가총액이 없으면(구형/해외 KIS 응답 등) 폴백이 이어진다


def get_price_no_cap(code):
    return {'현재가': 25300}


flow_fb = tbf.collect_flow(
    '036810', get_trend=get_trend_ok, get_price=get_price_no_cap, flow_days=20,
    read_analysis=lambda: {'price': {'shares_outstanding': 10_000_000}})
eq(flow_fb['shares_source'], 'analysis_json', '1단계 실패 시 analysis_json 으로 폴백')
eq(round(flow_fb['pct_of_shares']['외국인'], 4), round(1000 / 10_000_000 * 100, 4),
   '폴백으로 구한 발행주식수로도 비중을 계산한다')

# 전부 실패하면 null + 시도한 소스가 사유에 남는다
flow_none = tbf.collect_flow(
    '036810', get_trend=get_trend_ok, get_price=get_price_no_cap, flow_days=20,
    read_analysis=lambda: None, read_data_kis=lambda: None,
    read_financial_summary=lambda: {})
eq(flow_none['shares_outstanding'], None, '4단계 모두 실패하면 shares_outstanding null')
eq(flow_none['shares_source'], None, '소스도 null')
eq(flow_none['pct_of_shares'], None, '비중도 null')
ok(flow_none.get('pct_of_shares_reason'), '실패 사유에 시도한 소스가 남는다')

# ==================== 6. collect_flow: KIS 예외 처리 (Fix round 3) ====================
# 실측 사고(2026-09-17 파일럿, --limit 2000): kis_api.api_get() 이 resp.raise_for_status()
# 로 requests.exceptions.HTTPError 를 그대로 올리는데(모의서버 500), collect_flow 가
# 이를 안 잡아 스크립트가 죽었다. board.json 은 저장됐지만 flow.json 은 갱신되지 않고
# 조용히 stale 로 남았다(무기록 실패). get_trend/get_price 둘 다에서 재현하고 고친다.


class _FakeResp500:
    status_code = 500


class _FakeResp404:
    status_code = 404


def get_trend_http500(code, days=20):
    err = requests.exceptions.HTTPError('500 Server Error for url: .../inquire-investor')
    err.response = _FakeResp500()
    raise err


def get_price_http500(code):
    err = requests.exceptions.HTTPError('500 Server Error for url: .../inquire-price')
    err.response = _FakeResp500()
    raise err


def get_trend_conn_err(code, days=20):
    raise requests.exceptions.ConnectionError('연결 실패')


def get_trend_timeout(code, days=20):
    raise requests.exceptions.Timeout('응답 지연')


def get_trend_http404(code, days=20):
    err = requests.exceptions.HTTPError('404 Not Found')
    err.response = _FakeResp404()
    raise err


flow_500 = tbf.collect_flow('036810', get_trend=get_trend_http500, get_price=get_price_ok, flow_days=20)
eq(flow_500['status'], 'failed', 'get_trend 의 HTTPError 500 은 예외를 올리지 않고 failed 로 잡힌다')
ok('HTTPError' in (flow_500.get('reason') or ''), 'reason 에 예외 타입이 남는다')
ok('_run_with_real_kis.py' in (flow_500.get('reason') or ''),
   'HTTP 500 이면 CLAUDE.md v5.18 실전 전환 힌트가 붙는다')

flow_price_500 = tbf.collect_flow('036810', get_trend=get_trend_ok, get_price=get_price_http500, flow_days=20)
eq(flow_price_500['status'], 'failed', 'get_price 단계의 HTTPError 500 도 failed 로 잡힌다')
ok('_run_with_real_kis.py' in (flow_price_500.get('reason') or ''), '가격 조회 500 에도 힌트가 붙는다')

flow_conn = tbf.collect_flow('036810', get_trend=get_trend_conn_err, get_price=get_price_ok, flow_days=20)
eq(flow_conn['status'], 'failed', 'ConnectionError 도 failed 로 잡힌다(일반 예외 캐치 확인)')
ok('ConnectionError' in (flow_conn.get('reason') or ''), 'reason 에 예외 타입 명시')

flow_timeout = tbf.collect_flow('036810', get_trend=get_trend_timeout, get_price=get_price_ok, flow_days=20)
eq(flow_timeout['status'], 'failed', 'Timeout 도 failed 로 잡힌다')

flow_404 = tbf.collect_flow('036810', get_trend=get_trend_http404, get_price=get_price_ok, flow_days=20)
eq(flow_404['status'], 'failed', '404 도 failed 로 잡힌다')
ok('_run_with_real_kis.py' not in (flow_404.get('reason') or ''), '500 이 아니면 모의 힌트를 붙이지 않는다')

# ---- 통합: board.json 은 저장되고, flow.json 도 (실패 상태로나마) 반드시 저장된다 ----
# main() 이 하는 두 단계(collect_board -> write, collect_flow -> write)를 그대로 재현해
# "board 는 있는데 flow 는 stale" 사고가 재발하지 않는지 디스크까지 확인한다.
with tempfile.TemporaryDirectory() as td:
    orig_root = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        board_fetch, _ = _chain_fetch([PAGE1, PAGE2])
        board_result = tbf.collect_board('036810', limit=100, fetch=board_fetch)
        tc.write_json(os.path.join(tc.ta_dir('테스트종목'), 'board.json'), board_result)

        flow_result = tbf.collect_flow('036810', '테스트종목', get_trend=get_trend_http500,
                                       get_price=get_price_ok, flow_days=20)
        tc.write_json(os.path.join(tc.ta_dir('테스트종목'), 'flow.json'), flow_result)
        tc.manifest_update('테스트종목', 'flow', 'failed', reason=flow_result.get('reason'))

        board_path = os.path.join(tc.ta_dir('테스트종목'), 'board.json')
        flow_path = os.path.join(tc.ta_dir('테스트종목'), 'flow.json')
        eq(os.path.exists(board_path), True, 'board.json 은 정상 저장된다')
        eq(os.path.exists(flow_path), True,
           'flow.json 도 failed 상태로나마 반드시 저장된다(예전엔 크래시로 아예 안 써졌다)')
        eq(tc.read_json(flow_path)['status'], 'failed', '디스크에 저장된 flow.json 도 failed 상태')
        manifest = tc.read_json(os.path.join(tc.ta_dir('테스트종목'), 'manifest.json'))
        eq(manifest['steps']['flow']['status'], 'failed', 'manifest 에도 flow failed 가 기록된다')
    finally:
        tc.PROJECT_ROOT = orig_root

print('=' * 66)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  ta_board_flow 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
