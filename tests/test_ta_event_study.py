"""ta_event_study.py 테스트 -- 뉴스/공시 이벤트 초과수익(AR/CAR) (Task 3).

네트워크 금지. 가격은 합성 종가 Series 를 만들어 load_prices 로 주입한다.
거래일 달력은 실제 2026년 달력에 기대지 않고, 월요일부터 시작하는 영업일
리스트를 직접 만들어 주말 롤오버를 테스트한다(주 5일 + 주말 스킵만 재현
-- 공휴일 라이브러리 없이 "가격 시리즈 인덱스에서 거래일을 뽑는다"는
브리프 요구를 코드가 실제로 지키는지는 이 합성 달력으로 충분히 검증된다).

실행: python tests/test_ta_event_study.py
"""
import io
import json
import os
import sys
import tempfile
from datetime import date, datetime, time as dtime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import pandas as pd                                     # noqa: E402
import ta_common as tc                                  # noqa: E402
import ta_event_study as tes                             # noqa: E402

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


def approx(got, want, label, tol=1e-9):
    global _passed
    if got is None or want is None:
        eq(got, want, label)
        return
    if abs(got - want) <= tol:
        _passed += 1
    else:
        _failed.append((label, want, got))


# ==================== 합성 거래일 달력 (월요일 시작, 15일) ====================
_ref = date(2026, 8, 31)
_monday = _ref - timedelta(days=_ref.weekday())  # 그 주의 월요일로 되감기


def _bdays(start, n):
    days, d = [], start
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


TD = _bdays(_monday, 15)  # TD[0]=월 ... TD[4]=금, TD[5]=다음주 월 ... TD[14]=세번째주 금
SATURDAY = TD[4] + timedelta(days=1)  # TD[4] 다음날(토) -- 거래일이 아니다

# ==================== 초과수익(AR) 합성: 벤치는 idx1에서만 +1%, 그 외 0% ====================
STOCK_R = {1: 0.05, 2: 0.02, 3: 0.01, 4: 0.01, 5: 0.01, 6: 0.01,
           7: -0.10, 8: 0.005, 9: 0.0, 10: 0.0, 11: 0.0, 12: 0.0, 13: 0.0, 14: 0.02}
BENCH_R = {1: 0.01}


def _prices(base, r_map):
    vals = [base]
    for i in range(1, 15):
        vals.append(vals[-1] * (1 + r_map.get(i, 0.0)))
    return pd.Series(vals, index=pd.to_datetime(TD))


STOCK_CLOSE = _prices(100.0, STOCK_R)
BENCH_CLOSE = _prices(200.0, BENCH_R)

STOCK_CODE = '036810'
BENCH_CODE = '229200'


def fake_load_prices(code, start):
    if code == STOCK_CODE:
        return STOCK_CLOSE.copy()
    if code == BENCH_CODE:
        return BENCH_CLOSE.copy()
    raise KeyError(code)


def failing_load_prices(code, start):
    raise ConnectionError('네트워크 없음(테스트)')


# ==================== compute_ar / compute_car ====================
ar = tes.compute_ar(STOCK_CLOSE, BENCH_CLOSE)
eq(list(ar.index)[:2], [TD[0], TD[1]], 'compute_ar 인덱스는 date 객체')
approx(ar.loc[TD[1]], 0.04, '주식 +5% 벤치 +1% -> AR = 0.04 (브리프 예시)')
approx(ar.loc[TD[7]], -0.10, 'AR[7] = -10%')

c0, c1, c5, inc = tes.compute_car(ar, TD[1])
approx(c0, 0.04, 'car_d0(TD1)')
approx(c1, 0.06, 'car_d1(TD1) = AR1+AR2')
approx(c5, 0.10, 'car_d5(TD1) = AR1..AR6 합')
eq(inc, False, 'TD1 그룹은 완결')

c0t, c1t, c5t, inct = tes.compute_car(ar, TD[14])
approx(c0t, 0.02, 'car_d0(마지막 거래일)은 계산된다')
eq(c1t, None, '마지막 거래일은 D0+1 이 없어 car_d1 None')
eq(c5t, None, '마지막 거래일은 car_d5 도 None')
eq(inct, True, '끝부분 이벤트는 incomplete')

# ==================== resolve_d0 ====================
d0, basis = tes.resolve_d0(TD[1], dtime(15, 29), list(ar.index))
eq((d0, basis), (TD[1], 'same_day'), '15:29 뉴스 -> 당일 D0')

d0, basis = tes.resolve_d0(TD[1], dtime(15, 31), list(ar.index))
eq((d0, basis), (TD[2], 'next_trading_day'), '15:31 뉴스 -> 다음 거래일')

d0, basis = tes.resolve_d0(SATURDAY, dtime(10, 0), list(ar.index))
eq((d0, basis), (TD[5], 'next_trading_day'), '휴장일(토) 뉴스 -> 다음 거래일(월)')

d0, basis = tes.resolve_d0(TD[1], None, list(ar.index))
eq((d0, basis), (TD[2], 'next_day_conservative'), '공시는 항상 다음 거래일(보수적)')

# ==================== 픽스처 파일 기반 run() 통합 테스트 ====================
with tempfile.TemporaryDirectory() as td_root:
    orig_root = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td_root
    try:
        stock = '테스트종목'
        os.makedirs(os.path.join(td_root, 'scripts'), exist_ok=True)
        with open(os.path.join(td_root, 'scripts', f'analysis_{stock}.json'), 'w', encoding='utf-8') as f:
            json.dump({'meta': {'stock_code': STOCK_CODE, 'market': 'KOSDAQ'}}, f)

        news_items = [
            {'nid': 'N0001', 'datetime': f'{TD[1].isoformat()}T15:29:00+09:00',
             'title': '5% 이벤트', 'relevant': True, 'type': 'news'},
            {'nid': 'N0002', 'datetime': f'{TD[1].isoformat()}T15:31:00+09:00',
             'title': '다음날 이벤트', 'relevant': True, 'type': 'news'},
            {'nid': 'N0003', 'datetime': f'{SATURDAY.isoformat()}T10:00:00+09:00',
             'title': '주말 이벤트', 'relevant': True, 'type': 'news'},
            {'nid': 'N0004', 'datetime': f'{TD[7].isoformat()}T09:00:00+09:00',
             'title': '급락 이벤트', 'relevant': True, 'type': 'news'},
            {'nid': 'N0005', 'datetime': f'{TD[14].isoformat()}T09:00:00+09:00',
             'title': '마지막날 이벤트', 'relevant': True, 'type': 'news'},
            {'nid': 'N0006', 'datetime': f'{TD[3].isoformat()}T09:00:00+09:00',
             'title': '[특징주] 반응 기사 급등', 'relevant': True, 'type': 'reaction'},
            {'nid': 'N0007', 'datetime': f'{TD[3].isoformat()}T09:00:00+09:00',
             'title': '무관 기사', 'relevant': False, 'type': 'news'},
        ]
        ta_d = tc.ta_dir(stock)
        with open(os.path.join(ta_d, 'news.json'), 'w', encoding='utf-8') as f:
            json.dump({'items': news_items}, f, ensure_ascii=False)

        data_d = tc.data_dir(stock)
        with open(os.path.join(data_d, '_dart_filings.json'), 'w', encoding='utf-8') as f:
            json.dump({'list': [{'date': TD[1].strftime('%Y%m%d'), 'name': '주요사항보고서',
                                  'rcept_no': '20260901000111'}]}, f, ensure_ascii=False)

        with open(os.path.join(data_d, '_price_cycles.json'), 'w', encoding='utf-8') as f:
            json.dump({'cycles': [{'start': TD[7].isoformat(), 'end': TD[9].isoformat(),
                                    'change_pct': -10.0, 'direction': 'down'}]}, f, ensure_ascii=False)

        result = tes.run(stock, top=2, load_prices=fake_load_prices)

        eq(result['price_status']['status'], 'ok', '가격 로드 성공')
        eq(result['counts']['news_events'], 5, 'news_events = relevant+type news 5건')
        eq(result['counts']['filing_events'], 1, 'filing_events 1건')
        eq(result['counts']['reaction_excluded'], 1, 'reaction 1건 제외 카운트')
        eq(result['counts']['groups'], 5, 'D0 5개 그룹(TD1,TD2,TD5,TD7,TD14)')

        by_d0 = {g['d0']: g for g in result['groups']}
        eq(len(by_d0[TD[2].isoformat()]['events']), 2, '같은 D0(뉴스+공시) 는 한 그룹')
        eq(by_d0[TD[14].isoformat()]['incomplete'], True, '마지막날 그룹은 incomplete')
        eq(by_d0[TD[1].isoformat()]['incomplete'], False, 'TD1 그룹은 완결')
        approx(by_d0[TD[1].isoformat()]['car_d0'], 0.04, '통합 결과에서도 car_d0 = 0.04')

        eq(result['top_moves'][0]['d0'], TD[7].isoformat(), 'top_moves 1위는 |car_d0| 최대(TD7, -0.10)')
        eq(result['top_moves'][1]['d0'], TD[1].isoformat(), 'top_moves 2위는 TD1(0.04)')
        eq(len(result['top_moves']), 2, '--top 2 는 2건만 반환')

        eq(len(result['cycle_triggers']), 1, '사이클 1개에 트리거 1건')
        trig_d0s = {g['d0'] for g in result['cycle_triggers'][0]['groups']}
        eq(trig_d0s, {TD[2].isoformat(), TD[5].isoformat(), TD[7].isoformat()},
           '사이클 start(TD7) ±5거래일 창에 TD2/TD5/TD7 만 포함, TD1/TD14 는 창 밖')

        eq(result['note'], tes.NOTE, 'note 문구 고정')

        # write_json + manifest_update 경로도 확인 (main() 과 동일 순서)
        out_path = os.path.join(ta_d, 'event_study.json')
        tc.write_json(out_path, result)
        on_disk = tc.read_json(out_path)
        eq(on_disk['counts']['groups'], 5, '파일로 저장된 결과도 동일')

        m = tc.manifest_update(stock, 'event_study', 'ok', counts=result['counts'])
        eq(m['steps']['event_study']['status'], 'ok', 'manifest 기록')
    finally:
        tc.PROJECT_ROOT = orig_root

# ==================== 가격 로더 실패 -> price_status failed, 이벤트는 남는다 ====================
with tempfile.TemporaryDirectory() as td_root:
    orig_root = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td_root
    try:
        stock = '가격실패종목'
        os.makedirs(os.path.join(td_root, 'scripts'), exist_ok=True)
        with open(os.path.join(td_root, 'scripts', f'analysis_{stock}.json'), 'w', encoding='utf-8') as f:
            json.dump({'meta': {'stock_code': STOCK_CODE, 'market': 'KOSDAQ'}}, f)

        ta_d = tc.ta_dir(stock)
        with open(os.path.join(ta_d, 'news.json'), 'w', encoding='utf-8') as f:
            json.dump({'items': [{'nid': 'N0001', 'datetime': f'{TD[1].isoformat()}T09:00:00+09:00',
                                   'title': '이벤트', 'relevant': True, 'type': 'news'}]}, f,
                      ensure_ascii=False)

        result = tes.run(stock, load_prices=failing_load_prices)
        eq(result['price_status']['status'], 'failed', '가격 로더 예외 -> price_status failed')
        eq(result['counts']['news_events'], 1, '이벤트는 여전히 남는다')
        eq(result['groups'][0]['car_d0'], None, '가격 없으면 car 는 None')
        eq(result['groups'][0]['incomplete'], True, '가격 없으면 incomplete')
    finally:
        tc.PROJECT_ROOT = orig_root

print('=' * 66)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  ta_event_study 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
